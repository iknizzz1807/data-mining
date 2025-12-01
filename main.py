import joblib
import pandas as pd
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# 1. Khởi tạo App
app = FastAPI(title="Fire Risk Prediction API")

# 2. Cấu hình CORS (Để frontend gọi được API)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 3. Load Model
MODEL_PATH = "model/fire_risk_best_model.pkl"
try:
    model = joblib.load(MODEL_PATH)
    print("Model loaded successfully!")
except Exception as e:
    print(f"Error loading model: {e}")
    model = None


# 4. Định nghĩa dữ liệu đầu vào (Pydantic Model)
# Dựa trên 13 feature columns trong notebook của bạn
class FireInput(BaseModel):
    track: float
    bright_ti5: float
    Solar_rad_J_m2: float
    latitude_x: float
    fire_risk_score: float
    Precip_sum_30d: float
    GID_1: float
    Wind_max_kmh: float
    daynight_N: float
    longitude_x: float
    Precip_sum_7d: float
    acq_time: float
    no_rain_7d: float


# 5. API Endpoint dự đoán
@app.post("/api/predict")
def predict_fire_risk(input_data: FireInput):
    if not model:
        raise HTTPException(status_code=500, detail="Model not loaded")

    try:
        # Chuyển đổi input thành DataFrame (đúng thứ tự cột model yêu cầu)
        data_dict = input_data.dict()
        df = pd.DataFrame([data_dict])

        # Dự đoán
        # predict_proba trả về [[prob_0, prob_1]]
        probability = model.predict_proba(df)[0][1]

        # Ngưỡng 0.5 (như trong notebook)
        is_fire = bool(probability >= 0.5)

        return {
            "is_fire": is_fire,
            "fire_probability": round(float(probability), 4),
            "message": (
                "Cảnh báo: Nguy cơ cháy cao!" if is_fire else "An toàn: Nguy cơ thấp."
            ),
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# 6. Serve Frontend (Static files)
app.mount("/", StaticFiles(directory="static", html=True), name="static")

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
