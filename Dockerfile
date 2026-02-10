FROM python:3.11-slim

WORKDIR /app

# تثبيت التبعيات النظامية
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# نسخ ملف المتطلبات
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# نسخ الكود
COPY . .

# إنشاء مجلدات البيانات
RUN mkdir -p /app/data

# المنفذ
EXPOSE 8000

# أمر التشغيل
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
