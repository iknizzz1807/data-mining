import pandas as pd
import numpy as np
import joblib
import os
from sklearn.preprocessing import (
    RobustScaler,
    StandardScaler,
    TargetEncoder,
    FunctionTransformer,
)
from sklearn.model_selection import train_test_split
from catboost import CatBoostClassifier
import warnings

warnings.filterwarnings("ignore")

# ========== CONFIG ==========
DATA_PATH = "data.csv"
MODEL_DIR = "model"
os.makedirs(MODEL_DIR, exist_ok=True)


def load_and_prepare_data(filepath):
    """Load data và chuẩn bị như notebook"""
    print(f"📂 Đang đọc dữ liệu từ {filepath}...")
    df = pd.read_csv(filepath)

    # Đổi tên cột nếu cần (khớp notebook)
    if "latitude_x" in df.columns:
        df.rename(
            columns={"latitude_x": "latitude", "longitude_x": "longitude"}, inplace=True
        )

    # Chuyển đổi date thành datetime
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
        df["day_of_year"] = df["date"].dt.dayofyear
        df["day_sin"] = np.sin(2 * np.pi * df["day_of_year"] / 365)
        df["day_cos"] = np.cos(2 * np.pi * df["day_of_year"] / 365)

    # Map daynight
    if "daynight" in df.columns and df["daynight"].dtype == "object":
        df["daynight"] = df["daynight"].map({"D": 1, "N": 0})

    return df


def feature_engineering(df):
    """Feature Engineering giống y notebook"""
    print("⚙️ Đang tạo Features...")

    # 1. Tạo pixel_area
    if "scan" in df.columns and "track" in df.columns:
        df["pixel_area"] = df["scan"] * df["track"]

    # 2. Tạo frp_density
    if "frp" in df.columns and "pixel_area" in df.columns:
        df["frp_density"] = df["frp"] / (df["pixel_area"] + 1e-5)

    # 3. Tạo rain_ratio
    if "Precip_sum_7d" in df.columns and "Precip_sum_30d" in df.columns:
        df["rain_ratio_7d_30d"] = df["Precip_sum_7d"] / (df["Precip_sum_30d"] + 1e-5)

    return df


def preprocessing_pipeline(df_train, df_test=None):
    """
    Preprocessing theo ĐÚNG thứ tự notebook:
    1. Log Transform (Precip_sum_mm, Precip_sum_30d, frp)
    2. Robust Scaler (numeric features)
    3. Target Encoding (province)
    4. Standard Scaler (province sau encode, latitude, longitude)
    """
    print("🔄 Đang Fit Preprocessors...")

    X_train = df_train.drop(columns=["is_fire"])
    y_train = df_train["is_fire"]

    if df_test is not None:
        X_test = df_test.drop(columns=["is_fire"])
        y_test = df_test["is_fire"]

    preprocessors = {}

    # ========== 1. LOG TRANSFORM ==========
    log_cols = ["Precip_sum_mm", "Precip_sum_30d", "frp"]
    preprocessors["log_cols"] = log_cols

    for col in log_cols:
        if col in X_train.columns:
            X_train[col] = np.log1p(X_train[col])
            if df_test is not None and col in X_test.columns:
                X_test[col] = np.log1p(X_test[col])

    # ========== 2. ROBUST SCALER (Trước Target Encoding) ==========
    robust_cols = [
        "Tmax_C",
        "RHmax_pct",
        "Wind_max_kmh",
        "Solar_rad_J_m2",
        "bright_ti5",
        "Precip_sum_mm",
        "Precip_sum_30d",
        "frp",
        "pixel_area",
        "frp_density",
        "rain_ratio_7d_30d",
    ]
    real_robust_cols = [c for c in robust_cols if c in X_train.columns]

    if real_robust_cols:
        robust_scaler = RobustScaler()
        X_train[real_robust_cols] = robust_scaler.fit_transform(
            X_train[real_robust_cols]
        )
        preprocessors["robust_scaler"] = robust_scaler
        preprocessors["robust_cols"] = real_robust_cols

        if df_test is not None:
            X_test[real_robust_cols] = robust_scaler.transform(X_test[real_robust_cols])

    # ========== 3. TARGET ENCODING (Province) ==========
    if "province" in X_train.columns:
        target_encoder = TargetEncoder()
        X_train["province"] = target_encoder.fit_transform(
            X_train[["province"]], y_train
        )
        preprocessors["province_encoder"] = target_encoder

        if df_test is not None:
            X_test["province"] = target_encoder.transform(X_test[["province"]])

        # Scale province sau khi encode
        prov_scaler = StandardScaler()
        X_train["province"] = prov_scaler.fit_transform(X_train[["province"]])
        preprocessors["province_scaler"] = prov_scaler

        if df_test is not None:
            X_test["province"] = prov_scaler.transform(X_test[["province"]])

    # ========== 4. STANDARD SCALER (Lat/Lon) ==========
    geo_cols = ["latitude", "longitude"]
    geo_scaler = StandardScaler()
    X_train[geo_cols] = geo_scaler.fit_transform(X_train[geo_cols])
    preprocessors["geo_scaler"] = geo_scaler

    if df_test is not None:
        X_test[geo_cols] = geo_scaler.transform(X_test[geo_cols])
        return X_train, y_train, X_test, y_test, preprocessors

    return X_train, y_train, preprocessors


def train_model():
    """Train model đúng như notebook"""

    # 1. Load data
    df = load_and_prepare_data(DATA_PATH)

    # 2. Feature Engineering
    df = feature_engineering(df)

    # 3. Chọn cột theo notebook (SAU KHI DROP các cột thừa)
    final_cols = [
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
        "is_fire",
        "day_sin",
        "day_cos",
        "pixel_area",
        "frp_density",
        "rain_ratio_7d_30d",
    ]

    # Chỉ giữ cột tồn tại
    available_cols = [c for c in final_cols if c in df.columns]
    df_train = df[available_cols].copy()

    # Fill NaN
    df_train.fillna(0, inplace=True)

    # 4. Preprocessing
    X_train, y_train, preprocessors = preprocessing_pipeline(df_train)

    # 5. Train CatBoost (Theo notebook: Best model)
    print("🚀 Đang Train CatBoost (Best Model)...")

    # Tính scale_pos_weight
    count_neg = np.sum(y_train == 0)
    count_pos = np.sum(y_train == 1)
    scale_weight = count_neg / count_pos if count_pos > 0 else 1.0
    print(f"📊 Imbalance Ratio: {scale_weight:.2f}")

    model = CatBoostClassifier(
        iterations=500,
        learning_rate=0.1,
        depth=6,
        scale_pos_weight=scale_weight,
        verbose=0,
        random_state=42,
    )

    model.fit(X_train, y_train)

    # 6. Export
    joblib.dump(model, f"{MODEL_DIR}/fire_risk_best_model.pkl")
    joblib.dump(preprocessors, f"{MODEL_DIR}/preprocessor.pkl")

    # Lưu danh sách cột để verify
    expected_cols = list(X_train.columns)
    preprocessors["expected_columns"] = expected_cols
    joblib.dump(preprocessors, f"{MODEL_DIR}/preprocessor.pkl")

    print(f"✅ Hoàn tất! Đã lưu model và preprocessor vào thư mục '{MODEL_DIR}/'.")
    print(f"📋 Feature columns: {expected_cols}")
    print("👉 Bây giờ bạn có thể chạy: python main.py")


if __name__ == "__main__":
    train_model()
