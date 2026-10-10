# Notes — requirements

Promised on the public tool page. Every item must be built. Text lives in
`app/blueprints/marketing/tools_catalog.py` and `tool_articles.py` — if a
promise changes, update both places.

- Create a note with a **title** and text
- Edit anytime, delete
- Search by any word
- Works on every device (browser on phone, tablet, laptop); no app to install
- Only the owner can see their notes
- A deleted note **cannot be recovered** (no trash bin for now — if one is
  added later, update the FAQ)
- Guest: notes saved in the browser, offered a one-tap move into the account
  after login (see `guest_mode.md`)

**Status:** Live, built in Phase 3. See CLAUDE.md "Progress & decisions" for
the current state and the Supabase + guest-mode pattern it follows.
