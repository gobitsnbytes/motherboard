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
        border: "var(--border)",
        burgundy: "#97192c",
        orange: "#fc920d",
        dark: "#120f0a",
        // Neobrutalism tokens from @bnb/ui
        main: "var(--main)",
        "main-foreground": "var(--main-foreground)",
        "secondary-background": "var(--secondary-background)",
        foreground: "hsl(var(--foreground))",
        background: "hsl(var(--background))",
        bw: "var(--bw)",
        blank: "var(--blank)",
        text: "var(--text)",
        mtext: "var(--mtext)",
      },
      fontFamily: {
        heading: ["'Inter'", "sans-serif"],
        body: ["'Merriweather'", "serif"],
        base: ["'Merriweather'", "Georgia", "serif"],
      },
      borderRadius: {
        DEFAULT: "9999px",
        base: "var(--border-radius)",
      },
      boxShadow: {
        shadow: "var(--shadow)",
      },
      translate: {
        boxShadowX: "var(--box-shadow-x)",
        boxShadowY: "var(--box-shadow-y)",
        reverseBoxShadowX: "-4px",
        reverseBoxShadowY: "-4px",
      },
    }
  },
  plugins: [],
}
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
