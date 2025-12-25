// ==================== GLOBAL STATE ====================
let mapInstance = null;
let charts = { province: null, month: null };
let currentHotspots = [];
let hotspotsLayer = null;

// ==================== TAB NAVIGATION ====================
function initTabs() {
  const navButtons = document.querySelectorAll(".nav-item");

  navButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      const tabId = btn.getAttribute("data-tab");
      switchTab(tabId);
    });
  });
}

function switchTab(tabId) {
  document.querySelectorAll(".nav-item").forEach((btn) => {
    btn.classList.remove("active");
  });
  document.querySelector(`[data-tab="${tabId}"]`)?.classList.add("active");

  document.querySelectorAll(".tab-content").forEach((tab) => {
    tab.classList.remove("active");
  });
  document.getElementById(`tab-${tabId}`)?.classList.add("active");

  if (tabId === "map" && !mapInstance) {
    initMap();
  }
  if (tabId === "analytics" && !charts.province) {
    loadAnalytics();
  }
}

// ==================== TAB 1: PREDICT ====================
function initPredict() {
  const form = document.getElementById("predictForm");
  const btnRandom = document.getElementById("btnRandomData");

  if (btnRandom) {
    btnRandom.addEventListener("click", generateRandomData);
  }

  if (form) {
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      await handlePrediction(e.target);
    });
  }
}

function generateRandomData() {
  const isDangerous = Math.random() > 0.5;
  const form = document.getElementById("predictForm");

  const provinces = [
    "Gia Lai",
    "Kon Tum",
    "Đắk Lắk",
    "Lâm Đồng",
    "Nghệ An",
    "Hà Tĩnh",
  ];

  form.province.value = provinces[Math.floor(Math.random() * provinces.length)];
  form.latitude.value = (13 + Math.random() * 2).toFixed(4);
  form.longitude.value = (107 + Math.random() * 2).toFixed(4);

  if (isDangerous) {
    form.Tmax_C.value = (33 + Math.random() * 5).toFixed(1);
    form.RHmax_pct.value = Math.floor(40 + Math.random() * 15);
    form.Wind_max_kmh.value = (10 + Math.random() * 20).toFixed(1);
    form.Precip_sum_mm.value = 0;
    form.Precip_sum_7d.value = (Math.random() * 5).toFixed(1);
    form.Precip_sum_30d.value = (Math.random() * 10).toFixed(1);
    form.Solar_rad_J_m2.value = (20 + Math.random() * 10).toFixed(1);
    form.bright_ti5.value = (330 + Math.random() * 20).toFixed(1);
    form.frp.value = (10 + Math.random() * 20).toFixed(1);
  } else {
    form.Tmax_C.value = (20 + Math.random() * 8).toFixed(1);
    form.RHmax_pct.value = Math.floor(80 + Math.random() * 20);
    form.Wind_max_kmh.value = (5 + Math.random() * 10).toFixed(1);
    form.Precip_sum_mm.value = (5 + Math.random() * 20).toFixed(1);
    form.Precip_sum_7d.value = (30 + Math.random() * 50).toFixed(1);
    form.Precip_sum_30d.value = (100 + Math.random() * 100).toFixed(1);
    form.Solar_rad_J_m2.value = (5 + Math.random() * 10).toFixed(1);
    form.bright_ti5.value = (280 + Math.random() * 20).toFixed(1);
    form.frp.value = (0 + Math.random() * 2).toFixed(1);
  }

  showToast(
    isDangerous
      ? "Đã tạo dữ liệu kịch bản NGUY HIỂM"
      : "Đã tạo dữ liệu kịch bản AN TOÀN",
  );
}

async function handlePrediction(form) {
  const submitBtn = form.querySelector('button[type="submit"]');
  const submitText = document.getElementById("submitText");
  const originalText = submitText.textContent;

  submitBtn.disabled = true;
  submitText.textContent = "Đang phân tích...";

  try {
    const formData = new FormData(form);
    const data = {};

    for (let [key, value] of formData.entries()) {
      data[key] = key === "province" ? value : parseFloat(value);
    }

    const response = await fetch("/api/predict", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });

    if (!response.ok) throw new Error("API Error");

    const result = await response.json();
    displayResult(result);
    showToast("Phân tích thành công!");
  } catch (error) {
    showToast("❌ Lỗi: " + error.message);
    console.error(error);
  } finally {
    submitBtn.disabled = false;
    submitText.textContent = originalText;
  }
}

