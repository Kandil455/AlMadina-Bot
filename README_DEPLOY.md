Project: Al Madina Bot

Quick deploy/migration guide

- Prerequisites: Python 3.11+, pip, a Linux host (recommended) with basic build tools.
- Copy the repo to your new server (scp/git clone).
- Create a `.env` based on `.env.example` with your real tokens.
- Install: `python -m venv .venv && source .venv/bin/activate && pip install -U pip && pip install -r requirements.txt`
- Run locally: `python bot.py`
- Heroku/Render/Railway: Use the provided `Procfile` (`worker: python bot.py`).

Notes

- WeasyPrint needs system libs on Linux: cairo, pango, gdk-pixbuf, libffi, fonts. On Debian/Ubuntu run:
  `sudo apt-get update && sudo apt-get install -y libcairo2 libpango-1.0-0 libgdk-pixbuf-2.0-0 libffi8 libxml2 libxslt1.1 fonts-dejavu-core`.
- For large PDFs: the bot clamps very long text to keep response time stable. You can raise `MAX_TEXT_CHARS` in `config.py` if your host is powerful.
- Keep your `.env` secrets private; do not commit them.

