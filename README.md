# News Analyzer Dashboard

## 📰 درباره پروژه

داشبورد تحلیل اخبار یک سیستم جامع برای جمع‌آوری، تحلیل و گزارش‌گیری از اخبار خبرگزاری‌های مختلف است. این سیستم قابلیت‌های زیر را ارائه می‌دهد:

- 🔄 **جمع‌آوری خودکار اخبار** از خبرگزاری‌های مختلف
- 🤖 **تحلیل هوشمند محتوا** با استفاده از NLP
- 📊 **داشبورد تعاملی** برای نمایش آمار و تحلیل‌ها
- 🔍 **تشخیص اخبار تکراری** و گروه‌بندی
- ⚡ **محاسبه سرعت انتشار** اخبار
- 💭 **تحلیل احساسات** متون فارسی
- 📱 **اعلان‌رسانی تلگرام** برای اخبار مهم

## 🏗️ معماری سیستم

```
📁 NewsAnalyzerDashboard/
├── 📁 app/
│   ├── 📄 __init__.py          # تنظیمات اصلی Flask
│   ├── 📄 config.py            # پیکربندی‌های سیستم
│   ├── 📄 models.py            # مدل‌های پایگاه داده
│   ├── 📄 dashboard.py         # روت‌های داشبورد
│   ├── 📁 scrapers/
│   │   ├── 📄 __init__.py
│   │   └── 📄 generic_scraper.py  # اسکرپر عمومی
│   ├── 📁 tasks/
│   │   ├── 📄 __init__.py
│   │   ├── 📄 crawler_tasks.py    # تسک‌های کرالینگ
│   │   └── 📄 analysis_tasks.py   # تسک‌های تحلیل
│   └── 📁 templates/
│       ├── 📄 base.html
│       └── 📁 dashboard/
├── 📁 scrapers_config/
│   ├── 📄 farsnews.json        # پیکربندی فارس نیوز
│   └── 📄 mehrnews.json        # پیکربندی مهر نیوز
├── 📄 requirements.txt         # وابستگی‌های Python
├── 📄 .env.example            # نمونه متغیرهای محیطی
├── 📄 run.py                  # فایل اجرای اصلی
├── 📄 celery_worker.py        # Celery Worker
└── 📄 wsgi.py                 # WSGI Entry Point
```

## 🚀 نصب و راه‌اندازی

### پیش‌نیازها

- Python 3.8+
- MySQL/MariaDB
- Redis Server
- Git

### مرحله 1: دانلود پروژه

```bash
git clone <repository-url>
cd NewsAnalyzerDashboard
```

### مرحله 2: ایجاد محیط مجازی

```bash
# ایجاد محیط مجازی
python -m venv venv

# فعال‌سازی محیط مجازی
# در Windows:
venv\Scripts\activate
# در Linux/Mac:
source venv/bin/activate
```

### مرحله 3: نصب وابستگی‌ها

```bash
pip install -r requirements.txt
```

### مرحله 4: تنظیم پایگاه داده

```sql
-- ایجاد پایگاه داده در MySQL
CREATE DATABASE news_analyzer CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'news_user'@'localhost' IDENTIFIED BY 'your_password';
GRANT ALL PRIVILEGES ON news_analyzer.* TO 'news_user'@'localhost';
FLUSH PRIVILEGES;
```

### مرحله 5: تنظیم متغیرهای محیطی

```bash
# کپی فایل نمونه
cp .env.example .env

# ویرایش فایل .env
nano .env
```

متغیرهای مهم:

```env
# Flask
FLASK_ENV=development
SECRET_KEY=your-secret-key-here

# Database
DATABASE_URL=mysql://news_user:your_password@localhost/news_analyzer

# Redis
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# Telegram Bot (اختیاری)
TELEGRAM_BOT_TOKEN=your-bot-token
TELEGRAM_CHAT_ID=your-chat-id
```

### مرحله 6: راه‌اندازی پایگاه داده

```bash
# ایجاد جداول
python run.py init-db

# اضافه کردن خبرگزاری‌های نمونه
python run.py add-agencies
```

## 🔧 اجرای سیستم

### حالت Development

#### 1. اجرای Redis Server

```bash
# در Windows (با Redis for Windows)
redis-server

# در Linux/Mac
sudo systemctl start redis
# یا
redis-server
```

#### 2. اجرای Celery Worker

```bash
# در ترمینال جداگانه
python celery_worker.py
```

#### 3. اجرای Celery Beat (برای تسک‌های زمان‌بندی شده)

```bash
# در ترمینال جداگانه
celery -A app.celery beat --loglevel=info
```

#### 4. اجرای Flask Application

```bash
python run.py
```

داشبورد در آدرس `http://localhost:5000` در دسترس خواهد بود.

### حالت Production

#### با Gunicorn

