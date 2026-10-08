"""Entry point: `python run.py` locally, `gunicorn run:app` on Render."""
from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run()
