# CV Generator — requirements

Promised on the public tool page. Every item must be built. Text lives in
`app/blueprints/marketing/tools_catalog.py` and `tool_articles.py` — if a
promise changes, update both places.

- Simple step-by-step form: name and contact details, short summary, work
  experience, **education**, skills; no design skills needed
- Choice of clean templates; the user can switch template and download again
- Ready-to-send PDF download
- Optional AI help to write the summary and experience; the user can edit
  everything (AI help is optional — templates and PDF work without it)
- CVs saved in the account and editable anytime; a user can keep **several
  CVs** (different versions)
- A way to send a new CV to the CV Checker
- Guest: PDF download works without login, saving needs login (see
  `guest_mode.md`)
