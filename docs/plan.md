# longshot: Phase 0 plan

Date: 2026-11-19. Status: APPROVED by Oskar on 2026-11-19 (Phase 0 checkpoint).
Sources marked [S#] are listed at the end and will go into docs/sources.md.

## 0. Context

The repo is empty (README, .gitignore). Goal: find new long-period single and duotransit
candidates in public TESS data, with a reproducible pipeline whose credibility is the product.
This plan sets the target gap, data, methods, vetting, validation criteria, repo layout and
the publication route, based on a literature and archive review done today.

## 1. Findings that change your plan (read first)

1. **CTOI requires publication first; your order (CTOI, then RNAAS) cannot work.** Verified on
   ExoFOP's candidate guidelines today [S1]: community candidates must already be published in a
   peer-reviewed journal (paper URL required, plus approval through a "Published Candidate Upload
   Request"). An RNAAS note is accepted only if the detection and vetting method was previously
   published in a peer-reviewed journal and cited. The same page says RNAAS "is no longer accepting
   notes that use open data and standard, open source, tools to find transits ... presenting them
   as potential planet candidates". The RNAAS pages themselves do not say this [S2]; it needs
   confirming with the RNAAS editor by email (you).
2. **A single transit without a period will not be considered for TOI promotion.** ExoFOP: for TOI
   working group consideration, period, epoch, depth and duration must all be > 0 [S1]. So
   duotransits (which give a discrete alias set) are the more useful product; single transits are
   still searched and logged but are second priority.
3. **RNAAS limits are 1500 words (incl. a required 150-word abstract), one figure or one table**
   [S2]. Not 1000. Keeping under 1000 is fine as our own target.
4. **AAS AI policy (posted 2026-09-09):** LLM use must be disclosed in an AI disclosure statement
   at the end of the article, not in the acknowledgments; unsupervised AI generation of any part
   of a manuscript is not allowed [S3]. So every paper sentence must be reviewed and owned by you.
5. **Gaia DR4 releases 2026-12-02** [S4]. We build with DR3 and switch vetting cross-matches to
   DR4 when it is out (it will be before we vet anything).
6. **TRICERATOPS needs a period**; it is not built for single transits [S5]. We run it over the
   period posterior and report sensitivity; we never call its output "validation".

## 2. What is already done (prior work) and the gap

Archive check (ExoFOP TOI and CTOI tables downloaded 2026-11-19, 8175 TOIs, 5139 CTOIs):
- Single-transit CTOIs: 936, of which 813 have Tmag < 12 and only 29 have Tmag > 13.
- The TESS Single Transit Planet Candidate (TSTPC) working group submitted 238 of them, all Tmag <= 12.0.
- Single-transit CTOIs on stars with Teff < 4000 K: 59 of 911 with Teff. Single-transit TOIs: 109 total, 10 on Teff < 4000 K.

Published systematic searches (details in docs/sources.md):

| Search | Data | Coverage | Mono/duo? |
|---|---|---|---|
| Hawthorn+ 2024 [S6] | SPOC FFI | S1-38, South only, Tmag 8-14 | 85 duotransits |
| Eisner+ 2021 PHT [S7] | 2-min | S1-26 | 73 singles |
| Salinas+ 2025 / 2026 [S8] | FFI | S1-26 / S27-60 | 88 singles / mixed |
| T16 Planet Hunt [S9] | own FFI phot. | Cycle 1 only, T<16 | 411 bare singles |
| RAVEN [S10] | TESS-SPOC | S1-55, P<16 d | handful |
| LEO-Vetter M dwarfs [S11] | QLP | S1-70, Tmag<14 | **none (needs >=3 transits, P<40 d)** |
| NEMESIS II [S12] | own FFI phot. | S1-26 M dwarfs | none (P<9 d) |
| TSTPC WG (poster) [S13] | own pipeline | all sectors, ~150k stars/sector | not a catalog |

The gap, from this evidence:
- No published mono/duotransit catalog goes past ~sector 62. QLP now reaches sector 104.
- Bright stars (Tmag < 12) are well covered for singles by TSTPC. Fainter stars are not.
- **M dwarfs have been searched only for periodic, short-period signals.** The 2026 review [S14]
  lists "are giant planets around M dwarfs metal-poor? needs more long-period examples" as open.

## 3. Recommendation: target selection

**Primary target set: M dwarfs, all sky, all QLP sectors 1-104.**
- TIC v8.2: 2400 < Teff < 3900 K, R* < 0.6 Rsun, Tmag <= 13.5, TIC contamination ratio < 0.5.
  The sample definition is identical to LEO-Vetter's [S11], so it is citable and comparable. Expected about 170k stars with QLP light curves.
- Why M dwarfs:
  - The search gap is verified (section 2).
  - Small stars give deep transits, so Neptunes and giants are detectable in FFI data at Tmag 12-13.5.
  - Stellar densities are well constrained, which tightens single-transit period estimates and makes the duration vs density test a strong false-positive filter.
  - The science question is clear and open.
  - The sample is small enough for a home PC.
- Honest downside: follow-up (RVs) of faint M dwarfs needs NIR spectrographs. That is fine for a
  candidate catalog but lowers the chance of a quick confirmation by others.

Alternatives (one of them could be the second target set later):
- B. Northern-ecliptic duotransits on FGK dwarfs (the unpublished mirror of Hawthorn 2024), but
  TSTPC likely holds many of the bright ones privately.
- C. FGK dwarfs Tmag 12-13.5 in sectors 56-104.

## 4. Data products

| Use | Product | Why |
|---|---|---|
| Primary search | **QLP** FFI light curves, S1-104 [S15] | Only product covering all sectors to Tmag 13.5; 3 apertures (used in vetting) |
| Independent check | **TESS-SPOC** FFI, S1-86 [S16]; SPOC 2-min where present | Different photometry: a real event must appear in both |
| Pixel vetting | **TESScut** FFI cutouts (and TGLC on candidates only) [S17] | Difference images, centroids, Gaia-PSF photometry for blends |

Known product issues, handled in code with tests:
- QLP S99-104 have a barycentric timing error, and corrected files are pending. Detection is still allowed, but epochs from those sectors stay flagged until the files are redelivered.
- QLP photometry changed at S94.
- TGLC on MAST covers only S1-55.
- eleanor, unpopular, VESPA and allesfitter are unmaintained, so we don't use them.

## 5. Methods

**Detrending:**
- Quality-flag mask, plus extra masks for momentum dumps and orbit-gap edges.
- wotan biweight (pinned 2.x [S18]), window = 3x the longest searched duration (0.75 d for M dwarfs; recorded in decisions).
- Transits are masked when we refit candidates.

**Single-event search:**
- No maintained library exists (MonoTools pins lightkurve 1.11 and scipy 1.12 [S19]; Hawthorn's `monofind` is not packaged).
- So we write a small box/trapezoid matched filter over (t0, duration in 0.5-8 h), with:
  - white noise plus a red-noise (binned-rms beta) term;
  - a minimum number of in-transit points;
  - depth > 0 only.
- We test it against astropy `BoxLeastSquares`: on one transit with P > baseline, our depth and SNR must match BLS to tolerance.

**Periodic check:** stars with >= 3 consistent events are tagged periodic and passed to cross-match only (out of scope, logged).

**Duotransit linking:**
- Pair events on the same star across sectors whose depth and duration agree within 3 sigma.
- Enumerate aliases P_n = dT/n. Reject an alias if a predicted transit lands in good-quality data from any product.
- Weight the survivors by the duration/density likelihood.
- Use tess-point for future coverage only.

**Fitting and period posterior:**
- pytransit or juliet fit with a TIC/Gaia stellar density prior.
- Eccentricity: once circular, once with the Kipping 2013 prior.
- P^-5/3 geometric prior, truncated by the coverage limits (the standard approach, Osborn+ 2016, MonoTools).
- MonoTools runs in an isolated environment as a cross-check on finalists only.

**Thresholds, fixed before any search:**
- Detection threshold from **inverted light curves**: flip the flux and search again; any "dip" found is a false alarm. The threshold is the SNR that gives at most 1 false alarm per 1000 stars.
- Completeness from **injection-recovery** into real light curves.
- Both are run on a calibration subsample that is then excluded from candidate claims.

## 6. Vetting (Phase 3), in order; every step writes to the registry

1. **Automatic triage:**
   - Proximity to momentum dumps, gaps and sector edges, and scattered-light flags.
   - **Common-mode check:** the same dip time in many stars on the same camera/CCD means a systematic.
   - **Asteroid check** with IMCCE SkyBoT at the event time.
2. **Cross-match:**
   - TOI and CTOI (ExoFOP, dated snapshot).
   - NASA Exoplanet Archive PS.
   - TESS EBs (Prsa+ 2022) and TESS Ten Thousand EB (2025) [S20].
   - Gaia DR3/DR4 eclipsing binaries.
   - VSX.
3. **Photometric:**
   - The event must be present in the second product.
   - Depth must be constant across QLP's 3 apertures.
   - Odd/even depths (duos).
   - Secondary eclipse search at each surviving alias.
   - Transit shape (V vs U).
   - Implied Rp < 2 RJ, else likely EB, brown dwarf or low-mass star.
4. **Pixel:**
   - In/out-of-transit difference image from TESScut; centroid offset vs Gaia DR3 positions.
   - For each Gaia neighbor within 2.5', the depth it would need: neighbors that would need >100% eclipses are excluded.
5. **Star:**
   - Gaia RUWE <= 1.4. Above that it is a flag, not an automatic reject.
   - Gaia non-single-star flags.
   - Duration vs stellar density consistency with the allowed period range.
6. **TRICERATOPS FPP/NFPP** over the period posterior.
   - "Vetted candidate" requires FPP < 0.5 and NFPP < 1e-3 (Giacalone "likely planet" [S5]) at all plausible periods.
7. **skeptic-vetter** subagent review (independent, only gets the id), then your review.

Status flow: signal -> rejected | candidate -> vetted -> (published) -> submitted -> toi.

## 7. Phase 1 validation: pass criteria (fixed now, before running)

**Validation set:** at least 8 known long-period transiting systems in QLP, chosen to include single and duotransit cases and at least 3 M/K dwarfs.

- Proposed set, to be confirmed in Phase 1 from the archive:
  - TOI-904 c (84 d, M0)
  - TOI-2257 b (35 d, M3)
  - LHS 1140 b (25 d, M4.5)
  - TOI-1899 b (29 d, M dwarf)
  - TOI-4600 c (483 d, K dwarf, single)
  - TOI-2180 b (261 d, single)
  - TOI-5678 b (48 d, duo)
  - NGTS-30 b (98 d, duo)
- Hidden among about 2000 random sample stars and run blind with the production config.

Pass requires all of:
1. >= 5 of the validation targets recovered:
   - event epoch within 0.5 x duration;
   - duration within 30%;
   - depth within 3 sigma of the literature value;
   - above the production threshold, with no special casing.
2. For each recovered duotransit, the true period is among the surviving aliases.
3. Injection-recovery on >= 20k injections:
   - >= 80% recovery for single events with expected SNR >= 10 that are not in gaps;
   - a completeness map published as a function of Rp and P.
4. False-alarm rate from inverted light curves <= 1 per 1000 stars at the chosen threshold.
5. All stages reproduce from a clean state (the reproducibility-checker agrees with the manifest).

If any check fails: fix, record why in decisions.md, and rerun. Thresholds may change only through a logged decision, never after looking at search results.

## 8. Engineering

**Environment:** uv with `uv.lock`, Python 3.12.
- It is fast, keeps a cross-platform lockfile that works on your Windows PC, and manages the Python version.
- tglc requires Python < 3.13 and astropy 8 requires >= 3.11.
- wotan 2.x and TLS 2.x were rewritten in late 2026, so they are pinned exactly, and tests guard their behavior.

**Repo layout:**
```
CLAUDE.md  README.md  pyproject.toml  uv.lock
configs/        targets_mdwarf.yaml validation.yaml inject.yaml search.yaml vet.yaml
src/longshot/   cli.py config.py manifest.py registry.py report.py
  catalogs/     TIC/Gaia queries; dated TOI/CTOI/NEA/EB snapshots
  data/         QLP, TESS-SPOC, TESScut fetch + cache (data/, gitignored), checksums
  lc/           masking, stitching, detrending
  search/       single.py (matched filter), link.py (duotransits, aliases)
  inject/       injection-recovery, inverted-LC false alarms
  fit/          transit fits, period posteriors
  vet/          triage, crossmatch, photometric, pixel, star, fpp
tests/          pytest; small committed fixtures; network tests marked and skipped offline
results/runs/<run_id>/manifest.json + small summary tables (committed); bulk outputs gitignored
candidates/registry.csv  candidates/reports/<id>.md + figures
docs/           plan.md decisions.md log.md sources.md
.claude/agents/ literature-scout.md skeptic-vetter.md reproducibility-checker.md
```

**Commands:**
- One per stage: `uv run longshot <stage> --config configs/<x>.yaml`. Stages: targets, fetch, search, inject, validate, link, vet, report.
- Each stage writes a manifest with: git commit, dirty flag, config and hash, package versions, data product versions and snapshot dates, timestamps and counts.

**Registry columns:** id, tic, sectors, epochs_btjd, depth_ppm, depth_err, duration_h, snr, period_est_d, period_aliases, tmag, teff, product, status, rejection_reason, report_path, run_id, date_added.

**Git:**
- One branch per step, small commits, a PR per step, merged by me after tests pass. Never force-push main.
- CI: GitHub Actions running offline pytest.

**Compute split:**
- Cloud: build, tests, Phase 1 on about 2k stars, injection on a subsample, and vetting single candidates.
- Your PC: the full 170k-star search, about 6 sectors per star. It streams download, then search, then deletes the light curves, keeping only results; I will give the exact command.

## 9. Publication route (proposal)

Because of section 1:
- (a) You email the RNAAS editor and the ExoFOP help desk now, to confirm the current rules. I draft both emails.
- (b) Plan for a **refereed** short paper that publishes method plus candidates, which unlocks the CTOI upload. Candidate journals: AJ, MNRAS, or the free Open Journal of Astrophysics. To be decided at the Phase 4 checkpoint.
- (c) Optionally, contact the TSTPC working group, which posts single-transit CTOIs through TFOP.
- An RNAAS on method plus sensitivity (or a null result) stays as the fallback outcome.

## 9b. Decisions from Oskar (2026-11-19)
- Targets: M dwarfs (section 3).
- Publishing: ask first, decide at the Phase 4 checkpoint. I draft emails to the RNAAS editor and the ExoFOP help desk in Phase 0 (docs/emails/), and Oskar sends them.
- Home PC disk: 100-500 GB, so we cache primary QLP light curves for the sample (estimated under 200 GB) and stream TESS-SPOC.
- No ExoFOP account or astronomer contact yet. Human tasks for Oskar, logged in docs/log.md:
  - create an ExoFOP account;
  - look for an advisor (a Polish university astronomy department or a TFOP member). That matters for a refereed paper.

## 10. Phase 0 deliverables (on approval)
- docs/emails/ with the two draft emails (RNAAS editor, ExoFOP help desk).
- CLAUDE.md, docs/plan.md (this), docs/decisions.md (first entries: target set, products, uv, thresholds method), docs/log.md, docs/sources.md, candidates/registry.csv header, the 3 agent files, pyproject + uv.lock skeleton, CI, PR.

## 11. Verification of this plan's execution
- Phase 0: `uv sync && uv run pytest` passes on a fresh clone; the agent files load.
- Phase 1: the pass criteria in section 7, plus reproducibility-checker sign-off.

## 12. Sources
- S1 ExoFOP candidate guidelines https://exofop.ipac.caltech.edu/tess/candidate_help.php
- S2 RNAAS guidelines https://journals.aas.org/research-note-preparation-guidelines/
- S3 AAS LLM policy https://journals.aas.org/author-llm-guidelines/
- S4 Gaia news https://www.cosmos.esa.int/web/gaia/news
- S5 Giacalone+ 2021 TRICERATOPS https://arxiv.org/abs/2002.00691
- S6 Hawthorn+ 2024 https://arxiv.org/abs/2310.17268
- S7 Eisner+ 2021 https://arxiv.org/abs/2011.13944
- S8 Salinas+ 2025 https://arxiv.org/abs/2502.07542 ; Salinas+ 2026 https://arxiv.org/abs/2610.24882
- S9 Roth+ 2026 T16 https://arxiv.org/abs/2604.18579
- S10 Lafarga+ 2026 RAVEN https://arxiv.org/abs/2603.22597
- S11 Kunimoto+ 2025 LEO-Vetter https://arxiv.org/abs/2509.10619
- S12 Feliz+ 2026 NEMESIS II https://arxiv.org/abs/2611.21758
- S13 TSTPC poster https://vmnexsci.ipac.caltech.edu/workshop/2026/posters/Poster_BrettSkinner_33.pdf
- S14 Long-period review 2026 https://arxiv.org/abs/2604.09254
- S15 QLP https://archive.stsci.edu/hlsp/qlp ; DRN https://arxiv.org/abs/2603.22236
- S16 TESS-SPOC https://archive.stsci.edu/hlsp/tess-spoc
- S17 TGLC https://archive.stsci.edu/hlsp/tglc
- S18 wotan https://pypi.org/project/wotan/
- S19 MonoTools https://github.com/hposborn/MonoTools
- S20 TESS Ten Thousand EBs https://arxiv.org/abs/2506.05631
