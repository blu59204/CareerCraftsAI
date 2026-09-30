import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },
        success: "hsl(var(--success))",
        warning: "hsl(var(--warning))",
        danger: "hsl(var(--danger))",
      },
      // Vanguard motion + depth tokens. `ease-vanguard` is the default for
      // every interactive transition on redesigned screens (never linear /
      // ease-in-out); `ease-vanguard-out` for entrances.
      transitionTimingFunction: {
        vanguard: "cubic-bezier(0.32, 0.72, 0, 1)",
        "vanguard-out": "cubic-bezier(0.16, 1, 0.3, 1)",
      },
      boxShadow: {
        // Inner-core top highlight of a Double-Bezel card.
        "bezel-core": "inset 0 1px 1px hsl(0 0% 100% / 0.65)",
        "bezel-core-dark": "inset 0 1px 1px hsl(0 0% 100% / 0.08)",
        // Very soft, highly diffused ambient lift — tinted by the warm foreground.
        ambient: "0 40px 80px -48px hsl(var(--foreground) / 0.18), 0 12px 24px -20px hsl(var(--foreground) / 0.08)",
        "ambient-sm": "0 16px 32px -24px hsl(var(--foreground) / 0.16)",
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 4px)",
        sm: "calc(var(--radius) - 8px)",
        "3xl": "calc(var(--radius) + 0.5rem)",
      },
      fontFamily: {
        sans: ["var(--font-dm-sans)", "ui-sans-serif", "system-ui", "sans-serif"],
        chrome: ["-apple-system", "BlinkMacSystemFont", "SF Pro Text", "SF Pro Display", "Segoe UI", "var(--font-dm-sans)", "ui-sans-serif", "system-ui", "sans-serif"],
        display: ["var(--font-instrument-serif)", "Iowan Old Style", "Georgia", "serif"],
        hero: ["var(--font-playfair)", "Iowan Old Style", "Georgia", "serif"],
        // Dashboard/software-UI headlines — never serif (design-taste-frontend rule).
        command: ["var(--font-outfit)", "ui-sans-serif", "system-ui", "sans-serif"],
        // Vanguard in-app redesign (components/vanguard, app screens).
        geist: ["var(--font-geist)", "ui-sans-serif", "system-ui", "sans-serif"],
        "geist-mono": ["var(--font-geist-mono)", "ui-monospace", "SFMono-Regular", "monospace"],
      },
    },
  },
  plugins: [],
};

export default config;
