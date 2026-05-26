# Frontend Visual Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current Tailwind-admin look with a MotionSites-inspired premium UI — light marketing zone, dark app zone, liquid-glass surfaces, editorial typography, motion-driven entrances — without touching API, auth, store, or backend contracts.

**Architecture:** Next.js 14 App Router split into three route groups: `(marketing)` (light default, public), `(app)` (dark default, Clerk-protected), `(auth)` (untouched). One `ThemeProvider` powers theme persistence via `localStorage`. Visual primitives (`LiquidGlassButton`, `MetricCard`, etc.) live under `components/ui/`; route shells (`AppShell`, `MarketingNavbar`) under `components/layout/` and `components/marketing/`. All colors flow through CSS custom properties — zero hardcoded `bg-white`/`bg-gray-900`.

**Tech Stack:** Next.js 14.2 App Router, Tailwind 3.4 (`darkMode: ["class"]`), Radix UI, `motion` (motion/react), Inter + Instrument Serif (next/font/google), Clerk 5, lucide-react.

**Spec reference:** `docs/superpowers/specs/2026-05-24-frontend-redesign.md`.

**Verification model:** Visual layer — no unit tests added. Each task verified by `npm run type-check && npm run lint` plus dev-server render check at the route under change. "Dev render check" = boot `npm run dev`, open the route in a browser (or hit it via curl for HTTP 200), confirm no console errors and visible content matches the spec section. State that explicitly if browser is not accessible.

**Working directory:** `frontend/`. All file paths below are relative to repo root.

---

## File Structure Overview

### New files

```
frontend/src/
  app/
    (marketing)/
      layout.tsx                          # public shell
      page.tsx                            # /
      pricing/page.tsx                    # /pricing
    (app)/
      layout.tsx                          # auth shell
      dashboard/page.tsx                  # /dashboard
      resume/page.tsx                     # /resume
      applications/page.tsx               # /applications
      agents/page.tsx                     # /agents
      onboarding/page.tsx                 # /onboarding
      settings/models/page.tsx            # /settings/models
  components/
    theme/
      ThemeProvider.tsx
      ThemeToggle.tsx
      theme-script.tsx                    # inline no-flash script
    marketing/
      Navbar.tsx
      Footer.tsx
      MarqueeRow.tsx
      HeroA.tsx
      HeroB.tsx
      HowItWorks.tsx
      FeaturesGrid.tsx
      PricingSection.tsx
      FaqAccordion.tsx
    layout/
      AppShell.tsx
      AppSidebar.tsx
      AppTopbar.tsx
    ui/
      LiquidGlassButton.tsx
      MetricCard.tsx
      FeatureCard.tsx
      PricingCard.tsx
      ResumeScoreCard.tsx
      JobMatchCard.tsx
      EmptyState.tsx
      LoadingState.tsx
      ErrorState.tsx
      VideoBackground.tsx
    apps/
      ApplicationKanban.tsx
      ApplicationDrawer.tsx
    agents/
      AgentStatusCard.tsx
      ApprovalCard.tsx
    resume/
      AtsScoreRing.tsx
      KeywordCoverage.tsx
      SuggestionsList.tsx
    onboarding/
      OnboardingStepper.tsx
  lib/
    motion-variants.ts                    # fadeUp/fadeIn/stagger/cardHover
```

### Files modified

- `frontend/src/app/globals.css` — replace tokens, add `.liquid-glass`, `.noise-overlay`, marquee keyframes
- `frontend/src/app/layout.tsx` — strip sidebar; keep only ClerkProvider + ThemeProvider + QueryProvider + Toaster
- `frontend/tailwind.config.ts` — extend palette (success/warning/danger/accent), `--radius` 1.5rem
- `frontend/package.json` — add `motion`, `@radix-ui/react-accordion`, `@radix-ui/react-avatar`
- `frontend/src/app/dashboard/page.tsx` — DELETE (replaced by `(app)/dashboard/page.tsx`)
- `frontend/src/app/applications/page.tsx` — DELETE (replaced by `(app)/applications/page.tsx`)
- `frontend/src/app/jobs/search/page.tsx` — DELETE; folded into `(app)/applications` filter
- `frontend/src/app/resume/optimize/page.tsx` — DELETE (replaced by `(app)/resume/page.tsx`)
- `frontend/src/app/settings/models/page.tsx` — MOVE to `(app)/settings/models/page.tsx`, restyle
- `frontend/src/components/layout/Sidebar.tsx` — DELETE (superseded by `AppSidebar.tsx`)
- `frontend/src/components/agents/AgentStatusStream.tsx` — keep, re-skin via wrapping `AgentStatusCard`
- `frontend/src/components/agents/ApprovalModal.tsx` — keep, re-skin via wrapping `ApprovalCard`

### Files NOT touched

- `frontend/src/lib/api.ts`
- `frontend/src/lib/sse.ts`
- `frontend/src/lib/auth.ts`
- `frontend/src/store/agentSlice.ts`
- `frontend/src/store/userSlice.ts`
- `frontend/src/middleware.ts`
- `frontend/src/app/(auth)/login/page.tsx`
- `frontend/src/app/(auth)/register/page.tsx`
- All `apiClient.*` call sites — only re-arrange around them

---

# Phase 1 — Design System Foundation

Owns: tokens, motion install, theme plumbing. Nothing visible to the user yet.

---

### Task 1: Install motion and accordion/avatar Radix deps

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/package-lock.json` (auto)

- [ ] **Step 1: Install dependencies**

Run:
```bash
cd frontend && npm install motion @radix-ui/react-accordion @radix-ui/react-avatar
```

Expected: `added N packages, changed 0 packages`. No vulnerability errors above moderate.

- [ ] **Step 2: Verify motion import resolves**

Create throwaway file `frontend/scratch-import-check.ts`:
```ts
import { motion, AnimatePresence } from "motion/react";
export const _t = [motion, AnimatePresence];
```

Run:
```bash
cd frontend && npx tsc --noEmit scratch-import-check.ts
```

Expected: no errors. Delete the scratch file:
```bash
rm frontend/scratch-import-check.ts
```

- [ ] **Step 3: Commit**

```bash
git add frontend/package.json frontend/package-lock.json
git commit -m "build(frontend): add motion and radix accordion/avatar for redesign"
```

---

### Task 2: Rewrite globals.css with new tokens and utilities

**Files:**
- Modify: `frontend/src/app/globals.css`

- [ ] **Step 1: Replace globals.css contents**

Overwrite `frontend/src/app/globals.css` with:

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

@layer base {
  :root {
    --background: 0 0% 100%;
    --foreground: 222 47% 8%;
    --card: 0 0% 100%;
    --card-foreground: 222 47% 8%;
    --muted: 210 40% 96%;
    --muted-foreground: 215 16% 47%;
    --border: 214 32% 91%;
    --input: 214 32% 91%;
    --primary: 245 75% 59%;
    --primary-foreground: 0 0% 100%;
    --secondary: 210 40% 96%;
    --secondary-foreground: 222 47% 11%;
    --accent: 262 83% 65%;
    --accent-foreground: 0 0% 100%;
    --success: 142 71% 45%;
    --warning: 38 92% 50%;
    --danger: 0 84% 60%;
    --ring: 245 75% 59%;
    --radius: 1.5rem;
  }

  .dark {
    --background: 240 10% 3%;
    --foreground: 210 40% 98%;
    --card: 240 9% 6%;
    --card-foreground: 210 40% 98%;
    --muted: 240 6% 10%;
    --muted-foreground: 215 20% 65%;
    --border: 240 6% 13%;
    --input: 240 6% 13%;
    --primary: 258 80% 60%;
    --primary-foreground: 0 0% 100%;
    --secondary: 240 6% 10%;
    --secondary-foreground: 210 40% 98%;
    --accent: 265 83% 65%;
    --accent-foreground: 0 0% 100%;
    --success: 142 71% 45%;
    --warning: 38 92% 50%;
    --danger: 0 84% 60%;
    --ring: 258 80% 60%;
  }
}

* {
  border-color: hsl(var(--border));
}

body {
  background-color: hsl(var(--background));
  color: hsl(var(--foreground));
  font-feature-settings: "rlig" 1, "calt" 1;
}

@layer utilities {
  .liquid-glass {
    background: rgba(255, 255, 255, 0.01);
    backdrop-filter: blur(4px);
    -webkit-backdrop-filter: blur(4px);
    box-shadow: inset 0 1px 1px rgba(255, 255, 255, 0.10);
    position: relative;
    overflow: hidden;
  }
  .liquid-glass::before {
    content: "";
    position: absolute;
    inset: 0;
    border-radius: inherit;
    padding: 1.4px;
    background: linear-gradient(180deg,
      rgba(255, 255, 255, 0.45) 0%,
      rgba(255, 255, 255, 0.15) 20%,
      rgba(255, 255, 255, 0) 40%,
      rgba(255, 255, 255, 0) 60%,
      rgba(255, 255, 255, 0.15) 80%,
      rgba(255, 255, 255, 0.45) 100%);
    -webkit-mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
    -webkit-mask-composite: xor;
    mask-composite: exclude;
    pointer-events: none;
  }

  .noise-overlay {
    position: relative;
  }
  .noise-overlay::after {
    content: "";
    position: absolute;
    inset: 0;
    pointer-events: none;
    opacity: 0.35;
    mix-blend-mode: soft-light;
    background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='240' height='240'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='2' stitchTiles='stitch'/></filter><rect width='100%25' height='100%25' filter='url(%23n)' opacity='0.55'/></svg>");
    background-size: 240px 240px;
  }

  .gradient-mesh-light {
    background:
      radial-gradient(60% 50% at 15% 10%, hsl(245 90% 90% / 0.55), transparent 70%),
      radial-gradient(50% 40% at 85% 20%, hsl(262 90% 88% / 0.45), transparent 70%),
      radial-gradient(70% 60% at 50% 100%, hsl(220 90% 92% / 0.45), transparent 70%),
      hsl(var(--background));
  }
  .gradient-mesh-dark {
    background:
      radial-gradient(60% 50% at 15% 10%, hsl(258 90% 25% / 0.55), transparent 70%),
      radial-gradient(50% 40% at 85% 20%, hsl(280 90% 22% / 0.45), transparent 70%),
      radial-gradient(70% 60% at 50% 100%, hsl(220 90% 20% / 0.45), transparent 70%),
      hsl(var(--background));
  }

  @keyframes marquee-left {
    from { transform: translateX(0); }
    to { transform: translateX(-50%); }
  }
  @keyframes marquee-right {
    from { transform: translateX(-50%); }
    to { transform: translateX(0); }
  }
  .animate-marquee-left { animation: marquee-left 22s linear infinite; }
  .animate-marquee-right { animation: marquee-right 26s linear infinite; }

  .font-display { font-family: "Instrument Serif", "Iowan Old Style", "Georgia", serif; font-style: italic; }
}
```

- [ ] **Step 2: Type-check passes**

Run:
```bash
cd frontend && npm run type-check
```

Expected: exit 0.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/globals.css
git commit -m "feat(frontend): redesign tokens — light/dark vars, liquid-glass, mesh, marquee utils"
```

---

### Task 3: Extend tailwind.config.ts with new palette + radius scale

**Files:**
- Modify: `frontend/tailwind.config.ts`

- [ ] **Step 1: Replace tailwind.config.ts contents**

Overwrite `frontend/tailwind.config.ts` with:

```ts
import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class"],
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
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 4px)",
        sm: "calc(var(--radius) - 8px)",
        "3xl": "calc(var(--radius) + 0.5rem)",
      },
      fontFamily: {
        sans: ["var(--font-inter)", "ui-sans-serif", "system-ui", "sans-serif"],
        display: ["var(--font-instrument-serif)", "Iowan Old Style", "Georgia", "serif"],
      },
    },
  },
  plugins: [],
};

export default config;
```

- [ ] **Step 2: Type-check + lint**

Run:
```bash
cd frontend && npm run type-check && npm run lint
```

Expected: exit 0. Lint warnings allowed; no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/tailwind.config.ts
git commit -m "feat(frontend): extend tailwind palette and radius scale"
```

---

### Task 4: Create motion variants library

**Files:**
- Create: `frontend/src/lib/motion-variants.ts`

- [ ] **Step 1: Write motion-variants.ts**

Create `frontend/src/lib/motion-variants.ts`:

```ts
import type { Variants } from "motion/react";

export const fadeUp: Variants = {
  hidden: { opacity: 0, y: 20 },
  show: { opacity: 1, y: 0, transition: { duration: 0.5, ease: "easeOut" } },
};

export const fadeIn: Variants = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { duration: 0.4 } },
};

export const stagger: Variants = {
  hidden: {},
  show: { transition: { staggerChildren: 0.08 } },
};

export const cardHover = {
  whileHover: { scale: 1.02, transition: { duration: 0.2 } },
};

export const slideRight: Variants = {
  hidden: { opacity: 0, x: -16 },
  show: { opacity: 1, x: 0, transition: { duration: 0.35 } },
};
```

- [ ] **Step 2: Type-check passes**

