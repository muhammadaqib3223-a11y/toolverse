"""Entry point for Vercel, which looks for a Flask object named `app` in wsgi.py."""
from app import create_app

app = create_app()
