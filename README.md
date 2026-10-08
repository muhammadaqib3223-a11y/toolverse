# Toolverse

A free web app: one account, five tools (CV Checker, CV Generator, Captions, Notes, Expenses).
Built with Flask, Jinja2, Tailwind CSS and Flask-Babel (English + Urdu). Rules for the project are in [CLAUDE.md](CLAUDE.md).

## Run it on your computer (Windows, PowerShell)

First time only:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
Copy-Item .env.example .env        # then put a long random SECRET_KEY in .env
.\.venv\Scripts\pybabel.exe compile -d app/translations
```

Every time:

```powershell
.\.venv\Scripts\python.exe run.py
```

Open http://127.0.0.1:5000 in your browser. Press `Ctrl+C` in the terminal to stop.

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest
```

## Changing styles (Tailwind)

The compiled `app/static/css/app.css` is committed, so you only need this after changing classes in templates or `input.css`.
Download the Tailwind CLI once (v3.4.17) to `.tools\tailwindcss.exe`:

```powershell
New-Item -ItemType Directory -Force .tools
Invoke-WebRequest https://github.com/tailwindlabs/tailwindcss/releases/download/v3.4.17/tailwindcss-windows-x64.exe -OutFile .tools\tailwindcss.exe
```

Then build (add `--watch` to rebuild automatically while you work):

```powershell
.\.tools\tailwindcss.exe -i app/static/css/input.css -o app/static/css/app.css --minify
```

## Translations (English / Urdu)

Every visible text is written in English inside `_('...')` (templates) or `_l('...')` (Python).
After adding or changing texts:

```powershell
.\.venv\Scripts\pybabel.exe extract -F babel.cfg -k _l -o messages.pot .
.\.venv\Scripts\pybabel.exe update -i messages.pot -d app/translations
# fill in the Urdu text in app/translations/ur/LC_MESSAGES/messages.po
.\.venv\Scripts\pybabel.exe compile -d app/translations
```

## Deploy on Render (free)

1. Push this repo to GitHub.
2. On Render: **New → Blueprint**, pick this repo. Render reads `render.yaml`.
3. Render installs the packages, compiles the translations and starts `gunicorn run:app`.
   `SECRET_KEY` is generated automatically.
