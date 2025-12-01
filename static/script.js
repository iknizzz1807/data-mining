// Định nghĩa khoảng giá trị hợp lý cho từng trường (dựa trên placeholder đã chuẩn hóa)
const FIELD_RANGES = {
  track: { min: -2.0, max: 2.0, decimals: 2 },
  bright_ti5: { min: -2.0, max: 2.0, decimals: 2 },
  Solar_rad_J_m2: { min: -2.0, max: 2.0, decimals: 2 },
  latitude_x: { min: -2.0, max: 2.0, decimals: 2 },
  longitude_x: { min: -2.0, max: 2.0, decimals: 2 },
  fire_risk_score: { min: 0, max: 1, decimals: 2 }, // Score thường 0-1 hoặc chuẩn hóa
  Precip_sum_30d: { min: -1.0, max: 5.0, decimals: 2 },
  Precip_sum_7d: { min: -1.0, max: 5.0, decimals: 2 },
  no_rain_7d: { min: -1.0, max: 2.0, decimals: 2 },
  GID_1: { min: -2.0, max: 2.0, decimals: 2 },
  Wind_max_kmh: { min: -2.0, max: 2.0, decimals: 2 },
  daynight_N: { min: -1.0, max: 1.0, decimals: 4 }, // Feature nhị phân chuẩn hóa
  acq_time: { min: -2.0, max: 2.0, decimals: 3 },
};

// Hàm sinh số ngẫu nhiên
function getRandomValue(field) {
  const config = FIELD_RANGES[field] || { min: -1, max: 1, decimals: 2 };
  const rand = Math.random() * (config.max - config.min) + config.min;
  return parseFloat(rand.toFixed(config.decimals));
}

// Xử lý sự kiện Random cho 1 ô
document.querySelectorAll(".btn-mini-rand").forEach((btn) => {
  btn.addEventListener("click", function () {
    const targetId = this.getAttribute("data-target");
    const input = document.getElementById(targetId);
    if (input) {
      input.value = getRandomValue(targetId);
      // Hiệu ứng nháy nhẹ để biết đã thay đổi
      input.style.backgroundColor = "#fffacd";
      setTimeout(() => (input.style.backgroundColor = "#fff"), 300);
    }
  });
});

// Xử lý sự kiện Random All
document.getElementById("randomAllBtn").addEventListener("click", function () {
  for (const [key, config] of Object.entries(FIELD_RANGES)) {
    const input = document.getElementById(key);
    if (input) {
      input.value = getRandomValue(key);
    }
  }
});

// Logic Submit Form (Giữ nguyên logic gọi API cũ, chỉ đổi update UI)
document
  .getElementById("predictionForm")
  .addEventListener("submit", async function (e) {
    e.preventDefault();
    const submitBtn = document.getElementById("submitBtn");
    const statusBox = document.getElementById("statusBox");
    const statusIcon = document.getElementById("statusIcon");
    const resultText = document.getElementById("predictionResult");
    const probBar = document.getElementById("probabilityBar");
    const probText = document.getElementById("probText");

    // Loading State
    submitBtn.disabled = true;
    submitBtn.textContent = "ĐANG TÍNH TOÁN...";
    statusBox.className = "status-box waiting";
    resultText.textContent = "PROCESSING...";

    // Thu thập dữ liệu
    const formData = new FormData(e.target);
    const data = Object.fromEntries(formData.entries());
    for (let key in data) {
      data[key] = parseFloat(data[key]);
    }

    try {
      const response = await fetch("/api/predict", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      });

      if (!response.ok)
        throw new Error(`HTTP error! status: ${response.status}`);

      const result = await response.json();

      // Cập nhật UI kết quả
      statusBox.className = result.is_fire
        ? "status-box danger"
        : "status-box safe";
      statusIcon.textContent = result.is_fire ? "🔥" : "🌲";
      resultText.textContent = result.is_fire ? "CẢNH BÁO: CHÁY" : "AN TOÀN";

      const percent = (result.fire_probability * 100).toFixed(2);
      probText.textContent = `${percent}%`;

      probBar.style.width = `${percent}%`;
      probBar.style.backgroundColor = result.is_fire ? "#8b0000" : "#006400";
    } catch (error) {
      alert("Lỗi hệ thống: " + error.message);
      console.error(error);
    } finally {
      submitBtn.disabled = false;
      submitBtn.textContent = "CHẠY MÔ HÌNH (RUN)";
    }
  });

// Tự động random dữ liệu khi trang vừa load để không bị trống
window.addEventListener("DOMContentLoaded", () => {
  document.getElementById("randomAllBtn").click();
});