Run:
```bash
cd frontend && npm run type-check
```

Expected: exit 0.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/motion-variants.ts
git commit -m "feat(frontend): add motion variants library (fadeUp, fadeIn, stagger, cardHover)"
```

---

### Task 5: ThemeProvider + no-flash inline script

**Files:**
- Create: `frontend/src/components/theme/ThemeProvider.tsx`
- Create: `frontend/src/components/theme/theme-script.tsx`

- [ ] **Step 1: Write ThemeProvider.tsx**

Create `frontend/src/components/theme/ThemeProvider.tsx`:

```tsx
"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

export type Theme = "light" | "dark";
export type Zone = "marketing" | "app";

type ThemeContextValue = {
  theme: Theme;
  setTheme: (t: Theme) => void;
  toggleTheme: () => void;
};

const ThemeContext = createContext<ThemeContextValue | null>(null);

const STORAGE_KEY = "theme";

function readSaved(): Theme | null {
  if (typeof window === "undefined") return null;
  const v = window.localStorage.getItem(STORAGE_KEY);
  return v === "light" || v === "dark" ? v : null;
}

function systemTheme(): Theme {
  if (typeof window === "undefined") return "light";
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function ThemeProvider({
  children,
  zoneDefault,
}: {
  children: React.ReactNode;
  zoneDefault: Theme;
}) {
  const [theme, setThemeState] = useState<Theme>(zoneDefault);

  useEffect(() => {
    const saved = readSaved();
    const initial: Theme = saved ?? zoneDefault ?? systemTheme();
    setThemeState(initial);
    document.documentElement.classList.remove("light", "dark");
    document.documentElement.classList.add(initial);
  }, [zoneDefault]);

  const setTheme = useCallback((t: Theme) => {
    setThemeState(t);
    window.localStorage.setItem(STORAGE_KEY, t);
    document.documentElement.classList.remove("light", "dark");
    document.documentElement.classList.add(t);
  }, []);

  const toggleTheme = useCallback(() => {
    setTheme(theme === "dark" ? "light" : "dark");
  }, [theme, setTheme]);

  const value = useMemo(() => ({ theme, setTheme, toggleTheme }), [theme, setTheme, toggleTheme]);

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useTheme must be used inside <ThemeProvider>");
  return ctx;
}
```

- [ ] **Step 2: Write theme-script.tsx (no-flash)**

Create `frontend/src/components/theme/theme-script.tsx`:

```tsx
import Script from "next/script";

export function ThemeScript({ zoneDefault }: { zoneDefault: "light" | "dark" }) {
  const code = `
    (function () {
      try {
        var saved = localStorage.getItem("theme");
        var chosen = saved === "light" || saved === "dark"
          ? saved
          : ${JSON.stringify(zoneDefault)};
        document.documentElement.classList.remove("light", "dark");
        document.documentElement.classList.add(chosen);
      } catch (_) {}
    })();
  `;
  return (
    <Script id="theme-init" strategy="beforeInteractive">
      {code}
    </Script>
  );
}
```

- [ ] **Step 3: Type-check**

Run:
```bash
cd frontend && npm run type-check
```

Expected: exit 0.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/theme/
git commit -m "feat(frontend): ThemeProvider with localStorage persistence and no-flash script"
```

---

### Task 6: ThemeToggle button component

**Files:**
- Create: `frontend/src/components/theme/ThemeToggle.tsx`

- [ ] **Step 1: Write ThemeToggle.tsx**

Create `frontend/src/components/theme/ThemeToggle.tsx`:

```tsx
"use client";

import { Moon, Sun } from "lucide-react";
import { useTheme } from "./ThemeProvider";

export function ThemeToggle({ className = "" }: { className?: string }) {
  const { theme, toggleTheme } = useTheme();
  const isDark = theme === "dark";
  return (
    <button
      type="button"
      onClick={toggleTheme}
      aria-label={`Switch to ${isDark ? "light" : "dark"} theme`}
      className={`inline-flex h-9 w-9 items-center justify-center rounded-full border border-border bg-card/60 text-foreground transition-colors hover:bg-card ${className}`}
    >
      {isDark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
    </button>
  );
}
```

- [ ] **Step 2: Type-check + lint**

Run:
```bash
cd frontend && npm run type-check && npm run lint
```

Expected: exit 0.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/theme/ThemeToggle.tsx
git commit -m "feat(frontend): ThemeToggle sun/moon button"
```

---

### Task 7: Strip root layout to bare providers + load fonts + theme script

**Files:**
- Modify: `frontend/src/app/layout.tsx`
- Modify: `frontend/src/components/layout/Providers.tsx` (read existing, then adapt)

- [ ] **Step 1: Read existing Providers.tsx**

Run:
```bash
cat frontend/src/components/layout/Providers.tsx
```

Confirm it wraps `QueryClientProvider` + `Toaster`. If it also wraps Clerk or Sidebar, leave Clerk for root layout and remove Sidebar references here.

- [ ] **Step 2: Replace `frontend/src/app/layout.tsx`**

Overwrite with:

```tsx
import type { Metadata } from "next";
import { Inter, Instrument_Serif } from "next/font/google";
import { ClerkProvider } from "@clerk/nextjs";
import { Providers } from "@/components/layout/Providers";
import "./globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter", display: "swap" });
const instrumentSerif = Instrument_Serif({
  subsets: ["latin"],
  weight: "400",
  style: "italic",
  variable: "--font-instrument-serif",
  display: "swap",
});

export const metadata: Metadata = {
  title: "CareerCraft AI — Apply smarter. Tailor faster.",
  description: "AI job-search copilot for students and freshers.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <ClerkProvider>
      <html lang="en" className={`${inter.variable} ${instrumentSerif.variable}`} suppressHydrationWarning>
        <body className="font-sans antialiased">
          <Providers>{children}</Providers>
        </body>
      </html>
    </ClerkProvider>
  );
}
```

Note: the per-zone `ThemeProvider` is mounted in each route group's `layout.tsx` (Tasks 8 and 14), not here. Root stays theme-agnostic so `(auth)` pages keep their current look untouched.

- [ ] **Step 3: Remove Sidebar import + render from root layout (already done in Step 2). Type-check**

Run:
```bash
cd frontend && npm run type-check
```

Expected: exit 0. If `Providers` still re-exports Sidebar, type-check will succeed regardless; we'll delete Sidebar.tsx in Task 12.

- [ ] **Step 4: Dev render check — `(auth)` pages still load**

Run:
```bash
cd frontend && npm run dev
```

In another shell:
```bash
curl -sI http://localhost:3000/login | head -1
curl -sI http://localhost:3000/register | head -1
```

Expected: `HTTP/1.1 200 OK` for both (or 307 redirect to Clerk-hosted page — also OK). Kill dev server.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/app/layout.tsx
git commit -m "feat(frontend): strip root layout to bare providers, load Inter+Instrument Serif"
```

---

# Phase 2 — Marketing Zone

Owns: `(marketing)` route group, Navbar, Footer, landing page, pricing page.

---

### Task 8: Marketing route group layout

**Files:**
- Create: `frontend/src/app/(marketing)/layout.tsx`

- [ ] **Step 1: Write `(marketing)/layout.tsx`**

Create:

```tsx
import { ThemeProvider } from "@/components/theme/ThemeProvider";
import { ThemeScript } from "@/components/theme/theme-script";
import { MarketingNavbar } from "@/components/marketing/Navbar";
import { MarketingFooter } from "@/components/marketing/Footer";

export default function MarketingLayout({ children }: { children: React.ReactNode }) {
  return (
    <ThemeProvider zoneDefault="light">
      <ThemeScript zoneDefault="light" />
      <div className="min-h-screen bg-background text-foreground">
        <MarketingNavbar />
        <main>{children}</main>
        <MarketingFooter />
      </div>
    </ThemeProvider>
  );
}
```

- [ ] **Step 2: Type-check (will fail until Navbar + Footer exist)**

Skip the check until Tasks 9 + 10 land. Move on.

- [ ] **Step 3: Commit**

```bash
git add "frontend/src/app/(marketing)/layout.tsx"
git commit -m "feat(frontend): marketing route group layout (light default)"
```

---

### Task 9: MarketingNavbar

**Files:**
- Create: `frontend/src/components/marketing/Navbar.tsx`

- [ ] **Step 1: Write Navbar.tsx**

Create:

```tsx
"use client";

import Link from "next/link";
import { SignedIn, SignedOut, UserButton } from "@clerk/nextjs";
import { ThemeToggle } from "@/components/theme/ThemeToggle";

const NAV = [
  { href: "/#features", label: "Features" },
  { href: "/#how", label: "How it Works" },
  { href: "/pricing", label: "Pricing" },
  { href: "/#demo", label: "Demo" },
];

export function MarketingNavbar() {
  return (
    <header className="sticky top-0 z-40 w-full border-b border-border/60 bg-background/70 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-6">
        <Link href="/" className="flex items-center gap-2 text-lg font-semibold">
          <span className="inline-flex h-7 w-7 items-center justify-center rounded-full bg-primary text-primary-foreground">C</span>
          CareerCraft AI
        </Link>
        <nav className="hidden items-center gap-8 md:flex">
          {NAV.map((n) => (
            <Link key={n.href} href={n.href} className="text-sm text-muted-foreground hover:text-foreground">
              {n.label}
            </Link>
          ))}
        </nav>
        <div className="flex items-center gap-3">
          <ThemeToggle />
          <SignedOut>
            <Link href="/login" className="text-sm text-muted-foreground hover:text-foreground">
              Log in
            </Link>
            <Link
              href="/register"
              className="inline-flex h-9 items-center rounded-full bg-primary px-4 text-sm font-medium text-primary-foreground hover:opacity-90"
            >
              Get Started
            </Link>
          </SignedOut>
          <SignedIn>
            <Link
              href="/dashboard"
              className="inline-flex h-9 items-center rounded-full bg-primary px-4 text-sm font-medium text-primary-foreground hover:opacity-90"
            >
              Dashboard
            </Link>
            <UserButton afterSignOutUrl="/" />
          </SignedIn>
        </div>
      </div>
    </header>
  );
}
```

- [ ] **Step 2: Type-check**

Run:
```bash
cd frontend && npm run type-check
```

Expected: exit 0 (Footer still missing — will keep failing until Task 10. If errors complain only about `MarketingFooter`, proceed. Otherwise fix.)

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/marketing/Navbar.tsx
git commit -m "feat(frontend): marketing navbar with Clerk auth state and theme toggle"
```

---

### Task 10: MarketingFooter + VideoBackground

**Files:**
- Create: `frontend/src/components/ui/VideoBackground.tsx`
- Create: `frontend/src/components/marketing/Footer.tsx`

- [ ] **Step 1: Write VideoBackground.tsx**

Create `frontend/src/components/ui/VideoBackground.tsx`:

```tsx
type Props = {
  src: string;
  poster?: string;
  className?: string;
  overlayClassName?: string;
};

export function VideoBackground({ src, poster, className = "", overlayClassName = "" }: Props) {
  return (
    <div className={`absolute inset-0 -z-10 overflow-hidden ${className}`}>
      <video
        autoPlay
        muted
        loop
        playsInline
        poster={poster}
        className="h-full w-full object-cover"
      >
        <source src={src} type="video/mp4" />
      </video>
      <div className={`absolute inset-0 bg-background/60 ${overlayClassName}`} />
    </div>
  );
}
```

- [ ] **Step 2: Write Footer.tsx**

Create `frontend/src/components/marketing/Footer.tsx`:

```tsx
import Link from "next/link";
import { VideoBackground } from "@/components/ui/VideoBackground";

const COLUMNS: { title: string; links: { href: string; label: string }[] }[] = [
  {
    title: "Product",
    links: [
      { href: "/#features", label: "Features" },
      { href: "/pricing", label: "Pricing" },
      { href: "/#how", label: "How it Works" },
    ],
  },
  {
    title: "Agents",
    links: [
      { href: "/agents?focus=resume", label: "Resume Agent" },
      { href: "/agents?focus=job", label: "Job Search Agent" },
      { href: "/agents?focus=email", label: "Email Agent" },
      { href: "/agents?focus=followup", label: "Follow-up Agent" },
    ],
  },
  {
    title: "Company",
    links: [
      { href: "/about", label: "About" },
      { href: "/privacy", label: "Privacy" },
      { href: "/terms", label: "Terms" },
    ],
  },
  {
    title: "Support",
    links: [
      { href: "/docs", label: "Docs" },
      { href: "/contact", label: "Contact" },
      { href: "/status", label: "Status" },
    ],
  },
];

