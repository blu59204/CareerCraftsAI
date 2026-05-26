# CareerCraft AI — Frontend Visual Redesign Spec
**Date:** 2026-05-24  
**Status:** Approved  
**Scope:** Visual layer only — no changes to API calls, auth, Zustand, SSE, or backend contracts

---

## 1. Guiding Visual Language

Inspired by MotionSites aesthetic — NOT a generic Tailwind admin template.

Key visual principles:
- Large whitespace breathing room
- Premium editorial typography (Inter for UI, Instrument Serif italic for hero display words)
- `rounded-3xl` cards throughout — never sharp corners
- Video-backed sections (hero, footer, How It Works strip)
- Liquid-glass overlays on cards, navbars, buttons
- Soft gradient mesh backgrounds (not flat solid colors)
- Subtle blur (backdrop-filter) for depth
- Animated entrance transitions on every page mount
- Marquee rows for logos/feature chips
- Dark dashboard surfaces — deep `#050505`/`#070612` not generic `gray-900`

All content is CareerCraft AI specific. No placeholder brand names.

---

## 2. Route Architecture

```
src/app/
  (marketing)/           ← public, no auth, light default
    layout.tsx           ← MarketingNavbar + MarketingFooter, no sidebar
    page.tsx             ← /
    pricing/page.tsx     ← /pricing
  (app)/                 ← Clerk-protected, dark default
    layout.tsx           ← AppShell (sidebar + topbar)
    dashboard/page.tsx
    resume/page.tsx
    applications/page.tsx
    agents/page.tsx
    onboarding/page.tsx
    settings/models/page.tsx
  (auth)/                ← existing Clerk pages, untouched
```

Root `layout.tsx` → bare ClerkProvider + ThemeProvider + QueryProvider + Toaster only.

---

## 3. Theme System

### Strategy
- Tailwind `darkMode: ["class"]` (already configured)
- `<html>` gets `class="dark"` or `class="light"` — never inline styles
- All colors via CSS custom properties, consumed as `bg-background`, `text-foreground`, etc.
- Zero hardcoded `bg-white`, `text-black`, `dark:bg-gray-900` patterns in components

### Default per zone
| Zone | Default | Can toggle to |
|------|---------|--------------|
| Public marketing | light | dark |
| Authenticated app | dark | light |

### Persistence
- All users → `localStorage.setItem("theme", value)` (no backend column needed)
- System preference respected only on first visit (no saved preference)
- No flash on load: theme class applied in `<head>` via inline script before paint
- Note: API persistence deferred — `theme_preference` column does not exist in DB yet

### ThemeProvider
- React context: `{ theme, setTheme, toggleTheme }`
- On mount: read saved preference → fall back to zone default → fall back to system
- Provides `useTheme()` hook

---

## 4. CSS Design Tokens

### Light theme (`:root`)
```css
--background: 0 0% 100%;
--foreground: 222 47% 8%;
--card: 0 0% 100%;
--card-foreground: 222 47% 8%;
--muted: 210 40% 96%;
--muted-foreground: 215 16% 47%;
--border: 214 32% 91%;
--input: 214 32% 91%;
--primary: 245 75% 59%;        /* #6366f1 indigo */
--primary-foreground: 0 0% 100%;
--secondary: 210 40% 96%;
--accent: 262 83% 65%;         /* violet */
--success: 142 71% 45%;
--warning: 38 92% 50%;
--danger: 0 84% 60%;
--radius: 1.5rem;               /* rounded-3xl base */
```

### Dark theme (`.dark`)
```css
--background: 240 10% 3%;      /* #050508 */
--foreground: 210 40% 98%;
--card: 240 9% 6%;             /* #0d0d12 */
--card-foreground: 210 40% 98%;
--muted: 240 6% 10%;
--muted-foreground: 215 20% 65%;
--border: 240 6% 13%;
--input: 240 6% 13%;
--primary: 258 80% 60%;        /* #7b39fc purple */
--primary-foreground: 0 0% 100%;
--secondary: 240 6% 10%;
--accent: 265 83% 65%;
--success: 142 71% 45%;
--warning: 38 92% 50%;
--danger: 0 84% 60%;
```

