/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        primary: { DEFAULT: "#1e3a5f", light: "#2a5298", dark: "#0f1e30" },
        accent: { DEFAULT: "#e85d04", light: "#fb923c", dark: "#c2410c" },
        critical: "#dc2626",
        high: "#f59e0b",
        normal: "#6b7280",
        positive: "#16a34a",
        c0: "#6366f1",
        c1: "#e85d04",
        c2: "#10b981",
        c3: "#f59e0b",
        c4: "#3b82f6",
        c5: "#ec4899",
        c6: "#14b8a6",
        c7: "#a855f7",
        c8: "#84cc16",
        c9: "#f97316",
        surface: {
          DEFAULT: "#0f172a",
          card: "#1e293b",
          border: "#334155",
          hover: "#2d3f55",
        },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "monospace"],
      },
      animation: {
        "pulse-slow": "pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite",
        "fade-in": "fadeIn 0.3s ease-in-out",
        "slide-in": "slideIn 0.2s ease-out",
      },
      keyframes: {
        fadeIn: {
          "0%": { opacity: "0" },
          "100%": { opacity: "1" },
        },
        slideIn: {
          "0%": { transform: "translateX(-10px)", opacity: "0" },
          "100%": { transform: "translateX(0)", opacity: "1" },
        },
      },
    },
  },
  plugins: [],
};
