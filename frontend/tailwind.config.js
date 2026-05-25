// tailwind.config.js
/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: "class",
  content: [
    "./app/**/*.{js,ts,jsx,tsx}",
    "./components/**/*.{js,ts,jsx,tsx}",
    "./src/**/*.{js,ts,jsx,tsx}",
    "./pages/**/*.{js,ts,jsx,tsx}"
  ],
  theme: {
    extend: {
      colors: {
        primary: "hsl(210, 40%, 50%)",
        secondary: "hsl(340, 60%, 55%)",
        accent: "hsl(45, 80%, 55%)",
        // add more custom palettes as needed
      }
    }
  },
  plugins: []
};
