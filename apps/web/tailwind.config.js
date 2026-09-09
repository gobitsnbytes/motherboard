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
        surface: "#141418",
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
        display: ["'Anton'", "'Inter'", "sans-serif"],
        body: ["'Merriweather'", "'Georgia'", "serif"],
        base: ["'Merriweather'", "'Georgia'", "serif"],
        mono: ["'JetBrains Mono'", "'Fira Code'", "monospace"],
      },
      borderRadius: {
        none: "0px",
        base: "var(--border-radius)",
        sm: "2px",
        md: "4px",
      },
      boxShadow: {
        shadow: "var(--shadow)",
        light: "2px 2px 0px 0px rgba(0, 0, 0, 1)",
        dark: "4px 4px 0px 0px rgba(0, 0, 0, 1)",
        heavy: "6px 6px 0px 0px rgba(0, 0, 0, 1)",
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

