# longshot: project brain

Search public NASA TESS data for long-period transiting exoplanet candidates with one or two
transits (single transits, duotransits) around M dwarfs. Credibility is the product:
reproducible, honestly vetted, clearly documented. A clean null result is a valid outcome.

People: Oskar (student, Poland) decides at checkpoints, handles accounts, submissions, emails.
Claude does science and engineering. Claude never submits anything to ExoFOP or journals.

## Start of every session
1. Read this file and the top entry of docs/log.md.
2. Check open PRs and the "Current state" section below.

## End of every session
- Add a dated entry at the top of docs/log.md: done, found, next, open questions for Oskar.
- Update "Current state" below.

## Where things live
- docs/plan.md: approved plan (targets, data, methods, vetting, Phase 1 pass criteria).
- docs/decisions.md: dated decisions with reasons (D001...). Thresholds are set here BEFORE
  looking at search results.
- docs/log.md: research journal, newest first.
- docs/sources.md: every paper, dataset, tool, policy, with links.
- docs/emails/: drafts for Oskar to send.
- candidates/registry.csv: single source of truth for every signal. Reports in
  candidates/reports/<id>.md.
- configs/*.yaml: one config per stage run.
- src/longshot/: package. CLI: `uv run longshot <stage> --config configs/<x>.yaml`.
- results/runs/<run_id>/manifest.json: git commit, config, data versions, timestamps, counts.
- data/: download cache, gitignored, always re-downloadable.
- .claude/agents/: literature-scout, skeptic-vetter, reproducibility-checker.

## Rules
- Never call anything a "planet". Use: signal, candidate, vetted candidate, CTOI.
- Every claim in docs or the paper traces to a file in results/ or a cited source.
- When unsure whether a signal is real, it is not real until vetting says otherwise.
- Prefer maintained libraries; own algorithms must be tested against a known implementation.
- Tests (pytest) for every stage. Every run writes a manifest.
- Never use em dashes anywhere (docs, code, commits, paper).
- No raw data in git. No secrets in git.
- Git: develop on the session's designated branch, PR to main, merge after tests pass, then
  restart the branch from main (D010). Never force-push main.
- Runs needing > ~20 min compute or > 16 GB RAM: stop and give Oskar the exact command for his
  PC (Windows, RTX 3060 Ti 8 GB, 32 GB RAM, 100-500 GB free disk).
- Cloud network: if a download is blocked, stop and tell Oskar the exact domains to allow.
- AI use is disclosed in an AI disclosure statement at the end of any paper (AAS policy).

## Environment
- uv + uv.lock, Python 3.12. `uv sync` then `uv run pytest`.
- Hosts used: mast.stsci.edu, archive.stsci.edu, stpubdata.s3.amazonaws.com,
  exofop.ipac.caltech.edu, exoplanetarchive.ipac.caltech.edu, gea.esac.esa.int,
  ssp.imcce.fr, pypi.org.

## Current state (update every session)
- Phase: 0 complete (plan approved 2026-11-19). Phase 1 (validation) starting.
- Target set: M dwarfs, QLP S1-104, TESS-SPOC as independent check (D001, D002).
- Waiting on Oskar: send emails in docs/emails/; ExoFOP account after Phase 1; advisor search.
- Candidates: none. Registry empty.
