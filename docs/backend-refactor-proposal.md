# Backend Refactor Proposal

## Muc tieu

Tai cau truc backend de file ngan hon, ro vai tro hon, test nhanh hon, nhung khong pha pipeline sinh screenplay hien tai.

Pham vi uu tien: `backend/app/services/production/producer.py`, `backend/app/core/validation.py`, `backend/app/core/production_prompts.py`, `backend/app/api/v1/endpoints/script_production.py`, `backend/app/api/v1/endpoints/series.py`.

## Bang chung hien tai

- `graphify update backend` da chay ngay 2026-07-28: `1012 nodes`, `1944 edges`, `96 communities`; `backend/graphify-out/GRAPH_REPORT.md` built from commit `a3fbe06e`.
- Hotspot theo line count:
  - `services/production/producer.py`: 2603 dong.
  - `core/validation.py`: 1090 dong.
  - `core/production_prompts.py`: 672 dong.
  - `api/v1/endpoints/series.py`: 611 dong.
  - `services/production/base.py`: 474 dong.
- Graphify chi dung de dinh huong kien truc; khi tach module, `rg --files`, import graph thuc te, va tests la nguon xac minh cuoi.

## OpenSpec artifacts

Proposal nay da duoc chuyen thanh OpenSpec change de de review/apply theo tung task:

- `openspec/changes/refactor-backend-production-architecture/proposal.md`: why/what/impact.
- `openspec/changes/refactor-backend-production-architecture/design.md`: technical design va trade-offs.
- `openspec/changes/refactor-backend-production-architecture/specs/backend-production-architecture/spec.md`: testable requirements.
- `openspec/changes/refactor-backend-production-architecture/tasks.md`: implementation checklist.

`openspec status --change refactor-backend-production-architecture` hien `4/4 artifacts complete`.

## Van de kien truc

### 1. `ScriptProducer` dang la God Object

`ScriptProducer` gom orchestration, cache resume, prompt assembly, LLM retry, scene merge, semantic verifier, packaging, fact-check, persistence, debug snapshot. Vi pham SRP va Open/Closed: them phase moi phai sua file 2600 dong.

### 2. `validation.py` gom nhieu mien

File nay dang tron schema adapter, story contract, constraint model, scene validator, emotion arc validator, state machine, historical coverage. Vi pham Interface Segregation: caller phai import 1 module lon cho nhieu nhu cau nho.

### 3. Prompt constants la blob

`production_prompts.py` gom prompt runtime, series prompt, safety rules, verifier prompt, packaging prompt. Kho review diff, kho versioning, kho test prompt theo role.

### 4. Endpoint lam qua nhieu

`script_production.py` vua parse input, xu ly YouTube/topic, tao project, chon suggestion, khoi tao service, stream SSE. Nen endpoint chi lam HTTP adapter.

### 5. Mixin facade khong ro contract

`ProductionService(IdeaSuggester, TopicSuggester, ScriptProducer)` la multiple inheritance de gom API. De dung nhanh, nhung kho thay the role va kho mock theo interface.

## Nguyen tac refactor

1. Public API giu nguyen: `/suggestions`, `/script/generate`, schema response, SSE event format.
2. Cache/schema giu nguyen: producer van lam viec qua legacy v2 adapter va save canonical v3.
3. Role graph thay phase list: moi role co `Input -> Output + Invariants`.
4. Declarative dispatch: routing, validators, phase order, prompt selection la data table, khong rai `if/else`.
5. Strangler pattern: boc tach quanh file cu, khong rewrite lon 1 lan.
6. Test first around seam: moi lan tach 1 role, chay test lien quan truoc khi tach tiep.

## Chuan bo sung de code de review

### 1. Clean Architecture / Hexagonal Architecture

Backend nen chia theo huong dependency vao trong:

```text
api/endpoints -> application/use_cases -> domain/contracts -> infrastructure
```

Quy tac import:

