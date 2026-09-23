## 2026-05-30 - Browser Automation Artifacts Can Leak Session Data
**Vulnerability:** Browser automation folders such as `.browser_data/`, `.playwright-cli/`, and `.playwright-mcp/` were not ignored and can contain cookies, tokens, Chrome local state, screenshots, or page captures.
**Learning:** Job-board automation creates realistic browser state during local smoke tests, so generated runtime folders can become sensitive even when application secrets stay in `.env`.
**Prevention:** Keep browser profile and capture directories ignored at repo root and nested service paths before running live browser workflows.
