# Premium Career Command OS Implementation Plan

## Summary

Redesign CareerCraft AI into a premium job-command workspace using selected MotionSites designs as layout/style references, not copied branding:

- `Sync AI` for clean hero hierarchy, bottom proof bar, monochrome premium CTA.
- `Synapse Dark Hero` for black glass hero, badge row, muted logo/proof strip.
- `Landing page hero2` for secondary landing composition and product preview depth.
- `AI Workflow Hero` for how-it-works flow sections.
- `AI Automation Hero` for feature blocks, dark left-aligned automation storytelling.
- `Grow AI Talent Platform` for talent platform tone and hiring proof.
- `HR SaaS Hero` for resume builder/editorial page style.
- `Taskora SaaS Hero` for application tracker/dashboard preview style.
- `Finlytic AI Agent` for AI chat/agents page style.
- `Aurora Onboard` for signup/onboarding flow style.
- `SaaS Pricing Flow` for pricing page/cards.
- `Dashboard UI` for dashboard screen density and hierarchy.
- `Lumina Footer Section` for footer CTA/link layout.
- `Velorah Agency` and `Max Reed Portfolio Features` for refined spacing and feature presentation.

Chosen direction: **Premium Career Command OS**. Dark-first, elegant, immersive, job-focused. Light mode remains frosted and readable. Backend/API/database behavior stays unchanged. Email/apply approval gates stay unchanged.

## Key Changes

- Add `three`, `@react-three/fiber`, and `@react-three/drei` for subtle procedural canvas only. No generated images/videos in the main app.
- Add shared UI system:
  - `ImmersiveCanvas`
  - `CareerCommandScene`
  - `VideoBackdrop`
  - `GlassSurface`
  - `CommandHeader`
  - `MetricOrb`
  - `BlurText`
  - `FilmGrain`
- Redesign shell:
  - glass command rail sidebar.
  - pill command topbar.
  - subtle coded WebGL/canvas depth.
  - route transitions with blur/fade.
- Redesign core pages:
  - `/` Sync/Synapse inspired coded hero + proof marquee + product mockup.
  - `/dashboard` command center with metric orbs.
  - `/jobs` radar cockpit.
  - `/agents` 3D agent network.
  - `/resume` ATS glass workspace.
  - `/interview-prep` interview studio.
  - `/email`, `/linkedin`, `/applications`, `/leads`, `/settings` polished with same glass system.

## Assets

No generated image/video assets inside the main app. Premium look comes from:

- coded dashboard mockups.
- CSS glass, grain, grid, glow, shadows.
- subtle procedural canvas.
- typography, spacing, motion.

## Test Plan

- `cd frontend && npm run build`
- `cd frontend && npm run lint`
- Browser visual pass:
  - `/`
  - `/dashboard`
  - `/jobs`
  - `/agents`
  - `/resume`
  - `/interview-prep`
  - `/email`
  - `/linkedin`
  - `/applications`
  - `/settings/account`
- Verify no invisible text, no horizontal overflow, no console errors, nonblank 3D/canvas, working fallback, and unchanged approval gates.
