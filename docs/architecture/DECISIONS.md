# Architecture decisions

## Physical monorepo migration

The M1–M6 capability boundaries remain documented but no longer dictate top-level directories. Serving data/features/inference/risk modules now live in `packages/strikecast_core/`; the only served API lives in `apps/api/strikecast_api/`; the UI lives in `apps/web/`. The experimental multimodal stack is under `ml/research/strikecast/`, with trainer source in `ml/training/strikecast_training/`. Exact source destinations are listed in [the migration map](MIGRATION_MAP.md).

## Separate serving and research contracts

The served point path consumes a six-step, 3×3, eight-feature tensor. The research package builds a distinct gridded multimodal contract. No validated compatible artifact or preprocessing bridge exists, so research candidates are not imported by the API or promoted automatically.

## One API boundary

`apps/api/strikecast_api/main.py` is the only served service. `ml/research/legacy_api/` remains for research compatibility tests and is not launched by root scripts, CI deployment, frontend configuration, or Compose.

## Scientific status

The bundled model is synthetic-trained and DEMO_ONLY. There is no verified real labeled dataset, held-out evaluation, calibration, or production model. Risk thresholds remain provisional and LIVE prediction fails closed. Software checks do not establish forecast skill.