- `api/*` duoc import `schemas`, `deps`, `application`.
- `application/*` duoc import `services/production`, `crud` qua Protocol, khong biet FastAPI `Request`.
- `services/production/*` duoc import domain contracts, prompt catalog, repository Protocol.
- `core/repository.py` / `crud/*` la infrastructure, khong duoc import endpoint.
- `models/*` khong import service, endpoint, prompt.

Neu can enforcement ve sau: them `import-linter` contract hoac test tu viet bang `ast` de chan import nguoc.

### 2. DDD nhe, khong over-engineer

Bounded contexts nen tach:

- `production`: screenplay role graph, prompt, validation, SSE artifact stream.
- `catalog`: topic/trending/topic suggestion.
- `series`: series/episode continuity va episode project bridge.
- `identity/quota`: API key, quota, auth dependency.
- `transcript`: YouTube transcript + compression.

Khong can entity/repository phuc tap cho moi bang. Chi ap dung DDD o noi co business rule that: production pipeline, series continuity, quota.

### 3. ADR va RFC nho

Moi thay doi kien truc lon nen co ADR ngan trong `docs/adr/`:

```text
docs/adr/
├── 0001-production-role-graph.md
├── 0002-validation-registry.md
└── 0003-prompt-catalog.md
```

Template ADR:

```md
# ADR-000X: Decision title

## Context
Van de can quyet dinh.

## Decision
Lua chon chinh.

## Consequences
Loi, hai, migration cost.

## Reversal Plan
Neu sai thi rollback the nao.
```

RFC truoc khi code phase lon:

- Problem statement.
- Affected files.
- Public API compatibility.
- Migration path.
- Test plan.
- Rollback plan.

### 4. Reviewability budget

Moi PR refactor nen co gioi han:

- <= 8 files runtime changed.
- <= 500 changed lines, tru compatibility re-export.
- 1 semantic move per PR: state, validation, prompt, role, endpoint.
- Khong vua move code vua doi behavior trong cung commit.
- Neu phai doi behavior: test regression truoc, implementation sau.

Diff review labels:

- `pure-move`: doi path/import, behavior same.
- `compat-shim`: re-export/deprecation layer.
- `behavior-change`: co test bat buoc.
- `contract-change`: schema/API/SSE/cache, can migration note.

### 5. Module public surface

Moi package moi can `__all__` ro hoac import public trong `__init__.py`.

Quy tac:

- Public function/class khong bat dau `_`.
- Private helper nam cung module role, khong export.
- Cross-package import chi dung public symbol.
- Compatibility module cu (`core/validation.py`, `core/production_prompts.py`) chi re-export, khong them logic moi.

### 6. Complexity gates

Muc tieu de code de doc:

- File runtime <= 400 dong, hard cap 800 dong.
- Function <= 60 dong, hard cap 120 dong.
- Cyclomatic complexity <= 10 cho function business logic.
- Role object <= 1 public `run()` + helper private.
- Endpoint function <= 80 dong.
- Prompt file <= 350 dong va chi 1 domain/role.

Neu vuot cap, PR phai co ly do trong comment/ADR.

### 7. Contract-first schema

Truoc khi tach role, dinh nghia contract noi bo:

```python
@dataclass(frozen=True)
class RoleResult:
    role_name: str
    schema_version: str
    artifacts: dict
    validation_issues: list[ValidationIssue]
    warnings: list[str]
```

Rule:

- Role khong tra raw tuple/dict loose neu output di qua phase tiep.
- Moi output co `schema_version`.
- Adapter lo v2/v3/canonical; validator chi thay contract.
- SSE payload la adapter tu `RoleResult`, khong build string rai rac.

### 8. Observability standard

Phase log can du de debug:

- `stage_role`
- `schema_version`
- `artifact_keys`
- `validation_errors`
- `retry_count`
- `latency_ms`
- `model_name`
- `cache_hit`

Khong log raw prompt/output day du vao DB mac dinh. Debug snapshot nen gated by config va scrub key/token.

