# Contributing to StampChain

## Branch Strategy

- `main` — production releases only
- `dev` — active development
- `feature/xxx` — new features
- `fix/xxx` — bug fixes
- `release/x.x.x` — release preparation

## Commit Convention

Format: `type: description`

Types:
- `feat:` — new feature
- `fix:` — bug fix
- `fiscal:` — tax/compliance change
- `docs:` — documentation
- `test:` — test addition/fix
- `chore:` — maintenance

Examples:

```
feat: add stamp recovery quarantine workflow
fix: FIFO sequence not resetting on new year
fiscal: add recovery movement to balance calc
```

## Before Submitting

1. Run all tests:
   ```bash
   docker compose exec odoo odoo \
     -d stampchain_dev --test-enable \
     --test-tags stamp_chain \
     --stop-after-init --no-http
   ```
2. Update CHANGELOG.md
3. Update ROADMAP.md checklist

## Author

jotaccf