function displayResult(result) {
  document.getElementById("resultPlaceholder")?.classList.add("hidden");
  const resultCard = document.getElementById("resultCard");
  resultCard.classList.remove("hidden");

  const now = new Date();
  const timestampEl = document.getElementById("resultTimestamp");
  if (timestampEl) {
    timestampEl.textContent = now.toLocaleString("vi-VN");
  }

  const riskEl = document.getElementById("resultRisk");
  riskEl.textContent = result.risk_level;

  const percent = (result.probability * 100).toFixed(1);
  document.getElementById("probabilityValue").textContent = `${percent}%`;

  const progressBar = document.getElementById("probabilityBar");
  progressBar.style.width = `${percent}%`;

  resultCard.classList.remove("danger", "safe");
  if (result.is_fire) {
    resultCard.classList.add("danger");
    progressBar.style.background = "var(--danger)";
    riskEl.style.color = "var(--danger)";
  } else {
    resultCard.classList.add("safe");
    progressBar.style.background = "var(--success)";
    riskEl.style.color = "var(--success)";
  }

  const recommendations = {
    high: "⚠️ NGUY CƠ CAO: Tuyệt đối không đốt rừng, tăng cường tuần tra canh phòng. Chuẩn bị phương án chữa cháy khẩn cấp.",
    medium:
      "⚡ RỦI RO TRUNG BÌNH: Hạn chế các hoạt động có nguy cơ gây cháy. Theo dõi chặt chẽ diễn biến thời tiết.",
    low: "✅ AN TOÀN: Điều kiện thời tiết thuận lợi. Duy trì các biện pháp phòng cháy thông thường.",
  };

  let level = "low";
  if (result.probability > 0.7) level = "high";
  else if (result.probability > 0.4) level = "medium";

  const recommendationEl = document.getElementById("recommendationText");
  if (recommendationEl) {
    recommendationEl.textContent = recommendations[level];
  }

  resultCard.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

// ==================== TAB 2: MAP ====================
async function initMap() {
  if (mapInstance) return;

  const loadingEl = document.getElementById("mapLoading");

  try {
    mapInstance = L.map("leafletMap").setView([16, 106], 6);

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: "© OpenStreetMap contributors",
      maxZoom: 18,
    }).addTo(mapInstance);

    hotspotsLayer = L.layerGroup().addTo(mapInstance);

    await loadHotspots(1);

    mapInstance.on("click", handleMapClickEmpty);

    const btnRefresh = document.getElementById("btnRefreshMap");
    if (btnRefresh) {
      btnRefresh.addEventListener("click", async () => {
        const timeRange = document.getElementById("timeRange");
        const days = parseInt(timeRange.value);
        await loadHotspots(days);
      });
    }

    if (loadingEl) {
      loadingEl.style.display = "none";
    }
  } catch (error) {
    console.error("Map error:", error);
    showToast("❌ Lỗi tải bản đồ");
    if (loadingEl) {
      loadingEl.innerHTML = "<p>❌ Không thể tải bản đồ</p>";
    }
  }
}

async function loadHotspots(days) {
  const loadingEl = document.getElementById("mapLoading");
  const mapCard = document.querySelector(".map-card");

  if (loadingEl) loadingEl.style.display = "flex";
  if (mapCard) mapCard.classList.add("map-updating");

  try {
    const response = await fetch(`/api/realtime/hotspots?days=${days}`);
    const json = await response.json();

    if (hotspotsLayer) {
      hotspotsLayer.clearLayers();
    }
    currentHotspots = json.data || [];

    const countEl = document.getElementById("hotspotCount");
    if (countEl) {
      countEl.textContent = json.count.toLocaleString();
    }

    if (currentHotspots.length > 0) {
      currentHotspots.forEach((point) => {
        const marker = L.circleMarker([point.lat, point.lon], {
          radius: 6,
          fillColor: "#dc2626",
          color: "#991b1b",
          weight: 1,
          opacity: 1,
          fillOpacity: 0.7,
        });

        marker.hotspotData = point;

        marker.bindTooltip(
          `<strong>${point.province}</strong><br>
           Độ sáng: ${point.bright}K<br>
           FRP: ${point.frp.toFixed(2)}`,
          { direction: "top" },
        );

        marker.on("click", (e) => {
          L.DomEvent.stopPropagation(e);
          handleHotspotClick(point);
        });

        if (hotspotsLayer) {
          hotspotsLayer.addLayer(marker);
        }
      });

      showToast(`✅ Đã tải ${json.count} điểm nóng (${days} ngày)`);
    } else {
      showToast(`ℹ️ Không có điểm nóng trong ${days} ngày qua`);
    }
  } catch (error) {
    console.error("Hotspot error:", error);
    showToast("❌ Lỗi tải điểm nóng");
  } finally {
    if (loadingEl) loadingEl.style.display = "none";
    if (mapCard) mapCard.classList.remove("map-updating");
  }
}

