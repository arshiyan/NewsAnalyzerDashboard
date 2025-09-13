import logging
from celery import current_app as celery_app
from app import db
from app.models import NewsItem, NewsGroup, NewsGroupItem, AnalysisResult
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from hazm import Normalizer, word_tokenize, stopwords_list
import numpy as np
from datetime import datetime, timedelta
import json

logger = logging.getLogger(__name__)

# Initialize Persian text processor
normalizer = Normalizer()
persian_stopwords = set(stopwords_list())

def preprocess_persian_text(text):
    """Preprocess Persian text for analysis"""
    if not text:
        return ""
    
    try:
        # Normalize text
        normalized = normalizer.normalize(text)
        
        # Tokenize
        tokens = word_tokenize(normalized)
        
        # Remove stopwords and short tokens
        filtered_tokens = [
            token for token in tokens 
            if len(token) > 2 and token not in persian_stopwords
        ]
        
        return ' '.join(filtered_tokens)
    except Exception as e:
        logger.warning(f"Text preprocessing failed: {e}")
        return text

@celery_app.task(bind=True, max_retries=3)
def analyze_news_item(self, news_item_id):
    """Analyze a single news item for duplicates and grouping"""
    try:
        news_item = NewsItem.query.get(news_item_id)
        if not news_item:
            logger.warning(f"News item {news_item_id} not found")
            return {'status': 'not_found'}
        
        # Skip if already processed
        if news_item.is_duplicate:
            return {'status': 'already_duplicate'}
        
        # Preprocess text for similarity comparison
        item_text = preprocess_persian_text(news_item.title + ' ' + (news_item.full_text or ''))
        
        if not item_text.strip():
            logger.warning(f"No text to analyze for item {news_item_id}")
            return {'status': 'no_text'}
        
        # Find similar items from the last 7 days
        week_ago = datetime.utcnow() - timedelta(days=7)
        recent_items = NewsItem.query.filter(
            NewsItem.id != news_item.id,
            NewsItem.crawler_timestamp >= week_ago,
            NewsItem.is_duplicate == False
        ).all()
        
        if not recent_items:
            # Create new group for this item
            news_group = NewsGroup(
                main_title=news_item.title,
                creation_timestamp=datetime.utcnow()
            )
            db.session.add(news_group)
            db.session.flush()
            
            # Add item to group
            group_item = NewsGroupItem(
                news_group_id=news_group.id,
                news_item_id=news_item.id,
                similarity_score=1.0
            )
            db.session.add(group_item)
            db.session.commit()
            
            return {
                'status': 'new_group',
                'group_id': news_group.id
            }
        
        # Prepare texts for similarity comparison
        texts = [item_text]
        item_ids = [news_item.id]
        
        for item in recent_items:
            processed_text = preprocess_persian_text(item.title + ' ' + (item.full_text or ''))
            if processed_text.strip():
                texts.append(processed_text)
                item_ids.append(item.id)
        
        if len(texts) < 2:
            # Create new group
            news_group = NewsGroup(
                main_title=news_item.title,
                creation_timestamp=datetime.utcnow()
            )
            db.session.add(news_group)
            db.session.flush()
            
            group_item = NewsGroupItem(
                news_group_id=news_group.id,
                news_item_id=news_item.id,
                similarity_score=1.0
            )
            db.session.add(group_item)
            db.session.commit()
            
            return {
                'status': 'new_group',
                'group_id': news_group.id
            }
        
        # Calculate TF-IDF and cosine similarity
        try:
            vectorizer = TfidfVectorizer(max_features=1000, ngram_range=(1, 2))
            tfidf_matrix = vectorizer.fit_transform(texts)
            
            # Calculate similarity with the first item (our target item)
            similarities = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:]).flatten()
            
            # Find the most similar item
            max_similarity_idx = np.argmax(similarities)
            max_similarity = similarities[max_similarity_idx]
            
            similarity_threshold = 0.75  # From config
            
            if max_similarity >= similarity_threshold:
                # Find existing group for the similar item
                similar_item_id = item_ids[max_similarity_idx + 1]  # +1 because we skip index 0
                similar_item = NewsItem.query.get(similar_item_id)
                
                # Find the group this similar item belongs to
                existing_group_item = NewsGroupItem.query.filter_by(
                    news_item_id=similar_item_id
                ).first()
                
                if existing_group_item:
                    # Add to existing group
                    group_item = NewsGroupItem(
                        news_group_id=existing_group_item.news_group_id,
                        news_item_id=news_item.id,
                        similarity_score=float(max_similarity)
                    )
                    db.session.add(group_item)
                    
                    # Mark as duplicate if similarity is very high
                    if max_similarity >= 0.9:
                        news_item.is_duplicate = True
                    
                    db.session.commit()
                    
                    # Calculate publication speed
                    calculate_publication_speed.delay(existing_group_item.news_group_id)
                    
                    return {
                        'status': 'added_to_group',
                        'group_id': existing_group_item.news_group_id,
                        'similarity': float(max_similarity),
                        'is_duplicate': news_item.is_duplicate
                    }
            
            # No similar items found, create new group
            news_group = NewsGroup(
                main_title=news_item.title,
                creation_timestamp=datetime.utcnow()
            )
            db.session.add(news_group)
            db.session.flush()
            
            group_item = NewsGroupItem(
                news_group_id=news_group.id,
                news_item_id=news_item.id,
                similarity_score=1.0
            )
            db.session.add(group_item)
            db.session.commit()
            
            return {
                'status': 'new_group',
                'group_id': news_group.id,
                'max_similarity': float(max_similarity)
            }
            
        except Exception as e:
            logger.error(f"Similarity calculation failed: {e}")
            # Fallback: create new group
            news_group = NewsGroup(
                main_title=news_item.title,
                creation_timestamp=datetime.utcnow()
            )
            db.session.add(news_group)
            db.session.flush()
            
            group_item = NewsGroupItem(
                news_group_id=news_group.id,
                news_item_id=news_item.id,
                similarity_score=1.0
            )
            db.session.add(group_item)
            db.session.commit()
            
            return {
                'status': 'new_group_fallback',
                'group_id': news_group.id,
                'error': str(e)
            }
        
    except Exception as e:
        logger.error(f"Analysis failed for item {news_item_id}: {e}")
        raise self.retry(countdown=60 * (2 ** self.request.retries))

