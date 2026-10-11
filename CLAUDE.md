# Toolverse — Project Rules

> Read this file fully before doing ANY work. These rules apply to every task.

## 1. About the project

Toolverse is a free SaaS web app: one account, five tools.

- **Marketing website** (public): hero, tools, how it works, FAQ, footer
- **Dashboard** (login required): sidebar with the five tools
  1. AI CV Checker · 2. CV Generator · 3. AI Caption Generator · 4. Notes · 5. Expense Tracker
- CV Generator + CV Checker = one "CV section": build → check → improve.
- Every user's data is private. Budget: **$0** — free tiers only.

The project owner is a beginner learning to code. Explain what you did in simple words after each task.

**Tool requirements** live in `docs/requirements/`. Before building any tool, read **only that tool's file**. Guest-mode rules are in `docs/requirements/guest_mode.md`.

## 2. Tech stack (fixed — do not change without asking)

| Part | Choice |
|---|---|
| Language | Python 3 |
| Backend | Flask (app factory + Blueprints) |
| Frontend | Jinja2 + Tailwind CSS + vanilla JS |
| Animations | CSS + AOS for scroll reveal |
| Auth | Supabase Auth — email/password AND Google login |
| Database | Supabase (Postgres) + Row Level Security |
| File storage | Supabase Storage |
| PDF generation | fpdf2 + uharfbuzz (pure Python, Urdu shaping) — no system packages |
| AI | Google Gemini API (free tier) |
| Languages | English + Urdu (Flask-Babel), Urdu RTL. English: `/tools`, Urdu: `/ur/tools`. Use `localized_route` from `app/i18n.py`. Every page gets hreflang tags (en, ur, x-default). |
| Hosting | Vercel (free Hobby plan) |

**Vercel note:** serverless — no file saves on the server; all files go to Supabase Storage. Request body limit ≈4.5 MB; CV upload limit = **4 MB**.

**Emails:** dev = Supabase built-in (≤3/hour, own email only). Before going live: add Brevo SMTP (free, 300/day) in Supabase dashboard.

## 3. Golden rules

1. **No shortcuts.** Write code that scales to thousands of users.
2. **Plan first.** Before coding, list files/folders to create or change; wait for "OK" on anything big.
3. **One responsibility per file.** Routes / logic / AI calls / DB calls in separate files.
4. **Never hardcode secrets.** All keys in `.env`. Keep `.env.example` updated. Never commit `.env`.
5. **Never hardcode user-facing text.** Every string goes through translations (EN + UR).
6. **AI provider must be swappable.** All AI calls go through `app/services/ai/`. Switching Gemini → another provider must only need a new provider file + config change.
7. **Mobile-first and responsive.** Every page works on phone, tablet and laptop.
8. **Respect `prefers-reduced-motion`** for all animations.
9. **Handle errors.** Friendly messages for users, detailed logs for the developer. No blank crashes.
10. **Small steps.** Finish and test one feature before starting the next.
11. **Do not delete or rewrite working code** without asking first.
12. **Do not add new libraries** without saying why and asking first.
13. **Follow the design** (section 5) exactly. Do not invent a new style.
14. **Tests:** during work, run only the tests related to the file you changed. Run the full suite only before pushing.
15. **Browser screenshots:** only take them when the user explicitly asks.
16. **Short answers:** give short, direct replies. No padding.

## 4. Folder structure

