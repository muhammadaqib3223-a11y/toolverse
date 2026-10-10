# Toolverse — Project Rules & Requirements

> Read this file fully before doing ANY work in this project.
> These rules apply to every task, big or small.

## 1. About the project

Toolverse is a free SaaS web app: one account, five tools.

- **Marketing website** (public): hero, tools, how it works, "100% free", FAQ, footer
- **App / dashboard** (login required): sidebar with the five tools
- **Tools:**
  1. AI CV Checker (upload PDF → score + suggestions)
  2. CV Generator (fill a form → choose a template → download PDF; optional AI help to write summary/experience; CVs saved and editable)
  3. AI Caption Generator (topic → Instagram/LinkedIn captions)
  4. Notes (create, edit, delete, search)
  5. Expense Tracker (add expenses, monthly total)
- CV Generator and CV Checker form one "CV section": build a CV → check it → improve it.
- Every user's data is private to them and saved in their account.
- Budget: **$0**. Use only free tiers. No paid services.

The project owner is a beginner learning to code. Explain what you did in simple words after each task.

## 2. Tech stack (fixed — do not change without asking)

| Part | Choice |
|---|---|
| Language | Python 3 |
| Backend | Flask (app factory + Blueprints) |
| Frontend | Jinja2 templates + Tailwind CSS + small vanilla JS |
| Animations | CSS animations + a light library (e.g. AOS) for scroll reveal |
| Auth | Supabase Auth — email/password AND Google login |
| Database | Supabase (Postgres) with Row Level Security |
| File storage | Supabase Storage (for CV PDFs) |
| PDF generation | A pure-Python library (e.g. xhtml2pdf) so it runs on Vercel without system packages |
| AI | Google Gemini API (free tier) |
| Languages | English + Urdu (Flask-Babel), Urdu must be RTL. Language comes from the URL: English has no prefix (`/tools`), Urdu uses `/ur` (`/ur/tools`). Register page routes with `localized_route` from `app/i18n.py`; every page gets hreflang tags (en, ur, x-default) |
| Hosting | Vercel (free Hobby plan) |

**Emails (signup confirm, password reset):** abhi development mein Supabase ka built-in email use ho raha hai, jo sirf project team ke emails par aur bohot kam (ghante mein 2–3) bhejta hai. Is liye abhi sirf apne email se test karna hai. **Live karne se pehle Brevo (free plan, 300 emails/din) ka SMTP Supabase mein lagana zaroori hai**, warna asal users ko confirm/reset emails nahi milenge.

**Vercel note:** Vercel serverless hai: server par files save nahi hoti, sab files Supabase Storage mein jayengi. Request body ki limit takreeban 4.5MB hai, is liye CV upload ki limit 4MB rakhni hai.

## 3. Golden rules for the AI assistant

1. **No shortcuts.** Write code as if the app will grow to thousands of users.
2. **Plan first.** Before coding, list the files/folders you will create or change and wait for "OK" on anything big.
3. **Folders before code.** If something needs a new folder or module, create it properly. Never dump code into an existing file just because it is faster.
4. **One responsibility per file.** Routes, business logic, AI calls and database calls live in separate files.
5. **Never hardcode secrets.** All keys go in `.env`. Keep `.env.example` updated. Never commit `.env`.
6. **Never hardcode user-facing text.** Every visible string goes through translations (English + Urdu).
7. **AI provider must be swappable.** All AI calls go through `app/services/ai/`. Switching Gemini → OpenAI later must only need a new provider file + a config change.
8. **Mobile-first and responsive.** Every page must work on phone, tablet and laptop.
9. **Respect `prefers-reduced-motion`** for all animations.
10. **Handle errors.** Show friendly messages to users, log details for the developer. No blank crashes.
11. **Small steps.** Finish and test one feature before starting the next.
12. **Do not delete or rewrite working code** without asking first.
13. **Do not add new libraries** without saying why and asking first.
14. **Follow the design** (section 6) exactly. Do not invent a new style.

## 4. Folder structure

```
toolverse/
├── app/
│   ├── __init__.py            # create_app() factory
│   ├── config.py              # settings loaded from .env
│   ├── extensions.py          # Babel, etc.
│   ├── blueprints/
│   │   ├── marketing/         # public landing page
│   │   ├── auth/              # login, signup, logout, Google callback
│   │   ├── dashboard/         # dashboard home
│   │   └── tools/
│   │       ├── cv_checker/
│   │       ├── cv_generator/
│   │       ├── captions/
│   │       ├── notes/
│   │       └── expenses/
│   │   (each blueprint: __init__.py, routes.py, services.py, forms.py if needed)
│   ├── services/
│   │   ├── ai/
│   │   │   ├── base.py        # AIProvider interface
│   │   │   ├── gemini.py      # Gemini implementation
│   │   │   └── __init__.py    # get_ai_provider() from config
│   │   ├── supabase_client.py
│   │   ├── pdf_reader.py      # read uploaded CVs (checker)
│   │   └── pdf_builder.py     # build CV PDFs (generator)
│   ├── templates/
│   │   ├── base.html
│   │   ├── partials/          # navbar, footer, sidebar, flash messages
│   │   ├── marketing/
│   │   ├── auth/
│   │   ├── dashboard/
│   │   ├── tools/
│   │   └── cv_templates/      # CV designs used for PDF output
│   └── translations/          # en, ur
├── public/
│   └── static/                # served by Vercel's CDN (Flask serves it locally)
│       ├── css/
│       ├── js/
│       └── img/
├── tests/
├── .env.example
├── .gitignore
├── requirements.txt
├── run.py                     # local: python run.py
├── wsgi.py                    # Vercel entrypoint
└── README.md
```

