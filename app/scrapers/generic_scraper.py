import json
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import logging
import re
from urllib.parse import urljoin, urlparse
from dateutil import parser as date_parser
import pytz

logger = logging.getLogger(__name__)

class GenericScraper:
    """Generic scraper that works with configuration files"""
    
    def __init__(self, config_path, user_agent=None, timeout=30):
        self.config_path = config_path
        self.config = self._load_config()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': user_agent or 'NewsAnalyzer/1.0 (+http://localhost:5000)'
        })
        self.timeout = timeout
        self.tehran_tz = pytz.timezone('Asia/Tehran')
    
    def _load_config(self):
        """Load scraper configuration from JSON file"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load config from {self.config_path}: {e}")
            raise
    
    def _make_request(self, url, retries=3):
        """Make HTTP request with retry logic"""
        for attempt in range(retries):
            try:
                response = self.session.get(url, timeout=self.timeout)
                response.raise_for_status()
                return response
            except requests.RequestException as e:
                logger.warning(f"Request attempt {attempt + 1} failed for {url}: {e}")
                if attempt == retries - 1:
                    raise
        return None
    
    def _extract_text(self, soup, selector):
        """Extract text using CSS selector"""
        if not selector:
            return None
        
        try:
            element = soup.select_one(selector)
            if element:
                return element.get_text(strip=True)
        except Exception as e:
            logger.warning(f"Failed to extract text with selector '{selector}': {e}")
        return None
    
    def _extract_attribute(self, soup, selector, attribute='href'):
        """Extract attribute value using CSS selector"""
        if not selector:
            return None
        
        try:
            element = soup.select_one(selector)
            if element:
                return element.get(attribute)
        except Exception as e:
            logger.warning(f"Failed to extract {attribute} with selector '{selector}': {e}")
        return None
    
    def _parse_date(self, date_string):
        """Parse various Persian and English date formats"""
        if not date_string:
            return None
        
        # Clean the date string
        date_string = date_string.strip()
        
        # Common Persian month names mapping
        persian_months = {
            'فروردین': 'Farvardin', 'اردیبهشت': 'Ordibehesht', 'خرداد': 'Khordad',
            'تیر': 'Tir', 'مرداد': 'Mordad', 'شهریور': 'Shahrivar',
            'مهر': 'Mehr', 'آبان': 'Aban', 'آذر': 'Azar',
            'دی': 'Dey', 'بهمن': 'Bahman', 'اسفند': 'Esfand'
        }
        
        try:
            # Try to parse as ISO format first
            if 'T' in date_string or '-' in date_string:
                parsed_date = date_parser.parse(date_string)
                if parsed_date.tzinfo is None:
                    parsed_date = self.tehran_tz.localize(parsed_date)
                return parsed_date.astimezone(pytz.UTC)
            
            # Try relative time parsing (e.g., "2 ساعت پیش")
            relative_patterns = [
                (r'(\d+)\s*دقیقه\s*پیش', 'minutes'),
                (r'(\d+)\s*ساعت\s*پیش', 'hours'),
                (r'(\d+)\s*روز\s*پیش', 'days'),
            ]
            
            for pattern, unit in relative_patterns:
                match = re.search(pattern, date_string)
                if match:
                    value = int(match.group(1))
                    now = datetime.now(self.tehran_tz)
                    if unit == 'minutes':
                        parsed_date = now - timedelta(minutes=value)
                    elif unit == 'hours':
                        parsed_date = now - timedelta(hours=value)
                    elif unit == 'days':
                        parsed_date = now - timedelta(days=value)
                    return parsed_date.astimezone(pytz.UTC)
            
            # If all else fails, return current time
            logger.warning(f"Could not parse date: {date_string}")
            return datetime.now(pytz.UTC)
            
        except Exception as e:
            logger.warning(f"Date parsing failed for '{date_string}': {e}")
            return datetime.now(pytz.UTC)
    
    def _determine_position(self, element, soup):
        """Determine position of news item on page"""
        try:
            # Simple heuristic based on element position
            all_news = soup.select(self.config.get('news_list_selector', ''))
            if not all_news:
                return 'unknown'
            
            element_index = -1
            for i, news_elem in enumerate(all_news):
                if element in news_elem.find_all():
                    element_index = i
                    break
            
            if element_index == -1:
                return 'unknown'
            elif element_index < 3:
                return 'homepage_top'
            elif element_index < len(all_news) // 2:
                return 'homepage_middle'
            else:
                return 'homepage_bottom'
                
        except Exception as e:
            logger.warning(f"Failed to determine position: {e}")
            return 'unknown'
    
    def scrape_news_list(self):
        """Scrape news items from the configured source"""
        try:
            base_url = self.config['base_url']
            response = self._make_request(base_url)
            if not response:
                return []
            
            soup = BeautifulSoup(response.content, 'html.parser')
            news_items = []
            
            # Get news list elements
            news_list_selector = self.config.get('news_list_selector')
            if news_list_selector:
                news_elements = soup.select(news_list_selector)
            else:
                news_elements = [soup]  # Use entire page if no list selector
            
            selectors = self.config.get('news_item_selectors', {})
            
            for element in news_elements:
                try:
                    # Extract basic information
                    title = self._extract_text(element, selectors.get('title'))
                    if not title:
                        continue
                    
                    # Extract URL
                    url = self._extract_attribute(element, selectors.get('url'), 'href')
                    if url:
                        url = urljoin(base_url, url)
                    
                    # Extract other fields
                    category = self._extract_text(element, selectors.get('category'))
                    main_image = self._extract_attribute(element, selectors.get('main_image'), 'src')
                    if main_image:
                        main_image = urljoin(base_url, main_image)
                    
                    # Extract publication time
                    pub_time_text = self._extract_text(element, selectors.get('publication_timestamp'))
                    publication_timestamp = self._parse_date(pub_time_text)
                    
                    # Determine position
                    position = self._determine_position(element, soup)
                    
                    # Get full text if URL is available
                    full_text = None
                    if url and selectors.get('full_text'):
                        full_text = self._extract_full_text(url, selectors.get('full_text'))
                    
                    news_item = {
                        'title': title,
                        'url': url,
                        'full_text': full_text,
                        'publication_timestamp': publication_timestamp,
                        'category': category,
                        'main_image_url': main_image,
                        'position_on_page': position
                    }
                    
                    news_items.append(news_item)
                    
                except Exception as e:
                    logger.warning(f"Failed to extract news item: {e}")
                    continue
            
            logger.info(f"Scraped {len(news_items)} news items from {self.config['name']}")
            return news_items
            
        except Exception as e:
            logger.error(f"Failed to scrape news from {self.config.get('name', 'unknown')}: {e}")
            return []
    
    def _extract_full_text(self, url, full_text_selector):
        """Extract full text from individual news page"""
        try:
            response = self._make_request(url)
            if not response:
                return None
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extract full text
            full_text_elements = soup.select(full_text_selector)
            if full_text_elements:
                # Combine all matching elements
                full_text = ' '.join([elem.get_text(strip=True) for elem in full_text_elements])
                return full_text
            
        except Exception as e:
            logger.warning(f"Failed to extract full text from {url}: {e}")
        
        return None
    
    def get_agency_name(self):
        """Get the name of the news agency"""
        return self.config.get('name', 'Unknown')
    
    def is_valid_config(self):
        """Check if the configuration is valid"""
        required_fields = ['name', 'base_url', 'news_item_selectors']
        return all(field in self.config for field in required_fields)