#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WSGI Entry Point for News Analyzer Dashboard

This module provides the WSGI application entry point for production deployment.
It's used by WSGI servers like Gunicorn, uWSGI, or mod_wsgi.
"""

import os
import sys
from dotenv import load_dotenv

# Add the project root to Python path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

# Load environment variables
load_dotenv()

# Import the Flask application
from app import create_app

# Create the application instance
application = create_app()

# For compatibility with some WSGI servers
app = application

if __name__ == "__main__":
    # This allows running the WSGI app directly for testing
    application.run()