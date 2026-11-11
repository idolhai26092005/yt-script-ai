## Why

The current series flow is not a real independent generation pipeline: it is a large FastAPI endpoint that builds weak episode outlines, mutates episode suggestions with rolling context, then routes generation through the single-video `ProductionService`. This makes episode continuity poor, encourages each episode to close like a standalone video, and lets series-specific behavior risk the single/longform pipeline.

This change rebuilds series generation as a dedicated v2 flow on the existing `/api/v1/series` surface, with explicit phase artifacts, add-only database tables, user-editable episode briefs, flexible scene counts per episode, fewer LLM calls, and soft quality review instead of broad hard-coded content rejection.

## What Changes

- **BREAKING**: Replace the legacy `/api/v1/series` API contract with a v2 contract; old request/response shapes are not preserved.
- Add a dedicated series v2 backend flow with clear phases: intake/routing, series bible, season map, episode brief gate, episode blueprint, episode scene generation, technical validation, optional semantic/fact review, continuity delta, and final persistence.
- Add user-editable episode brief support so the old 3-option episode suggestion step is removed; users can adjust title, premise, required inclusions, exclusions, scene count, and ending mode before generation.
- Add flexible per-episode scene count for long and short series instead of hard-coding `series_short=8` and `series_long=30`.
- Add continuity-first episode handoff artifacts so non-final episodes are designed to leave forward-driving unresolved state rather than closing as isolated stories.
- Add series v2 database tables without dropping or migrating legacy `series`/`episodes` data.
- Hide existing frontend series entry points until a rebuilt series UI is implemented.
- Add tests that keep single/longform isolated from series and prevent the v2 core from importing legacy series orchestration.

## Capabilities

### New Capabilities
- `series-generation-v2`: Defines the v2 series generation API, data model, generation phases, continuity handoff behavior, user-editable episode briefs, flexible scene counts, validation posture, and performance constraints.

### Modified Capabilities
- `backend-maintenance-stability`: Series feature gating changes from preserving the old beta flow to mounting the v2 implementation on `/api/v1/series` while keeping legacy tables deploy-safe.
- `backend-production-architecture`: Series generation adopts explicit role-style phase contracts and must remain independent from the single-video `ProductionService` orchestration.
- `youtube-script-ai`: Frontend behavior changes by hiding the old series UI entry points until the rebuilt series interface targets the v2 contract.

## Impact

- Backend API: `app/api/v1/endpoints/series.py`, `app/api/v1/router.py`, config flags, schemas, services, repositories, tests.
- Backend database: new Alembic migration for `series_v2` and `series_episode_v2`; no destructive migration for legacy tables.
- Backend generation: new `app/services/series_v2/` package that reuses small infrastructure helpers but does not call `ProductionService`.
- Frontend: hide current series mode selector, navigation item, and redirect path that call the legacy contract.
- Deployment: Supabase/Render startup migrations remain add-only and rollback-safe; Vercel frontend must not expose dead series actions during the backend contract break.
