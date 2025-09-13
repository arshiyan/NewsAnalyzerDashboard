from datetime import datetime
from app import db

class NewsAgency(db.Model):
    """Model for news agencies"""
    __tablename__ = 'news_agencies'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    base_url = db.Column(db.String(255), nullable=False)
    config_file_path = db.Column(db.String(255), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    news_items = db.relationship('NewsItem', backref='agency', lazy='dynamic', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<NewsAgency {self.name}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'base_url': self.base_url,
            'config_file_path': self.config_file_path,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class NewsItem(db.Model):
    """Model for individual news items"""
    __tablename__ = 'news_items'
    
    id = db.Column(db.Integer, primary_key=True)
    agency_id = db.Column(db.Integer, db.ForeignKey('news_agencies.id'), nullable=False)
    title = db.Column(db.Text, nullable=False)
    url = db.Column(db.String(500), nullable=False, unique=True)
    full_text = db.Column(db.Text)
    publication_timestamp = db.Column(db.DateTime)
    crawler_timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    category = db.Column(db.String(100))
    main_image_url = db.Column(db.String(500))
    position_on_page = db.Column(db.String(50))  # 'homepage_top', 'homepage_middle', 'section_page'
    is_duplicate = db.Column(db.Boolean, default=False, nullable=False)
    
    # Relationships
    analysis_results = db.relationship('AnalysisResult', backref='news_item', lazy='dynamic', cascade='all, delete-orphan')
    group_items = db.relationship('NewsGroupItem', backref='news_item', lazy='dynamic', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<NewsItem {self.title[:50]}...>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'agency_id': self.agency_id,
            'agency_name': self.agency.name if self.agency else None,
            'title': self.title,
            'url': self.url,
            'full_text': self.full_text,
            'publication_timestamp': self.publication_timestamp.isoformat() if self.publication_timestamp else None,
            'crawler_timestamp': self.crawler_timestamp.isoformat() if self.crawler_timestamp else None,
            'category': self.category,
            'main_image_url': self.main_image_url,
            'position_on_page': self.position_on_page,
            'is_duplicate': self.is_duplicate
        }

class NewsGroup(db.Model):
    """Model for grouped similar news items"""
    __tablename__ = 'news_groups'
    
    id = db.Column(db.Integer, primary_key=True)
    main_title = db.Column(db.Text, nullable=False)
    creation_timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    group_items = db.relationship('NewsGroupItem', backref='news_group', lazy='dynamic', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<NewsGroup {self.main_title[:50]}...>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'main_title': self.main_title,
            'creation_timestamp': self.creation_timestamp.isoformat() if self.creation_timestamp else None,
            'items_count': self.group_items.count()
        }
    
    @property
    def items_count(self):
        return self.group_items.count()
    
    @property
    def first_publication_time(self):
        """Get the earliest publication time from grouped items"""
        earliest_item = db.session.query(NewsItem).join(NewsGroupItem).filter(
            NewsGroupItem.news_group_id == self.id
        ).order_by(NewsItem.publication_timestamp.asc()).first()
        return earliest_item.publication_timestamp if earliest_item else None

class NewsGroupItem(db.Model):
    """Association table for news groups and items"""
    __tablename__ = 'news_group_items'
    
    id = db.Column(db.Integer, primary_key=True)
    news_group_id = db.Column(db.Integer, db.ForeignKey('news_groups.id'), nullable=False)
    news_item_id = db.Column(db.Integer, db.ForeignKey('news_items.id'), nullable=False)
    similarity_score = db.Column(db.Float)  # Similarity score with main item
    added_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Unique constraint to prevent duplicate associations
    __table_args__ = (db.UniqueConstraint('news_group_id', 'news_item_id', name='unique_group_item'),)
    
    def __repr__(self):
        return f'<NewsGroupItem group:{self.news_group_id} item:{self.news_item_id}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'news_group_id': self.news_group_id,
            'news_item_id': self.news_item_id,
            'similarity_score': self.similarity_score,
            'added_at': self.added_at.isoformat() if self.added_at else None
        }

class AnalysisResult(db.Model):
    """Model for storing analysis results"""
    __tablename__ = 'analysis_results'
    
    id = db.Column(db.Integer, primary_key=True)
    news_item_id = db.Column(db.Integer, db.ForeignKey('news_items.id'), nullable=False)
    analysis_type = db.Column(db.String(50), nullable=False)  # 'sentiment', 'speed_to_publish', 'keywords'
    value = db.Column(db.Text)  # Can store float, text, or JSON depending on analysis type
    analysis_timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<AnalysisResult {self.analysis_type} for item {self.news_item_id}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'news_item_id': self.news_item_id,
            'analysis_type': self.analysis_type,
            'value': self.value,
            'analysis_timestamp': self.analysis_timestamp.isoformat() if self.analysis_timestamp else None
        }
    
    @property
    def numeric_value(self):
        """Try to convert value to float for numeric analysis types"""
        try:
            return float(self.value)
        except (ValueError, TypeError):
            return None