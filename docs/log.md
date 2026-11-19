# Research log

Newest first. Each session ends with: done, found, next, open questions for Oskar.

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