### CSS Utilities (in globals.css)
```css
/* Liquid glass */
.liquid-glass {
  background: rgba(255,255,255,0.01);
  backdrop-filter: blur(4px);
  -webkit-backdrop-filter: blur(4px);
  box-shadow: inset 0 1px 1px rgba(255,255,255,0.10);
  position: relative;
  overflow: hidden;
}
.liquid-glass::before {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: inherit;
  padding: 1.4px;
  background: linear-gradient(180deg,
    rgba(255,255,255,0.45) 0%, rgba(255,255,255,0.15) 20%,
    rgba(255,255,255,0) 40%, rgba(255,255,255,0) 60%,
    rgba(255,255,255,0.15) 80%, rgba(255,255,255,0.45) 100%);
  -webkit-mask: linear-gradient(#fff 0 0) content-box,
                linear-gradient(#fff 0 0);
  -webkit-mask-composite: xor;
  mask-composite: exclude;
  pointer-events: none;
}

/* Noise overlay */
.noise-overlay::after {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  opacity: 0.35;
  mix-blend-mode: soft-light;
  background-image: url("data:image/svg+xml;utf8,..."); /* fractalNoise */
  background-size: 240px 240px;
}

/* Marquee */
@keyframes marquee-left  { from { transform: translateX(0); }    to { transform: translateX(-50%); } }
@keyframes marquee-right { from { transform: translateX(-50%); } to { transform: translateX(0); } }
.animate-marquee-left  { animation: marquee-left 22s linear infinite; }
.animate-marquee-right { animation: marquee-right 26s linear infinite; }
```

---

## 5. Animation System (motion/react)

```
npm install motion
import { motion, AnimatePresence } from "motion/react"
```

### Reusable variants
```ts
fadeUp   = { hidden: { opacity: 0, y: 20 }, show: { opacity: 1, y: 0, transition: { duration: 0.5 } } }
fadeIn   = { hidden: { opacity: 0 }, show: { opacity: 1, transition: { duration: 0.4 } } }
stagger  = { show: { transition: { staggerChildren: 0.08 } } }
cardHover = { whileHover: { scale: 1.02, transition: { duration: 0.2 } } }
```

Rules:
- Every page: `motion.div` wrapper with `fadeUp` on mount
- Hero headline: stagger word-by-word
- Cards: `cardHover` lift + subtle shadow
- Sidebar: width transition on collapse
- No animation on table rows, form inputs, or large data lists

---

## 6. Component Inventory

| Component | File | Purpose |
|-----------|------|---------|
| `ThemeProvider` | `components/theme/ThemeProvider.tsx` | Context + persistence |
| `ThemeToggle` | `components/theme/ThemeToggle.tsx` | Sun/Moon icon button |
| `MarketingNavbar` | `components/marketing/Navbar.tsx` | Public site header |
| `MarketingFooter` | `components/marketing/Footer.tsx` | Liquid-glass footer |
| `AppShell` | `components/layout/AppShell.tsx` | Authenticated wrapper |
| `AppSidebar` | `components/layout/AppSidebar.tsx` | Dark glass sidebar |
| `AppTopbar` | `components/layout/AppTopbar.tsx` | Search + notif + toggle + avatar |
| `LiquidGlassButton` | `components/ui/LiquidGlassButton.tsx` | CTA button variant |
| `MetricCard` | `components/ui/MetricCard.tsx` | Stat + trend display |
| `FeatureCard` | `components/ui/FeatureCard.tsx` | Dark feature grid card |
| `PricingCard` | `components/ui/PricingCard.tsx` | Pricing tier card |
| `ResumeScoreCard` | `components/ui/ResumeScoreCard.tsx` | ATS + keyword scores |
| `JobMatchCard` | `components/ui/JobMatchCard.tsx` | Match % + role preview |
| `ApplicationKanban` | `components/apps/ApplicationKanban.tsx` | Column drag board |
| `AgentStatusCard` | `components/agents/AgentStatusCard.tsx` | Run status + streaming |
| `ApprovalCard` | `components/agents/ApprovalCard.tsx` | Human-in-loop gate UI |
| `EmptyState` | `components/ui/EmptyState.tsx` | Empty data placeholder |
| `LoadingState` | `components/ui/LoadingState.tsx` | Skeleton loader |
| `ErrorState` | `components/ui/ErrorState.tsx` | Error + retry UI |
| `VideoBackground` | `components/ui/VideoBackground.tsx` | Looping video bg |

