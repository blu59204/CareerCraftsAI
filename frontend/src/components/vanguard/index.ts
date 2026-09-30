/**
 * Vanguard design system — shared primitives for the redesigned app screens.
 *
 * Vibe: Soft Structuralism on the existing warm-neutral + single green brand
 * tokens (light + dark). Geist type, Phosphor Light icons, Double-Bezel
 * enclosures, island pill buttons with nested trailing icons, spring/cubic
 * motion (never linear/ease-in-out), IntersectionObserver reveals.
 *
 * Rules for screens using this kit:
 *  - Icons: `@phosphor-icons/react` with `weight="light"` only. No lucide-react.
 *  - No `backdrop-blur` on scrolling content; only on fixed overlays.
 *  - No `border border-border` 1px gray boxes; use Bezel / ring-foreground/[0.06].
 *  - No `shadow-md/lg/xl`; use `shadow-ambient`, `shadow-ambient-sm`, bezel highlights.
 *  - Transitions: `duration-500 ease-vanguard` (or motion tokens from ./motion).
 *  - Animate transform/opacity only.
 */
export { Bezel, bezelShell, bezelCore, type BezelSize, type BezelTone } from "./Bezel";
export { IslandButton, IslandLink, IconButton, type IslandTone, type IslandSize } from "./IslandButton";
export { Eyebrow, PageHero, SectionHeading, PanelTitle } from "./PageHero";
export { Input, Textarea, Select, Field, inputTrayClass, inputControlClass } from "./Field";
export { Segmented, Toggle, Chip } from "./Controls";
export { StatusPill, Stat, StatStrip, EmptyPanel, Skeleton, Hairline, Notice, type StatusTone } from "./Display";
export { Reveal, RevealGroup } from "./Reveal";
export { Screen, Section } from "./Screen";
export * from "./motion";
