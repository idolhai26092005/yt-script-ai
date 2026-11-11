## 1. Baseline And Architecture Records

- [x] 1.1 Add characterization tests for production SSE event keys, resume cache compatibility, phase log writes, and canonical v3 save shape.
- [x] 1.2 Generate an import map for `ProductionService`, `app.core.validation`, and `app.core.production_prompts`.
- [x] 1.3 Add ADR-0001 for production role graph with context, decision, consequences, and reversal plan.
- [x] 1.4 Add ADR-0002 for validation registry and compatibility re-export strategy.
- [x] 1.5 Add ADR-0003 for prompt catalog and prompt ownership/versioning.

## 2. State And Support Seams

- [x] 2.1 Create `backend/app/services/production/state.py` and move script work-state creation, resume signature, cache compatibility, and cache hydrate helpers behind compatibility calls.
- [x] 2.2 Create `backend/app/services/production/support/sse.py` and move shared SSE event/heartbeat behavior without changing event payload keys.
- [x] 2.3 Create `backend/app/services/production/support/scene_merge.py` and move scene upsert/find/prepare helpers without changing merge behavior.
- [ ] 2.4 Run targeted producer resume and SSE tests after the state/support extraction.

## 3. Validation Package

- [x] 3.1 Create `backend/app/services/production/validation/contracts.py` for `SceneContract`, `ScriptContract`, `ValidationIssue`, and severity constants.
- [x] 3.2 Create `backend/app/services/production/validation/adapters.py` for legacy/canonical scene and script normalization.
- [x] 3.3 Move story contract, scene, emotion arc, and constraint validators into role-specific validation modules.
- [x] 3.4 Add `backend/app/services/production/validation/registry.py` with phase-to-validator mapping and stable rule codes.
- [x] 3.5 Convert `backend/app/core/validation.py` into a compatibility re-export while existing imports migrate.
- [ ] 3.6 Run validation, semantic verifier, and constraint lock tests.

## 4. Prompt Catalog

- [x] 4.1 Create `backend/app/services/production/prompts/catalog.py` with `PromptSpec` and stable prompt ids.
- [x] 4.2 Split blueprint, scene batch, semantic verifier, packaging, safety, and series prompts into role-owned prompt modules.
- [x] 4.3 Convert `backend/app/core/production_prompts.py` into a compatibility re-export while existing imports migrate.
- [x] 4.4 Add prompt catalog tests that verify prompt id, owner role, version, and expected output schema metadata.
- [ ] 4.5 Run prompt tag/style, series prompt, and bilingual prompt tests.

## 5. Role Graph Runner

- [x] 5.1 Add `backend/app/services/production/ports.py` with minimal Protocols for LLM, repository, clock, and sleeper behavior used by roles.
- [x] 5.2 Add `RoleResult`, `RoleSpec`, and `RoleContext` types with schema version, artifact keys, validation issues, warnings, retry count, and cache-hit fields.
- [x] 5.3 Add `backend/app/services/production/orchestrator.py` to execute role specs declaratively and adapt role results to existing SSE events.
- [x] 5.4 Extract `BlueprintRole` and `EmotionArcRole` behind existing `ScriptProducer` public methods.
- [x] 5.5 Extract `SceneBatchRole` and `SemanticVerifierRole` behind existing `ScriptProducer` public methods.
- [x] 5.6 Extract `PackagingRole` and `FactCheckRole`, including no-op strategies for disabled optional roles.
- [ ] 5.7 Run producer flow, longform, resume cache, semantic verifier, and observability tests.

## 6. Endpoint Application Services

- [x] 6.1 Create application service for script suggestions that handles topic/YouTube/project orchestration outside FastAPI endpoint code.
- [x] 6.2 Create application service for selected project/suggestion resolution used by full script generation.
- [x] 6.3 Update `script_production.py` endpoint functions to remain thin HTTP adapters.
- [x] 6.4 Update `series.py` episode script generation to reuse the same application/service seam where applicable.
- [ ] 6.5 Run routing, script production SSE, CRUD series/episode integration, and endpoint tests.

## 7. Review And Boundary Enforcement

- [x] 7.1 Add an AST-based import-boundary test or equivalent linter config for endpoint/application/production/infrastructure direction.
- [x] 7.2 Add PR review checklist documentation for pure move, compatibility shim, behavior change, and contract change labels.
- [x] 7.3 Add complexity/line-count check script or documented command for runtime file and function size gates.
- [x] 7.4 Ensure compatibility shims include durable comments with removal phase.

## 8. Cleanup And Verification

- [x] 8.1 Migrate runtime and test imports away from compatibility modules where stable.
- [x] 8.2 Remove stale compatibility shims after their migration phase expires.
- [x] 8.3 Update backend/docs README files and ADR status after module structure changes.
- [ ] 8.4 Run the full targeted backend test set for production, validation, prompt, endpoint, and observability behavior.
- [x] 8.5 Run `graphify update backend` after backend runtime code changes and verify backend graph artifacts refresh.