---

## 7. Public Pages (Zone 1 — light default)

### `/` — Home
Sections in order:
1. **MarketingNavbar** — logo left, nav center (Features / How it Works / Pricing / Demo), theme toggle + Login + Get Started right
2. **Hero A** — badge "AI job-search copilot for students and freshers" → staggered headline "Apply smarter. Tailor faster. *Get noticed.*" (Instrument Serif italic on last phrase) → subtitle → CTA buttons → product preview mockup floating below
3. **Marquee row** — feature chips: Resume AI · Job Match · Email Agent · Application Tracker · BYOK Models · ATS Optimizer · Follow-up Agent
4. **Hero B / Social proof** — editorial large headline "Craft" + subheading + logo bar
5. **How It Works** — dark strip, 4-step flow with glass cards + connector lines
6. **Features grid** — `#0a0a0a` bg, 6 cards (Resume Intelligence, AI Orchestrator, Job Match, App Tracker, Email Drafts, BYOK Models)
7. **Pricing** — 3 tier cards
8. **MarketingFooter** — liquid-glass, video bg, 4 link columns

### `/pricing`
Standalone pricing page. Same navbar/footer. 3 cards + FAQ accordion.

---

## 8. App Pages (Zone 2 — dark default)

### `/dashboard`
- AppShell wraps all app pages
- Greeting card + date
- Row: 4 MetricCards (Applications, Interviews, Avg Match, Follow-ups Due)
- Row: ResumeScoreCard + JobMatchCard
- Row: Recent agent runs (AgentStatusCard list) + Pending approvals (ApprovalCard list)
- Row: Recommended jobs

### `/resume`
- 3-col layout: upload/parsed left, preview center, AI suggestions right
- ATS score ring, keyword coverage bar, missing keywords list
- Suggested bullet rewrites with accept/reject
- Export PDF / DOCX buttons

### `/applications`
- Top: filter bar + kanban/table toggle
- Kanban: columns Saved / Applied / Viewed / Interview / Offer / Rejected
- Each card: company, role, match score badge, status, next follow-up
- Table view: sortable columns, same data
- Right drawer: application detail + draft email + update status

### `/agents`
- Left: agent list sidebar (Resume, Job Search, LinkedIn, Email, Follow-up, Orchestrator)
- Center: streaming chat panel with tool call cards + ApprovalCard
- Right: context panel (resume loaded, target job, model provider, run history)
- Empty state: hero prompt "Automate repetitive applications."

### `/onboarding`
- 6-step flow: Welcome → Goal → Upload Resume → Target Role → Locations → BYOK Model → Done
- Light theme, progress dots, slide transition between steps
- Mobile friendly

### `/settings/models`
- BYOK model cards: OpenAI, Anthropic, Gemini, Groq, Ollama, Azure
- Each card: name, model select, API key input (masked), test connection button
- Theme preference toggle section

---

## 9. What Is NOT Changed

- `src/lib/api.ts` — Axios client + Clerk auth interceptor
- `src/lib/sse.ts` — fetchEventSource streaming
- `src/store/agentSlice.ts` — Zustand agent state
- `src/store/userSlice.ts` — Zustand user state
- `src/middleware.ts` — Clerk route protection
- All `apiClient.*` call sites — just restyled around
- Backend contracts, FastAPI endpoints, auth flow

---

## 10. Phased Build Order

| Phase | Scope | Key files |
|-------|-------|-----------|
| P1 | Design system | `globals.css`, `tailwind.config.ts`, `ThemeProvider`, `ThemeToggle`, install `motion` |
| P2 | Marketing shell + landing | `(marketing)/layout.tsx`, `Navbar`, `Footer`, `/page.tsx`, `/pricing/page.tsx` |
| P3 | App shell + dashboard | `(app)/layout.tsx`, `AppShell`, `AppSidebar`, `AppTopbar`, `/dashboard/page.tsx` |
| P4 | Core app pages | `/resume`, `/applications`, `/agents` |
| P5 | Onboarding + settings | `/onboarding`, `/settings/models` |

Each phase: build → type-check → lint → verify dev server renders correctly before next phase.