```bash
# نصب Gunicorn
pip install gunicorn

# اجرای application
gunicorn --bind 0.0.0.0:8000 --workers 4 wsgi:application
```

#### با Docker (اختیاری)

```dockerfile
# Dockerfile نمونه
FROM python:3.9-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8000
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "wsgi:application"]
```

## 📊 استفاده از سیستم

### داشبورد اصلی

- **آمار کلی**: تعداد اخبار، خبرگزاری‌ها، گروه‌های خبری
- **نمودار زمانی**: روند انتشار اخبار در طول زمان
- **تحلیل احساسات**: توزیع احساسات در اخبار
- **آمار خبرگزاری‌ها**: عملکرد هر خبرگزاری

### جستجو و فیلتر

- جستجو در عنوان و متن اخبار
- فیلتر بر اساس خبرگزاری
- فیلتر بر اساس بازه زمانی
- مرتب‌سازی بر اساس تاریخ یا امتیاز

### API Endpoints

```
GET /api/stats              # آمار کلی
GET /api/news-groups        # لیست گروه‌های خبری
GET /api/group/<id>         # جزئیات گروه خبری
GET /api/agencies           # لیست خبرگزاری‌ها
GET /api/timeline           # داده‌های نمودار زمانی
GET /api/sentiment          # تحلیل احساسات
```

## 🔧 دستورات CLI

```bash
# نمایش آمار
python run.py stats

# تست پیکربندی خبرگزاری
python run.py test-scraper farsnews

# لیست خبرگزاری‌ها
python run.py list-agencies

# اعتبارسنجی فایل‌های پیکربندی
python run.py validate-configs

# ریست پایگاه داده
python run.py reset-db

# بررسی سلامت سیستم
curl http://localhost:5000/health
```

## ⚙️ پیکربندی خبرگزاری‌ها

برای اضافه کردن خبرگزاری جدید، فایل JSON در پوشه `scrapers_config` ایجاد کنید:

```json
{
  "name": "نام خبرگزاری",
  "base_url": "https://example.com",
  "list_url": "https://example.com/news",
  "selectors": {
    "news_list": ".news-item",
    "title": ".title",
    "link": "a",
    "date": ".date",
    "summary": ".summary"
  },
  "detail_selectors": {
    "content": ".content",
    "full_date": ".full-date",
    "author": ".author",
    "tags": ".tags a"
  },
  "date_format": "%Y-%m-%d %H:%M:%S",
  "headers": {
    "User-Agent": "Mozilla/5.0..."
  }
}
```

## 🐛 عیب‌یابی

### مشکلات رایج

1. **خطای اتصال به پایگاه داده**
   ```bash
   # بررسی اتصال
   mysql -u news_user -p news_analyzer
   ```

2. **خطای اتصال به Redis**
   ```bash
   # بررسی وضعیت Redis
   redis-cli ping
   ```

3. **خطای import ماژول‌ها**
   ```bash
   # بررسی نصب وابستگی‌ها
   pip list
   pip install -r requirements.txt
   ```

### لاگ‌ها

- **Flask**: `logs/app.log`
- **Celery Worker**: `logs/celery_worker.log`
- **Scraper**: `logs/scraper.log`

## 🔒 امنیت

- همیشه `SECRET_KEY` قوی استفاده کنید
- اطلاعات حساس را در فایل `.env` نگهداری کنید
- فایل `.env` را در `.gitignore` قرار دهید
- برای production از HTTPS استفاده کنید
- دسترسی‌های پایگاه داده را محدود کنید

## 📈 بهینه‌سازی عملکرد

### تنظیمات Celery

```python
# در config.py
CELERY_WORKER_CONCURRENCY = 4
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_TASK_TIME_LIMIT = 300
```

### تنظیمات پایگاه داده

```sql
-- ایجاد ایندکس برای بهبود عملکرد
CREATE INDEX idx_news_items_published_at ON news_items(published_at);
CREATE INDEX idx_news_items_agency_id ON news_items(agency_id);
CREATE INDEX idx_news_items_url_hash ON news_items(url_hash);
```

## 🤝 مشارکت

برای مشارکت در پروژه:

1. پروژه را Fork کنید
2. شاخه جدید ایجاد کنید (`git checkout -b feature/amazing-feature`)
3. تغییرات را Commit کنید (`git commit -m 'Add amazing feature'`)
4. به شاخه Push کنید (`git push origin feature/amazing-feature`)
5. Pull Request ایجاد کنید

## 📝 لایسنس

این پروژه تحت لایسنس MIT منتشر شده است.

## 📞 پشتیبانی

برای گزارش باگ یا درخواست ویژگی جدید، از بخش Issues استفاده کنید.

---

**ساخته شده با ❤️ برای جامعه توسعه‌دهندگان ایرانی**