/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        surface: "#0f172a",
        "surface-hover": "#1e293b",
        accent: "#38bdf8",
        accent-hover: "#7dd3fc",
        danger: "#f87171",
        success: "#4ade80",
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
