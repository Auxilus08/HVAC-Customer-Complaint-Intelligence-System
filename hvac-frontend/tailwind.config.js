/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        carrier: {
          DEFAULT: "#1E3A5F",
          dark: "#15294A",
          light: "#EEF2F8",
        },
        ink: {
          900: "#0F172A",
          700: "#334155",
          500: "#64748B",
          300: "#CBD5E1",
          100: "#F1F5F9",
        },
        surface: {
          DEFAULT: "#FFFFFF",
          soft: "#F8FAFC",
          card: "#FFFFFF",
          border: "#E2E8F0",
        },
        status: {
          critical: "#DC2626",
          high: "#F59E0B",
          normal: "#94A3B8",
          positive: "#16A34A",
        },
        // kept for backward compat in components not yet migrated
        accent: { DEFAULT: "#1E3A5F", light: "#EEF2F8", dark: "#15294A" },
        critical: "#DC2626",
        high: "#F59E0B",
        normal: "#94A3B8",
        positive: "#16A34A",
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