### 9. Error taxonomy

Dung 4 nhom loi:

- `BLOCK`: sai contract, khong duoc save complete.
- `RETRY`: co the retry LLM voi feedback cu the.
- `WARN`: chat luong can xem nhung khong stop.
- `SYSTEM`: DB/network/provider error, khong coi la validation.

Moi role chi throw exception cho `SYSTEM`; validation phai tra `ValidationIssue`.

### 10. Test pyramid

Thu tu test theo refactor:

- Unit: adapter/validator/prompt renderer, khong LLM.
- Characterization: input cu -> event/cache shape cu.
- Contract: role input/output fields.
- Integration: `ProductionService` voi fake LLM/repo.
- Endpoint: FastAPI request/SSE wrapper.
- Golden sample: 1-2 screenplay sample de bat drift lon.

Khong chay full integration cho moi pure move neu unit/import tests da du.

### 11. Compatibility clock

Moi shim cu co comment va han xoa:

```python
# Compatibility shim: keep legacy imports stable while validation package migrates.
# Remove after all imports move to app.services.production.validation in Phase B.
```

Rule: shim khong song qua 2 phase lien tiep neu khong co ly do.

### 12. "Design patent" vs Design Patterns

Trong proposal nay, "Design patent" duoc hieu la "Design Patterns" / chuan thiet ke phan mem. Neu can bao ve UI/product IP thi la mien phap ly khac, khong lien quan refactor backend.

## Kien truc de xuat

```text
backend/app/services/production/
├── facade.py                 # Public API compatibility: ProductionService
├── orchestrator.py           # RoleGraphRunner / SSE stream orchestration
├── state.py                  # ScriptWorkState, resume signature/cache hydrate
├── ports.py                  # Protocols: LLMClient, Repository, Clock, Sleeper
├── roles/
│   ├── blueprint.py          # Narrative Blueprint + Continuity Anchor
│   ├── emotion_arc.py        # Emotion/Beat Layer
│   ├── scene_batch.py        # Scene/Shot Layer
│   ├── semantic_verify.py    # Content Verification
│   ├── packaging.py          # Packaging & Metadata
│   └── fact_check.py         # Reality-bound fact-check
├── prompts/
│   ├── catalog.py            # Declarative PromptSpec registry
│   ├── blueprint.py
│   ├── scenes.py
│   ├── verifier.py
│   └── packaging.py
├── validation/
│   ├── contracts.py          # SceneContract, ScriptContract, ValidationIssue
│   ├── adapters.py           # legacy/canonical -> contract
│   ├── registry.py           # Declarative validator registry
│   ├── scene.py
│   ├── emotion_arc.py
│   ├── story_contract.py
│   └── constraints.py
└── support/
    ├── story_spine.py
    ├── scene_merge.py
    └── sse.py
```

`backend/app/core/validation.py` va `backend/app/core/production_prompts.py` ban dau nen thanh compatibility re-export de test/import cu chua vo.

## Design Patterns ap dung

- Strangler Fig: tao module moi, re-export tu module cu, cat dan method.
- Template Method: `BaseRole.run()` gom log latency, validate, retry, save phase log.
- Strategy: `FactCheckStrategy`, `SemanticVerifierStrategy`, `BatchingStrategy`.
- Registry: `VALIDATOR_REGISTRY`, `PROMPT_CATALOG`, `ROUTING_TABLE`.
- Facade: `ProductionService` giu API cu, uy quyen cho orchestrator.
- Repository/Ports: business logic chi goi Protocol, khong goi SQLAlchemy truc tiep.
- Adapter: schema v2/v3/canonical chuyen ve contract noi bo.
- Command: moi role la command co `role_name`, `requires`, `produces`.
- Null Object: `NoopFactCheckRole`, `NoopSemanticVerifierRole` thay `if enabled` rai rac.
- Specification: validation rule la object/function co `code`, `severity`, `phase`, `check()`.
- Unit of Work: DB transaction gom cac update lien quan phase neu can consistency.

