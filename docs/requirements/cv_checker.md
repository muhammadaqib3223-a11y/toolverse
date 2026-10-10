# CV Checker — requirements

Promised on the public tool page. Every item must be built. Text lives in
`app/blueprints/marketing/tools_catalog.py` and `tool_articles.py` — if a
promise changes, update both places.

- PDF upload only, max **4 MB**
- One overall score
- Practical, specific tips
- Structure check (sections clear and in order)
- Wording check (points out weak or unclear wording)
- Looks at skills too
- CV saved privately in the user's account, only the owner can see it
- Works with the CV Generator: build → check → improve in one place
- Fair daily limit on checks
- Make clear that AI can make mistakes
- Shows a progress bar while the AI reads the CV
- Does not rewrite the CV — it only gives a score and tips
- Guest check: the file is only checked, never saved (see `guest_mode.md`)
