#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Celery Worker for News Analyzer Dashboard

This script starts the Celery worker for background task processing.
It handles news crawling, analysis, and reporting tasks.
"""

import os
import sys
from dotenv import load_dotenv

# Add the project root to Python path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

# Load environment variables
load_dotenv()

from app import create_app
from celery import Celery
import logging

# Create Flask application
flask_app = create_app()

# Get Celery instance from Flask app
celery = flask_app.extensions['celery']

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/celery_worker.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

def setup_logging():
    """Setup logging configuration for Celery worker."""
    # Create logs directory if it doesn't exist
    logs_dir = os.path.join(project_root, 'logs')
    os.makedirs(logs_dir, exist_ok=True)
    
    # Configure Celery logging
    celery.conf.update(
        worker_log_format='[%(asctime)s: %(levelname)s/%(processName)s] %(message)s',
        worker_task_log_format='[%(asctime)s: %(levelname)s/%(processName)s][%(task_name)s(%(task_id)s)] %(message)s',
        worker_log_color=True,
        worker_redirect_stdouts=True,
        worker_redirect_stdouts_level='INFO'
    )

def print_banner():
    """Print startup banner."""
    print(f"""
    ╔══════════════════════════════════════════════════════════════╗
    ║                   Celery Worker                              ║
    ║              News Analyzer Dashboard                         ║
    ║                                                              ║
    ║  🔄 Worker Status: Starting...                               ║
    ║  📊 Broker: {os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0'):<44} ║
    ║  💾 Backend: {os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0'):<43} ║
    ║  📁 Logs: logs/celery_worker.log                             ║
    ║                                                              ║
    ║  Available Tasks:                                            ║
    ║    • crawl_agency - Crawl single news agency                ║
    ║    • crawl_all_agencies - Crawl all active agencies         ║
    ║    • analyze_news_item - Analyze single news item           ║
    ║    • analyze_new_items - Analyze all new items              ║
    ║    • calculate_publication_speed - Calculate speeds          ║
    ║    • analyze_sentiment - Sentiment analysis                 ║
    ║    • cleanup_old_news - Clean up old news items             ║
    ║                                                              ║
    ║  Press Ctrl+C to stop the worker                            ║
    ╚══════════════════════════════════════════════════════════════╝
    """)

def register_signal_handlers():
    """Register signal handlers for graceful shutdown."""
    import signal
    
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}. Shutting down gracefully...")
        celery.control.shutdown()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

def check_dependencies():
    """Check if required services are available."""
    try:
        # Test Redis connection
        from redis import Redis
        redis_url = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
        
        # Parse Redis URL
        if redis_url.startswith('redis://'):
            import urllib.parse
            parsed = urllib.parse.urlparse(redis_url)
            redis_client = Redis(
                host=parsed.hostname or 'localhost',
                port=parsed.port or 6379,
                db=int(parsed.path.lstrip('/')) if parsed.path else 0
            )
            redis_client.ping()
            logger.info("✓ Redis connection successful")
        
    except Exception as e:
        logger.error(f"❌ Redis connection failed: {e}")
        logger.error("Please ensure Redis server is running")
        sys.exit(1)
    
    try:
        # Test database connection
        with flask_app.app_context():
            from app import db
            db.session.execute('SELECT 1')
            logger.info("✓ Database connection successful")
    except Exception as e:
        logger.error(f"❌ Database connection failed: {e}")
        logger.error("Please ensure database server is running and configured")
        sys.exit(1)

def main():
    """Main function to start Celery worker."""
    print_banner()
    setup_logging()
    register_signal_handlers()
    
    logger.info("Starting dependency checks...")
    check_dependencies()
    
    logger.info("Starting Celery worker...")
    
    # Import tasks to register them
    with flask_app.app_context():
        from app.tasks import crawler_tasks, analysis_tasks
        logger.info("Tasks imported successfully")
    
    # Configure worker options
    worker_options = {
        'loglevel': os.getenv('CELERY_LOG_LEVEL', 'INFO'),
        'concurrency': int(os.getenv('CELERY_WORKER_CONCURRENCY', 4)),
        'prefetch_multiplier': int(os.getenv('CELERY_WORKER_PREFETCH_MULTIPLIER', 1)),
        'max_tasks_per_child': int(os.getenv('CELERY_WORKER_MAX_TASKS_PER_CHILD', 1000)),
        'task_time_limit': int(os.getenv('CELERY_TASK_TIME_LIMIT', 300)),
        'task_soft_time_limit': int(os.getenv('CELERY_TASK_SOFT_TIME_LIMIT', 240)),
    }
    
    logger.info(f"Worker configuration: {worker_options}")
    
    try:
        # Start the worker
        celery.worker_main([
            'worker',
            f'--loglevel={worker_options["loglevel"]}',
            f'--concurrency={worker_options["concurrency"]}',
            f'--prefetch-multiplier={worker_options["prefetch_multiplier"]}',
            f'--max-tasks-per-child={worker_options["max_tasks_per_child"]}',
            f'--time-limit={worker_options["task_time_limit"]}',
            f'--soft-time-limit={worker_options["task_soft_time_limit"]}',
            '--without-gossip',
            '--without-mingle',
            '--without-heartbeat'
        ])
    except KeyboardInterrupt:
        logger.info("\n👋 Worker stopped by user")
    except Exception as e:
        logger.error(f"❌ Error starting worker: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()