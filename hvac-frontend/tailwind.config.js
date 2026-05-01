/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        // HVAC brand palette
        primary: {
          50:  "#e8edf4",
          100: "#c5d0e3",
          200: "#9eb0cf",
          300: "#7790bb",
          400: "#5878ac",
          500: "#3a619e",
          600: "#2e5192",
          700: "#1e3a5f",  // core dark navy — trust, industrial
          800: "#172d4a",
          900: "#0f1e32",
        },
        accent: {
          50:  "#fff3ec",
          100: "#ffe2ce",
          200: "#ffcaab",
          300: "#ffac7c",
          400: "#ff8c4c",
          500: "#e85d04",  // warm orange — urgency, alerts
          600: "#c94e00",
          700: "#a84000",
          800: "#893400",
          900: "#6a2800",
        },
        // Severity colours (mirrored in CSS variables)
        critical: "#dc2626",   // red — critical sentiment
        emerging: "#f59e0b",   // amber — emerging clusters
        safe:     "#16a34a",   // green — positive sentiment
        // Neutral dark background palette (dark mode default)
        gray: {
          850: "#1a1f2e",
          900: "#111827",
          950: "#0a0e1a",
        },
      },
      fontFamily: {
        sans: [
          "Inter",
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "BlinkMacSystemFont",
          "sans-serif",
        ],
        mono: [
          "JetBrains Mono",
          "ui-monospace",
          "SFMono-Regular",
          "monospace",
        ],
      },
      boxShadow: {
        "glow-orange": "0 0 12px rgba(232, 93, 4, 0.35)",
        "glow-red":    "0 0 12px rgba(220, 38, 38, 0.35)",
      },
      animation: {
        "pulse-slow": "pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite",
      },
    },
  },
  plugins: [
    require("@tailwindcss/forms"),
  ],
};
