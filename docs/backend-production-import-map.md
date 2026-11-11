# Backend Production Import Map

Generated for OpenSpec change `refactor-backend-production-architecture`.

## Scope

Tracked symbols:

- `ProductionService`
- `app.core.validation`
- `app.core.production_prompts`

Source commands:

```bash
rg -n "ProductionService|from app\.core\.validation|from app\.core\.production_prompts" backend/app backend/tests
graphify update backend
```

## Runtime imports

- `backend/app/services/production/__init__.py` exports `ProductionService`.
- `backend/app/services/production/facade.py` composes `IdeaSuggester`, `TopicSuggester`, and `ScriptProducer`.
- `backend/app/api/v1/endpoints/script_production.py` imports `ProductionService`.
- `backend/app/api/v1/endpoints/series.py` imports `ProductionService` and series prompt constants from `app.core.production_prompts`.
- `backend/app/services/production/producer.py` imports validators from `app.core.validation` and prompt constants from `app.core.production_prompts`.
- `backend/app/services/production/context_compressor.py` imports `CONTEXT_COMPRESSION_PROMPT` from `app.core.production_prompts`.
- `backend/app/services/production/idea_suggester.py` imports `SYSTEM_PROMPT_GENERATE_SUGGESTIONS` from `app.core.production_prompts`.
- `backend/app/services/production/topic_suggester.py` imports `SYSTEM_PROMPT_TOPIC_SUGGESTIONS` from `app.core.production_prompts`.

## Test imports

- Production facade tests import `ProductionService` widely in producer, validation, semantic verifier, context injection, chunk split, longform, single-flow, and script producer tests.
- Validation tests import public validators from `app.core.validation`.
- Prompt tests import constants from `app.core.production_prompts`.
- Resume cache tests import both validation symbols and production prompt constants.

## Migration notes

- Keep `ProductionService` constructor stable until role graph delegation is complete.
- Keep `app.core.validation` as compatibility re-export during validation package migration.
- Keep `app.core.production_prompts` as compatibility re-export during prompt catalog migration.
- Move tests only after runtime imports are stable; test imports are useful tripwires for compatibility.
