import numpy as np
import pandas as pd
import requests
from datetime import datetime, date, timedelta
import geopandas as gpd
from shapely.geometry import Point
import os
import io
import time

# ========== CONFIG ==========
FIRMS_KEY = os.getenv("FIRMS_API_KEY", "3462395fdce3c9da8d92cefcbade1e3c")
FIRMS_AREA = "102.14,8.61,109.47,23.39"
OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
GADM_PATH = "gadm41_VNM.gpkg"

FIRMS_SOURCES_NRT = [
    "VIIRS_NOAA21_NRT",
    "VIIRS_NOAA20_NRT",
    "VIIRS_SNPP_NRT",
    "MODIS_NRT",
]

vn_map = None


def load_vn_map():
    """Load bản đồ Việt Nam"""
    global vn_map
    if vn_map is None and os.path.exists(GADM_PATH):
        try:
            print("🗺️ Loading VN map...")
            vn_map = gpd.read_file(GADM_PATH, layer="ADM_ADM_1")
            vn_map = vn_map[["NAME_1", "geometry"]]
            print("✅ VN map loaded")
        except Exception as e:
            print(f"❌ Map load error: {e}")


def get_province_from_latlon(lat, lon):
    """Xác định tỉnh từ tọa độ"""
    load_vn_map()
    if vn_map is None:
        return "Unknown"

    try:
        point = Point(lon, lat)
        point_gdf = gpd.GeoDataFrame(geometry=[point], crs="EPSG:4326")
        joined = gpd.sjoin(point_gdf, vn_map, how="inner", predicate="within")

        if not joined.empty:
            return joined.iloc[0]["NAME_1"]
    except:
        pass

    return "Unknown"


def crawl_firms_realtime():
    """Crawl hôm nay"""
    load_vn_map()
    today = date.today().strftime("%Y-%m-%d")

    for source in FIRMS_SOURCES_NRT:
        url = f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{FIRMS_KEY}/{source}/{FIRMS_AREA}/1/{today}"

        try:
            print(f"📡 {source} (today)...")
            resp = requests.get(url, timeout=30)

            if resp.status_code == 429:
                print(f"⚠️ Rate limit, wait 60s...")
                time.sleep(60)
                continue

            resp.raise_for_status()
            df = pd.read_csv(io.StringIO(resp.text))

            if not df.empty:
                print(f"✅ {len(df)} hotspots from {source}")
                return _process_firms_data(df)

        except Exception as e:
            print(f"⚠️ {source}: {str(e)[:80]}")
            continue

    print("ℹ️ No hotspots today")
    return []


def crawl_firms_historical(days=7):
    """
    Crawl lịch sử - LOGIC MỚI

    Strategy mới:
    1. Nếu days <= 10: Single request
    2. Nếu days > 10: Single request với min(days, 10) ngày gần nhất
       → Vì NRT data chỉ có ~10 ngày

    KHÔNG chia batch nữa vì sẽ bị overlap!
    """
    load_vn_map()
    today = date.today()

    # QUAN TRỌNG: NRT data chỉ có ~10 ngày
    # Nếu user chọn 30 ngày, chỉ lấy được 10 ngày gần nhất
    actual_days = min(days, 10)

    if days > 10:
        print(
            f"⚠️ NRT data limited to 10 days. Requesting {actual_days} days instead of {days}"
        )

    # Calculate date range
    end_date = today
    start_date = today - timedelta(days=actual_days - 1)

    print(
        f"📅 Date range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}"
    )

    # Try sources
    for source in FIRMS_SOURCES_NRT:
        # Use end_date as reference point
        url = f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{FIRMS_KEY}/{source}/{FIRMS_AREA}/{actual_days}/{end_date.strftime('%Y-%m-%d')}"

        try:
            print(f"📡 {source} ({actual_days} days)...")
            resp = requests.get(url, timeout=30)

            if resp.status_code == 429:
                print(f"⚠️ Rate limit, wait 60s...")
                time.sleep(60)
                resp = requests.get(url, timeout=30)

            resp.raise_for_status()
            df = pd.read_csv(io.StringIO(resp.text))

            if not df.empty:
                # Filter by date range to be extra safe
                if "acq_date" in df.columns:
                    df["acq_date_parsed"] = pd.to_datetime(df["acq_date"])
                    df = df[
                        (df["acq_date_parsed"].dt.date >= start_date)
                        & (df["acq_date_parsed"].dt.date <= end_date)
                    ]
                    df = df.drop(columns=["acq_date_parsed"])

                print(f"✅ {len(df)} hotspots from {source}")
                return _process_firms_data(df)
            else:
                print(f"ℹ️ No data from {source}")

        except Exception as e:
            print(f"⚠️ {source}: {str(e)[:80]}")
            continue

    print(f"ℹ️ No hotspots in last {actual_days} days")
    return []