## SOLID mapping

- SRP: role chi sinh/kiem tra 1 artifact.
- OCP: them content category bang routing/validator/prompt data, khong sua runner.
- LSP: fake role/fake repo thay duoc role/repo that trong test.
- ISP: tach `PromptRenderer`, `ScreenplayRepository`, `PhaseLogger`, `QuotaCounter`.
- DIP: orchestrator phu thuoc Protocol, khong phu thuoc Gemini/SQLAlchemy truc tiep.

## Lap trinh khai bao

### Role graph

```python
ROLE_GRAPH = [
    RoleSpec("blueprint", requires=["request"], produces=["prompt_0", "story_contract"]),
    RoleSpec("emotion_arc", requires=["prompt_0"], produces=["emotion_arc"]),
    RoleSpec("scene_batch", requires=["prompt_0", "emotion_arc"], produces=["scenes"]),
    RoleSpec("semantic_verify", requires=["scenes"], produces=["quality_warnings"]),
    RoleSpec("packaging", requires=["scenes"], produces=["reference_images"]),
    RoleSpec("fact_check", requires=["scenes"], produces=["fact_check_notes"], when="fact_check_enabled"),
]
```

### Validator registry

```python
VALIDATOR_REGISTRY = {
    "scene_batch": [
        validate_scene_generation_issues,
        validate_story_contract_issues,
        validate_emotion_arc_constraints,
    ],
    "complete": [
        validate_script,
        validate_state_invariants,
        validate_historical_coverage,
    ],
}
```

### Prompt catalog

```python
PROMPT_CATALOG = {
    "blueprint.v1": PromptSpec(template=PROMPT_0_GENERATION_TEMPLATE, schema="Prompt0Output"),
    "scene_batch.v1": PromptSpec(template=BATCH_SCENE_GENERATION_TEMPLATE, schema="SceneBatchOutput"),
}
```

## Ke hoach migrate an toan

### Phase 0: characterization baseline

1. Dong bang current behavior bang test snapshot cho SSE event keys, cache resume, phase log, schema v3 save.
2. Lap import map bang `rg` cho `ProductionService`, `core.validation`, `core.production_prompts`.
3. Them ADR-0001 mo ta role graph va rollback.

Test: `pytest backend/tests/test_producer_resume_cache.py backend/tests/test_script_production_sse.py backend/tests/test_observability.py`.

### Phase A: tao seam, khong doi behavior

1. Tao `production/state.py`: chuyen `_new_script_data`, resume signature, cache hydrate.
2. Tao `production/support/sse.py`: chuyen `_stream_event`, `safe_sse_stream` dung chung endpoint/producer.
3. Tao `production/support/scene_merge.py`: chuyen `_upsert_scene`, `_find_scene`, `_prepare_scene`, title standardization wrapper.
4. Giu import cu bang re-export de tests khong vo.

Test: `pytest backend/tests/test_producer_resume_cache.py backend/tests/test_script_production_sse.py`.

### Phase B: tach validation package

1. Tao `production/validation/contracts.py`, `adapters.py`, `scene.py`, `story_contract.py`, `emotion_arc.py`, `constraints.py`.
2. `app/core/validation.py` re-export API cu.
3. Them `registry.py` de producer goi theo phase.

Test: `pytest backend/tests/test_validation.py backend/tests/test_semantic_verifier.py backend/tests/test_constraint_lock_pipeline.py`.

### Phase C: tach prompt catalog

1. Tach prompt theo role trong `production/prompts/`.
2. `core/production_prompts.py` re-export constants cu.
3. Them `PromptSpec` gom `id`, `template`, `expected_json`, `version`, `owner_role`.

Test: `pytest backend/tests/test_prompt_tag_style.py backend/tests/test_prompts_series.py backend/tests/test_prompts_bilingual.py`.

### Phase D: role objects

