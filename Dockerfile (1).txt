# ════════════════════════════════════════════════════
#  🐳 Dockerfile — ربات Life Simulator بله
#  این فایل به fly.io (و هر هاست دیگه) می‌گه چطور ربات رو بسازه و اجرا کنه
# ════════════════════════════════════════════════════
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# اول کتابخانه‌ها نصب می‌شن (requests)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# بعد کل ربات کپی می‌شه
COPY main.py .

# پورت داخلی (فایل fly.toml بهش وصله)
EXPOSE 8080

CMD ["python", "main.py"]
