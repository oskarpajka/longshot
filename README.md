# longshot

An open, reproducible search for long-period transiting exoplanet candidates with only one or
two transits (single transits and duotransits) around M dwarfs in public NASA TESS data.

Status: Phase 1 (pipeline validation). No candidates yet. See `docs/plan.md` for the plan,
`docs/decisions.md` for every choice and threshold, and `docs/log.md` for progress.

## Quick start

```bash
uv sync
uv run pytest
uv run longshot check-registry --config configs/check_registry.yaml
```

Every stage runs as `uv run longshot <stage> --config configs/<file>.yaml` and writes
`results/runs/<run_id>/manifest.json` (git commit, config, data versions, counts, checksums).
Raw data is cached in `data/` (not committed) and can always be re-downloaded from MAST.

## Terminology

Nothing here is called a planet. Signals become candidates, then vetted candidates, after the
checks in `docs/plan.md` section 6. Confirmation requires follow-up observations outside the
scope of this project.

## AI assistance

This project is developed with substantial help from an AI assistant (Claude, Anthropic). All
decisions, data products and claims are reviewed by the human author. Any publication will
include an AI disclosure statement following AAS policy.
