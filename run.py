#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
News Analyzer Dashboard - Main Application Runner

This script runs the Flask application for the News Analyzer Dashboard.
It handles environment setup, configuration loading, and application initialization.
"""

import os
import sys
from dotenv import load_dotenv

# Add the project root to Python path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

# Load environment variables
load_dotenv()

from app import create_app, db
from app.models import NewsAgency, NewsItem, NewsGroup, AnalysisResult
from flask.cli import with_appcontext
import click
import json

# Create Flask application
app = create_app()

@app.cli.command()
@with_appcontext
def init_db():
    """Initialize the database with tables and sample data."""
    click.echo('Creating database tables...')
    db.create_all()
    
    # Add sample news agencies if they don't exist
    agencies_data = [
        {
            'name': 'Fars News Agency',
            'base_url': 'https://www.farsnews.ir',
            'config_file': 'farsnews.json',
            'is_active': True
        },
        {
            'name': 'Mehr News Agency', 
            'base_url': 'https://www.mehrnews.com',
            'config_file': 'mehrnews.json',
            'is_active': True
        }
    ]
    
    for agency_data in agencies_data:
        existing_agency = NewsAgency.query.filter_by(name=agency_data['name']).first()
        if not existing_agency:
            agency = NewsAgency(**agency_data)
            db.session.add(agency)
            click.echo(f'Added agency: {agency_data["name"]}')
    
    try:
        db.session.commit()
        click.echo('Database initialized successfully!')
    except Exception as e:
        db.session.rollback()
        click.echo(f'Error initializing database: {e}', err=True)

@app.cli.command()
@with_appcontext
def reset_db():
    """Reset the database (drop and recreate all tables)."""
    if click.confirm('This will delete all data. Are you sure?'):
        click.echo('Dropping all tables...')
        db.drop_all()
        click.echo('Recreating tables...')
        db.create_all()
        click.echo('Database reset complete!')

@app.cli.command()
@with_appcontext
def show_stats():
    """Show database statistics."""
    stats = {
        'News Agencies': NewsAgency.query.count(),
        'News Items': NewsItem.query.count(),
        'News Groups': NewsGroup.query.count(),
        'Analysis Results': AnalysisResult.query.count()
    }
    
    click.echo('\nDatabase Statistics:')
    click.echo('=' * 30)
    for key, value in stats.items():
        click.echo(f'{key}: {value:,}')
    click.echo()

@app.cli.command()
@click.argument('agency_name')
@with_appcontext
def test_scraper(agency_name):
    """Test scraper configuration for a specific agency."""
    agency = NewsAgency.query.filter_by(name=agency_name).first()
    if not agency:
        click.echo(f'Agency "{agency_name}" not found.', err=True)
        return
    
    click.echo(f'Testing scraper for: {agency.name}')
    
    # Import and test the scraper
    try:
        from app.tasks.crawler_tasks import test_agency_config
        result = test_agency_config.delay(agency.id)
        
        click.echo('Test task started. Check Celery logs for results.')
        click.echo(f'Task ID: {result.id}')
    except Exception as e:
        click.echo(f'Error starting test: {e}', err=True)

@app.cli.command()
@with_appcontext
def list_agencies():
    """List all news agencies."""
    agencies = NewsAgency.query.all()
    
    if not agencies:
        click.echo('No agencies found.')
        return
    
    click.echo('\nNews Agencies:')
    click.echo('=' * 50)
    for agency in agencies:
        status = '✓ Active' if agency.is_active else '✗ Inactive'
        click.echo(f'{agency.name} - {status}')
        click.echo(f'  URL: {agency.base_url}')
        click.echo(f'  Config: {agency.config_file}')
        click.echo()

@app.cli.command()
@click.argument('config_file')
@with_appcontext
def validate_config(config_file):
    """Validate a scraper configuration file."""
    config_path = os.path.join(project_root, 'scrapers_config', config_file)
    
    if not os.path.exists(config_path):
        click.echo(f'Config file not found: {config_path}', err=True)
        return
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        # Basic validation
        required_fields = ['name', 'base_url', 'selectors']
        missing_fields = [field for field in required_fields if field not in config]
        
        if missing_fields:
            click.echo(f'Missing required fields: {missing_fields}', err=True)
            return
        
        click.echo(f'✓ Configuration file "{config_file}" is valid')
        click.echo(f'  Agency: {config["name"]}')
        click.echo(f'  Base URL: {config["base_url"]}')
        
    except json.JSONDecodeError as e:
        click.echo(f'Invalid JSON in config file: {e}', err=True)
    except Exception as e:
        click.echo(f'Error validating config: {e}', err=True)

@app.shell_context_processor
def make_shell_context():
    """Make database models available in Flask shell."""
    return {
        'db': db,
        'NewsAgency': NewsAgency,
        'NewsItem': NewsItem,
        'NewsGroup': NewsGroup,
        'AnalysisResult': AnalysisResult
    }

@app.route('/health')
def health_check():
    """Health check endpoint."""
    try:
        # Test database connection
        db.session.execute('SELECT 1')
        return {'status': 'healthy', 'database': 'connected'}, 200
    except Exception as e:
        return {'status': 'unhealthy', 'error': str(e)}, 500

if __name__ == '__main__':
    # Get configuration from environment
    host = os.getenv('FLASK_HOST', '127.0.0.1')
    port = int(os.getenv('FLASK_PORT', 5000))
    debug = os.getenv('FLASK_ENV') == 'development'
    
    print(f"""
    ╔══════════════════════════════════════════════════════════════╗
    ║                News Analyzer Dashboard                       ║
    ║                                                              ║
    ║  🌐 Server: http://{host}:{port:<45} ║
    ║  🔧 Environment: {os.getenv('FLASK_ENV', 'production'):<42} ║
    ║  📊 Debug Mode: {str(debug):<44} ║
    ║                                                              ║
    ║  Available Commands:                                         ║
    ║    flask init-db     - Initialize database                  ║
    ║    flask reset-db    - Reset database                       ║
    ║    flask show-stats  - Show statistics                      ║
    ║    flask list-agencies - List news agencies                 ║
    ║                                                              ║
    ║  Press Ctrl+C to stop the server                            ║
    ╚══════════════════════════════════════════════════════════════╝
    """)
    
    try:
        app.run(
            host=host,
            port=port,
            debug=debug,
            threaded=True
        )
    except KeyboardInterrupt:
        print("\n\n👋 Server stopped by user")
    except Exception as e:
        print(f"\n❌ Error starting server: {e}")
        sys.exit(1)