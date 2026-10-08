# Phase 2 — Auth + Dashboard (plan)

> Status: **plan only, not approved yet.** No code has been written for Phase 2.
> Open questions are at the end — answer them before starting.

Goal (CLAUDE.md section 5): Supabase Auth with email/password signup, login, logout,
password reset and Google login. A protected dashboard after login, with the 5 tools
in a sidebar (all "Coming soon" for now). Login/signup pages in the same design,
English + Urdu (`/ur`). Keep guest mode in mind: tools must later work without login.

---

## 1. Login kaise kaam karega

- **Login ka record:** login par Supabase do tokens deta hai: access aur refresh. Yeh Flask ki **signed cookie** mein rakhe jayenge (HttpOnly, production mein Secure, SameSite=Lax).
- **Cookie chhoti rakhni hai:** cookie mein sirf tokens aur user ki ID/email hogi, poora session object nahi. Cookie 4KB se zyada ho to browser use kaat deta hai.
- **Token ki jaanch:** har request par access token check hoga. Purana ho gaya ho to refresh token se naya le liya jayega. User ko kuch nahi karna padta.
- **Email links kisi bhi device par chalein:** email confirm aur password reset `token_hash` + `verify_otp` tareeqe se honge. Is liye email ka link kisi dusre device ya browser mein khole tab bhi chalega.
- **Google login:** PKCE tareeqa. User Google par jata hai, `/auth/callback` par wapas aata hai, aur code ke badle session ban jata hai.

## 2. Pages aur URLs

Har page English aur Urdu (`/ur`) dono mein `localized_route` se banega, isi design mein.

| Page | URL |
|---|---|
| Signup (email/password + "Continue with Google") | `/signup` · `/ur/signup` |
| Login | `/login` · `/ur/login` |
| Password bhool gaye | `/forgot-password` |
| Naya password (email link se) | `/reset-password` |
| "Apna email check karein" | `/check-email` |
| Email link ka landing (`token_hash` verify karta hai) | `/auth/confirm` |
| Google se wapsi | `/auth/callback` |
| Logout | `POST /logout` (CSRF ke saath, GET se logout nahi) |
| Dashboard (sirf login ke baad) | `/dashboard` · `/ur/dashboard` |

- **Dashboard:** left mein sidebar, jis mein 5 tools honge, sab par "Coming soon". Upar "Welcome" aur tools ke cards. Mobile par sidebar neeche ka menu ban jayegi (CLAUDE.md section 6).
- **Navbar:** login ke baad "Log in / Sign up" ki jagah "Dashboard" aur "Log out" aayenge.
- **Coming-soon pages:** login aur signup ab asli pages honge, is liye un ke coming-soon pages hat jayenge. Privacy, Terms aur Contact ke coming-soon pages rahenge.
- **Guest mode ki tayyari:** do decorators banenge:
  - `login_required`: sirf dashboard home ke liye.
  - `login_optional`: baad mein tools (`/dashboard/<tool>`) ke liye, taake guest bhi tool chala sake aur login wala user apna data save kar sake.

## 3. Files

```
app/services/supabase_client.py      # per-request Supabase client (keys from .env)
app/blueprints/auth/
  __init__.py, routes.py             # pages
  services.py                        # Supabase calls + error code → friendly message
  forms.py                           # signup/login/forgot/reset forms (validation + CSRF)
  session.py                         # tokens in the cookie, current user (g.user), token refresh
  decorators.py                      # login_required, login_optional
app/blueprints/dashboard/__init__.py, routes.py
app/templates/auth/                  # login, signup, forgot, reset, check_email, _form macros
app/templates/dashboard/             # app_layout (with sidebar), home
app/templates/partials/sidebar.html, flash_messages.html
tests/test_auth.py, test_dashboard.py  # fake auth service instead of Supabase, no network
```

- **Messages:** saare messages English + Urdu mein translate honge.
- **Error codes:** Supabase ke codes achhe messages mein badle jayenge, jaise `invalid_credentials`, `email_not_confirmed`, `weak_password`, `over_email_send_rate_limit`. Poori detail sirf log mein jayegi.
- **Database:** is phase mein koi table nahi banega, Supabase ka `auth.users` kaafi hai. Tables (notes waghera) aur RLS Phase 3 se aayenge.

## 4. Hifazat

- **CSRF:** har form par CSRF token hoga.
- **Redirect:** `next=` mein sirf apni site ke andar ka rasta allowed hoga (open redirect nahi).
- **Email ka pata na chale:** forgot password par hamesha ek hi message aayega, chahe email registered ho ya na ho. Signup mein bhi aisa hi hoga. Is se koi yeh nahi jaan sakega ke kaunsa email registered hai.
- **Password:** kam se kam 8 characters. Yeh check server par bhi hoga aur Supabase mein bhi.
- **Login ki koshishen:** Supabase ki apni rate limits lagengi.
- **Production cookies:** Secure.

## 5. Nayi libraries (approval chahiye — CLAUDE.md rule 13)

