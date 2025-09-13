from flask import Blueprint, render_template, request, jsonify, current_app
from app import db
from app.models import NewsAgency, NewsItem, NewsGroup, NewsGroupItem, AnalysisResult
from sqlalchemy import func, desc, and_
from datetime import datetime, timedelta
import json

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/')
def index():
    """Main dashboard page"""
    # Get basic statistics
    stats = get_dashboard_stats()
    
    # Get recent news groups
    recent_groups = get_recent_news_groups(limit=10)
    
    # Get agency statistics
    agency_stats = get_agency_statistics()
    
    return render_template('dashboard/index.html', 
                         stats=stats, 
                         recent_groups=recent_groups,
                         agency_stats=agency_stats)

@dashboard_bp.route('/api/stats')
def api_stats():
    """API endpoint for dashboard statistics"""
    return jsonify(get_dashboard_stats())

@dashboard_bp.route('/api/news-groups')
def api_news_groups():
    """API endpoint for news groups with pagination"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    
    # Get news groups with item counts
    groups_query = db.session.query(
        NewsGroup,
        func.count(NewsGroupItem.id).label('item_count')
    ).outerjoin(
        NewsGroupItem, NewsGroup.id == NewsGroupItem.news_group_id
    ).group_by(NewsGroup.id).order_by(desc(NewsGroup.creation_timestamp))
    
    groups = groups_query.paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    result = {
        'groups': [],
        'pagination': {
            'page': groups.page,
            'pages': groups.pages,
            'per_page': groups.per_page,
            'total': groups.total
        }
    }
    
    for group, item_count in groups.items:
        # Get sample items from this group
        sample_items = db.session.query(NewsItem).join(
            NewsGroupItem, NewsItem.id == NewsGroupItem.news_item_id
        ).filter(
            NewsGroupItem.news_group_id == group.id
        ).order_by(desc(NewsItem.publication_timestamp)).limit(3).all()
        
        result['groups'].append({
            'id': group.id,
            'main_title': group.main_title,
            'creation_timestamp': group.creation_timestamp.isoformat(),
            'item_count': item_count,
            'sample_items': [{
                'id': item.id,
                'title': item.title,
                'agency_name': item.agency.name if item.agency else 'Unknown',
                'publication_timestamp': item.publication_timestamp.isoformat() if item.publication_timestamp else None,
                'url': item.url
            } for item in sample_items]
        })
    
    return jsonify(result)

@dashboard_bp.route('/api/group/<int:group_id>')
def api_group_details(group_id):
    """API endpoint for detailed group information"""
    group = NewsGroup.query.get_or_404(group_id)
    
    # Get all items in this group
    items_query = db.session.query(
        NewsItem, NewsGroupItem.similarity_score
    ).join(
        NewsGroupItem, NewsItem.id == NewsGroupItem.news_item_id
    ).filter(
        NewsGroupItem.news_group_id == group_id
    ).order_by(desc(NewsItem.publication_timestamp))
    
    items = []
    for item, similarity in items_query.all():
        # Get analysis results for this item
        analysis_results = {}
        for result in item.analysis_results:
            if result.analysis_type == 'sentiment':
                try:
                    analysis_results['sentiment'] = json.loads(result.value)
                except:
                    analysis_results['sentiment'] = {'label': 'unknown'}
            elif result.analysis_type == 'speed_to_publish':
                analysis_results['speed_to_publish'] = float(result.value)
        
        items.append({
            'id': item.id,
            'title': item.title,
            'agency_name': item.agency.name if item.agency else 'Unknown',
            'publication_timestamp': item.publication_timestamp.isoformat() if item.publication_timestamp else None,
            'crawler_timestamp': item.crawler_timestamp.isoformat(),
            'url': item.url,
            'similarity_score': similarity,
            'is_duplicate': item.is_duplicate,
            'analysis': analysis_results
        })
    
    return jsonify({
        'group': {
            'id': group.id,
            'main_title': group.main_title,
            'creation_timestamp': group.creation_timestamp.isoformat()
        },
        'items': items
    })

@dashboard_bp.route('/api/agencies')
def api_agencies():
    """API endpoint for news agencies information"""
    agencies = NewsAgency.query.all()
    
    result = []
    for agency in agencies:
        # Get recent statistics
        today = datetime.utcnow().date()
        yesterday = today - timedelta(days=1)
        
        today_count = NewsItem.query.filter(
            NewsItem.agency_id == agency.id,
            func.date(NewsItem.crawler_timestamp) == today
        ).count()
        
        yesterday_count = NewsItem.query.filter(
            NewsItem.agency_id == agency.id,
            func.date(NewsItem.crawler_timestamp) == yesterday
        ).count()
        
        # Get last crawl time
        last_item = NewsItem.query.filter(
            NewsItem.agency_id == agency.id
        ).order_by(desc(NewsItem.crawler_timestamp)).first()
        
        result.append({
            'id': agency.id,
            'name': agency.name,
            'base_url': agency.base_url,
            'is_active': agency.is_active,
            'today_count': today_count,
            'yesterday_count': yesterday_count,
            'last_crawl': last_item.crawler_timestamp.isoformat() if last_item else None
        })
    
    return jsonify(result)

@dashboard_bp.route('/api/timeline')
def api_timeline():
    """API endpoint for news timeline"""
    hours = request.args.get('hours', 24, type=int)
    start_time = datetime.utcnow() - timedelta(hours=hours)
    
    # Get news items grouped by hour
    timeline_data = db.session.query(
        func.date_trunc('hour', NewsItem.crawler_timestamp).label('hour'),
        func.count(NewsItem.id).label('count'),
        NewsAgency.name.label('agency_name')
    ).join(
        NewsAgency, NewsItem.agency_id == NewsAgency.id
    ).filter(
        NewsItem.crawler_timestamp >= start_time
    ).group_by(
        func.date_trunc('hour', NewsItem.crawler_timestamp),
        NewsAgency.name
    ).order_by('hour').all()
    
    # Format data for chart
    result = {}
    for hour, count, agency_name in timeline_data:
        hour_str = hour.isoformat()
        if hour_str not in result:
            result[hour_str] = {}
        result[hour_str][agency_name] = count
    
    return jsonify(result)

@dashboard_bp.route('/api/sentiment-analysis')
def api_sentiment_analysis():
    """API endpoint for sentiment analysis overview"""
    # Get sentiment distribution
    sentiment_results = db.session.query(
        AnalysisResult.value
    ).filter(
        AnalysisResult.analysis_type == 'sentiment',
        AnalysisResult.analysis_timestamp >= datetime.utcnow() - timedelta(days=7)
    ).all()
    
    sentiment_counts = {'positive': 0, 'negative': 0, 'neutral': 0}
    
    for result in sentiment_results:
        try:
            sentiment_data = json.loads(result.value)
            label = sentiment_data.get('label', 'neutral')
            sentiment_counts[label] = sentiment_counts.get(label, 0) + 1
        except:
            sentiment_counts['neutral'] += 1
    
    return jsonify(sentiment_counts)

@dashboard_bp.route('/search')
def search():
    """Search page"""
    query = request.args.get('q', '')
    page = request.args.get('page', 1, type=int)
    
    if not query:
        return render_template('dashboard/search.html', query='', results=None)
    
    # Search in news items
    search_results = NewsItem.query.filter(
        db.or_(
            NewsItem.title.contains(query),
            NewsItem.full_text.contains(query)
        )
    ).order_by(desc(NewsItem.publication_timestamp)).paginate(
        page=page, per_page=20, error_out=False
    )
    
    return render_template('dashboard/search.html', 
                         query=query, 
                         results=search_results)

def get_dashboard_stats():
    """Get basic dashboard statistics"""
    today = datetime.utcnow().date()
    yesterday = today - timedelta(days=1)
    week_ago = today - timedelta(days=7)
    
    stats = {
        'total_news': NewsItem.query.count(),
        'today_news': NewsItem.query.filter(
            func.date(NewsItem.crawler_timestamp) == today
        ).count(),
        'yesterday_news': NewsItem.query.filter(
            func.date(NewsItem.crawler_timestamp) == yesterday
        ).count(),
        'week_news': NewsItem.query.filter(
            func.date(NewsItem.crawler_timestamp) >= week_ago
        ).count(),
        'total_groups': NewsGroup.query.count(),
        'today_groups': NewsGroup.query.filter(
            func.date(NewsGroup.creation_timestamp) == today
        ).count(),
        'total_agencies': NewsAgency.query.count(),
        'active_agencies': NewsAgency.query.filter(
            NewsAgency.is_active == True
        ).count(),
        'duplicates_found': NewsItem.query.filter(
            NewsItem.is_duplicate == True
        ).count()
    }
    
    # Calculate growth rate
    if stats['yesterday_news'] > 0:
        stats['growth_rate'] = ((stats['today_news'] - stats['yesterday_news']) / stats['yesterday_news']) * 100
    else:
        stats['growth_rate'] = 0
    
    return stats

def get_recent_news_groups(limit=10):
    """Get recent news groups with basic info"""
    groups = db.session.query(
        NewsGroup,
        func.count(NewsGroupItem.id).label('item_count')
    ).outerjoin(
        NewsGroupItem, NewsGroup.id == NewsGroupItem.news_group_id
    ).group_by(NewsGroup.id).order_by(
        desc(NewsGroup.creation_timestamp)
    ).limit(limit).all()
    
    result = []
    for group, item_count in groups:
        result.append({
            'id': group.id,
            'main_title': group.main_title,
            'creation_timestamp': group.creation_timestamp,
            'item_count': item_count
        })
    
    return result

def get_agency_statistics():
    """Get statistics for each news agency"""
    today = datetime.utcnow().date()
    
    agency_stats = db.session.query(
        NewsAgency.name,
        func.count(NewsItem.id).label('total_news'),
        func.count(
            db.case([(func.date(NewsItem.crawler_timestamp) == today, NewsItem.id)])
        ).label('today_news')
    ).outerjoin(
        NewsItem, NewsAgency.id == NewsItem.agency_id
    ).group_by(NewsAgency.id, NewsAgency.name).all()
    
    return [{
        'name': name,
        'total_news': total_news,
        'today_news': today_news
    } for name, total_news, today_news in agency_stats]