export function MarketingFooter() {
  return (
    <footer className="relative isolate mt-32 overflow-hidden rounded-t-[3rem] border-t border-border">
      <VideoBackground src="/videos/footer.mp4" poster="/videos/footer-poster.jpg" overlayClassName="bg-background/85" />
      <div className="relative mx-auto max-w-7xl px-6 py-20">
        <div className="grid grid-cols-2 gap-10 md:grid-cols-5">
          <div className="col-span-2">
            <div className="text-2xl font-semibold">CareerCraft AI</div>
            <p className="mt-3 max-w-xs text-sm text-muted-foreground">
              The AI job-search copilot for students and freshers. Tailor resumes, match jobs, follow up — automatically.
            </p>
          </div>
          {COLUMNS.map((c) => (
            <div key={c.title}>
              <div className="text-sm font-medium">{c.title}</div>
              <ul className="mt-4 space-y-2">
                {c.links.map((l) => (
                  <li key={l.href}>
                    <Link href={l.href} className="text-sm text-muted-foreground hover:text-foreground">
                      {l.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
        <div className="mt-14 flex items-center justify-between border-t border-border/60 pt-6 text-xs text-muted-foreground">
          <span>© {new Date().getFullYear()} CareerCraft AI</span>
          <span>Built with care.</span>
        </div>
      </div>
    </footer>
  );
}
```

- [ ] **Step 3: Create asset placeholders so build doesn't 404**

Run:
```bash
mkdir -p frontend/public/videos
# placeholders — replace with real assets later
touch frontend/public/videos/footer.mp4
touch frontend/public/videos/footer-poster.jpg
```

(The `<video>` tag tolerates an empty file at build time; runtime simply has no playback. Real assets ship in a follow-up.)

- [ ] **Step 4: Type-check + lint**

Run:
```bash
cd frontend && npm run type-check && npm run lint
```

Expected: exit 0.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/ui/VideoBackground.tsx frontend/src/components/marketing/Footer.tsx frontend/public/videos/
git commit -m "feat(frontend): liquid-glass footer with video bg + VideoBackground primitive"
```

---

### Task 11: LiquidGlassButton primitive

**Files:**
- Create: `frontend/src/components/ui/LiquidGlassButton.tsx`

- [ ] **Step 1: Write LiquidGlassButton.tsx**

Create:

```tsx
"use client";

import { forwardRef } from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const variants = cva(
  "inline-flex items-center justify-center gap-2 rounded-full font-medium transition-all liquid-glass focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50 disabled:pointer-events-none",
  {
    variants: {
      tone: {
        primary: "bg-primary text-primary-foreground hover:opacity-95",
        ghost: "bg-card/40 text-foreground hover:bg-card/70",
        dark: "bg-foreground text-background hover:opacity-90",
      },
      size: {
        sm: "h-9 px-4 text-sm",
        md: "h-11 px-6 text-sm",
        lg: "h-12 px-7 text-base",
      },
    },
    defaultVariants: { tone: "primary", size: "md" },
  },
);

export type LiquidGlassButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> &
  VariantProps<typeof variants>;

export const LiquidGlassButton = forwardRef<HTMLButtonElement, LiquidGlassButtonProps>(
  ({ className, tone, size, ...props }, ref) => (
    <button ref={ref} className={cn(variants({ tone, size }), className)} {...props} />
  ),
);
LiquidGlassButton.displayName = "LiquidGlassButton";
```

- [ ] **Step 2: Type-check + lint**

Run:
```bash
cd frontend && npm run type-check && npm run lint
```

Expected: exit 0.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/ui/LiquidGlassButton.tsx
git commit -m "feat(frontend): LiquidGlassButton CTA primitive with cva variants"
```

---

### Task 12: MarqueeRow component

**Files:**
- Create: `frontend/src/components/marketing/MarqueeRow.tsx`

- [ ] **Step 1: Write MarqueeRow.tsx**

Create:

```tsx
type Props = {
  items: string[];
  direction?: "left" | "right";
  className?: string;
};

export function MarqueeRow({ items, direction = "left", className = "" }: Props) {
  const doubled = [...items, ...items];
  const anim = direction === "left" ? "animate-marquee-left" : "animate-marquee-right";
  return (
    <div className={`relative overflow-hidden border-y border-border/60 bg-card/40 py-4 ${className}`}>
      <div className={`flex w-max gap-12 ${anim}`}>
        {doubled.map((item, i) => (
          <span key={i} className="whitespace-nowrap text-sm text-muted-foreground">
            {item}
          </span>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Type-check**

Run:
```bash
cd frontend && npm run type-check
```

Expected: exit 0.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/marketing/MarqueeRow.tsx
git commit -m "feat(frontend): marquee row component for feature chips/logos"
```

---

### Task 13: HeroA section (badge + staggered headline + CTA)

**Files:**
- Create: `frontend/src/components/marketing/HeroA.tsx`

- [ ] **Step 1: Write HeroA.tsx**

Create:

```tsx
"use client";

import Link from "next/link";
import { motion } from "motion/react";
import { fadeUp, stagger } from "@/lib/motion-variants";
import { LiquidGlassButton } from "@/components/ui/LiquidGlassButton";

const HEADLINE_WORDS = ["Apply", "smarter.", "Tailor", "faster."];
const HIGHLIGHT = "Get noticed.";

export function HeroA() {
  return (
    <section className="relative isolate overflow-hidden gradient-mesh-light noise-overlay pt-16">
      <div className="relative mx-auto max-w-6xl px-6 pb-32 pt-20 text-center">
        <motion.span
          initial="hidden"
          animate="show"
          variants={fadeUp}
          className="inline-flex items-center gap-2 rounded-full border border-border bg-card/70 px-4 py-1.5 text-xs font-medium text-muted-foreground"
        >
          <span className="inline-block h-1.5 w-1.5 rounded-full bg-primary" />
          AI job-search copilot for students and freshers
        </motion.span>

        <motion.h1
          initial="hidden"
          animate="show"
          variants={stagger}
          className="mx-auto mt-8 max-w-4xl text-balance text-5xl font-medium leading-tight tracking-tight md:text-7xl"
        >
          {HEADLINE_WORDS.map((w, i) => (
            <motion.span key={i} variants={fadeUp} className="inline-block">
              {w}&nbsp;
            </motion.span>
          ))}
          <motion.span variants={fadeUp} className="font-display text-primary">
            {HIGHLIGHT}
          </motion.span>
        </motion.h1>

        <motion.p
          initial="hidden"
          animate="show"
          variants={fadeUp}
          className="mx-auto mt-6 max-w-2xl text-base text-muted-foreground md:text-lg"
        >
          Resume tailoring, job matching, auto-apply, and follow-up — all powered by your own API keys.
        </motion.p>

        <motion.div
          initial="hidden"
          animate="show"
          variants={fadeUp}
          className="mt-10 flex items-center justify-center gap-3"
        >
          <Link href="/register">
            <LiquidGlassButton tone="primary" size="lg">
              Start free
            </LiquidGlassButton>
          </Link>
          <Link href="/#demo">
            <LiquidGlassButton tone="ghost" size="lg">
              Watch demo
            </LiquidGlassButton>
          </Link>
        </motion.div>

        <motion.div
          initial="hidden"
          animate="show"
          variants={fadeUp}
          className="relative mx-auto mt-20 aspect-[16/9] max-w-5xl overflow-hidden rounded-3xl border border-border bg-card shadow-2xl"
        >
          <div className="flex h-full items-center justify-center text-muted-foreground">
            Product preview
          </div>
        </motion.div>
      </div>
    </section>
  );
}
```

- [ ] **Step 2: Type-check**

Run:
```bash
cd frontend && npm run type-check
```

Expected: exit 0.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/marketing/HeroA.tsx
git commit -m "feat(frontend): HeroA — staggered headline, CTA, preview frame"
```

---

### Task 14: HowItWorks, FeaturesGrid, HeroB, PricingSection

**Files:**
- Create: `frontend/src/components/marketing/HowItWorks.tsx`
- Create: `frontend/src/components/marketing/FeaturesGrid.tsx`
- Create: `frontend/src/components/marketing/HeroB.tsx`
- Create: `frontend/src/components/ui/FeatureCard.tsx`
- Create: `frontend/src/components/ui/PricingCard.tsx`
- Create: `frontend/src/components/marketing/PricingSection.tsx`

- [ ] **Step 1: Write FeatureCard.tsx**

Create `frontend/src/components/ui/FeatureCard.tsx`:

```tsx
"use client";

import { motion } from "motion/react";
import { cardHover } from "@/lib/motion-variants";

export function FeatureCard({
  icon,
  title,
  description,
}: {
  icon: React.ReactNode;
  title: string;
  description: string;
}) {
  return (
    <motion.div
      {...cardHover}
      className="relative overflow-hidden rounded-3xl border border-white/10 bg-[#0d0d12] p-8 text-left"
    >
      <div className="mb-6 inline-flex h-11 w-11 items-center justify-center rounded-2xl bg-primary/15 text-primary">
        {icon}
      </div>
      <div className="text-lg font-medium text-white">{title}</div>
      <p className="mt-2 text-sm text-white/60">{description}</p>
    </motion.div>
  );
}
```

- [ ] **Step 2: Write FeaturesGrid.tsx**

Create `frontend/src/components/marketing/FeaturesGrid.tsx`:

```tsx
import { FileText, Bot, Target, KanbanSquare, Mail, KeyRound } from "lucide-react";
import { FeatureCard } from "@/components/ui/FeatureCard";

const FEATURES = [
  {
    icon: <FileText className="h-5 w-5" />,
    title: "Resume Intelligence",
    description: "ATS scoring, keyword coverage, and bullet rewrites tailored to each job.",
  },
  {
    icon: <Bot className="h-5 w-5" />,
    title: "AI Orchestrator",
    description: "A supervisor agent routes tasks across Resume, Job, Email, and Follow-up agents.",
  },
  {
    icon: <Target className="h-5 w-5" />,
    title: "Job Match",
    description: "Semantic search over LinkedIn, Naukri, and curated boards with match percentages.",
  },
  {
    icon: <KanbanSquare className="h-5 w-5" />,
    title: "Application Tracker",
    description: "Kanban board for every stage: Saved → Applied → Interview → Offer.",
  },
  {
    icon: <Mail className="h-5 w-5" />,
    title: "Email Drafts",
    description: "Gmail-connected agent drafts personalized follow-ups — you stay in control.",
  },
  {
    icon: <KeyRound className="h-5 w-5" />,
    title: "BYOK Models",
    description: "OpenAI, Anthropic, Gemini, Groq, Ollama. Your keys, your costs, your privacy.",
  },
];

export function FeaturesGrid() {
  return (
    <section id="features" className="bg-[#0a0a0a] py-28 text-white">
      <div className="mx-auto max-w-6xl px-6">
        <div className="mb-14 max-w-2xl">
          <div className="text-sm text-white/50">Features</div>
          <h2 className="mt-2 text-4xl font-medium md:text-5xl">
            Everything you need to land your first role.
          </h2>
        </div>
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((f) => (
            <FeatureCard key={f.title} {...f} />
          ))}
        </div>
      </div>
    </section>
  );
}
```

- [ ] **Step 3: Write HowItWorks.tsx**

Create `frontend/src/components/marketing/HowItWorks.tsx`:

```tsx
const STEPS = [
  { n: "01", title: "Upload your resume", body: "Drop a PDF or DOCX. We parse skills, projects, and experience." },
  { n: "02", title: "Add a target role", body: "Tell us the role, locations, and seniority. We build a job search plan." },
  { n: "03", title: "Agents go to work", body: "Resume tailoring, job search, application drafts — all in parallel." },
  { n: "04", title: "Approve and send", body: "You stay in the loop. Every email and apply goes through your approval." },
];

export function HowItWorks() {
  return (
    <section id="how" className="relative bg-[#070612] py-28 text-white">
      <div className="mx-auto max-w-6xl px-6">
        <div className="mb-14 max-w-2xl">
          <div className="text-sm text-white/50">How it works</div>
          <h2 className="mt-2 text-4xl font-medium md:text-5xl">From resume to interview in 4 steps.</h2>
        </div>
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
          {STEPS.map((s) => (
            <div key={s.n} className="rounded-3xl border border-white/10 bg-white/[0.02] p-6 liquid-glass">
              <div className="text-xs text-primary">{s.n}</div>
              <div className="mt-3 text-lg font-medium">{s.title}</div>
              <p className="mt-2 text-sm text-white/60">{s.body}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
```

- [ ] **Step 4: Write HeroB.tsx**

Create `frontend/src/components/marketing/HeroB.tsx`:

```tsx
export function HeroB() {
  return (
    <section className="border-y border-border bg-card/50 py-24">
      <div className="mx-auto max-w-5xl px-6 text-center">
        <h2 className="text-balance text-5xl font-medium leading-tight md:text-7xl">
          <span className="font-display text-primary">Craft</span> the career you want.
        </h2>
        <p className="mx-auto mt-5 max-w-xl text-muted-foreground">
          Built for students, freshers, and career-switchers who refuse to send the same resume twice.
        </p>
        <div className="mt-10 flex flex-wrap items-center justify-center gap-x-10 gap-y-4 text-sm text-muted-foreground">
          <span>Trusted by students at</span>
          <span className="opacity-80">IIT</span>
          <span className="opacity-80">NIT</span>
          <span className="opacity-80">BITS</span>
          <span className="opacity-80">IIIT</span>
          <span className="opacity-80">VIT</span>
        </div>
      </div>
    </section>
  );
}
```

- [ ] **Step 5: Write PricingCard.tsx**

Create `frontend/src/components/ui/PricingCard.tsx`:

```tsx
"use client";

import { Check } from "lucide-react";
import Link from "next/link";
import { motion } from "motion/react";
import { cardHover } from "@/lib/motion-variants";
import { LiquidGlassButton } from "./LiquidGlassButton";

export type PricingTier = {
  name: string;
  price: string;
  cadence?: string;
  description: string;
  features: string[];
  ctaHref: string;
  ctaLabel: string;
  highlighted?: boolean;
};

export function PricingCard({ tier }: { tier: PricingTier }) {
  return (
    <motion.div
      {...cardHover}
      className={`flex flex-col rounded-3xl border p-8 ${
        tier.highlighted
          ? "border-primary/40 bg-primary/[0.06] shadow-xl"
          : "border-border bg-card"
      }`}
    >
      <div className="text-sm font-medium text-muted-foreground">{tier.name}</div>
      <div className="mt-4 flex items-baseline gap-1">
        <span className="text-5xl font-medium">{tier.price}</span>
        {tier.cadence && <span className="text-sm text-muted-foreground">/{tier.cadence}</span>}
      </div>
      <p className="mt-4 text-sm text-muted-foreground">{tier.description}</p>
      <ul className="mt-8 space-y-3">
        {tier.features.map((f) => (
          <li key={f} className="flex items-start gap-2 text-sm">
            <Check className="mt-0.5 h-4 w-4 text-success" />
            <span>{f}</span>
          </li>
        ))}
      </ul>
      <div className="mt-auto pt-8">
        <Link href={tier.ctaHref} className="block">
          <LiquidGlassButton
            tone={tier.highlighted ? "primary" : "ghost"}
            size="md"
            className="w-full"
          >
            {tier.ctaLabel}
          </LiquidGlassButton>
        </Link>
      </div>
    </motion.div>
  );
}
```

- [ ] **Step 6: Write PricingSection.tsx**

Create `frontend/src/components/marketing/PricingSection.tsx`:

```tsx
import { PricingCard, type PricingTier } from "@/components/ui/PricingCard";

const TIERS: PricingTier[] = [
  {
    name: "Free",
    price: "$0",
    cadence: "forever",
    description: "Get started with resume tools and 5 AI runs per week.",
    features: ["Resume ATS scoring", "Job match preview", "5 agent runs / week", "BYOK API keys"],
    ctaHref: "/register",
    ctaLabel: "Start free",
  },
  {
    name: "Pro",
    price: "$12",
    cadence: "month",
    description: "Full automation for an active job hunt.",
    features: [
      "Unlimited agent runs",
      "LinkedIn + Naukri search",
      "Email drafting + send",
      "Follow-up sequencing",
      "Application kanban",
    ],
    ctaHref: "/register?plan=pro",
    ctaLabel: "Go Pro",
    highlighted: true,
  },
  {
    name: "Team",
    price: "Custom",
    description: "For bootcamps and university placement cells.",
    features: ["Everything in Pro", "Cohort management", "Bulk seats", "Shared templates", "Priority support"],
    ctaHref: "/contact",
    ctaLabel: "Talk to us",
  },
];

export function PricingSection() {
  return (
    <section id="pricing" className="bg-background py-28">
      <div className="mx-auto max-w-6xl px-6">
        <div className="mb-14 text-center">
          <div className="text-sm text-muted-foreground">Pricing</div>
          <h2 className="mt-2 text-4xl font-medium md:text-5xl">Simple plans. Your keys. Your costs.</h2>
        </div>
        <div className="grid gap-6 md:grid-cols-3">
          {TIERS.map((t) => (
            <PricingCard key={t.name} tier={t} />
          ))}
        </div>
      </div>
    </section>
  );
}
```

- [ ] **Step 7: Type-check + lint**

Run:
```bash
cd frontend && npm run type-check && npm run lint
```

Expected: exit 0.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/components/marketing/ frontend/src/components/ui/FeatureCard.tsx frontend/src/components/ui/PricingCard.tsx
git commit -m "feat(frontend): marketing sections — HowItWorks, FeaturesGrid, HeroB, Pricing"
```

---

### Task 15: Wire `/` landing page

**Files:**
- Create: `frontend/src/app/(marketing)/page.tsx`
- Delete: `frontend/src/app/page.tsx` (if exists)

- [ ] **Step 1: Check for existing root page**

Run:
```bash
ls frontend/src/app/page.tsx 2>/dev/null && echo "exists" || echo "not present"
```

If exists, delete it (we replace via route group):
```bash
rm frontend/src/app/page.tsx
```

- [ ] **Step 2: Write `(marketing)/page.tsx`**

Create:

```tsx
import { HeroA } from "@/components/marketing/HeroA";
import { MarqueeRow } from "@/components/marketing/MarqueeRow";
import { HeroB } from "@/components/marketing/HeroB";
import { HowItWorks } from "@/components/marketing/HowItWorks";
import { FeaturesGrid } from "@/components/marketing/FeaturesGrid";
import { PricingSection } from "@/components/marketing/PricingSection";

const CHIPS = [
  "Resume AI",
  "Job Match",
  "Email Agent",
  "Application Tracker",
  "BYOK Models",
  "ATS Optimizer",
  "Follow-up Agent",
];

export default function Home() {
  return (
    <>
      <HeroA />
      <MarqueeRow items={CHIPS} />
      <HeroB />
      <HowItWorks />
      <FeaturesGrid />
      <PricingSection />
    </>
  );
}
```

- [ ] **Step 3: Dev render check**

Run:
```bash
cd frontend && npm run dev
```

Wait ~5s, then in another shell:
```bash
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:3000/
```

Expected: `200`. Kill dev server.

- [ ] **Step 4: Commit**

```bash
git add "frontend/src/app/(marketing)/page.tsx"
git rm -f frontend/src/app/page.tsx 2>/dev/null || true
git commit -m "feat(frontend): landing page — hero, marquee, how, features, pricing"
```

---

### Task 16: `/pricing` page + FaqAccordion

**Files:**
- Create: `frontend/src/components/marketing/FaqAccordion.tsx`
- Create: `frontend/src/app/(marketing)/pricing/page.tsx`

- [ ] **Step 1: Write FaqAccordion.tsx**

Create `frontend/src/components/marketing/FaqAccordion.tsx`:

```tsx
"use client";

import * as Accordion from "@radix-ui/react-accordion";
import { ChevronDown } from "lucide-react";

const FAQ: { q: string; a: string }[] = [
  {
    q: "Do I need my own API keys?",
    a: "Yes. CareerCraft is BYOK — you bring OpenAI, Anthropic, Gemini, Groq, or a local Ollama. Your keys are encrypted at rest.",
  },
  {
    q: "Will you apply to jobs without my approval?",
    a: "No. Every email and application requires explicit approval in the UI. There is no autopilot for outbound actions.",
  },
  {
    q: "Does it work with LinkedIn?",
    a: "Yes. Browser automation runs with human-like delays. You'll see every action before it submits.",
  },
  {
    q: "How is my data stored?",
    a: "Resumes are stored as pgvector embeddings tied to your user ID. API keys are AES-256 encrypted. You can delete everything at any time.",
  },
];

export function FaqAccordion() {
  return (
    <Accordion.Root type="single" collapsible className="mx-auto max-w-3xl divide-y divide-border rounded-3xl border border-border bg-card">
      {FAQ.map((item, i) => (
        <Accordion.Item key={i} value={`q${i}`}>
          <Accordion.Header>
            <Accordion.Trigger className="group flex w-full items-center justify-between px-6 py-5 text-left text-base font-medium">
              {item.q}
              <ChevronDown className="h-4 w-4 transition-transform group-data-[state=open]:rotate-180" />
            </Accordion.Trigger>
          </Accordion.Header>
          <Accordion.Content className="px-6 pb-5 text-sm text-muted-foreground">
            {item.a}
          </Accordion.Content>
        </Accordion.Item>
      ))}
    </Accordion.Root>
  );
}
```

- [ ] **Step 2: Write `(marketing)/pricing/page.tsx`**

Create:

```tsx
import { PricingSection } from "@/components/marketing/PricingSection";
import { FaqAccordion } from "@/components/marketing/FaqAccordion";

export default function PricingPage() {
  return (
    <>
      <section className="bg-background pt-20 pb-6 text-center">
        <h1 className="mx-auto max-w-3xl px-6 text-5xl font-medium tracking-tight md:text-6xl">
          Simple <span className="font-display text-primary">pricing</span>.
        </h1>
        <p className="mx-auto mt-4 max-w-xl px-6 text-muted-foreground">
          Pay for the platform, not the tokens. Your keys cover the LLM costs.
        </p>
      </section>
      <PricingSection />
      <section className="bg-background pb-28">
        <div className="mx-auto max-w-6xl px-6">
          <div className="mb-10 text-center">
            <div className="text-sm text-muted-foreground">FAQ</div>
            <h2 className="mt-2 text-3xl font-medium md:text-4xl">Common questions</h2>
          </div>
          <FaqAccordion />
        </div>
      </section>
    </>
  );
}
```

- [ ] **Step 3: Dev render check**

Run:
```bash
cd frontend && npm run dev
```

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:3000/pricing
```

Expected: `200`. Kill dev server.

- [ ] **Step 4: Commit**

```bash
git add "frontend/src/app/(marketing)/pricing/page.tsx" frontend/src/components/marketing/FaqAccordion.tsx
git commit -m "feat(frontend): /pricing page with tiers and FAQ accordion"
```

---

# Phase 3 — App Shell + Dashboard

Owns: `(app)` route group, dark sidebar, topbar, dashboard, MetricCard.

---

### Task 17: App route group layout + delete old Sidebar

**Files:**
- Create: `frontend/src/app/(app)/layout.tsx`
- Delete: `frontend/src/components/layout/Sidebar.tsx`
- Modify: `frontend/src/components/layout/Providers.tsx` (remove Sidebar export if present)

- [ ] **Step 1: Write `(app)/layout.tsx`**

Create:

```tsx
import { ThemeProvider } from "@/components/theme/ThemeProvider";
import { ThemeScript } from "@/components/theme/theme-script";
import { AppShell } from "@/components/layout/AppShell";

export default function AppRouteLayout({ children }: { children: React.ReactNode }) {
  return (
    <ThemeProvider zoneDefault="dark">
      <ThemeScript zoneDefault="dark" />
      <AppShell>{children}</AppShell>
    </ThemeProvider>
  );
}
```

- [ ] **Step 2: Delete old Sidebar.tsx**

Run:
```bash
git rm frontend/src/components/layout/Sidebar.tsx
```

- [ ] **Step 3: Open Providers.tsx, remove any Sidebar export**

Read `frontend/src/components/layout/Providers.tsx`. If it imports or re-exports `Sidebar`, remove those lines. Save. (No code shown because content depends on current state — if Providers does not reference Sidebar, skip this step.)

- [ ] **Step 4: Type-check (will fail until AppShell exists). Commit layout + deletion**

```bash
git add "frontend/src/app/(app)/layout.tsx" frontend/src/components/layout/
git commit -m "feat(frontend): app route group layout (dark default), drop legacy Sidebar"
```

---

### Task 18: AppSidebar

**Files:**
- Create: `frontend/src/components/layout/AppSidebar.tsx`

- [ ] **Step 1: Write AppSidebar.tsx**

Create:

```tsx
"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  FileText,
  Briefcase,
  Bot,
  Mail,
  Settings,
  Sparkles,
} from "lucide-react";

const ITEMS = [
  { href: "/dashboard", icon: LayoutDashboard, label: "Dashboard" },
  { href: "/resume", icon: FileText, label: "Resume" },
  { href: "/applications", icon: Briefcase, label: "Applications" },
  { href: "/agents", icon: Bot, label: "Agents" },
  { href: "/email", icon: Mail, label: "Email" },
  { href: "/settings/models", icon: Settings, label: "Settings" },
];

export function AppSidebar() {
  const pathname = usePathname();
  return (
    <aside className="hidden h-screen w-64 shrink-0 border-r border-border bg-card/40 px-4 py-6 backdrop-blur md:flex md:flex-col">
      <Link href="/" className="mb-8 flex items-center gap-2 px-2 text-base font-semibold">
        <span className="inline-flex h-7 w-7 items-center justify-center rounded-full bg-primary text-primary-foreground">
          <Sparkles className="h-4 w-4" />
        </span>
        CareerCraft AI
      </Link>
      <nav className="flex-1 space-y-1">
        {ITEMS.map((item) => {
          const Icon = item.icon;
          const active = pathname === item.href || pathname.startsWith(item.href + "/");
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex items-center gap-3 rounded-2xl px-3 py-2 text-sm transition-colors ${
                active
                  ? "bg-primary/15 text-foreground"
                  : "text-muted-foreground hover:bg-card hover:text-foreground"
              }`}
            >
              <Icon className="h-4 w-4" />
              {item.label}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
```

- [ ] **Step 2: Type-check**

Run:
```bash
cd frontend && npm run type-check
```

Expected: passes when AppShell (Task 20) compiles. Skip until then.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/layout/AppSidebar.tsx
git commit -m "feat(frontend): AppSidebar dark glass nav"
```

---

### Task 19: AppTopbar

**Files:**
- Create: `frontend/src/components/layout/AppTopbar.tsx`

- [ ] **Step 1: Write AppTopbar.tsx**

Create:

```tsx
"use client";

import { UserButton } from "@clerk/nextjs";
import { Bell, Search } from "lucide-react";
import { ThemeToggle } from "@/components/theme/ThemeToggle";

export function AppTopbar() {
  return (
    <header className="sticky top-0 z-30 flex h-16 items-center gap-4 border-b border-border bg-background/70 px-6 backdrop-blur">
      <div className="flex flex-1 items-center gap-2 rounded-full border border-border bg-card/40 px-4 py-2 max-w-md">
        <Search className="h-4 w-4 text-muted-foreground" />
        <input
          placeholder="Search jobs, applications, agents…"
          className="flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground"
        />
      </div>
      <button
        type="button"
        aria-label="Notifications"
        className="inline-flex h-9 w-9 items-center justify-center rounded-full border border-border bg-card/60 text-foreground hover:bg-card"
      >
        <Bell className="h-4 w-4" />
      </button>
      <ThemeToggle />
      <UserButton afterSignOutUrl="/" />
    </header>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/layout/AppTopbar.tsx
git commit -m "feat(frontend): AppTopbar with search, notifications, user button"
```

---

### Task 20: AppShell

**Files:**
- Create: `frontend/src/components/layout/AppShell.tsx`

- [ ] **Step 1: Write AppShell.tsx**

Create:

```tsx
import { AppSidebar } from "./AppSidebar";
import { AppTopbar } from "./AppTopbar";

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen bg-background text-foreground">
      <AppSidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <AppTopbar />
        <main className="flex-1 px-6 py-8 md:px-8">{children}</main>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Type-check + lint**

Run:
```bash
cd frontend && npm run type-check && npm run lint
```

Expected: exit 0.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/layout/AppShell.tsx
git commit -m "feat(frontend): AppShell wrapping sidebar + topbar"
```

---

### Task 21: MetricCard + EmptyState + LoadingState + ErrorState primitives

**Files:**
- Create: `frontend/src/components/ui/MetricCard.tsx`
- Create: `frontend/src/components/ui/EmptyState.tsx`
- Create: `frontend/src/components/ui/LoadingState.tsx`
- Create: `frontend/src/components/ui/ErrorState.tsx`

- [ ] **Step 1: Write MetricCard.tsx**

Create:

```tsx
"use client";

import { ArrowDownRight, ArrowUpRight } from "lucide-react";
import { motion } from "motion/react";
import { cardHover } from "@/lib/motion-variants";

type Props = {
  label: string;
  value: string | number;
  trend?: { delta: string; direction: "up" | "down" };
  icon?: React.ReactNode;
};

export function MetricCard({ label, value, trend, icon }: Props) {
  return (
    <motion.div
      {...cardHover}
      className="rounded-3xl border border-border bg-card/60 p-6 backdrop-blur"
    >
      <div className="flex items-center justify-between">
        <span className="text-sm text-muted-foreground">{label}</span>
        {icon && <div className="text-muted-foreground">{icon}</div>}
      </div>
      <div className="mt-4 text-3xl font-medium">{value}</div>
      {trend && (
        <div className={`mt-2 inline-flex items-center gap-1 text-xs ${
          trend.direction === "up" ? "text-success" : "text-danger"
        }`}>
          {trend.direction === "up" ? <ArrowUpRight className="h-3 w-3" /> : <ArrowDownRight className="h-3 w-3" />}
          {trend.delta}
        </div>
      )}
    </motion.div>
  );
}
```

- [ ] **Step 2: Write EmptyState.tsx**

Create:

```tsx
import type { ReactNode } from "react";

export function EmptyState({
  icon,
  title,
  description,
  action,
}: {
  icon?: ReactNode;
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center rounded-3xl border border-dashed border-border bg-card/30 px-6 py-16 text-center">
      {icon && <div className="mb-4 text-muted-foreground">{icon}</div>}
      <div className="text-lg font-medium">{title}</div>
      {description && <p className="mt-2 max-w-md text-sm text-muted-foreground">{description}</p>}
      {action && <div className="mt-6">{action}</div>}
    </div>
  );
}
```

- [ ] **Step 3: Write LoadingState.tsx**

Create:

```tsx
export function LoadingState({ rows = 3 }: { rows?: number }) {
  return (
    <div className="space-y-3">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="h-16 animate-pulse rounded-3xl bg-card/40" />
      ))}
    </div>
  );
}
```

- [ ] **Step 4: Write ErrorState.tsx**

Create:

```tsx
import { AlertTriangle } from "lucide-react";
import { LiquidGlassButton } from "./LiquidGlassButton";

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-3xl border border-danger/30 bg-danger/5 px-6 py-12 text-center">
      <AlertTriangle className="mb-3 h-6 w-6 text-danger" />
      <div className="text-sm text-foreground">{message}</div>
      {onRetry && (
        <div className="mt-4">
          <LiquidGlassButton tone="ghost" size="sm" onClick={onRetry}>
            Retry
          </LiquidGlassButton>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 5: Type-check + lint**

Run:
```bash
cd frontend && npm run type-check && npm run lint
```

Expected: exit 0.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/ui/MetricCard.tsx frontend/src/components/ui/EmptyState.tsx frontend/src/components/ui/LoadingState.tsx frontend/src/components/ui/ErrorState.tsx
git commit -m "feat(frontend): metric/empty/loading/error state primitives"
```

---

### Task 22: ResumeScoreCard + JobMatchCard + AgentStatusCard + ApprovalCard

**Files:**
- Create: `frontend/src/components/ui/ResumeScoreCard.tsx`
- Create: `frontend/src/components/ui/JobMatchCard.tsx`
- Create: `frontend/src/components/agents/AgentStatusCard.tsx`
- Create: `frontend/src/components/agents/ApprovalCard.tsx`

- [ ] **Step 1: Write ResumeScoreCard.tsx**

Create:

```tsx
"use client";

import { motion } from "motion/react";
import { cardHover } from "@/lib/motion-variants";

type Props = {
  atsScore: number;
  keywordCoverage: number;
  missingKeywords: string[];
};

export function ResumeScoreCard({ atsScore, keywordCoverage, missingKeywords }: Props) {
  return (
    <motion.div {...cardHover} className="rounded-3xl border border-border bg-card/60 p-6">
      <div className="flex items-baseline justify-between">
        <div>
          <div className="text-sm text-muted-foreground">Resume score</div>
          <div className="mt-2 text-4xl font-medium">{atsScore}/100</div>
        </div>
        <div className="text-right text-sm text-muted-foreground">
          <div>Keyword coverage</div>
          <div className="mt-1 font-medium text-foreground">{keywordCoverage}%</div>
        </div>
      </div>
      <div className="mt-4 h-2 w-full overflow-hidden rounded-full bg-muted">
        <div className="h-full bg-primary" style={{ width: `${keywordCoverage}%` }} />
      </div>
      {missingKeywords.length > 0 && (
        <div className="mt-6">
          <div className="text-xs text-muted-foreground">Missing keywords</div>
          <div className="mt-2 flex flex-wrap gap-2">
            {missingKeywords.slice(0, 8).map((k) => (
              <span key={k} className="rounded-full border border-border bg-card px-3 py-1 text-xs">
                {k}
              </span>
            ))}
          </div>
        </div>
      )}
    </motion.div>
  );
}
```

- [ ] **Step 2: Write JobMatchCard.tsx**

Create:

```tsx
"use client";

import Link from "next/link";
import { motion } from "motion/react";
import { cardHover } from "@/lib/motion-variants";

type Props = {
  jobs: { id: string; company: string; role: string; matchPercent: number; location?: string }[];
};

export function JobMatchCard({ jobs }: Props) {
  return (
    <motion.div {...cardHover} className="rounded-3xl border border-border bg-card/60 p-6">
      <div className="flex items-center justify-between">
        <div className="text-sm text-muted-foreground">Top job matches</div>
        <Link href="/applications" className="text-xs text-primary hover:underline">
          View all
        </Link>
      </div>
      <ul className="mt-4 space-y-3">
        {jobs.slice(0, 4).map((j) => (
          <li key={j.id} className="flex items-center justify-between rounded-2xl border border-border/60 bg-card/40 px-4 py-3">
            <div>
              <div className="text-sm font-medium">{j.role}</div>
              <div className="text-xs text-muted-foreground">
                {j.company}
                {j.location ? ` · ${j.location}` : ""}
              </div>
            </div>
            <span className="rounded-full bg-primary/15 px-2.5 py-1 text-xs font-medium text-primary">
              {j.matchPercent}%
            </span>
          </li>
        ))}
      </ul>
    </motion.div>
  );
}
```

- [ ] **Step 3: Write AgentStatusCard.tsx**

Create:

```tsx
"use client";

import { motion } from "motion/react";
import { cardHover } from "@/lib/motion-variants";

export type AgentRunStatus = "queued" | "running" | "succeeded" | "failed" | "awaiting_approval";

const STATUS_STYLES: Record<AgentRunStatus, string> = {
  queued: "bg-muted text-muted-foreground",
  running: "bg-primary/15 text-primary",
  succeeded: "bg-success/15 text-success",
  failed: "bg-danger/15 text-danger",
  awaiting_approval: "bg-warning/15 text-warning",
};

type Props = {
  agentName: string;
  status: AgentRunStatus;
  latestMessage?: string;
  startedAt?: string;
};

export function AgentStatusCard({ agentName, status, latestMessage, startedAt }: Props) {
  return (
    <motion.div {...cardHover} className="rounded-3xl border border-border bg-card/60 p-5">
      <div className="flex items-center justify-between">
        <div className="text-sm font-medium">{agentName}</div>
        <span className={`rounded-full px-2 py-0.5 text-xs ${STATUS_STYLES[status]}`}>
          {status.replace("_", " ")}
        </span>
      </div>
      {latestMessage && <p className="mt-3 text-sm text-muted-foreground line-clamp-2">{latestMessage}</p>}
      {startedAt && <div className="mt-2 text-xs text-muted-foreground">Started {startedAt}</div>}
    </motion.div>
  );
}
```

- [ ] **Step 4: Write ApprovalCard.tsx**

Create:

```tsx
"use client";

import { motion } from "motion/react";
import { cardHover } from "@/lib/motion-variants";
import { LiquidGlassButton } from "@/components/ui/LiquidGlassButton";

type Props = {
  title: string;
  summary: string;
  onApprove: () => void;
  onReject: () => void;
};

export function ApprovalCard({ title, summary, onApprove, onReject }: Props) {
  return (
    <motion.div {...cardHover} className="rounded-3xl border border-warning/30 bg-warning/5 p-5">
      <div className="text-sm font-medium">{title}</div>
      <p className="mt-2 text-sm text-muted-foreground">{summary}</p>
      <div className="mt-4 flex gap-2">
        <LiquidGlassButton tone="primary" size="sm" onClick={onApprove}>
          Approve
        </LiquidGlassButton>
        <LiquidGlassButton tone="ghost" size="sm" onClick={onReject}>
          Reject
        </LiquidGlassButton>
      </div>
    </motion.div>
  );
}
```

- [ ] **Step 5: Type-check + lint**

Run:
```bash
cd frontend && npm run type-check && npm run lint
```

Expected: exit 0.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/ui/ResumeScoreCard.tsx frontend/src/components/ui/JobMatchCard.tsx frontend/src/components/agents/AgentStatusCard.tsx frontend/src/components/agents/ApprovalCard.tsx
git commit -m "feat(frontend): score/match/agent-status/approval display primitives"
```

---

### Task 23: `/dashboard` page

**Files:**
- Create: `frontend/src/app/(app)/dashboard/page.tsx`
- Delete: `frontend/src/app/dashboard/page.tsx` (old)

- [ ] **Step 1: Delete old dashboard**

```bash
git rm frontend/src/app/dashboard/page.tsx
```

- [ ] **Step 2: Write `(app)/dashboard/page.tsx`**

Create:

```tsx
"use client";

import { motion } from "motion/react";
import { Briefcase, Calendar, Target, Bell } from "lucide-react";
import { fadeUp, stagger } from "@/lib/motion-variants";
import { MetricCard } from "@/components/ui/MetricCard";
import { ResumeScoreCard } from "@/components/ui/ResumeScoreCard";
import { JobMatchCard } from "@/components/ui/JobMatchCard";
import { AgentStatusCard } from "@/components/agents/AgentStatusCard";
import { ApprovalCard } from "@/components/agents/ApprovalCard";

// TODO Phase 4: replace mock data with TanStack Query hooks that call apiClient.
const METRICS = [
  { label: "Applications", value: 24, trend: { delta: "+4 this week", direction: "up" as const }, icon: <Briefcase className="h-4 w-4" /> },
  { label: "Interviews", value: 3, trend: { delta: "+1 this week", direction: "up" as const }, icon: <Calendar className="h-4 w-4" /> },
  { label: "Avg match", value: "78%", trend: { delta: "+5%", direction: "up" as const }, icon: <Target className="h-4 w-4" /> },
  { label: "Follow-ups due", value: 5, icon: <Bell className="h-4 w-4" /> },
];

const JOBS = [
  { id: "1", company: "Acme Co", role: "Frontend Engineer", matchPercent: 92, location: "Remote" },
  { id: "2", company: "BetaCorp", role: "Full-stack Developer", matchPercent: 87, location: "Bangalore" },
  { id: "3", company: "Gamma", role: "Junior SDE", matchPercent: 81, location: "Hyderabad" },
];

export default function DashboardPage() {
  return (
    <motion.div initial="hidden" animate="show" variants={stagger} className="space-y-8">
      <motion.div variants={fadeUp}>
        <div className="text-sm text-muted-foreground">{new Date().toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric" })}</div>
        <h1 className="mt-1 text-3xl font-medium">Welcome back.</h1>
      </motion.div>

      <motion.div variants={fadeUp} className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {METRICS.map((m) => (
          <MetricCard key={m.label} {...m} />
        ))}
      </motion.div>

      <motion.div variants={fadeUp} className="grid gap-4 lg:grid-cols-2">
        <ResumeScoreCard atsScore={78} keywordCoverage={64} missingKeywords={["TypeScript", "AWS", "Docker", "CI/CD"]} />
        <JobMatchCard jobs={JOBS} />
      </motion.div>

      <motion.div variants={fadeUp} className="grid gap-4 lg:grid-cols-2">
        <div className="space-y-4">
          <div className="text-sm text-muted-foreground">Recent agent runs</div>
          <AgentStatusCard agentName="Resume Agent" status="succeeded" latestMessage="Tailored resume for BetaCorp Full-stack role." startedAt="2 min ago" />
          <AgentStatusCard agentName="Job Search Agent" status="running" latestMessage="Scanning LinkedIn — 12 leads so far." startedAt="just now" />
        </div>
        <div className="space-y-4">
          <div className="text-sm text-muted-foreground">Pending approvals</div>
          <ApprovalCard
            title="Send follow-up to Acme recruiter"
            summary="Subject: Following up on Frontend Engineer application — drafted in plain, friendly tone."
            onApprove={() => {}}
            onReject={() => {}}
          />
        </div>
      </motion.div>
    </motion.div>
  );
}
```

- [ ] **Step 3: Dev render check (requires Clerk session)**

Run:
```bash
cd frontend && npm run dev
```

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:3000/dashboard
```

Expected: `200` if Clerk dev keys allow unauth fallthrough, otherwise `307` redirect to login — either is OK. Kill dev server.

- [ ] **Step 4: Commit**

```bash
git add "frontend/src/app/(app)/dashboard/page.tsx"
git commit -m "feat(frontend): redesigned /dashboard with metrics, score, matches, runs, approvals"
```

---

# Phase 4 — Core App Pages

Owns: `/resume`, `/applications`, `/agents`.

---

### Task 24: AtsScoreRing + KeywordCoverage + SuggestionsList

**Files:**
- Create: `frontend/src/components/resume/AtsScoreRing.tsx`
- Create: `frontend/src/components/resume/KeywordCoverage.tsx`
- Create: `frontend/src/components/resume/SuggestionsList.tsx`

- [ ] **Step 1: Write AtsScoreRing.tsx**

Create:

```tsx
type Props = { score: number; size?: number };

export function AtsScoreRing({ score, size = 160 }: Props) {
  const r = (size - 16) / 2;
  const circ = 2 * Math.PI * r;
  const dash = (score / 100) * circ;
  return (
    <div className="relative inline-flex items-center justify-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} stroke="hsl(var(--muted))" strokeWidth="8" fill="none" />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          stroke="hsl(var(--primary))"
          strokeWidth="8"
          fill="none"
          strokeLinecap="round"
          strokeDasharray={`${dash} ${circ - dash}`}
        />
      </svg>
      <div className="absolute flex flex-col items-center">
        <div className="text-3xl font-medium">{score}</div>
        <div className="text-xs text-muted-foreground">ATS Score</div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Write KeywordCoverage.tsx**

Create:

```tsx
type Props = {
  matched: string[];
  missing: string[];
};

export function KeywordCoverage({ matched, missing }: Props) {
  const total = matched.length + missing.length;
  const pct = total === 0 ? 0 : Math.round((matched.length / total) * 100);
  return (
    <div className="rounded-3xl border border-border bg-card/60 p-6">
      <div className="flex items-baseline justify-between">
        <div className="text-sm text-muted-foreground">Keyword coverage</div>
        <div className="text-2xl font-medium">{pct}%</div>
      </div>
      <div className="mt-3 h-2 w-full overflow-hidden rounded-full bg-muted">
        <div className="h-full bg-primary" style={{ width: `${pct}%` }} />
      </div>
      <div className="mt-6 grid grid-cols-2 gap-4">
        <div>
          <div className="text-xs text-muted-foreground">Matched ({matched.length})</div>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {matched.map((k) => (
              <span key={k} className="rounded-full bg-success/15 px-2.5 py-1 text-xs text-success">{k}</span>
            ))}
          </div>
        </div>
        <div>
          <div className="text-xs text-muted-foreground">Missing ({missing.length})</div>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {missing.map((k) => (
              <span key={k} className="rounded-full bg-muted px-2.5 py-1 text-xs text-muted-foreground">{k}</span>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Write SuggestionsList.tsx**

Create:

```tsx
"use client";

import { Check, X } from "lucide-react";

export type Suggestion = { id: string; original: string; suggestion: string };

type Props = {
  suggestions: Suggestion[];
  onAccept: (id: string) => void;
  onReject: (id: string) => void;
};

export function SuggestionsList({ suggestions, onAccept, onReject }: Props) {
  return (
    <div className="space-y-3">
      {suggestions.map((s) => (
        <div key={s.id} className="rounded-3xl border border-border bg-card/60 p-4">
          <div className="text-xs text-muted-foreground">Original</div>
          <p className="mt-1 text-sm line-through opacity-70">{s.original}</p>
          <div className="mt-3 text-xs text-primary">Suggested</div>
          <p className="mt-1 text-sm">{s.suggestion}</p>
          <div className="mt-4 flex gap-2">
            <button onClick={() => onAccept(s.id)} className="inline-flex items-center gap-1 rounded-full bg-success/15 px-3 py-1.5 text-xs text-success hover:bg-success/25">
              <Check className="h-3 w-3" /> Accept
            </button>
            <button onClick={() => onReject(s.id)} className="inline-flex items-center gap-1 rounded-full bg-muted px-3 py-1.5 text-xs text-muted-foreground hover:bg-card">
              <X className="h-3 w-3" /> Reject
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 4: Type-check + lint**

Run:
```bash
cd frontend && npm run type-check && npm run lint
```

Expected: exit 0.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/resume/
git commit -m "feat(frontend): resume primitives — ATS ring, keyword coverage, suggestions"
```

---

### Task 25: `/resume` page

**Files:**
- Create: `frontend/src/app/(app)/resume/page.tsx`
- Delete: `frontend/src/app/resume/optimize/page.tsx` (and the empty `resume/` dir if any)

- [ ] **Step 1: Delete old resume page**

```bash
git rm frontend/src/app/resume/optimize/page.tsx
```

- [ ] **Step 2: Write `(app)/resume/page.tsx`**

Create:

```tsx
"use client";

import { useState } from "react";
import { motion } from "motion/react";
import { Upload, Download } from "lucide-react";
import { fadeUp, stagger } from "@/lib/motion-variants";
import { LiquidGlassButton } from "@/components/ui/LiquidGlassButton";
import { AtsScoreRing } from "@/components/resume/AtsScoreRing";
import { KeywordCoverage } from "@/components/resume/KeywordCoverage";
import { SuggestionsList, type Suggestion } from "@/components/resume/SuggestionsList";
import { EmptyState } from "@/components/ui/EmptyState";

// TODO Phase 4 wiring: pull from apiClient.resume.getCurrent() once endpoint is wired.
const MOCK_SUGGESTIONS: Suggestion[] = [
  {
    id: "1",
    original: "Worked on the backend team building REST APIs.",
    suggestion: "Designed and shipped 12 REST endpoints handling 4k+ daily requests; cut p95 latency from 320ms to 110ms.",
  },
  {
    id: "2",
    original: "Built a React dashboard.",
    suggestion: "Built a real-time React dashboard with TanStack Query and WebSockets, used daily by 200+ internal operators.",
  },
];

export default function ResumePage() {
  const [suggestions, setSuggestions] = useState<Suggestion[]>(MOCK_SUGGESTIONS);
  const accept = (id: string) => setSuggestions((s) => s.filter((x) => x.id !== id));
  const reject = (id: string) => setSuggestions((s) => s.filter((x) => x.id !== id));

  return (
    <motion.div initial="hidden" animate="show" variants={stagger} className="space-y-8">
      <motion.div variants={fadeUp} className="flex items-center justify-between">
        <div>
          <div className="text-sm text-muted-foreground">Resume Workspace</div>
          <h1 className="mt-1 text-3xl font-medium">Tailor your resume.</h1>
        </div>
        <div className="flex gap-2">
          <LiquidGlassButton tone="ghost" size="sm">
            <Upload className="h-4 w-4" /> Upload
          </LiquidGlassButton>
          <LiquidGlassButton tone="primary" size="sm">
            <Download className="h-4 w-4" /> Export
          </LiquidGlassButton>
        </div>
      </motion.div>

      <motion.div variants={fadeUp} className="grid gap-6 lg:grid-cols-[300px_1fr_320px]">
        <aside className="space-y-6">
          <div className="rounded-3xl border border-border bg-card/60 p-6 text-center">
            <AtsScoreRing score={78} />
          </div>
          <KeywordCoverage
            matched={["React", "TypeScript", "Python", "FastAPI"]}
            missing={["AWS", "Docker", "CI/CD", "PostgreSQL"]}
          />
        </aside>

        <section className="rounded-3xl border border-border bg-card/40 p-6">
          <div className="text-sm text-muted-foreground">Preview</div>
          <div className="mt-3 aspect-[8.5/11] w-full overflow-hidden rounded-2xl border border-border bg-background p-8 text-sm">
            <div className="text-2xl font-medium">Your Name</div>
            <div className="mt-1 text-muted-foreground">Frontend Engineer · email@you.com · github.com/you</div>
            <div className="mt-6 text-xs uppercase tracking-wide text-muted-foreground">Experience</div>
            <p className="mt-2">Resume preview pane — bullets you accept appear here. Connect parser to populate.</p>
          </div>
        </section>

        <aside className="space-y-3">
          <div className="text-sm text-muted-foreground">AI suggestions</div>
          {suggestions.length === 0 ? (
            <EmptyState title="All suggestions reviewed" description="Re-run the Resume Agent to get more tailored bullets." />
          ) : (
            <SuggestionsList suggestions={suggestions} onAccept={accept} onReject={reject} />
          )}
        </aside>
      </motion.div>
    </motion.div>
  );
}
```

- [ ] **Step 3: Type-check + lint**

Run:
```bash
cd frontend && npm run type-check && npm run lint
```

Expected: exit 0.

- [ ] **Step 4: Commit**

```bash
git add "frontend/src/app/(app)/resume/page.tsx" frontend/src/app/resume/
git commit -m "feat(frontend): /resume — 3-col layout with ATS ring, coverage, suggestions"
```

---

### Task 26: ApplicationKanban + ApplicationDrawer

**Files:**
- Create: `frontend/src/components/apps/ApplicationKanban.tsx`
- Create: `frontend/src/components/apps/ApplicationDrawer.tsx`

- [ ] **Step 1: Write ApplicationKanban.tsx**

Create:

```tsx
"use client";

import { motion } from "motion/react";
import { cardHover } from "@/lib/motion-variants";

export type AppStage = "saved" | "applied" | "viewed" | "interview" | "offer" | "rejected";

export type ApplicationItem = {
  id: string;
  company: string;
  role: string;
  matchPercent: number;
  stage: AppStage;
  nextFollowUp?: string;
};

const COLUMNS: { stage: AppStage; label: string }[] = [
  { stage: "saved", label: "Saved" },
  { stage: "applied", label: "Applied" },
  { stage: "viewed", label: "Viewed" },
  { stage: "interview", label: "Interview" },
  { stage: "offer", label: "Offer" },
  { stage: "rejected", label: "Rejected" },
];

type Props = {
  items: ApplicationItem[];
  onSelect: (id: string) => void;
};

export function ApplicationKanban({ items, onSelect }: Props) {
  return (
    <div className="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-6">
      {COLUMNS.map((col) => {
        const colItems = items.filter((it) => it.stage === col.stage);
        return (
          <div key={col.stage} className="rounded-3xl border border-border bg-card/40 p-4">
            <div className="mb-3 flex items-center justify-between text-xs text-muted-foreground">
              <span>{col.label}</span>
              <span>{colItems.length}</span>
            </div>
            <div className="space-y-3">
              {colItems.map((it) => (
                <motion.button
                  key={it.id}
                  type="button"
                  onClick={() => onSelect(it.id)}
                  {...cardHover}
                  className="w-full rounded-2xl border border-border bg-card p-3 text-left"
                >
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium">{it.company}</span>
                    <span className="rounded-full bg-primary/15 px-2 py-0.5 text-[10px] text-primary">{it.matchPercent}%</span>
                  </div>
                  <div className="mt-1 text-xs text-muted-foreground">{it.role}</div>
                  {it.nextFollowUp && (
                    <div className="mt-2 text-[10px] text-warning">Follow up {it.nextFollowUp}</div>
                  )}
                </motion.button>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 2: Write ApplicationDrawer.tsx**

Create:

```tsx
"use client";

import * as Dialog from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import { LiquidGlassButton } from "@/components/ui/LiquidGlassButton";
import type { ApplicationItem } from "./ApplicationKanban";

type Props = {
  application: ApplicationItem | null;
  open: boolean;
  onClose: () => void;
};

export function ApplicationDrawer({ application, open, onClose }: Props) {
  return (
    <Dialog.Root open={open} onOpenChange={(o) => !o && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-background/60 backdrop-blur-sm" />
        <Dialog.Content className="fixed right-0 top-0 z-50 h-full w-full max-w-md overflow-y-auto border-l border-border bg-card p-6">
          {application && (
            <>
              <div className="flex items-start justify-between">
                <div>
                  <Dialog.Title className="text-xl font-medium">{application.role}</Dialog.Title>
                  <Dialog.Description className="text-sm text-muted-foreground">{application.company}</Dialog.Description>
                </div>
                <button onClick={onClose} className="rounded-full p-2 hover:bg-muted" aria-label="Close">
                  <X className="h-4 w-4" />
                </button>
              </div>
              <div className="mt-6 space-y-4">
                <div className="rounded-2xl border border-border p-4">
                  <div className="text-xs text-muted-foreground">Match score</div>
                  <div className="mt-1 text-2xl font-medium">{application.matchPercent}%</div>
                </div>
                <div className="rounded-2xl border border-border p-4">
                  <div className="text-xs text-muted-foreground">Stage</div>
                  <div className="mt-1 text-sm">{application.stage}</div>
                </div>
                <div className="rounded-2xl border border-border p-4">
                  <div className="text-xs text-muted-foreground">Draft email</div>
                  <textarea
                    className="mt-2 w-full rounded-xl border border-border bg-background p-3 text-sm"
                    rows={5}
                    placeholder="Compose follow-up…"
                  />
                  <div className="mt-3 flex gap-2">
                    <LiquidGlassButton tone="primary" size="sm">Send</LiquidGlassButton>
                    <LiquidGlassButton tone="ghost" size="sm">Save draft</LiquidGlassButton>
                  </div>
                </div>
              </div>
            </>
          )}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
```

- [ ] **Step 3: Type-check + lint**

Run:
```bash
cd frontend && npm run type-check && npm run lint
```

Expected: exit 0.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/apps/
git commit -m "feat(frontend): ApplicationKanban + drawer for the apps page"
```

---

### Task 27: `/applications` page

**Files:**
- Create: `frontend/src/app/(app)/applications/page.tsx`
- Delete: `frontend/src/app/applications/page.tsx` (old)
- Delete: `frontend/src/app/jobs/search/page.tsx` (folded into filters)

- [ ] **Step 1: Delete old pages**

```bash
git rm frontend/src/app/applications/page.tsx
git rm frontend/src/app/jobs/search/page.tsx
```

- [ ] **Step 2: Write `(app)/applications/page.tsx`**

Create:

```tsx
"use client";

import { useState } from "react";
import { motion } from "motion/react";
import { fadeUp, stagger } from "@/lib/motion-variants";
import { ApplicationKanban, type ApplicationItem } from "@/components/apps/ApplicationKanban";
import { ApplicationDrawer } from "@/components/apps/ApplicationDrawer";

// TODO wire to apiClient.applications.list()
const MOCK: ApplicationItem[] = [
  { id: "1", company: "Acme", role: "Frontend Engineer", matchPercent: 92, stage: "saved" },
  { id: "2", company: "BetaCorp", role: "Full-stack Dev", matchPercent: 87, stage: "applied", nextFollowUp: "in 2 days" },
  { id: "3", company: "Gamma", role: "Junior SDE", matchPercent: 81, stage: "viewed" },
  { id: "4", company: "Delta", role: "Backend Engineer", matchPercent: 74, stage: "interview" },
  { id: "5", company: "Epsilon", role: "DevOps", matchPercent: 69, stage: "rejected" },
];

export default function ApplicationsPage() {
  const [items] = useState<ApplicationItem[]>(MOCK);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const selected = items.find((i) => i.id === selectedId) ?? null;

  return (
    <motion.div initial="hidden" animate="show" variants={stagger} className="space-y-6">
      <motion.div variants={fadeUp} className="flex items-center justify-between">
        <div>
          <div className="text-sm text-muted-foreground">Pipeline</div>
          <h1 className="mt-1 text-3xl font-medium">Applications</h1>
        </div>
        <div className="flex gap-2">
          <input
            placeholder="Filter by company or role…"
            className="h-10 rounded-full border border-border bg-card/40 px-4 text-sm placeholder:text-muted-foreground"
          />
        </div>
      </motion.div>

      <motion.div variants={fadeUp}>
        <ApplicationKanban items={items} onSelect={setSelectedId} />
      </motion.div>

      <ApplicationDrawer
        application={selected}
        open={selected !== null}
        onClose={() => setSelectedId(null)}
      />
    </motion.div>
  );
}
```

- [ ] **Step 3: Type-check + lint**

Run:
```bash
cd frontend && npm run type-check && npm run lint
```

Expected: exit 0.

- [ ] **Step 4: Commit**

```bash
git add "frontend/src/app/(app)/applications/page.tsx" frontend/src/app/applications/ frontend/src/app/jobs/
git commit -m "feat(frontend): /applications kanban with drawer; fold jobs/search into filters"
```

---

### Task 28: `/agents` page

**Files:**
- Create: `frontend/src/app/(app)/agents/page.tsx`

- [ ] **Step 1: Write `(app)/agents/page.tsx`**

Create:

```tsx
"use client";

import { useState } from "react";
import { motion } from "motion/react";
import { Bot, FileText, Search, Linkedin, Mail, Bell, Sparkles } from "lucide-react";
import { fadeUp, stagger } from "@/lib/motion-variants";
import { AgentStatusCard } from "@/components/agents/AgentStatusCard";
import { ApprovalCard } from "@/components/agents/ApprovalCard";
import { EmptyState } from "@/components/ui/EmptyState";
import { LiquidGlassButton } from "@/components/ui/LiquidGlassButton";

const AGENTS = [
  { key: "orchestrator", label: "Orchestrator", icon: Sparkles },
  { key: "resume", label: "Resume", icon: FileText },
  { key: "job", label: "Job Search", icon: Search },
  { key: "linkedin", label: "LinkedIn", icon: Linkedin },
  { key: "email", label: "Email", icon: Mail },
  { key: "followup", label: "Follow-up", icon: Bell },
];

export default function AgentsPage() {
  const [active, setActive] = useState("orchestrator");
  return (
    <motion.div initial="hidden" animate="show" variants={stagger} className="grid gap-6 lg:grid-cols-[220px_1fr_320px]">
      <motion.aside variants={fadeUp} className="rounded-3xl border border-border bg-card/40 p-3">
        <div className="px-2 py-2 text-xs uppercase tracking-wide text-muted-foreground">Agents</div>
        <nav className="space-y-1">
          {AGENTS.map((a) => {
            const Icon = a.icon;
            const isActive = active === a.key;
            return (
              <button
                key={a.key}
                onClick={() => setActive(a.key)}
                className={`flex w-full items-center gap-2 rounded-2xl px-3 py-2 text-sm ${
                  isActive ? "bg-primary/15 text-foreground" : "text-muted-foreground hover:bg-card"
                }`}
              >
                <Icon className="h-4 w-4" />
                {a.label}
              </button>
            );
          })}
        </nav>
      </motion.aside>

      <motion.section variants={fadeUp} className="rounded-3xl border border-border bg-card/40 p-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Bot className="h-5 w-5 text-primary" />
            <div className="font-medium">{AGENTS.find((a) => a.key === active)?.label} Agent</div>
          </div>
          <LiquidGlassButton tone="primary" size="sm">Run</LiquidGlassButton>
        </div>
        <div className="mt-6 min-h-[400px] rounded-2xl border border-border bg-background/40 p-4">
          <EmptyState
            icon={<Sparkles className="h-6 w-6" />}
            title="Automate repetitive applications."
            description="Tell the orchestrator what role you're after. It'll route work across the resume, job, email, and follow-up agents."
            action={<LiquidGlassButton tone="primary">Start run</LiquidGlassButton>}
          />
        </div>
      </motion.section>

      <motion.aside variants={fadeUp} className="space-y-3">
        <div className="text-sm text-muted-foreground">Context</div>
        <div className="rounded-3xl border border-border bg-card/40 p-4 text-sm">
          <div className="text-xs text-muted-foreground">Resume</div>
          <div className="mt-1">resume-v3.pdf</div>
          <div className="mt-3 text-xs text-muted-foreground">Target role</div>
          <div className="mt-1">Frontend Engineer</div>
          <div className="mt-3 text-xs text-muted-foreground">Model</div>
          <div className="mt-1">Anthropic · claude-sonnet-4-6</div>
        </div>
        <div className="text-sm text-muted-foreground">Run history</div>
        <AgentStatusCard agentName="Resume Agent" status="succeeded" latestMessage="Tailored for BetaCorp." startedAt="3 min ago" />
        <ApprovalCard
          title="Apply to Acme Frontend Engineer"
          summary="Application draft ready. Click approve to submit through the browser agent."
          onApprove={() => {}}
          onReject={() => {}}
        />
      </motion.aside>
    </motion.div>
  );
}
```

- [ ] **Step 2: Type-check + lint**

Run:
```bash
cd frontend && npm run type-check && npm run lint
```

Expected: exit 0.

- [ ] **Step 3: Commit**

```bash
git add "frontend/src/app/(app)/agents/page.tsx"
git commit -m "feat(frontend): /agents — agent list, run panel, context column"
```

---

# Phase 5 — Onboarding + Settings

Owns: `/onboarding`, `/settings/models`.

---

### Task 29: OnboardingStepper component

**Files:**
- Create: `frontend/src/components/onboarding/OnboardingStepper.tsx`

- [ ] **Step 1: Write OnboardingStepper.tsx**

Create:

```tsx
"use client";

import { AnimatePresence, motion } from "motion/react";
import type { ReactNode } from "react";

type Step = { id: string; title: string; content: ReactNode };

type Props = {
  steps: Step[];
  currentIndex: number;
  onChange: (i: number) => void;
};

export function OnboardingStepper({ steps, currentIndex, onChange }: Props) {
  const current = steps[currentIndex];
  return (
    <div className="mx-auto flex max-w-2xl flex-col items-center gap-10">
      <div className="flex items-center gap-2">
        {steps.map((s, i) => (
          <button
            key={s.id}
            type="button"
            onClick={() => onChange(i)}
            aria-label={`Go to step ${i + 1}`}
            className={`h-2 rounded-full transition-all ${
              i === currentIndex ? "w-8 bg-primary" : "w-2 bg-muted"
            }`}
          />
        ))}
      </div>
      <div className="text-center">
        <div className="text-xs uppercase tracking-wide text-muted-foreground">
          Step {currentIndex + 1} of {steps.length}
        </div>
        <h2 className="mt-2 text-3xl font-medium">{current.title}</h2>
      </div>
      <AnimatePresence mode="wait">
        <motion.div
          key={current.id}
          initial={{ opacity: 0, x: 24 }}
          animate={{ opacity: 1, x: 0 }}
          exit={{ opacity: 0, x: -24 }}
          transition={{ duration: 0.3 }}
          className="w-full"
        >
          {current.content}
        </motion.div>
      </AnimatePresence>
    </div>
  );
}
```

- [ ] **Step 2: Type-check**

Run:
```bash
cd frontend && npm run type-check
```

Expected: exit 0.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/onboarding/OnboardingStepper.tsx
git commit -m "feat(frontend): OnboardingStepper with progress dots and slide transitions"
```

---

### Task 30: `/onboarding` page

**Files:**
- Create: `frontend/src/app/(app)/onboarding/page.tsx`

- [ ] **Step 1: Write `(app)/onboarding/page.tsx`**

Create:

```tsx
"use client";

import { useState } from "react";
import { ThemeProvider } from "@/components/theme/ThemeProvider";
import { OnboardingStepper } from "@/components/onboarding/OnboardingStepper";
import { LiquidGlassButton } from "@/components/ui/LiquidGlassButton";

function StepWrapper({ children, onNext, onPrev, canPrev, isLast }: {
  children: React.ReactNode;
  onNext: () => void;
  onPrev: () => void;
  canPrev: boolean;
  isLast: boolean;
}) {
  return (
    <div className="space-y-6">
      <div className="rounded-3xl border border-border bg-card/60 p-6">{children}</div>
      <div className="flex items-center justify-between">
        <LiquidGlassButton tone="ghost" size="sm" onClick={onPrev} disabled={!canPrev}>Back</LiquidGlassButton>
        <LiquidGlassButton tone="primary" size="sm" onClick={onNext}>{isLast ? "Finish" : "Continue"}</LiquidGlassButton>
      </div>
    </div>
  );
}

export default function OnboardingPage() {
  const [i, setI] = useState(0);

  const next = () => setI((n) => Math.min(n + 1, 5));
  const prev = () => setI((n) => Math.max(n - 1, 0));
  const isLast = i === 5;

  const wrap = (node: React.ReactNode) => (
    <StepWrapper onNext={next} onPrev={prev} canPrev={i > 0} isLast={isLast}>{node}</StepWrapper>
  );

  const steps = [
    { id: "welcome", title: "Welcome to CareerCraft AI.", content: wrap(<p className="text-sm text-muted-foreground">Let's set up your job search in under two minutes.</p>) },
    { id: "goal", title: "What's your goal?", content: wrap(<select className="w-full rounded-2xl border border-border bg-background p-3 text-sm"><option>First job after college</option><option>Switch roles</option><option>Internship</option></select>) },
    { id: "resume", title: "Upload your resume", content: wrap(<input type="file" accept=".pdf,.docx" className="w-full rounded-2xl border border-dashed border-border bg-background p-4 text-sm" />) },
    { id: "role", title: "Target role", content: wrap(<input placeholder="e.g. Frontend Engineer" className="w-full rounded-2xl border border-border bg-background p-3 text-sm" />) },
    { id: "locations", title: "Preferred locations", content: wrap(<input placeholder="Bangalore, Remote, Hyderabad" className="w-full rounded-2xl border border-border bg-background p-3 text-sm" />) },
    { id: "model", title: "Bring your own model", content: wrap(<div className="space-y-3 text-sm"><label className="block">Provider <select className="mt-1 w-full rounded-2xl border border-border bg-background p-3"><option>Anthropic</option><option>OpenAI</option><option>Gemini</option><option>Groq</option><option>Ollama</option></select></label><label className="block">API key <input type="password" className="mt-1 w-full rounded-2xl border border-border bg-background p-3" /></label></div>) },
  ];

  return (
    <ThemeProvider zoneDefault="light">
      <div className="min-h-screen bg-background px-6 py-16">
        <OnboardingStepper steps={steps} currentIndex={i} onChange={setI} />
      </div>
    </ThemeProvider>
  );
}
```

Note: `/onboarding` lives in `(app)` so it inherits Clerk protection but overrides the theme to light by wrapping its own ThemeProvider. The outer app-zone ThemeProvider still exists; inner one wins for children. No hydration mismatch because both are client components.

- [ ] **Step 2: Type-check + lint**

Run:
```bash
cd frontend && npm run type-check && npm run lint
```

Expected: exit 0.

- [ ] **Step 3: Dev render check**

Run:
```bash
cd frontend && npm run dev
```

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:3000/onboarding
```

Expected: `200` or `307` (Clerk redirect). Kill dev server.

- [ ] **Step 4: Commit**

```bash
git add "frontend/src/app/(app)/onboarding/page.tsx"
git commit -m "feat(frontend): /onboarding 6-step flow with light theme override"
```

---

### Task 31: `/settings/models` page restyle

**Files:**
- Create: `frontend/src/app/(app)/settings/models/page.tsx`
- Delete: `frontend/src/app/settings/models/page.tsx` (old)

Context: the existing page wires `GET /api/v1/users/me/models` and `POST /api/v1/users/me/models` through `apiClient` plus TanStack Query. The contract MUST be preserved: same endpoints, same payload shape (`provider`, `api_key`, `model_name`, `ollama_url`), same five providers (anthropic, openai, google, ollama, nvidia_nim).

- [ ] **Step 1: Delete old page**

```bash
git rm frontend/src/app/settings/models/page.tsx
```

- [ ] **Step 2: Write `(app)/settings/models/page.tsx`**

Create:

```tsx
"use client";

import { useState } from "react";
import { motion } from "motion/react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { apiClient } from "@/lib/api";
import { fadeUp, stagger } from "@/lib/motion-variants";
import { LiquidGlassButton } from "@/components/ui/LiquidGlassButton";
import { EmptyState } from "@/components/ui/EmptyState";
import { useTheme } from "@/components/theme/ThemeProvider";

const PROVIDERS = [
  { value: "anthropic", label: "Anthropic (Claude)", defaultModel: "claude-sonnet-4-6" },
  { value: "openai", label: "OpenAI (GPT)", defaultModel: "gpt-4o" },
  { value: "google", label: "Google (Gemini)", defaultModel: "gemini-2.0-flash" },
  { value: "ollama", label: "Ollama (Local)", defaultModel: "llama3.2" },
  { value: "nvidia_nim", label: "NVIDIA NIM", defaultModel: "meta/llama-3.1-70b-instruct" },
] as const;

type Provider = (typeof PROVIDERS)[number]["value"];

interface ModelSetting {
  id: string;
  provider: string;
  model_name: string | null;
  is_active: boolean;
}

export default function SettingsModelsPage() {
  const { theme, toggleTheme } = useTheme();
  const qc = useQueryClient();
  const [provider, setProvider] = useState<Provider>("anthropic");
  const [apiKey, setApiKey] = useState("");
  const [modelName, setModelName] = useState("claude-sonnet-4-6");
  const [ollamaUrl, setOllamaUrl] = useState("http://localhost:11434");

  const { data: models = [] } = useQuery<ModelSetting[]>({
    queryKey: ["models"],
    queryFn: () =>
      apiClient.get("/api/v1/users/me/models").then((r) => r.data as ModelSetting[]),
  });

  const { mutate: addModel, isPending } = useMutation({
    mutationFn: () =>
      apiClient.post("/api/v1/users/me/models", {
        provider,
        api_key: apiKey,
        model_name: modelName,
        ollama_url: provider === "ollama" ? ollamaUrl : null,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["models"] });
      setApiKey("");
      toast.success("Model added");
    },
    onError: () => toast.error("Failed to add model"),
  });

  const onProviderChange = (next: Provider) => {
    setProvider(next);
    const found = PROVIDERS.find((p) => p.value === next);
    setModelName(found?.defaultModel ?? "");
  };

  return (
    <motion.div initial="hidden" animate="show" variants={stagger} className="space-y-8">
      <motion.div variants={fadeUp}>
        <div className="text-sm text-muted-foreground">Settings</div>
        <h1 className="mt-1 text-3xl font-medium">Models &amp; preferences</h1>
      </motion.div>

      <motion.div variants={fadeUp} className="grid gap-6 lg:grid-cols-[1fr_360px]">
        <section className="rounded-3xl border border-border bg-card/60 p-6">
          <div className="text-base font-medium">Add provider</div>
          <p className="mt-1 text-sm text-muted-foreground">
            BYOK — your keys are encrypted at rest. Use Ollama for free local inference.
          </p>

          <label className="mt-6 block text-xs text-muted-foreground">Provider</label>
          <select
            value={provider}
            onChange={(e) => onProviderChange(e.target.value as Provider)}
            className="mt-1 w-full rounded-2xl border border-border bg-background p-3 text-sm"
          >
            {PROVIDERS.map((p) => (
              <option key={p.value} value={p.value}>{p.label}</option>
            ))}
          </select>

          <label className="mt-4 block text-xs text-muted-foreground">Model name</label>
          <input
            value={modelName}
            onChange={(e) => setModelName(e.target.value)}
            placeholder="Model name"
            className="mt-1 w-full rounded-2xl border border-border bg-background p-3 text-sm"
          />

          <label className="mt-4 block text-xs text-muted-foreground">API key</label>
          <input
            type="password"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder={provider === "ollama" ? "No API key required" : "API key"}
            disabled={provider === "ollama"}
            className="mt-1 w-full rounded-2xl border border-border bg-background p-3 text-sm disabled:opacity-50"
          />

          {provider === "ollama" && (
            <>
              <label className="mt-4 block text-xs text-muted-foreground">Ollama URL</label>
              <input
                value={ollamaUrl}
                onChange={(e) => setOllamaUrl(e.target.value)}
                placeholder="http://localhost:11434"
                className="mt-1 w-full rounded-2xl border border-border bg-background p-3 text-sm"
              />
            </>
          )}

          <div className="mt-6">
            <LiquidGlassButton
              tone="primary"
              size="md"
              onClick={() => addModel()}
              disabled={isPending || (!apiKey && provider !== "ollama")}
            >
              {isPending ? "Adding…" : "Add model"}
            </LiquidGlassButton>
          </div>
        </section>

        <aside className="space-y-4">
          <div className="rounded-3xl border border-border bg-card/60 p-6">
            <div className="text-base font-medium">Theme</div>
            <p className="mt-1 text-sm text-muted-foreground">
              Current: {theme}. Saved in your browser.
            </p>
            <div className="mt-4">
              <LiquidGlassButton tone="ghost" size="sm" onClick={toggleTheme}>
                Switch to {theme === "dark" ? "light" : "dark"}
              </LiquidGlassButton>
            </div>
          </div>

          <div className="rounded-3xl border border-border bg-card/60 p-6">
            <div className="text-base font-medium">Configured models</div>
            <div className="mt-4 space-y-2">
              {models.length === 0 ? (
                <EmptyState title="No models yet" description="Add one to enable agent runs." />
              ) : (
                models.map((m) => (
                  <div
                    key={m.id}
                    className="flex items-center justify-between rounded-2xl border border-border bg-card px-4 py-3"
                  >
                    <div>
                      <div className="text-sm font-medium">{m.provider}</div>
                      <div className="text-xs text-muted-foreground">{m.model_name ?? "—"}</div>
                    </div>
                    {m.is_active && (
                      <span className="rounded-full bg-success/15 px-2 py-0.5 text-xs text-success">
                        Active
                      </span>
                    )}
                  </div>
                ))
              )}
            </div>
          </div>
        </aside>
      </motion.div>
    </motion.div>
  );
}
```

- [ ] **Step 3: Type-check + lint**

Run:
```bash
cd frontend && npm run type-check && npm run lint
```

Expected: exit 0.

- [ ] **Step 4: Dev render check**

Run:
```bash
cd frontend && npm run dev
```

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:3000/settings/models
```

Expected: `200` or `307`. Kill dev server.

- [ ] **Step 5: Commit**

```bash
git add "frontend/src/app/(app)/settings/models/page.tsx" frontend/src/app/settings/
git commit -m "feat(frontend): restyle /settings/models — BYOK provider cards, theme toggle, preserved API contract"
```

---

### Task 32: Final cleanup — drop empty dirs, full build verify

**Files:**
- Modify: any stale empty directories under `frontend/src/app/`

- [ ] **Step 1: Remove empty leftover directories**

Run:
```bash
cd frontend && find src/app -type d -empty -not -path "*/\.*" -print -delete
```

Expected: any `dashboard/`, `resume/`, `applications/`, `jobs/search/`, `settings/models/` parents whose page files moved into `(app)` are pruned.

- [ ] **Step 2: Full production build**

Run:
```bash
cd frontend && npm run build
```

Expected: build succeeds with zero errors. Warnings about unused exports or `<img>` (we use `<video>`/inline SVG only) are acceptable.

- [ ] **Step 3: Lint clean**

Run:
```bash
cd frontend && npm run lint
```

Expected: exit 0. No errors.

- [ ] **Step 4: Dev render check across every route**

Run:
```bash
cd frontend && npm run dev
```

In another shell:
```bash
for path in / /pricing /dashboard /resume /applications /agents /onboarding /settings/models; do
  echo -n "$path → "
  curl -s -o /dev/null -w "%{http_code}\n" "http://localhost:3000$path"
done
```

Expected: each line ends in `200` or `307` (Clerk auth redirect for `(app)` paths). Any `500` is a regression — open the page in a browser and read the console.

Kill dev server.

- [ ] **Step 5: Commit cleanup if any files changed**

```bash
git add -A
git diff --cached --quiet || git commit -m "chore(frontend): drop empty legacy route dirs"
```

If nothing changed, the commit is a no-op and the command exits 0 — fine either way.

---

## Done

All five phases shipped: design system, marketing zone, app shell + dashboard, core app pages, onboarding + settings. The visual layer is fully replaced; no API/auth/store/contract was touched.

**Follow-ups (out of scope for this plan):**
- Ship real `public/videos/footer.mp4` and product preview MP4.
- Wire mock data in dashboard/resume/applications/agents to actual `apiClient.*` calls (this is data integration, not the visual redesign).
- Persist theme preference to backend if/when `user_model_settings.theme_preference` column lands.
- Mobile sidebar drawer (currently `hidden md:flex`).
