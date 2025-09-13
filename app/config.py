import os
from datetime import timedelta

class Config:
    """Base configuration class"""
    
    # Flask settings
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    
    # Database settings
    MYSQL_HOST = os.environ.get('MYSQL_HOST') or 'localhost'
    MYSQL_PORT = os.environ.get('MYSQL_PORT') or '3306'
    MYSQL_USER = os.environ.get('MYSQL_USER') or 'newsanalyzer'
    MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD') or 'password'
    MYSQL_DATABASE = os.environ.get('MYSQL_DATABASE') or 'newsanalyzer_db'
    
    SQLALCHEMY_DATABASE_URI = f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_recycle': 300,
        'pool_pre_ping': True
    }
    
    # Redis settings
    REDIS_HOST = os.environ.get('REDIS_HOST') or 'localhost'
    REDIS_PORT = os.environ.get('REDIS_PORT') or '6379'
    REDIS_DB = os.environ.get('REDIS_DB') or '0'
    REDIS_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"
    
    # Celery settings
    CELERY_BROKER_URL = REDIS_URL
    CELERY_RESULT_BACKEND = REDIS_URL
    CELERY_TASK_SERIALIZER = 'json'
    CELERY_RESULT_SERIALIZER = 'json'
    CELERY_ACCEPT_CONTENT = ['json']
    CELERY_TIMEZONE = 'Asia/Tehran'
    CELERY_ENABLE_UTC = True
    
    # Celery beat schedule
    CELERYBEAT_SCHEDULE = {
        'crawl-news': {
            'task': 'app.tasks.crawler_tasks.crawl_all_agencies',
            'schedule': timedelta(minutes=30),
        },
        'analyze-news': {
            'task': 'app.tasks.analysis_tasks.analyze_new_items',
            'schedule': timedelta(minutes=45),
        },
        'daily-report': {
            'task': 'app.tasks.report_tasks.send_daily_report',
            'schedule': timedelta(hours=24),
        },
    }
    
    # Telegram Bot settings
    TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN') or 'YOUR_BOT_TOKEN_HERE'
    TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID') or 'YOUR_CHAT_ID_HERE'
    
    # Scraper settings
    SCRAPER_CONFIG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'configs', 'scrapers')
    SCRAPER_USER_AGENT = 'NewsAnalyzer/1.0 (+http://localhost:5000)'
    SCRAPER_TIMEOUT = 30
    SCRAPER_RETRY_ATTEMPTS = 3
    
    # Analysis settings
    SIMILARITY_THRESHOLD = 0.75
    MAX_KEYWORDS = 10
    
    # Logging
    LOG_LEVEL = os.environ.get('LOG_LEVEL') or 'INFO'
    LOG_FILE = os.environ.get('LOG_FILE') or 'newsanalyzer.log'

class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    
class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}