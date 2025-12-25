import joblib
import pandas as pd
import uvicorn
import os
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from utils import (
    preprocess_input,
    crawl_firms_realtime,
    crawl_firms_historical,
    get_weather_daily,
    get_province_from_latlon,
)

# ========== CONFIG ==========
MODEL_PATH = "model/fire_risk_best_model.pkl"
PREPROC_PATH = "model/preprocessor.pkl"
DATA_CSV = "data.csv"

app = FastAPI(title="Fire Risk Warning System")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

model = None
preprocessors = {}


@app.on_event("startup")
def startup_event():
    global model, preprocessors
    if not os.path.exists(MODEL_PATH):
        raise FileNotFoundError(
            f"❌ Model not found: {MODEL_PATH}. Run build_model.py first!"
        )

    model = joblib.load(MODEL_PATH)
    preprocessors = joblib.load(PREPROC_PATH)
    print("✅ Model & Preprocessors Loaded")
    print(f"📋 Expected features: {preprocessors.get('expected_columns', [])}")


# ========== PYDANTIC MODELS ==========
class PredictInput(BaseModel):
    province: str
    latitude: float
    longitude: float
    Tmax_C: float
    RHmax_pct: float
    Precip_sum_mm: float
    Precip_sum_7d: float
    Precip_sum_30d: float
    Wind_max_kmh: float
    Solar_rad_J_m2: float
    frp: float
    bright_ti5: float
    daynight: int
    scan: float = 0.5
    track: float = 0.5


class MapPoint(BaseModel):
    lat: float
    lon: float


class HotspotPoint(BaseModel):
    lat: float
    lon: float
    frp: float
    bright_ti5: float
    acq_time: int
    scan: float
    track: float


# ========== API ENDPOINTS ==========
@app.post("/api/predict")
def predict_manual(data: PredictInput):
    """Dự báo manual từ form"""
    if not model:
        raise HTTPException(500, "Model not ready")

    try:
        X_processed = preprocess_input(data.dict(), preprocessors)
        prob = model.predict_proba(X_processed)[0][1]

        return {
            "probability": round(float(prob), 4),
            "risk_level": (
                "Nguy cơ Rất Cao" if prob > 0.8 else ("Cao" if prob > 0.5 else "Thấp")
            ),
            "is_fire": bool(prob > 0.5),
        }
    except Exception as e:
        raise HTTPException(500, f"Prediction error: {str(e)}")


@app.get("/api/stats")
def get_stats():
    """Thống kê từ file CSV"""
    if not os.path.exists(DATA_CSV):
        return {"heatmap": {}, "monthly": {}, "total_fires": 0}

    df = pd.read_csv(DATA_CSV)
    df_fire = df[df["is_fire"] == 1]

    # Heatmap theo tỉnh
    heatmap_data = df_fire["province"].value_counts().head(20).to_dict()

    # Monthly distribution
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
        month_data = (
            df[df["is_fire"] == 1]["date"]
            .dt.month.value_counts()
            .sort_index()
            .to_dict()
        )
    else:
        month_data = {}

    return {"heatmap": heatmap_data, "monthly": month_data, "total_fires": len(df_fire)}


@app.get("/api/realtime/hotspots")
def get_realtime_data(
    days: int = Query(
        1, ge=1, le=365, description="Number of days to look back (1, 7, 30, 365)"
    )
):
    """
    Crawl NASA FIRMS với tùy chọn lịch sử
    - days=1: Hôm nay
    - days=7: 7 ngày qua
    - days=30: 30 ngày qua
    - days=365: 1 năm qua
    """
    try:
        if days == 1:
            # Realtime today
            data = crawl_firms_realtime()
        else:
            # Historical data
            data = crawl_firms_historical(days)

        features = [
            {
                "lat": row.get("latitude"),
                "lon": row.get("longitude"),
                "bright": row.get("bright_ti4", 300),
                "bright_ti5": row.get("bright_ti5", 295),
                "frp": row.get("frp", 5.0),
                "province": row.get("province", "Unknown"),
                "acq_date": row.get("acq_date", ""),
                "acq_time": row.get("acq_time", 1200),
                "scan": row.get("scan", 0.5),
                "track": row.get("track", 0.5),
            }
            for row in data
        ]

        return {"data": features, "count": len(features), "days": days}
    except Exception as e:
        raise HTTPException(500, f"FIRMS API error: {str(e)}")


@app.post("/api/realtime/predict-click")
def predict_map_click(point: MapPoint):
    """
    Dự báo khi click vào vị trí KHÔNG có điểm nóng
    (Giả định môi trường bình thường)
    """
    try:
        # 1. Lấy thời tiết
        weather = get_weather_daily(point.lat, point.lon)
        if not weather:
            raise HTTPException(500, "Weather API Error")

        # 2. Xác định tỉnh
        province_name = get_province_from_latlon(point.lat, point.lon)

        # 3. Giả định KHÔNG có lửa (môi trường bình thường)
        fake_input = {
            "province": province_name,
            "latitude": point.lat,
            "longitude": point.lon,
            **weather,
            "frp": 5.0,  # FRP trung bình giả định
            "bright_ti5": 310.0,  # Độ sáng bình thường
            "daynight": 1,  # Ban ngày
            "scan": 0.5,
            "track": 0.5,
        }

        X_proc = preprocess_input(fake_input, preprocessors)
        prob = model.predict_proba(X_proc)[0][1]

        return {
            "type": "environment",
            "weather": weather,
            "province": province_name,
            "probability": round(float(prob), 4),
            "risk_level": (
                "Nguy cơ Rất Cao" if prob > 0.8 else ("Cao" if prob > 0.5 else "Thấp")
            ),
            "is_fire": bool(prob > 0.5),
        }
    except Exception as e:
        raise HTTPException(500, f"Prediction error: {str(e)}")


@app.post("/api/realtime/predict-hotspot")
def predict_hotspot(point: HotspotPoint):
    """
    Dự báo khi click vào điểm nóng THỰC TẾ
    (Sử dụng dữ liệu thực từ vệ tinh)
    """
    try:
        # 1. Lấy thời tiết
        weather = get_weather_daily(point.lat, point.lon)
        if not weather:
            raise HTTPException(500, "Weather API Error")

        # 2. Xác định tỉnh
        province_name = get_province_from_latlon(point.lat, point.lon)

        # 3. Xác định daynight từ acq_time
        hour = point.acq_time // 100
        daynight = 1 if 6 <= hour <= 18 else 0

        # 4. Sử dụng DỮ LIỆU THỰC từ điểm nóng
        real_input = {
            "province": province_name,
            "latitude": point.lat,
            "longitude": point.lon,
            **weather,
            "frp": point.frp,  # FRP thực tế
            "bright_ti5": point.bright_ti5,  # Độ sáng thực tế
            "daynight": daynight,
            "scan": point.scan,
            "track": point.track,
        }

        X_proc = preprocess_input(real_input, preprocessors)
        prob = model.predict_proba(X_proc)[0][1]

        return {
            "type": "hotspot",
            "weather": weather,
            "province": province_name,
            "probability": round(float(prob), 4),
            "risk_level": (
                "Nguy cơ Rất Cao" if prob > 0.8 else ("Cao" if prob > 0.5 else "Thấp")
            ),
            "is_fire": bool(prob > 0.5),
            "hotspot_data": {
                "frp": point.frp,
                "brightness": point.bright_ti5,
                "time": point.acq_time,
            },
        }
    except Exception as e:
        raise HTTPException(500, f"Prediction error: {str(e)}")


# Mount static files
app.mount("/", StaticFiles(directory="static", html=True), name="static")

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