def _process_firms_data(df):
    """Process FIRMS data"""
    if df.empty:
        return []

    # Validate
    required = ["latitude", "longitude", "acq_date"]
    missing = [c for c in required if c not in df.columns]

    if missing:
        print(f"⚠️ Missing: {missing}")
        return []

    # Default values
    if "frp" not in df.columns:
        df["frp"] = 5.0

    if "bright_ti5" not in df.columns:
        if "bright_t31" in df.columns:
            df["bright_ti5"] = df["bright_t31"]  # MODIS
        else:
            df["bright_ti5"] = 310.0

    if "scan" not in df.columns:
        df["scan"] = 0.5
    if "track" not in df.columns:
        df["track"] = 0.5
    if "acq_time" not in df.columns:
        df["acq_time"] = 1200

    # Spatial filter
    if vn_map is None:
        df["province"] = "Unknown"
        return df.to_dict(orient="records")

    try:
        gdf = gpd.GeoDataFrame(
            df, geometry=gpd.points_from_xy(df.longitude, df.latitude), crs="EPSG:4326"
        )

        gdf_vn = gpd.sjoin(gdf, vn_map, how="inner", predicate="within")
        gdf_vn = gdf_vn.rename(columns={"NAME_1": "province"})

        print(f"🇻🇳 {len(df)} → {len(gdf_vn)} hotspots in VN")

        result = pd.DataFrame(gdf_vn.drop(columns="geometry"))
        return result.to_dict(orient="records")

    except Exception as e:
        print(f"⚠️ Filter error: {e}")
        df["province"] = "Unknown"
        return df.to_dict(orient="records")


def get_weather_daily(lat, lon):
    """Get weather data"""
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": [
            "temperature_2m_max",
            "relative_humidity_2m_max",
            "precipitation_sum",
            "wind_speed_10m_max",
            "shortwave_radiation_sum",
        ],
        "timezone": "Asia/Ho_Chi_Minh",
        "past_days": 30,
    }

    try:
        resp = requests.get(OPEN_METEO_URL, params=params, timeout=10).json()
        daily = resp.get("daily", {})

        if not daily:
            return None

        precip_list = daily.get("precipitation_sum", [])

        return {
            "Tmax_C": daily.get("temperature_2m_max", [])[-1],
            "RHmax_pct": daily.get("relative_humidity_2m_max", [])[-1],
            "Precip_sum_mm": precip_list[-1] if precip_list else 0.0,
            "Precip_sum_7d": (
                sum(precip_list[-7:]) if len(precip_list) >= 7 else sum(precip_list)
            ),
            "Precip_sum_30d": (
                sum(precip_list[-30:]) if len(precip_list) >= 30 else sum(precip_list)
            ),
            "Wind_max_kmh": daily.get("wind_speed_10m_max", [])[-1],
            "Solar_rad_J_m2": daily.get("shortwave_radiation_sum", [])[-1],
        }

    except Exception as e:
        print(f"❌ Weather: {e}")
        return None


def preprocess_input(input_dict, preprocessors):
    """Preprocess input"""
    df = pd.DataFrame([input_dict])

    # Features
    if "scan" not in df.columns:
        df["scan"] = 0.5
    if "track" not in df.columns:
        df["track"] = 0.5

    df["pixel_area"] = df["scan"] * df["track"]
    df["frp_density"] = df["frp"] / (df["pixel_area"] + 1e-5)
    df["rain_ratio_7d_30d"] = df["Precip_sum_7d"] / (df["Precip_sum_30d"] + 1e-5)

    # Cyclic
    doy = datetime.now().timetuple().tm_yday
    df["day_sin"] = np.sin(2 * np.pi * doy / 365)
    df["day_cos"] = np.cos(2 * np.pi * doy / 365)

    # Daynight
    if "daynight" in df.columns and isinstance(df["daynight"].iloc[0], str):
        df["daynight"] = df["daynight"].map({"D": 1, "N": 0})

    # Preprocessing
    for col in preprocessors.get("log_cols", []):
        if col in df.columns:
            df[col] = np.log1p(df[col])

    r_cols = preprocessors.get("robust_cols", [])
    if "robust_scaler" in preprocessors and r_cols:
        for c in r_cols:
            if c not in df.columns:
                df[c] = 0.0
        df[r_cols] = preprocessors["robust_scaler"].transform(df[r_cols])

    if "province" in df.columns:
        if "province_encoder" in preprocessors:
            try:
                df["province"] = preprocessors["province_encoder"].transform(
                    df[["province"]]
                )
                df["province"] = preprocessors["province_scaler"].transform(
                    df[["province"]]
                )
            except:
                df["province"] = 0.0
        else:
            df["province"] = 0.0

    if "geo_scaler" in preprocessors:
        df[["latitude", "longitude"]] = preprocessors["geo_scaler"].transform(
            df[["latitude", "longitude"]]
        )

    # Final columns
    expected = preprocessors.get(
        "expected_columns",
        [
            "Tmax_C",
            "RHmax_pct",
            "Precip_sum_mm",
            "Wind_max_kmh",
            "Solar_rad_J_m2",
            "province",
            "latitude",
            "longitude",
            "Precip_sum_30d",
            "bright_ti5",
            "frp",
            "daynight",
            "day_sin",
            "day_cos",
            "pixel_area",
            "frp_density",
            "rain_ratio_7d_30d",
        ],
    )

    final = pd.DataFrame()
    for col in expected:
        final[col] = df[col] if col in df.columns else 0.0

    return final