async function handleHotspotClick(hotspot) {
  const popup = L.popup()
    .setLatLng([hotspot.lat, hotspot.lon])
    .setContent(
      '<div class="popup-hotspot">⏳ Đang phân tích điểm nóng...</div>',
    )
    .openOn(mapInstance);

  try {
    const response = await fetch("/api/realtime/predict-hotspot", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        lat: hotspot.lat,
        lon: hotspot.lon,
        frp: hotspot.frp,
        bright_ti5: hotspot.bright_ti5,
        acq_time: hotspot.acq_time,
        scan: hotspot.scan,
        track: hotspot.track,
      }),
    });

    const result = await response.json();

    if (result.error) {
      popup.setContent('<div class="popup-hotspot">❌ Lỗi API</div>');
      return;
    }

    const color = result.is_fire ? "#dc2626" : "#16a34a";
    const percent = (result.probability * 100).toFixed(1);
    const dateStr = hotspot.acq_date || "Hôm nay";

    popup.setContent(`
      <div class="popup-hotspot">
        <div class="popup-header">
          <span class="popup-icon">🔥</span>
          <span class="popup-title">ĐIỂM NÓNG THỰC TẾ</span>
        </div>
        
        <div class="popup-risk" style="color: ${color};">
          ${result.risk_level}
        </div>
        
        <div class="popup-probability" style="color: ${color};">
          Xác suất: ${percent}%
        </div>
        
        <div class="popup-details">
          <strong>📍 ${result.province}</strong><br>
          <strong>📅 ${dateStr}</strong><br><br>
          
          <strong>Dữ liệu Vệ tinh:</strong><br>
          • FRP: ${result.hotspot_data.frp.toFixed(2)} MW<br>
          • Độ sáng: ${result.hotspot_data.brightness.toFixed(1)}K<br>
          • Thời gian: ${formatTime(result.hotspot_data.time)}<br><br>
          
          <strong>Thời tiết hiện tại:</strong><br>
          • Nhiệt độ: ${result.weather.Tmax_C}°C<br>
          • Độ ẩm: ${result.weather.RHmax_pct}%<br>
          • Mưa hôm nay: ${result.weather.Precip_sum_mm}mm<br>
          • Mưa 7 ngày: ${result.weather.Precip_sum_7d.toFixed(1)}mm
        </div>
        
        <div class="popup-footer">
          ✓ Dự báo dựa trên dữ liệu thực tế từ vệ tinh FIRMS
        </div>
      </div>
    `);
  } catch (error) {
    console.error("Hotspot prediction error:", error);
    popup.setContent('<div class="popup-hotspot">❌ Lỗi kết nối</div>');
  }
}

async function handleMapClickEmpty(e) {
  if (e.originalEvent.target.classList.contains("leaflet-interactive")) {
    return;
  }

  const { lat, lng } = e.latlng;

  const popup = L.popup()
    .setLatLng(e.latlng)
    .setContent(
      '<div class="popup-hotspot">⏳ Đang phân tích môi trường...</div>',
    )
    .openOn(mapInstance);

  try {
    const response = await fetch("/api/realtime/predict-click", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ lat, lon: lng }),
    });

    const result = await response.json();

    if (result.error) {
      popup.setContent('<div class="popup-hotspot">❌ Lỗi API</div>');
      return;
    }

    const color = result.is_fire ? "#dc2626" : "#16a34a";
    const percent = (result.probability * 100).toFixed(1);

    popup.setContent(`
      <div class="popup-hotspot">
        <div class="popup-header">
          <span class="popup-icon">🌍</span>
          <span class="popup-title">MÔI TRƯỜNG HIỆN TẠI</span>
        </div>
        
        <div class="popup-risk" style="color: ${color};">
          ${result.risk_level}
        </div>
        
        <div class="popup-probability" style="color: ${color};">
          Xác suất: ${percent}%
        </div>
        
        <div class="popup-details">
          <strong>📍 ${result.province}</strong><br><br>
          
          <strong>Thời tiết hiện tại:</strong><br>
          • Nhiệt độ: ${result.weather.Tmax_C}°C<br>
          • Độ ẩm: ${result.weather.RHmax_pct}%<br>
          • Gió: ${result.weather.Wind_max_kmh} km/h<br>
          • Mưa hôm nay: ${result.weather.Precip_sum_mm}mm<br>
          • Mưa 7 ngày: ${result.weather.Precip_sum_7d.toFixed(1)}mm<br>
          • Bức xạ: ${result.weather.Solar_rad_J_m2.toFixed(1)} J/m²
        </div>
        
        <div class="popup-footer">
          ℹ️ Dự báo dựa trên điều kiện môi trường (không có điểm nóng)
        </div>
      </div>
    `);
  } catch (error) {
    console.error("Map click prediction error:", error);
    popup.setContent('<div class="popup-hotspot">❌ Lỗi kết nối</div>');
  }
}

