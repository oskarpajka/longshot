# Decision log

Dated entries, newest last. Each entry: what, why, alternatives rejected.
Thresholds are fixed here before any search result is seen. Changing one needs a new entry
that says why and confirms it was not motivated by search results.

## D001 2026-11-19: Target set is M dwarfs, all sky
- What: TIC v8.2 stars with 2400 < Teff < 3900 K, R* < 0.6 Rsun, Tmag <= 13.5, contamination
  ratio < 0.5, with QLP light curves in sectors 1-104. Same cuts as Kunimoto+ 2025 (LEO-Vetter).
  The extra R* < 0.6 is paired with M* < 0.6 Msun when mass is available.
- Why: ExoFOP snapshot 2026-11-19 shows that single-transit CTOIs and TOIs on Teff < 4000 K
  stars are rare (59 of 911 single CTOIs with Teff, 10 of 109 single TOIs). Published M-dwarf
  searches (LEO-Vetter, NEMESIS) require >= 3 transits or P < 40 d. M dwarfs give deep transits
  and well-constrained densities. The sample (~170k) fits a home PC.
- Rejected: Northern FGK duotransits (bright ones likely held by the TSTPC working group);
  faint FGK in S56+ (weaker science case, bigger sample).
- Approved by Oskar 2026-11-19.

## D002 2026-11-19: Primary data product is QLP; TESS-SPOC is the independent check
- Why: QLP is the only product covering S1-104 to Tmag 13.5 and gives 3 apertures per star
  (useful for contamination tests). TESS-SPOC (S1-86) is a different photometric pipeline, so
  an event seen in both is unlikely to be a pipeline artifact.
- Known issues handled in code: QLP S99-104 barycentric timing error (epochs flagged until
  redelivered), QLP method change at S94, TGLC on MAST only S1-55.
- Rejected: TGLC as primary (stops at S55 on MAST; running it ourselves for 170k stars is too
  costly); eleanor and unpopular (unmaintained).

## D003 2026-11-19: Environment tool is uv, Python 3.12
- Why: lockfile (uv.lock) is cross-platform, so Oskar's Windows PC reproduces the cloud
  environment; uv also installs the pinned Python. tglc requires Python < 3.13; astropy 8
  requires >= 3.11. All core deps have wheels on PyPI.
- Rejected: conda (slower, no single cross-platform lock without extra tools); pip-tools
  (works, but uv does the same and manages Python too).

## D004 2026-11-19: Detection threshold set from inverted light curves, not from candidates
- What: run the production search on the flux-inverted light curves of a calibration
  subsample. The detection threshold is the lowest SNR at which the false-alarm rate is
  <= 1 per 1000 stars. Completeness is measured by injection-recovery into real light curves.
  The calibration subsample is excluded from candidate claims.
- Why: inverted data contain the same systematics and noise but no real transits, so any
  detection there is a false alarm (standard practice from Kepler DR25 vetting). This sets
  thresholds without looking at real candidates.

## D005 2026-11-19: Single-event search is our own matched filter, tested against astropy BLS
- Why: no maintained single-transit search library exists. MonoTools pins lightkurve 1.11 and
  scipy 1.12, and Hawthorn's monofind is not packaged. A box/trapezoid matched filter is short
  and can be verified numerically against astropy BoxLeastSquares on a single transit.
- MonoTools may be used in an isolated environment as a cross-check on finalists only.

## D006 2026-11-19: Duotransits are the primary product, singles secondary
- Why: ExoFOP requires period, epoch, depth and duration > 0 for TOI working group
  consideration of a CTOI. A duotransit gives a discrete alias set; a lone single does not.

## D007 2026-11-19: Vetted-candidate bar
- What: a "vetted candidate" must pass all vetting steps in docs/plan.md section 6 and have
  TRICERATOPS FPP < 0.5 and NFPP < 1e-3 at every plausible period (Giacalone+ 2021 "likely
  planet" bar). RUWE > 1.4 is a flag that requires written justification, not an automatic
  reject. Implied Rp > 2 RJ is a reject.
- Why: conservative published thresholds. TRICERATOPS output is never called validation.

## D008 2026-11-19: Publication route deferred to Phase 4 checkpoint
- What: Oskar emails the RNAAS editor and ExoFOP help desk (drafts in docs/emails/) to
  confirm (a) whether RNAAS accepts candidate notes and (b) how single and duotransit CTOIs are
  handled. Plan assumes a refereed paper may be needed for CTOI upload.
- Why: ExoFOP candidate guidelines (checked 2026-11-19) require prior peer-reviewed
  publication and state RNAAS no longer accepts open-data transit candidate notes; RNAAS's own
  pages do not say this.

## D009 2026-11-19: Gaia catalog version for vetting
- What: build and test with Gaia DR3; switch vetting cross-matches (neighbors, RUWE,
  non-single-star, EB tables) to DR4 after its release (planned 2026-12-02), and record which
  release each report used.

## D010 2026-11-19: Branching under the cloud session constraint
- What: each step uses the session's designated branch, is merged to main by PR, then the
  branch is restarted from main for the next step.
- Why: the cloud session may push only to its designated branch; this keeps "one branch per
  step, one PR per step" while respecting that rule.
