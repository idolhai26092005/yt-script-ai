# Backend Complexity Gates

Use these gates while refactoring backend production code.

## Soft Gates

- Runtime file: <= 400 lines.
- Runtime function: <= 60 lines.
- Endpoint function: <= 80 lines.
- Prompt module: <= 350 lines.
- PR: <= 8 runtime files and <= 500 changed runtime lines.

## Hard Gates

- Runtime file: <= 800 lines unless ADR explains exception.
- Runtime function: <= 120 lines unless ADR explains exception.
- Do not combine pure move and behavior change in one PR.
- Do not add runtime dependency without ADR.
- Do not run `graphify update .`; backend changes use `graphify update backend`.

## Manual Audit Commands

```bash
find backend/app -name '*.py' -print0 | xargs -0 wc -l | sort -nr | head -25
rg -n '^def |^async def |^    def |^    async def |^class ' backend/app/services/production
```

## Notes

These gates are review aids first. Turn them into CI only after current long files are split enough to avoid noisy failures.

