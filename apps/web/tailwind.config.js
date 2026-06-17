/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "../../packages/ui/src/**/*.{js,ts,jsx,tsx,mdx}"
  ],
  theme: {
    extend: {
      colors: {
        border: "#120f0a",
        burgundy: "#97192c",
        orange: "#fc920d",
        dark: "#120f0a",
      },
      fontFamily: {
        heading: ["'Inter'", "sans-serif"],
        body: ["'Merriweather'", "serif"],
      },
      borderRadius: {
        DEFAULT: "9999px",
      }
    }
  },
  plugins: [],
}
