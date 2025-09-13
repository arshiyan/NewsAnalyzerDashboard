import os
import logging
from celery import current_app as celery_app
from app import db
from app.models import NewsAgency, NewsItem
from app.scrapers.generic_scraper import GenericScraper
from datetime import datetime
from sqlalchemy.exc import IntegrityError

logger = logging.getLogger(__name__)

@celery_app.task(bind=True, max_retries=3)
def crawl_agency(self, agency_id):
    """Crawl news from a specific agency"""
    try:
        agency = NewsAgency.query.get(agency_id)
        if not agency or not agency.is_active:
            logger.warning(f"Agency {agency_id} not found or inactive")
            return {'status': 'skipped', 'reason': 'agency not active'}
        
        # Check if config file exists
        config_path = agency.config_file_path
        if not os.path.exists(config_path):
            logger.error(f"Config file not found: {config_path}")
            return {'status': 'error', 'reason': 'config file not found'}
        
        # Initialize scraper
        scraper = GenericScraper(config_path)
        
        if not scraper.is_valid_config():
            logger.error(f"Invalid config for agency {agency.name}")
            return {'status': 'error', 'reason': 'invalid config'}
        
        # Scrape news items
        news_items = scraper.scrape_news_list()
        
        saved_count = 0
        duplicate_count = 0
        error_count = 0
        
        for item_data in news_items:
            try:
                # Check if item already exists
                existing_item = NewsItem.query.filter_by(url=item_data['url']).first()
                if existing_item:
                    duplicate_count += 1
                    continue
                
                # Create new news item
                news_item = NewsItem(
                    agency_id=agency.id,
                    title=item_data['title'],
                    url=item_data['url'],
                    full_text=item_data.get('full_text'),
                    publication_timestamp=item_data.get('publication_timestamp'),
                    category=item_data.get('category'),
                    main_image_url=item_data.get('main_image_url'),
                    position_on_page=item_data.get('position_on_page', 'unknown'),
                    crawler_timestamp=datetime.utcnow()
                )
                
                db.session.add(news_item)
                db.session.commit()
                saved_count += 1
                
                # Trigger analysis task for new item
                from app.tasks.analysis_tasks import analyze_news_item
                analyze_news_item.delay(news_item.id)
                
            except IntegrityError:
                db.session.rollback()
                duplicate_count += 1
            except Exception as e:
                db.session.rollback()
                logger.error(f"Error saving news item: {e}")
                error_count += 1
        
        result = {
            'status': 'success',
            'agency_name': agency.name,
            'total_scraped': len(news_items),
            'saved': saved_count,
            'duplicates': duplicate_count,
            'errors': error_count
        }
        
        logger.info(f"Crawling completed for {agency.name}: {result}")
        return result
        
    except Exception as e:
        logger.error(f"Crawling failed for agency {agency_id}: {e}")
        # Retry with exponential backoff
        raise self.retry(countdown=60 * (2 ** self.request.retries))

@celery_app.task
def crawl_all_agencies():
    """Crawl news from all active agencies"""
    try:
        active_agencies = NewsAgency.query.filter_by(is_active=True).all()
        
        if not active_agencies:
            logger.warning("No active agencies found")
            return {'status': 'no_agencies'}
        
        results = []
        for agency in active_agencies:
            try:
                # Start crawling task for each agency
                task_result = crawl_agency.delay(agency.id)
                results.append({
                    'agency_id': agency.id,
                    'agency_name': agency.name,
                    'task_id': task_result.id
                })
            except Exception as e:
                logger.error(f"Failed to start crawling task for {agency.name}: {e}")
                results.append({
                    'agency_id': agency.id,
                    'agency_name': agency.name,
                    'error': str(e)
                })
        
        logger.info(f"Started crawling tasks for {len(results)} agencies")
        return {
            'status': 'started',
            'agencies_count': len(active_agencies),
            'tasks': results
        }
        
    except Exception as e:
        logger.error(f"Failed to start crawling tasks: {e}")
        return {'status': 'error', 'message': str(e)}

@celery_app.task
def test_agency_config(agency_id):
    """Test scraper configuration for an agency"""
    try:
        agency = NewsAgency.query.get(agency_id)
        if not agency:
            return {'status': 'error', 'message': 'Agency not found'}
        
        config_path = agency.config_file_path
        if not os.path.exists(config_path):
            return {'status': 'error', 'message': 'Config file not found'}
        
        scraper = GenericScraper(config_path)
        
        if not scraper.is_valid_config():
            return {'status': 'error', 'message': 'Invalid configuration'}
        
        # Try to scrape a few items
        news_items = scraper.scrape_news_list()
        
        return {
            'status': 'success',
            'agency_name': agency.name,
            'items_found': len(news_items),
            'sample_titles': [item['title'] for item in news_items[:3]]
        }
        
    except Exception as e:
        logger.error(f"Config test failed for agency {agency_id}: {e}")
        return {'status': 'error', 'message': str(e)}

@celery_app.task
def cleanup_old_news(days_to_keep=30):
    """Clean up old news items"""
    try:
        from datetime import timedelta
        
        cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
        
        # Delete old news items
        old_items = NewsItem.query.filter(
            NewsItem.crawler_timestamp < cutoff_date
        ).all()
        
        deleted_count = len(old_items)
        
        for item in old_items:
            db.session.delete(item)
        
        db.session.commit()
        
        logger.info(f"Cleaned up {deleted_count} old news items")
        return {
            'status': 'success',
            'deleted_count': deleted_count,
            'cutoff_date': cutoff_date.isoformat()
        }
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Cleanup failed: {e}")
        return {'status': 'error', 'message': str(e)}