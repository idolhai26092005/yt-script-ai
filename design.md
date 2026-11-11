# ScriptForge Frontend Design System

## Direction
- Genre: modern-minimal.
- Macrostructure: Workbench + Narrative Workflow.
- Theme: Cobalt-dark, technical dashboard, dense but readable.
- Reference DNA: fixed/collapsible side rail, compact action strips, workbench panels, horizontal workflow/timeline, large output canvas.

## Tokens
- Colors live in `frontend/src/styles/tokens.css` and must use semantic OKLCH variables.
- Page CSS must reference tokens, not inline hex/rgb/oklch values.
- Radius target: controls `6px`, repeated cards `8px`, large panels only when needed.
- Typography: display `Space Grotesk`, body `IBM Plex Sans`, mono `JetBrains Mono`.

## Layout
- App shell owns sidebar, mobile drawer, page width, and footer.
- Individual tabs own only their work surface.
- Avoid card-in-card; use hairline dividers, panels, inline rules, and dense grids.
- Header is optional; page-level action strips replace a global header.

## Interaction
- Sidebar collapses on desktop and becomes a drawer on mobile.
- Buttons and nav links must stay one line at 320/375/414/768 px.
- Focus rings are visible and immediate.
- Success feedback should be inline when the result is visible, especially copy actions.

## Rollout
- Implement one tab per pass.
- First pass only establishes shell, routes, and tokens.
- Later passes redesign Home, unified History, Single, Series intake/workbench,
  then secondary tabs.
- Legacy `/projects` and `/series-history` routes stay as hidden aliases into
  unified History filters.