```
toolverse/
├── app/
│   ├── __init__.py            # create_app() factory
│   ├── config.py
│   ├── extensions.py          # Babel, etc.
│   ├── blueprints/
│   │   ├── marketing/
│   │   ├── auth/
│   │   ├── dashboard/
│   │   └── tools/
│   │       ├── cv_checker/    # __init__.py, routes.py, services.py, repository.py
│   │       ├── cv_generator/
│   │       ├── captions/
│   │       ├── notes/
│   │       └── expenses/
│   ├── services/
│   │   ├── ai/
│   │   │   ├── base.py        # AIProvider interface
│   │   │   ├── gemini.py
│   │   │   └── __init__.py    # get_ai_provider()
│   │   ├── supabase_client.py
│   │   ├── pdf_reader.py
│   │   └── pdf_builder.py     # fpdf2 setup: fonts, Urdu shaping
│   ├── assets/fonts/          # PDF fonts (Geist, Noto Nastaliq Urdu); shipped with the function
│   ├── templates/
│   │   ├── base.html
│   │   ├── partials/
│   │   ├── marketing/ auth/ dashboard/ tools/
│   └── translations/          # en, ur
├── public/static/             # css/ js/ img/
├── docs/
│   ├── requirements/          # one file per tool + guest_mode.md + account.md
│   ├── phase2-plan.md
│   └── supabase-email-templates.md
├── tests/
├── supabase/migrations/
├── .env.example
├── requirements.txt
├── run.py                     # local dev
└── wsgi.py                    # Vercel entrypoint
```

## 5. Design (applies everywhere — homepage, auth, dashboard, every tool)

Style: approved "Version 3 — Framer style" (premium, minimal, like framer.com / vercel.com).

**Colors:** bg `#000000` · surfaces `#0B0B0D` · cards `#111113` · borders `#1E1E22` / `#222226` · text `#FFFFFF` · muted `#8F8F98` · labels `#6B6B73` · accent purple `#9B8CFF` (use sparingly)
Primary button: white bg, black text, pill. Secondary: `#141416` + border, pill.

**Fonts (only these two):** Geist (headings + body, bold 700, tight letter-spacing ≈-0.05em) · Geist Mono (labels, step numbers, tags). Urdu: Noto Nastaliq Urdu + RTL.

**Shapes:** cards 14–22px radius, 1px border, no heavy shadows. Buttons + badges: pill. Icons: line SVGs stroke ~1.8, never emoji.

**Animations (smooth, never flashy):** hero words blur-in · sections fade-up on scroll · cards/buttons small lift on hover · dashboard page fade-in + spinner/progress · always `prefers-reduced-motion`.

**Layout:** max width ~1240px · alternating left/right feature sections · mobile: single column, sidebar → top/bottom menu.

## 6. Privacy

- CVs are personal data: store privately, only owner can access.
- Row Level Security on **every** table.

## 7. Progress & decisions

**Done (tested, pushed to `main`):**
- Phase 1: landing page, `/tools` catalog, tool pages with guides/FAQs, Urdu `/ur`, hreflang, sitemap/robots, Vercel hosting.
- Phase 2: Supabase Auth (signup, login, logout, forgot/reset, Google), protected `/dashboard` with sidebar. Docs: `docs/phase2-plan.md`, `docs/supabase-email-templates.md`.
- Privacy Policy (`/privacy`) + Terms (`/terms`), EN + UR. Text: `app/blueprints/marketing/legal.py`.
- Phase 3: Notes tool at `/dashboard/notes` (+ `/ur`). Supabase + RLS for logged-in users; guest notes in `localStorage` with one-tap import after login. SQL: `supabase/migrations/20261010_notes.sql`.

- Phase 4: Expense Tracker at `/dashboard/expenses` (+ currency). SQL: `supabase/migrations/20261011_expenses.sql`.
- Phase 5: Caption Generator at `/dashboard/captions`. First AI tool (Gemini `gemini-3.5-flash-lite` via `google-genai`). Daily limits: guest 3 (by IP), user 20, whole site 500 — all in config. History for logged-in users. SQL: `20261012_captions.sql` + `20261013_captions_limits.sql`.

- Phase 6A: CV Generator at `/dashboard/cv-generator`: step form, Classic + Modern templates, PDF download for guests and users (`POST /api/cv-generator/pdf`, stores nothing). Form kept in `localStorage` (`toolverse_guest_cvs`, `public/static/js/cv_generator/stores.js`). PDF layouts: `cv_generator/pdf_templates/`.

**Next:** Phase 6B: saved CVs (several per user) + AI help for summary/experience + "check this CV" link. Then CV Checker. See `docs/requirements/`.

