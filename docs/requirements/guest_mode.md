# Guest mode — requirements

User bina login ke tools try kar sake.

- **CV Checker:** 1 free check (IP ke hisaab se limit)
- **Captions:** 3 free tries (IP ke hisaab se limit, taake Gemini ki free
  limit khatam na ho)
- **CV Generator:** PDF download bina login, save ke liye login
- **Notes aur Expenses:** guest ke liye browser mein save hon
  (`localStorage`), aur login karne par account mein chale jayein
- Login Google se ek click mein bhi ho

## Zaroori baatein

- **IP ki ginti Supabase mein:** Vercel serverless hai, server ki memory har
  request ke baad khatam ho jati hai. Is liye guest tries ki ginti (IP ke
  hisaab se) Supabase ki table mein rakhni hai.
- **Guest ki CV save na ho:** guest jab bina login ke CV check kare, us ki
  file kahin save nahi hogi — sirf check ho kar khatam (section 7 Privacy ke
  mutabiq, CLAUDE.md).
- **Landing FAQ badalna:** guest mode banne ke baad landing page ka "Why do I
  need to log in?" wala jawab update karna hai, kyunki tab login ke baghair
  bhi tools try ho sakenge.
- **"Try it free" seedha tool khole:** guest mode banne ke baad tool pages ka
  "Try it free" button coming-soon page ki jagah seedha tool kholega.

## Implementation pattern

See CLAUDE.md "Progress & decisions" → "How a tool with Supabase data +
guest mode works" for the routes/services/repository layering and the
`localStorage` store pattern (reference implementation: Notes,
`public/static/js/notes/stores.js`).