## 5. Build phases (one at a time)

1. Project setup + folder structure + marketing landing page (EN/UR toggle) → deploy on Vercel
2. Auth: signup, login, logout, Google login, protected dashboard
3. Notes tool
4. Expense Tracker tool
5. AI Caption Generator (first Gemini integration)
6. CV Generator (form + templates + PDF download, then optional AI help)
7. AI CV Checker (PDF upload + Gemini), linked with the CV Generator

AI tools must have a **daily usage limit per user** to stay inside the free tier.

### Guest mode

Guest mode: user bina login ke tools try kar sake. CV Checker mein 1 free check, Captions mein 3 free tries (IP ke hisaab se limit, taake Gemini ki free limit khatam na ho). CV Generator mein PDF download bina login, save ke liye login. Notes aur Expenses guest ke liye browser mein save hon, aur login karne par account mein chale jayein. Login Google se ek click mein bhi ho.

Guest mode ke liye zaroori baatein:
- **IP ki ginti Supabase mein:** Vercel serverless hai, server ki memory har request ke baad khatam ho jati hai. Is liye guest tries ki ginti (IP ke hisaab se) Supabase ki table mein rakhni hai.
- **Guest ki CV save na ho:** guest jab bina login ke CV check kare, us ki file kahin save nahi hogi — sirf check ho kar khatam. (Section 7 Privacy ke mutabiq.)
- **Landing FAQ badalna:** guest mode banne ke baad landing page ka "Why do I need to log in?" wala jawab update karna hai, kyunki tab login ke baghair bhi tools try ho sakenge.
- **"Try it free" seedha tool khole:** guest mode banne ke baad tool pages ka "Try it free" button coming-soon page ki jagah seedha tool kholega.

### Tool requirements (promised on the public tool pages — every item must be built)

The text for these lives in `app/blueprints/marketing/tools_catalog.py` and `tool_articles.py`. If a promise changes, update both places.

**CV Checker**
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
- Guest check: the file is only checked, never saved

**CV Generator**
- Simple step-by-step form: name and contact details, short summary, work experience, **education**, skills; no design skills needed
- Choice of clean templates; the user can switch template and download again
- Ready-to-send PDF download
- Optional AI help to write the summary and experience; the user can edit everything (AI help is optional — templates and PDF work without it)
- CVs saved in the account and editable anytime; a user can keep **several CVs** (different versions)
- A way to send a new CV to the CV Checker

**Captions**
- Topic input + platform choice: Instagram or LinkedIn
- Captions written for the chosen platform
- More than one caption to choose from
- Works for any topic
- "Copy in one tap" button on every caption
- Captions are editable before posting
- Fair daily limit
- Toolverse **does not post** for the user and does not connect to social media accounts

**Notes**
- Create a note with a **title** and text
- Edit anytime, delete
- Search by any word
- Works on every device (browser on phone, tablet, laptop); no app to install
- Only the owner can see their notes
- A deleted note **cannot be recovered** (no trash bin for now — if one is added later, update the FAQ)

**Expenses**
- Quick entry: amount + what it was for
- Monthly total
- Daily list (expenses grouped by day)
- **Edit and delete** an expense
- Monthly total = sum of all expenses entered for that month
- Works on every device; only the owner can see their expenses
- No bank connection — the user adds expenses themselves
- Currency: default **PKR (Rs)**; the user can change the currency in their settings

## 6. Design (applies to the WHOLE software: homepage, auth pages, dashboard, every tool)

Style reference: the approved "Version 3 — Framer style" landing page (premium, minimal, like framer.com / vercel.com).

**Colors**
- Background `#000000`, raised surfaces `#0B0B0D`, inner cards `#111113`
- Borders `#1E1E22` (subtle) and `#222226`
- Text `#FFFFFF`, muted text `#8F8F98`, faint labels `#6B6B73`
- Accent (purple) `#9B8CFF` — used sparingly: highlights, active states, progress bars, one word in a heading
- Primary button: white background, black text, pill shape. Secondary button: `#141416` with border, pill shape

**Fonts (only these two, never add more)**
- **Geist** — all headings and body text
- **Geist Mono** — small labels, step numbers, tags (e.g. "01 — CV CHECKER")
- Headings: bold (700), very tight letter-spacing (about -0.05em), line-height ~1
- For Urdu text use a proper Urdu font (e.g. Noto Nastaliq Urdu) with RTL layout

**Shapes**
- Cards: 14–22px radius, 1px subtle border, no heavy shadows
- Buttons and badges: fully rounded (pill)
- Icons: simple line SVGs (stroke ~1.8), never emoji

**Animations (smooth, never flashy)**
- Hero heading: words blur-in one by one on load
- Product preview: rises up on load
- Sections: fade up when scrolled into view
- Animated "how it works" demo (upload → AI checks → results), looping
- Cards and buttons: small lift/scale on hover
- Dashboard: page content fades in, loading states use spinner + progress bar
- Always respect `prefers-reduced-motion`

**Layout**
- Max content width ~1240px, generous spacing between sections
- Alternating left/right feature sections for tools
- Mobile: everything stacks in one column, sidebar becomes a top/bottom menu

## 7. Privacy

- CVs contain personal data: store them privately, only the owner can access them.
- Use Supabase Row Level Security on every table.
