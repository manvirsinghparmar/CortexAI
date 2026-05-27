/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: "media",
  theme: {
    extend: {
      fontFamily: {
        sans: ["Hanken Grotesk", "system-ui", "-apple-system", "sans-serif"],
      },
      colors: {
        surface: "#f7f9fb",
        primary: "#000000",
      },
    },
  },
  plugins: [require("@tailwindcss/typography")],
};
