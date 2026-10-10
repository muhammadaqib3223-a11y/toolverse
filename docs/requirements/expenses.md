# Expense Tracker — requirements

Promised on the public tool page. Every item must be built. Text lives in
`app/blueprints/marketing/tools_catalog.py` and `tool_articles.py` — if a
promise changes, update both places.

- Quick entry: amount + what it was for
- Monthly total
- Daily list (expenses grouped by day)
- **Edit and delete** an expense
- Monthly total = sum of all expenses entered for that month
- Works on every device; only the owner can see their expenses
- No bank connection — the user adds expenses themselves
- Currency: default **PKR (Rs)**; the user can change the currency in their
  settings
- Guest: expenses saved in the browser, offered a one-tap move into the
  account after login (see `guest_mode.md`)

**Status:** Next up (Phase 4). Follow the Supabase + guest-mode pattern
described in CLAUDE.md "Progress & decisions" (same shape as Notes).
