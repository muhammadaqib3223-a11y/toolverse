# Supabase email templates

Supabase → **Authentication → Emails → Templates**. Har template ka **Subject** aur **Body** neeche se copy karke paste karein, phir **Save** dabayein.

Yeh templates `token_hash` wala link bhejte hain. Is liye link kisi bhi device ya browser mein khole tab bhi chalta hai. Link hamare page `/auth/confirm` par aata hai, aur wahan user ek button dabata hai. Token sirf button dabane par use hota hai, is liye email scanners (jo links khud khol lete hain) use zaaya nahi kar sakte.

> **Zaroori:** `{{ .RedirectTo }}` sirf tab kaam karta hai jab hamara URL **Authentication → URL Configuration → Redirect URLs** mein ho
> (`http://127.0.0.1:5000/**`, `http://localhost:5000/**`, `https://<aap-ka-vercel-domain>/**`).
> Warna Supabase Site URL use karta hai aur link home page par khulta hai.

---

## 1. Confirm signup

**Subject**

```
Confirm your Toolverse account
```

**Body**

```html
<div style="font-family: Arial, Helvetica, sans-serif; max-width: 480px; margin: 0 auto; padding: 24px; color: #111;">
  <h2 style="margin: 0 0 12px;">Confirm your email</h2>
  <p style="margin: 0 0 20px; line-height: 1.6;">
    Welcome to Toolverse! Press the button below to confirm your email and open your dashboard.
  </p>
  <p style="margin: 0 0 24px;">
    <a href="{{ .RedirectTo }}?token_hash={{ .TokenHash }}&type=email"
       style="display: inline-block; background: #000; color: #fff; text-decoration: none; padding: 12px 22px; border-radius: 999px; font-weight: bold;">
      Confirm my email
    </a>
  </p>

  <div dir="rtl" style="font-family: 'Noto Nastaliq Urdu', Tahoma, serif; line-height: 2; margin: 0 0 24px;">
    <p style="margin: 0;">ٹول ورس میں خوش آمدید! اوپر والا بٹن دبا کر اپنا ای میل کنفرم کریں اور اپنا ڈیش بورڈ کھولیں۔</p>
  </div>

  <p style="margin: 0; font-size: 13px; color: #666; line-height: 1.6;">
    If you did not sign up for Toolverse, you can ignore this email.<br>
    <span dir="rtl">اگر آپ نے ٹول ورس پر سائن اپ نہیں کیا تو اس ای میل کو نظر انداز کر دیں۔</span>
  </p>
</div>
```

---

## 2. Reset password

**Subject**

```
Reset your Toolverse password
```

**Body**

```html
<div style="font-family: Arial, Helvetica, sans-serif; max-width: 480px; margin: 0 auto; padding: 24px; color: #111;">
  <h2 style="margin: 0 0 12px;">Reset your password</h2>
  <p style="margin: 0 0 20px; line-height: 1.6;">
    Someone asked to reset the password of your Toolverse account. Press the button below to choose a new password.
  </p>
  <p style="margin: 0 0 24px;">
    <a href="{{ .RedirectTo }}?token_hash={{ .TokenHash }}&type=recovery"
       style="display: inline-block; background: #000; color: #fff; text-decoration: none; padding: 12px 22px; border-radius: 999px; font-weight: bold;">
      Choose a new password
    </a>
  </p>

  <div dir="rtl" style="font-family: 'Noto Nastaliq Urdu', Tahoma, serif; line-height: 2; margin: 0 0 24px;">
    <p style="margin: 0;">آپ کے ٹول ورس اکاؤنٹ کا پاس ورڈ ری سیٹ کرنے کی درخواست آئی ہے۔ اوپر والا بٹن دبا کر نیا پاس ورڈ چنیں۔</p>
  </div>

  <p style="margin: 0; font-size: 13px; color: #666; line-height: 1.6;">
    If you did not ask for this, you can ignore this email. Your password will not change.<br>
    <span dir="rtl">اگر یہ درخواست آپ نے نہیں کی تو اس ای میل کو نظر انداز کر دیں۔ آپ کا پاس ورڈ نہیں بدلے گا۔</span>
  </p>
</div>
```
