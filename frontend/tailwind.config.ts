import type { Config } from 'tailwindcss'

const config: Config = {
  darkMode: "class",
  content: [
    './pages/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        "primary": "#11d411",
        "background-light": "#f6f8f6",
        "background-dark": "#102210",
        "vintage-paper": "#f5f5dc",
        "forest-deep": "#0d1a0d",
        "slate-accent": "#2f3e2f"
      },
      fontFamily: {
        "display": ["Noto Serif", "serif"],
        "sans": ["Noto Sans", "sans-serif"]
      },
      borderRadius: {
        "DEFAULT": "0.5rem", 
        "lg": "1rem", 
        "xl": "1.5rem", 
        "full": "9999px"
      },
    },
  },
  plugins: [],
}
export default config
