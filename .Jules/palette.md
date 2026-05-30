## 2026-05-30 - Accessible Preference Chips
**Learning:** Job preference chips and selected tag pills are reused as stateful controls, but visual selected/removable states are not enough for screen readers.
**Action:** When adding chip-style controls in this app, pair selected pills with `aria-pressed` and give each icon-only remove button a target-specific label.
