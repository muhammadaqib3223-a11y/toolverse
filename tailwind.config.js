/** Tailwind config — design tokens from CLAUDE.md section 6. */
/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./app/templates/**/*.html",
    "./app/static/js/**/*.js",
  ],
  theme: {
    extend: {
      colors: {
        bg: "#000000",
        surface: "#0B0B0D",
        card: "#111113",
        line: "#1E1E22",
        "line-strong": "#222226",
        fg: "#FFFFFF",
        muted: "#8F8F98",
        faint: "#6B6B73",
        accent: "#9B8CFF",
        "btn-secondary": "#141416",
      },
      fontFamily: {
        sans: ["Geist", "Noto Nastaliq Urdu", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["Geist Mono", "Noto Nastaliq Urdu", "ui-monospace", "monospace"],
      },
      maxWidth: {
        content: "1240px",
      },
    },
  },
  plugins: [],
};
