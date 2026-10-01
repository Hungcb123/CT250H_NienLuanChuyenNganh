/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        "surface": "#fcfcfd",
        "surface-dim": "#f4f5f8",
        "surface-bright": "#ffffff",
        "surface-container-lowest": "#ffffff",
        "surface-container-low": "#f8f9fa",
        "surface-container": "#f1f3f7",
        "surface-container-high": "#eaedf2",
        "surface-container-highest": "#e2e6ed",
        "primary": "#0f172a",
        "primary-container": "#1e293b",
        "secondary": "#0284c7",
        "secondary-container": "#e0f2fe",
        "accent-gold": "#b45309",
        "accent-gold-light": "#fef3c7",
        "accent-emerald": "#059669",
        "accent-emerald-light": "#ecfdf5",
        "accent-rose": "#e11d48",
        "accent-rose-light": "#ffe4e6",
        "text-primary": "#090d16",
        "text-secondary": "#475569",
        "text-muted": "#94a3b8",
        "border-subtle": "#e2e8f0",
        "border-highlight": "#cbd5e1",
      },
      fontFamily: {
        sans: ['"Plus Jakarta Sans"', 'system-ui', '-apple-system', 'sans-serif'],
      }
    },
  },
  plugins: [],
}