**How PDFs work (follow for CV Checker too):**
- `app/services/pdf_builder.py`: `new_document()` + `render()`. Text is real text (ATS-readable); tests read it back with `pypdf` (dev only).
- Urdu text must use the Nastaliq font as the MAIN font (`CvLayout.font(text=...)`), not Geist's fallback, or readers get the words in reverse order. No letter-spacing (readers split the letters).
- Shaped Urdu adds zero-width spaces (U+200B) in extracted text: the CV Checker's `pdf_reader.py` must remove them.
- Fonts are static Regular/Bold TTFs (variable fonts took ~10 s per PDF).

**How AI works (follow for CV Checker/Generator):**
- Tools call `get_ai_provider().generate_json(system=, prompt=, schema=)` only. Errors: `AIUnavailable` / `AIQuotaExceeded` / `AIBlocked` (`.code`). New vendor = new file in `app/services/ai/` + `PROVIDERS` entry + `AI_PROVIDER` in `.env`.
- Prompts live in the tool's `prompts.py`. Tests use `ai_provider` fixture (`FakeAIProvider`), never the real API.
- Daily limits: reserve a try in Postgres BEFORE the AI call (`consume_caption_try`), refund by secret try id if AI fails. Guest IP = `app/services/client_ip.py` (`ip_fingerprint()`, HMAC, IPv6 /64); on Vercel the IP comes from the last X-Forwarded-For entry via ProxyFix.

**How auth works (follow in every phase):**
- All Supabase calls → `app/blueprints/auth/services.py` (`get_auth_service()`). Routes get `AuthError` with a code; text in `auth/messages.py`.
- New Supabase client per request (`app/services/supabase_client.py`). Publishable key only.
- Cookie: access token + refresh token + expiry. Verified with PyJWT + Supabase public keys; auto-refreshed. Current user = `g.user` (`None` for guests).
- `login_required` for logged-in-only pages; `login_optional` for tools (guest mode).
- Flask-WTF CSRF on every form. Logout = POST only. `?next=` → `safe_next_url`.
- Email links use `token_hash` behind `/auth/confirm` (scanner-safe, any-device).
- Tests never call Supabase: use `auth_service` / `log_in` fixtures + `tests/fakes.py`.

**Tool + guest-mode pattern (follow for Expenses, Captions, CVs):**
- Layers: `routes.py` → `services.py` (no Supabase) → `repository.py` (only file touching Supabase). Repo registered in `app.extensions["<tool>_repository"]`; tests swap a fake (`tests/fakes.py`).
- User's own Supabase client via `create_user_client(access_token)`; RLS enforces ownership. Access token from `current_auth_session()`.
- Page route: `login_optional`. JSON API routes: `login_optional` but check `g.user`; return JSON `login_required` for guests (not a redirect).
- Guest data: `localStorage` store with same methods (`list`/`create`/`update`/`remove`) as the server store — JS doesn't know which one it's using (reference: `public/static/js/notes/stores.js`). After login: `partials/guest_import_prompt.html` + `guest_import.js` → `/api/<tool>/import`; `client_id` + DB unique constraint = safe to retry.
- Every blueprint: `localized_route` on page AND API routes. Template globals → `_register_template_globals()` in `app/__init__.py` (not `@bp.context_processor`).

**Owner still to do (outside the code):**
- Supabase + Google Cloud setup (`docs/phase2-plan.md`, sections A–C); add `SUPABASE_URL` + `SUPABASE_PUBLISHABLE_KEY` to `.env` and Vercel.
- Send real Vercel URL for Supabase Site URL + Redirect URLs.
- Test real signup/login/reset/Google with own email.
- Run `supabase/migrations/20261010_notes.sql` in Supabase SQL Editor, then test Notes.
- Run `20261013_captions_limits.sql` in Supabase SQL Editor; add `GEMINI_API_KEY` to `.env` + Vercel; then test Captions.
- Run once (fix): `alter table public.expenses alter column user_id set default auth.uid();`
- Before going live: Brevo SMTP.
- Pre-existing gap: some Terms/Privacy lines, a few FAQ/landing strings still lack Urdu translation in `app/translations/ur/LC_MESSAGES/messages.po`.
