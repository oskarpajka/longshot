# Research log

Newest first. Each session ends with: done, found, next, open questions for Oskar.

## 2026-11-19 (session 1, continued): Phase 1 attempt 1 fails; false-alarm work

Done:
- Calibration searches finished with 0 errors: calib-normal (2012 stars, 11,225 star-sectors)
  and calib-inverted. Both committed.
- Production tooling for Oskar's PC: full-sample selection minus calibration and dev draws,
  resumable checkpoints, light curve deletion, `python -m longshot`, docs/home_pc.md (D016).
- Pipeline fixes, each with a rule written before its test:
  - D018: scattered-light mask from SAP background, set on a separate dev sample.
  - D019: centroid-motion veto. It failed its safety check (removed 5 of 21 known
    transits), so it was dropped.
  - D020: known-asteroid veto. SkyBoT plus JPL Horizons positions as seen from TESS; 0.67%
    chance rate, so adopted.
  - D021: two-sided background mask; out-of-transit data required on both sides.
- Injection expected SNR now uses the same masks as the search (bug found and fixed).

Found:
- Phase 1 attempt 1 fails criterion 4. 62% of calibration stars had an inverted false alarm
  at SNR >= 7.1, up to SNR 39. The injection run was stopped (D017, D018).
- Main cause: scattered-light ramps in 200 s sectors (S56+) that QLP quality flags miss.
- Second cause: asteroids crossing the aperture. Seen from TESS they pass within one pixel of
  the star (11-33"); seen from the geocentre they look 3-4' away (TESS parallax).
- On the dev sample the fraction of stars with an inverted event at SNR >= 15 fell from 21% to
  4%. About 2% still have a surviving event at SNR >= 16, many in sector 86 at the same times
  (a common-mode systematic). A 1e-3 per-star rate is not reachable yet.

Next:
- Common-mode flag (proposed D022): a fixed reference set of random targets per
  sector/camera (excluded from claims), and a table of bad times where many reference stars
  deviate together. Apply it identically to calibration, injections and production, so the
  false-alarm estimate stays consistent with production. Test on the dev sample first.
- Then Phase 1 attempt 2: rerun calib-normal, calib-inverted, inject (20,500), validate,
  reproducibility check.
- If 1e-3 per star is still out of reach, write up the measured trade-off (threshold vs
  completeness) and ask Oskar before changing any pass criterion.

Open questions / tasks for Oskar:
- No decision needed yet. Phase 1 has not passed, so wait with the ExoFOP account request.
- Emails in docs/emails/ can still go out.

## 2026-11-19 (session 1, continued): Phase 1 build

Done:
- PR 1 (Phase 0) merged.
- Built stages: targets, availability, search (normal/inverted), inject, validate.
  Modules: QLP access, light curve prep, box matched filter (checked against astropy BLS),
  duotransit linking with alias pruning, batman injection.
- Decisions D011-D015 fix every Phase 1 setting and pass criterion before any run.
- Runs: targets (102,254 M dwarfs; D012 corrects the plan's ~170k) and availability
  (100,152 stars with QLP data in S1-105, 559,907 star-sectors).

Found:
- QLP SAP flux in some 30-min sectors (e.g. S26) has large scattered-light swings near orbit
  edges that produce strong false dips. Expect these in the production search; vetting triage
  must catch them.
- Single transits of TOI-2257 b (Tmag 13, depth 0.4%) have expected SNR ~5-6, below any sane
  threshold: a sensitivity limit, kept as an honest control in the validation set.
- Search compute is ~0.03 s per sector; downloads dominate.

Next:
- Run calib-normal, calib-inverted, calib-inject, then validate. Reproducibility check.

## 2026-11-19 (session 1): Phase 0 plan

Done:
- Literature and archive review (three parallel research agents plus direct checks).
- Plan written and approved by Oskar: docs/plan.md.
- Memory files, decision log, sources, agent definitions, email drafts, package skeleton.

Found:
- ExoFOP accepts community candidates only after peer-reviewed publication; RNAAS is
  reportedly no longer accepting open-data transit candidate notes (ExoFOP page; not stated on
  RNAAS pages). The original order CTOI then RNAAS is not possible. See D008.
- Single-transit CTOIs are dominated by Tmag < 12 (813 of 936); M dwarfs are rare among them.
  Published M-dwarf searches require >= 3 transits. Target set: M dwarfs (D001).
- RNAAS limit is 1500 words with a required abstract; AAS AI disclosure goes at the end of the
  article (not acknowledgments).
- Gaia DR4 planned for 2026-12-02 (D009).

Next:
- Phase 1: data access (QLP, TESS-SPOC), detrending, single-event search, duotransit linking,
  injection-recovery, inverted-LC false alarms, validation set run.

Open questions / tasks for Oskar:
- Send the two emails in docs/emails/ (ExoFOP help desk can go now; RNAAS editor too).
- ExoFOP account: wait until Phase 1 passes, then request with a link to the public repo.
- Look for an astronomer advisor (Polish university astronomy department or a TFOP member).