| Library | Kyun |
|---|---|
| `supabase` | Supabase ka official Python client. Auth abhi, aur Database/Storage baad ke phases mein |
| `Flask-WTF` | Forms ki validation aur CSRF protection |
| `email-validator` | Email ka format check karta hai (Flask-WTF ka Email check isi se chalta hai) |

Install ke baad check karna hai ke `supabase` ka version token ko apne server par hi (JWKS se) verify kar sakta hai ya nahi, taake har request par Supabase ko network call na karni pade. Agar nahi kar sakta to `PyJWT` ki ijazat maangni hogi.

---

# Aap ko khud kya karna hai (step by step)

## A. Supabase project

1. https://supabase.com par login karein → **New project**.
   - Plan: Free.
   - Region: aap ke qareeb, jaise Mumbai ya Singapore.
   - Database password strong rakhein aur kahin safe likh lein. Yeh `.env` mein **nahi** jayega.
2. **Project Settings → API Keys** se do cheezein copy karein:
   - **Project URL**, jaise `https://abcd1234.supabase.co`
   - **Publishable key** (`sb_publishable_...`). Agar purane keys dikhen to `anon` key bhi chal jayegi.

   **Secret / service_role key copy na karein.** Is phase mein us ki zaroorat nahi, aur woh kabhi browser ya git mein nahi jani chahiye.
3. **Authentication → Sign In / Providers → Email:**
   - Enable rakhein.
   - **Confirm email: ON**.
   - Minimum password length: **8**.
4. **Authentication → URL Configuration:**
   - **Site URL:** aap ka Vercel URL, jaise `https://toolverse-xyz.vercel.app`.
   - **Redirect URLs** mein yeh teeno add karein:
     - `http://127.0.0.1:5000/**`
     - `http://localhost:5000/**`
     - `https://<aap-ka-vercel-domain>/**`
5. **Authentication → Emails → Templates:** do templates ke link badalne hain:
   - **Confirm signup:** `{{ .RedirectTo }}?token_hash={{ .TokenHash }}&type=email`
   - **Reset password:** `{{ .RedirectTo }}?token_hash={{ .TokenHash }}&type=recovery`

   Poora template HTML code ke saath diya jayega, aap ko sirf paste karna hoga.

## B. Google Cloud (Google login)

1. https://console.cloud.google.com → **New Project** → naam "Toolverse".
2. **APIs & Services → OAuth consent screen** (naye interface mein "Google Auth Platform"):
   - **Branding:** app name "Toolverse", support email aur developer contact email.
   - **Audience:** External.
   - **Data access:** sirf `email`, `profile`, `openid` scopes. Yeh "non-sensitive" hain, is liye Google ki verification ki zaroorat nahi.
   - Aakhir mein app ko **Publish / In production** kar dein. "Testing" mein sirf 100 test users login kar sakte hain.
3. **Clients → Create client:**
   - Type: **Web application**, naam "Toolverse web".
   - **Authorized redirect URIs:** `https://<project-ref>.supabase.co/auth/v1/callback`. Yeh URL Supabase mein **Authentication → Providers → Google** par likha hota hai.
4. Is ke baad **Client ID** aur **Client Secret** milenge.
5. Supabase mein **Authentication → Sign In / Providers → Google** kholein: Enable karein, Client ID aur Secret paste karein, aur Save dabayein.

Google ka Client ID aur Secret **sirf Supabase** mein jayenge. Hamari `.env` ya Vercel mein nahi.

## C. Keys kahan daalni hain

| Key | `.env` (local) | Vercel → Settings → Environment Variables |
|---|---|---|
| `SUPABASE_URL` | ✅ | ✅ |
| `SUPABASE_PUBLISHABLE_KEY` | ✅ | ✅ |
| `APP_ENV` | `development` | `production` (pehle se) |
| `SECRET_KEY` | ✅ (pehle se) | ✅ (pehle se) |

`.env.example` code ke saath update hogi, lekin us mein asal values nahi hongi.

---

## Open questions (shuru karne se pehle jawab chahiye)

1. **Emails ke liye SMTP:** Supabase ka free built-in email ab sirf project ke team members ke emails par bhejta hai, aur woh bhi bohot kam (ghante mein 2–3). Asal users ko confirm aur reset ke emails ke liye free SMTP chahiye. Options:
   - **(a)** Abhi development mein sirf apne email se test karein, SMTP baad mein lagayein.
   - **(b)** Brevo ka free plan (300 emails/din). Domain ki zaroorat nahi, sirf sender email verify karna hota hai, lekin emails kabhi kabhi spam mein ja sakte hain.
   - **(c)** Resend ka free plan. Behtar hai lekin apna domain chahiye, aur domain ke paise lagte hain.

   Mashwara: abhi **(a)**, aur live karne se pehle **(b)**.
2. **Vercel URL:** kya project Vercel par deploy ho chuka hai? Us ka URL kya hai? Yeh Supabase ki Site URL aur Redirect URLs ke liye chahiye.
3. **Libraries:** `supabase`, `Flask-WTF` aur `email-validator` ki ijazat hai?