function formatTime(acqTime) {
  const timeStr = acqTime.toString().padStart(4, "0");
  const hours = timeStr.substring(0, 2);
  const minutes = timeStr.substring(2, 4);
  return `${hours}:${minutes}`;
}

// ==================== TAB 3: ANALYTICS ====================
async function loadAnalytics() {
  try {
    const response = await fetch("/api/stats");
    const data = await response.json();

    const statTotalEl = document.getElementById("statTotalFires");
    if (statTotalEl) {
      statTotalEl.textContent = data.total_fires.toLocaleString();
    }

    const topProvinces = Object.keys(data.heatmap).length;
    const statHighRiskEl = document.getElementById("statHighRisk");
    if (statHighRiskEl) {
      statHighRiskEl.textContent = topProvinces;
    }

    if (data.monthly && Object.keys(data.monthly).length > 0) {
      const peakMonth = Object.entries(data.monthly).reduce((a, b) =>
        a[1] > b[1] ? a : b,
      );
      const monthNames = [
        "Tháng 1",
        "Tháng 2",
        "Tháng 3",
        "Tháng 4",
        "Tháng 5",
        "Tháng 6",
        "Tháng 7",
        "Tháng 8",
        "Tháng 9",
        "Tháng 10",
        "Tháng 11",
        "Tháng 12",
      ];
      const statPeakEl = document.getElementById("statPeakMonth");
      if (statPeakEl) {
        statPeakEl.textContent = monthNames[parseInt(peakMonth[0]) - 1];
      }
    }

    const provinceCtx = document.getElementById("provinceChart");
    if (provinceCtx) {
      charts.province = new Chart(provinceCtx, {
        type: "bar",
        data: {
          labels: Object.keys(data.heatmap),
          datasets: [
            {
              label: "Số điểm nóng",
              data: Object.values(data.heatmap),
              backgroundColor: "rgba(220, 38, 38, 0.8)",
              borderColor: "rgba(220, 38, 38, 1)",
              borderWidth: 1,
            },
          ],
        },
        options: {
          indexAxis: "y",
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { display: false },
            tooltip: {
              callbacks: {
                label: (context) => `${context.parsed.x} điểm nóng`,
              },
            },
          },
          scales: {
            x: {
              beginAtZero: true,
              grid: { color: "rgba(0, 0, 0, 0.05)" },
            },
            y: {
              grid: { display: false },
            },
          },
        },
      });
    }

    const monthCtx = document.getElementById("monthChart");
    if (monthCtx) {
      const monthLabels = Object.keys(data.monthly).map((m) => `Tháng ${m}`);
      const monthData = Object.values(data.monthly);

      charts.month = new Chart(monthCtx, {
        type: "line",
        data: {
          labels: monthLabels,
          datasets: [
            {
              label: "Tần suất cháy",
              data: monthData,
              borderColor: "rgba(37, 99, 235, 1)",
              backgroundColor: "rgba(37, 99, 235, 0.1)",
              borderWidth: 3,
              tension: 0.4,
              fill: true,
              pointRadius: 5,
              pointHoverRadius: 7,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { display: false },
            tooltip: {
              callbacks: {
                label: (context) => `${context.parsed.y} điểm nóng`,
              },
            },
          },
          scales: {
            y: {
              beginAtZero: true,
              grid: { color: "rgba(0, 0, 0, 0.05)" },
            },
            x: {
              grid: { display: false },
            },
          },
        },
      });
    }

    showToast("Đã tải thống kê thành công");
  } catch (error) {
    console.error("Analytics error:", error);
    showToast("❌ Lỗi tải thống kê");
  }
}

// ==================== UTILITIES ====================
function showToast(message) {
  const toast = document.getElementById("toast");
  const toastMessage = document.getElementById("toastMessage");

  if (toast && toastMessage) {
    toastMessage.textContent = message;
    toast.classList.remove("hidden");

    setTimeout(() => {
      toast.classList.add("hidden");
    }, 3000);
  }
}

// ==================== INITIALIZATION ====================
document.addEventListener("DOMContentLoaded", () => {
  initTabs();
  initPredict();
  console.log("🔥 FireGuard AI System Initialized");
});