@celery_app.task
def calculate_publication_speed(group_id):
    """Calculate publication speed for items in a group"""
    try:
        group = NewsGroup.query.get(group_id)
        if not group:
            return {'status': 'group_not_found'}
        
        # Get all items in the group with publication timestamps
        group_items = db.session.query(NewsItem, NewsGroupItem).join(
            NewsGroupItem, NewsItem.id == NewsGroupItem.news_item_id
        ).filter(
            NewsGroupItem.news_group_id == group_id,
            NewsItem.publication_timestamp.isnot(None)
        ).order_by(NewsItem.publication_timestamp.asc()).all()
        
        if len(group_items) < 2:
            return {'status': 'insufficient_items'}
        
        # Find the first published item
        first_item, _ = group_items[0]
        first_time = first_item.publication_timestamp
        
        speeds_calculated = 0
        
        for news_item, group_item in group_items[1:]:
            if news_item.publication_timestamp:
                # Calculate time difference in minutes
                time_diff = (news_item.publication_timestamp - first_time).total_seconds() / 60
                
                # Store the speed analysis result
                existing_result = AnalysisResult.query.filter_by(
                    news_item_id=news_item.id,
                    analysis_type='speed_to_publish'
                ).first()
                
                if not existing_result:
                    speed_result = AnalysisResult(
                        news_item_id=news_item.id,
                        analysis_type='speed_to_publish',
                        value=str(time_diff),
                        analysis_timestamp=datetime.utcnow()
                    )
                    db.session.add(speed_result)
                    speeds_calculated += 1
        
        db.session.commit()
        
        return {
            'status': 'success',
            'group_id': group_id,
            'speeds_calculated': speeds_calculated
        }
        
    except Exception as e:
        logger.error(f"Speed calculation failed for group {group_id}: {e}")
        return {'status': 'error', 'message': str(e)}

