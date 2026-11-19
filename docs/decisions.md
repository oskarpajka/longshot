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

## D011 2026-11-19: Search QLP SAP flux with our own detrending
- What: search QLP SAP_FLUX after our masking and wotan biweight detrending. QLP's detrended
  flux (KSPSAP_FLUX / DET_FLUX) is kept for vetting only.
- Why: injection tests must pass through the same processing as the data. We cannot re-run QLP's
  own detrending on injected light curves, so searching their detrended flux would overstate
  completeness. A check on TOI-2257 (11 sectors) gave nearly identical scatter for SAP+biweight
  and QLP detrended flux.
- Settings (configs/search_common.yaml):
  - drop every cadence with a nonzero QLP quality flag;
  - split segments at gaps > 0.5 d and trim 0.1 d from each segment edge;
  - clip upward outliers > 5 robust sigma (flares);
  - box durations 0.5-12 h (14 log steps);
  - biweight window 0.75 d for durations <= 5 h and 1.5 d for durations up to 12 h (about 3x duration);
  - an event needs >= 3 points and >= 50% of the expected in-transit cadences;
  - events below SNR 5 are not recorded.
- Why 12 h: an M dwarf with M = R = 0.6 (in solar units) has a central-transit duration of about 10 h at P = 500 d.

## D012 2026-11-19: Target count correction
- The targets stage gives 102,254 stars (TIC v8.2, cuts of D001), not the ~170k in the plan.
  The plan's figure came from LEO-Vetter's sample, which goes to Tmag < 14; ours stops at 13.5.
  Run: results/runs/*_targets_mdwarf-tic82/.

## D013 2026-11-19: Phase 1 validation set and matching rules (set before any validation run)
- Set: 13 known transiting planets with P > 18 d, durations <= 12 h. QLP data must exist.
  - M dwarfs: LHS 1140 b, TOI-2257 b, TOI-1231 b, TOI-904 c, TOI-700 d, TOI-1899 b.
  - K/G: TOI-1759 b, TOI-4600 b, TOI-4600 c, TOI-5678 b (duo), NGTS-30 b (duo), TOI-2010 b, TOI-199 b.
- Dropped from the plan's list: TOI-2180 b. Its 24 h transit is outside the 12 h grid and its host is not an M dwarf.
- Low-SNR controls: TOI-2257 b and TOI-700 d have expected single-transit SNR near or below the threshold. They are kept as honest controls.
- Disclosure: during development, LHS 1140 and TOI-2257 were used as smoke tests of the search code, before these rules were written.
- Rules:
  - A predicted transit counts if >= 50% of its T14 window has good data.
  - It is detected if an event above the threshold lies within 0.5 x T14 of the predicted time.
  - Depth passes if the box depth is within 3 x the event's depth error of the literature model's mean depth over the same box window. The model is batman with NASA Exoplanet Archive pscomppars Rp/R*, a/R* and b.
  - Duration passes if |D_box / T14 - 1| <= 0.3.
  - A target is recovered if >= 1 of its transits passes all three.
  - Criterion 1 needs >= 5 recovered targets.
- Criterion 2: for every pair of detected events that are true transits of the same planet, the true period must be among the surviving aliases.

## D014 2026-11-19: False-alarm calibration details
- Calibration sample: 2000 stars drawn at random (seed 20261119) from targets with QLP data.
  These stars are excluded from candidate claims in the production search.
- Inverted run: the detrended flux is mirrored about 1 after flare clipping. Mirroring before clipping would turn flares into transit-like dips and inflate the false-alarm rate.
- Threshold: the smallest SNR at which the fraction of calibration stars with any inverted event
  >= SNR (over all their sectors) is <= 1e-3, with a floor of 7.1. The floor is the
  conventional Kepler-era detection threshold (Jenkins et al. 2002).
- Why the floor: with 2000 stars, 1e-3 means at most 2 stars, which is statistically noisy.
- Known limitation: inversion does not reproduce dip-shaped systematics. The production false-alarm rate will be higher; the vetting triage (common-mode and edge checks) handles those.

## D015 2026-11-19: Injection-recovery design
- Count and placement: 20,000 injections. Each lands in a random (star, sector) from the calibration stars, one per light curve per run.
- Injected parameters:
  - Rp log-uniform 1-15 Earth radii;
  - P log-uniform 20-500 d;
  - b uniform 0-0.9;
  - circular orbit;
  - quadratic limb darkening (0.25, 0.35);
  - TIC stellar radius and mass;
  - t0 uniform over the sector span, so some injections fall in gaps.
- Injection: multiplied into SAP flux before masking and detrending, with 5x supersampling for 600 s and 1800 s cadences.
- Recovered: an event above the threshold within 0.5 x T14 of the injected time.
- Criterion 3: >= 80% recovered among injections with expected SNR >= 10 and >= 80% good-data coverage of T14. Expected SNR is the mean model depth over good in-transit cadences divided by (sigma / sqrt(n)).
- Linking (criterion 2 and production):
  - depths consistent within 3 sigma;
  - duration ratio <= 1.5;
  - aliases tested down to P = 10 d;
  - an alias is rejected when a predicted transit has >= 50% good coverage and no event (SNR >= threshold) lies within one duration.

## D016 2026-11-19: Production search design (written before any production result)
- Stars: every target of the targets run that has QLP data (availability run), minus the
  2000-star calibration draw of D014. Input runs are pinned by id, not "latest", so the
  exclusion is exactly reproducible. Result: 98,145 stars (100,145 targets with QLP data minus
  2000; test_production.py checks this). The 7 validation stars added to the availability
  run as extra_tics are not targets.
- Settings: identical to the calibration runs (configs/search_common.yaml). No change.
- Disk: each light curve is deleted after it is searched (full cache would be about 450 GB,
  from 8.9 GB per 2012 calibration stars). Candidates are re-downloaded for vetting.
- Resumable: finished 500-star chunks are saved under data/checkpoints/. A resumed run must
  have the same config and the same git commit, so it equals an uninterrupted run (tested).
- Where: Oskar's PC (download-bound, roughly 12-24 h), per the 20-minute rule.
- Gzip outputs are written with mtime 0 so reruns give identical checksums. The coverage
  files of the two calibration searches were written before this fix and differ only in the
  gzip header timestamp; compare them by decompressed content.

## D017 2026-11-19: Phase 1 injection run executed in the cloud
- The 20,500-injection run takes about 55 min on 4 cloud cores (1.3 GB RAM), above the
  ~20 min guideline. It was run in the cloud because the approved plan (section 8) places
  Phase 1 injection-recovery on the calibration subsample in the cloud, the light curves were
  already cached there, and memory use is small. Recorded here as a deviation.

## D018 2026-11-19: Phase 1 attempt 1 failed criterion 4; scattered-light mask added
- Finding (calib-inverted run 20261119T105806Z): 1252 of 2012 calibration stars have an
  inverted event with SNR >= 7.1; the largest is SNR 39. A 1e-3 threshold would sit near 39.
  Criterion 4 cannot pass with that pipeline, so the injection run was stopped at 2500 of
  20,500 (its results would describe a pipeline that is being changed; it left only an
  _inprogress folder) and validate was not run.
- Cause: of the 300 strongest inverted events (one per star), 84% have the SAP background
  more than 5 robust sigma above its orbit median inside the box, and 88% lie within 1 d of
  a segment edge. They are scattered-light ramps, mostly in 200 s sectors, that QLP quality
  flags do not mark. Plots were checked by eye.
- Fix: drop cadences whose SAP_BKG is more than bkg_z_max robust sigma above the orbit median,
  widened by bkg_pad_d on each side (lc/prep.py scattered_light_mask). Background only, so
  a real transit (a flux change) cannot trigger it.
- How the values are chosen (rule written before the comparison was run): a separate
  development sample of 500 targets (seed 20261121, outside the calibration draw, inverted
  flux only, excluded from candidate claims) is searched with each variant of
  bkg_z_max in {off, 3, 5, 10} and bkg_pad_d in {0, 0.25, 0.5} d. Metric: fraction of dev stars
  with any inverted event at SNR >= 10. Choose the variant with the lowest metric; among
  variants within 0.01 (absolute) of the lowest, choose the one that keeps the most data.
- Then every Phase 1 run (calib-normal, calib-inverted, inject, validate) is redone from
  scratch with the new settings. Pass criteria are unchanged.

## D019 2026-11-19: Centroid-motion veto for moving objects (rule fixed before use)
- Finding: after scattered light, the remaining strong inverted events in the calibration
  sample include symmetric 3-5 h flux bumps (inverted into dips). Spot checks of three
  showed the flux-weighted centroid (SAP_X, SAP_Y) moving at 10-42 sigma during the bump,
  versus 1.1 and 3.6 sigma during the two QLP transits of LHS 1140 b. These look like
  asteroids crossing the aperture. They cannot mimic a dip in normal flux, but they set the
  inverted false-alarm tail and would make the threshold meaningless.
- Statistic (search/centroid.py): a transit, on target or on a blend, moves the centroid in
  proportion to the flux change (dx = k df). A crossing object moves it first one way then
  the other. cen_unexpl_z = robust z of the in-box centroid motion that is not proportional
  to the flux change, against every other box position of the same duration in the sector.
- Rule: computed for every event with SNR >= 7.0. An event with cen_unexpl_z > 5 is vetoed
  ("moving-object") in the same way for normal, inverted, injected and validation events.
  The false-alarm threshold (D014) is computed on events that survive.
- Safety check, run before the calibration reruns, with this exact rule: compute
  cen_unexpl_z at the predicted transit times of confirmed transiting planets (NASA
  Exoplanet Archive pscomppars) around stars in our target list, excluding the Phase 1
  validation set, at most 3 transits per planet, for transits with expected box SNR >= 7.
  If more than 2% are vetoed, the veto is dropped entirely (z = 5 is not tuned).
- Limitation: injections do not move the centroid, so measured completeness does not include
  any veto loss; the safety check bounds it.
- Outcome (run 20261119T113856Z_study_centroid-veto): 200 confirmed planets around targets,
  21 transits with SNR >= 7 tested, 5 vetoed (24%), far above 2%. Per the rule above, the
  veto is DROPPED. The statistic grows with SNR squared when a real centroid track is not
  exactly proportional to the flux (detrending, ingress/egress, cadence effects; TOI-873 b at
  SNR 289 scores 3071). centroid_snr_min stays unset (off). The centroid statistics remain
  in the code for possible use in Phase 3 vetting, not as a search veto.

## D020 2026-11-19: Known-asteroid veto with TESS-centred ephemerides (rule fixed before use)
- Finding: the three bump-shaped inverted events checked under D019 each have a catalogued
  asteroid of V = 17.1-17.3 passing 11-33 arcsec from the target at the event mid-time, as
  seen from TESS (JPL Horizons, observer 500@-95). Seen from the geocentre they are 200-240
  arcsec away: TESS parallax matters, so geocentric SkyBoT positions alone are not enough.
  A V = 17.2 asteroid next to a Tmag 13 star gives a ~2-3% bump, as observed.
- Rule (vet/asteroids.py): for an event (t0, duration D, depth d) on a star (RA, Dec, Tmag),
  1. SkyBoT cone search at t0, geocentric, radius 15 arcmin (covers TESS parallax);
  2. keep asteroids with V <= Tmag - 2.5 log10(d) + 1.5 (bright enough to cause the depth,
     with 1.5 mag margin for colour and partial aperture overlap);
  3. for each, JPL Horizons positions from TESS at t0 - D/2, t0, t0 + D/2; the event is vetoed
     ("asteroid") if the closest approach to the target on that path is <= 42 arcsec
     (2 TESS pixels).
  Applied the same way to inverted calibration events, normal events and validation events.
  Queries are cached under data/asteroids/ and the cache is listed in the run manifest.
- Safety check, run before use: 300 random (calibration star, epoch, depth, duration)
  combinations taken from the injection draw (D015), queried with this exact rule. If more
  than 1% are vetoed by chance, the veto is dropped (thresholds not tuned). The measured
  chance rate is reported as a completeness loss.
- Outcome (run 20261119T114731Z_study_asteroid-veto): 300 random epochs, 2 vetoed (0.67%),
  within the 1% limit, so the veto is ADOPTED (asteroid_veto: true in the validate config).
  Both chance vetoes were shallow (~0.1%) with an asteroid 6-7 arcsec from the star. The
  0.7% is reported as a completeness loss alongside the injection results.
