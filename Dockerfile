FROM python:3.12-slim

WORKDIR /app

# Copy file requirements và cài thư viện
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy toàn bộ code (main.py, static, model...)
COPY . .

# Mở port bên trong container (mặc định FastAPI chạy 8000)
EXPOSE 8000

# Lệnh chạy app
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