@celery_app.task
def analyze_sentiment(news_item_id):
    """Basic sentiment analysis for Persian text"""
    try:
        news_item = NewsItem.query.get(news_item_id)
        if not news_item:
            return {'status': 'not_found'}
        
        text = (news_item.title or '') + ' ' + (news_item.full_text or '')
        if not text.strip():
            return {'status': 'no_text'}
        
        # Simple keyword-based sentiment analysis
        positive_keywords = [
            'موفقیت', 'پیروزی', 'خوب', 'عالی', 'بهتر', 'پیشرفت', 'توسعه',
            'رشد', 'افزایش', 'بهبود', 'مثبت', 'امید', 'خوشحالی'
        ]
        
        negative_keywords = [
            'مشکل', 'بحران', 'خطر', 'نگرانی', 'کاهش', 'افت', 'بد', 'منفی',
            'تهدید', 'ضرر', 'زیان', 'نابودی', 'تخریب', 'جنگ', 'درگیری'
        ]
        
        # Normalize and tokenize text
        processed_text = preprocess_persian_text(text)
        tokens = processed_text.split()
        
        positive_score = sum(1 for token in tokens if token in positive_keywords)
        negative_score = sum(1 for token in tokens if token in negative_keywords)
        
        # Calculate sentiment score (-1 to 1)
        total_sentiment_words = positive_score + negative_score
        if total_sentiment_words > 0:
            sentiment_score = (positive_score - negative_score) / total_sentiment_words
        else:
            sentiment_score = 0.0
        
        # Determine sentiment label
        if sentiment_score > 0.2:
            sentiment_label = 'positive'
        elif sentiment_score < -0.2:
            sentiment_label = 'negative'
        else:
            sentiment_label = 'neutral'
        
        # Store result
        sentiment_data = {
            'score': sentiment_score,
            'label': sentiment_label,
            'positive_words': positive_score,
            'negative_words': negative_score
        }
        
        existing_result = AnalysisResult.query.filter_by(
            news_item_id=news_item_id,
            analysis_type='sentiment'
        ).first()
        
        if existing_result:
            existing_result.value = json.dumps(sentiment_data)
            existing_result.analysis_timestamp = datetime.utcnow()
        else:
            sentiment_result = AnalysisResult(
                news_item_id=news_item_id,
                analysis_type='sentiment',
                value=json.dumps(sentiment_data),
                analysis_timestamp=datetime.utcnow()
            )
            db.session.add(sentiment_result)
        
        db.session.commit()
        
        return {
            'status': 'success',
            'sentiment': sentiment_data
        }
        
    except Exception as e:
        logger.error(f"Sentiment analysis failed for item {news_item_id}: {e}")
        return {'status': 'error', 'message': str(e)}

@celery_app.task
def analyze_new_items():
    """Analyze all unprocessed news items"""
    try:
        # Find items that haven't been analyzed yet
        unanalyzed_items = NewsItem.query.outerjoin(
            AnalysisResult, NewsItem.id == AnalysisResult.news_item_id
        ).filter(
            AnalysisResult.id.is_(None),
            NewsItem.crawler_timestamp >= datetime.utcnow() - timedelta(hours=24)
        ).limit(100).all()
        
        if not unanalyzed_items:
            return {'status': 'no_items'}
        
        results = []
        for item in unanalyzed_items:
            try:
                # Start analysis tasks
                analyze_task = analyze_news_item.delay(item.id)
                sentiment_task = analyze_sentiment.delay(item.id)
                
                results.append({
                    'item_id': item.id,
                    'analyze_task_id': analyze_task.id,
                    'sentiment_task_id': sentiment_task.id
                })
            except Exception as e:
                logger.error(f"Failed to start analysis for item {item.id}: {e}")
                results.append({
                    'item_id': item.id,
                    'error': str(e)
                })
        
        return {
            'status': 'started',
            'items_count': len(unanalyzed_items),
            'tasks': results
        }
        
    except Exception as e:
        logger.error(f"Failed to analyze new items: {e}")
        return {'status': 'error', 'message': str(e)}