# AI Caption Generator — requirements

Promised on the public tool page. Every item must be built. Text lives in
`app/blueprints/marketing/tools_catalog.py` and `tool_articles.py` — if a
promise changes, update both places.

- Topic input + platform choice: Instagram or LinkedIn
- Captions written for the chosen platform
- More than one caption to choose from
- Works for any topic
- "Copy in one tap" button on every caption
- Captions are editable before posting
- Fair daily limit
- Toolverse **does not post** for the user and does not connect to social
  media accounts
- Guest: 3 free tries, counted by IP (see `guest_mode.md`)