1. Tao `RoleContext`: state, routing, repo, llm, model, timing, request settings.
2. Tach `BlueprintRole`, `EmotionArcRole`, `SceneBatchRole`, `SemanticVerifierRole`, `PackagingRole`, `FactCheckRole`.
3. `RoleGraphRunner` stream event theo role output, luu phase log.
4. `ScriptProducer.generate_full_script_stream()` chi uy quyen runner.

Test: producer flow/resume/longform tests.

### Phase E: endpoint thin adapter

1. Tach `SuggestionApplicationService`.
2. Tach `ProjectSelectionService`.
3. Endpoint chi validate HTTP, auth, call application service.

Test: `pytest backend/tests/test_routing.py backend/tests/test_script_production_sse.py backend/tests/test_crud_series_episode_integration.py`.

### Phase F: remove shims

1. Doi imports test/runtime sang module moi.
2. Xoa logic con lai trong compatibility module, giu re-export neu public API can.
3. Cap nhat `backend/README.md` va ADR status.

Test: targeted + import smoke test.

## Thu tu uu tien

1. Phase 0 characterization: bat behavior hien tai truoc.
2. `producer.py` tach state/support truoc: rui ro thap, giam 300-500 dong.
3. `validation.py` tach package: giam blast radius, giu API cu.
4. `production_prompts.py` tach catalog: review prompt de hon.
5. RoleGraphRunner: thay doi lon nhat, chi lam sau khi seam/test da on.
6. Endpoint service layer: lam sau core pipeline.
7. Remove shims: chi lam khi imports da di het.

## Guardrails bat buoc

- Moi block code moi/sua phai co durable comment ngan theo `comment-before-change`.
- Sau moi lan sua code backend: chay tests lien quan va `graphify update backend`.
- Khong merge output LLM failed validation vao final output.
- Khong doi `ProductionService` public constructor trong lan dau.
- Khong doi DB schema khi chi tach module.
- Khong doi SSE payload key khi khong co migration frontend.
- Khong them dependency moi neu Python stdlib/FastAPI/Pydantic da du.
- Khong de endpoint import role noi bo; endpoint chi goi application service/facade.
- Khong de role goi SQLAlchemy session truc tiep.
- Khong de prompt template import validator/runtime service.

## Review checklist

Dung checklist nay khi review PR refactor:

- File move co behavior test hoac pure-move proof.
- Public imports cu van pass.
- SSE event keys khong doi.
- Cache resume tu old v2/new v3 van pass.
- Role output co validation result.
- New module khong import nguoc layer tren.
- Validation rule co `code` on dinh de log/retry.
- Prompt change co test tag/style/schema.
- Failure path co test, khong chi happy path.
- `graphify update backend` da chay neu sua backend code.

## Suggested PR slices

```text
PR-01: characterization tests + ADR-0001
PR-02: production/state.py + compatibility calls
PR-03: support/sse.py + endpoint/producer reuse
PR-04: support/scene_merge.py + tests
PR-05: validation/contracts.py + adapters.py re-export
PR-06: validation/story_contract.py + scene.py
PR-07: validation/registry.py + producer registry call
PR-08: prompts/catalog.py + prompt re-export
PR-09: BlueprintRole + EmotionArcRole behind ScriptProducer
PR-10: SceneBatchRole + SemanticVerifierRole
PR-11: PackagingRole + FactCheckRole
PR-12: application services for endpoints
PR-13: remove stale shims + backend README/ADR update
```

## Done criteria

- Khong file backend app nao > 800 dong, rieng prompt file moi moi file < 350 dong.
- `producer.py` con facade/compat < 300 dong hoac xoa han sau khi caller migrate.
- Validator moi co package rieng, `core/validation.py` chi re-export.
- Prompt moi co catalog + test import cu.
- Import boundary test/import-linter rule co trong CI hoac pytest.
- ADR cho role graph, validation registry, prompt catalog da co.
- Review checklist duoc copy vao PR template hoac docs.
- Full targeted tests xanh.
- `graphify update backend` chay sau code backend changes.
