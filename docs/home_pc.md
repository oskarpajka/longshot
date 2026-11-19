# Running the production search on Oskar's PC (Windows)

Status: ready to use once Phase 1 passes and Claude names the commit to run (step 3).
Why on your PC: the full search downloads about 550,000 light curves (97,656 stars), which
takes roughly 12 to 24 hours. See D016 and D018 in docs/decisions.md.

What it needs: about 3 GB RAM, under 5 GB free disk at any time (each light curve is deleted
after it is searched), a stable internet connection. No GPU.

## 1. One-time setup

Install Git for Windows from https://git-scm.com/download/win (default options are fine).

Install uv. Open PowerShell and run:

```
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Close and reopen PowerShell, then check that `uv --version` works.

## 2. Get the code

Pick a folder on a disk with space, for example D:\, then:

```
cd D:\
git clone https://github.com/oskarpajka/longshot.git
cd longshot
```

## 3. Check out the exact commit Claude gives you

```
git fetch origin
git checkout <COMMIT>
```

## 4. Install the environment and run the tests

```
uv sync --frozen
uv run pytest -q
```

All tests should pass (some are skipped without network). If any fail, stop and send Claude
the output.

## 5. Stop Windows from sleeping

Settings > System > Power > Screen and sleep: set "When plugged in, put my device to sleep
after" to Never while the search runs.

## 6. Run the search

```
uv run python -m longshot search --config configs/search_production.yaml
```

It prints a line every 500 stars, like `  1500/97656 stars (0 from checkpoint)`.

If it stops for any reason (crash, reboot, internet drop, you close the window), just run the
same command again in the same folder. It continues from the last finished 500-star chunk.
Do not edit any file in the folder between runs: the program refuses to run with uncommitted
changes, and refuses to resume from a different commit.

When it finishes it prints `search: ok. manifest: results\runs\<run id>\manifest.json`.
If it prints `too_many_errors` or a traceback, send Claude the last 30 lines.

## 7. Send the results back

```
git checkout -b results/production-normal
git add results/runs
git commit -m "Add production search run"
git push -u origin results/production-normal
```

Then tell Claude the branch name. Large bulk files (coverage) are excluded by .gitignore and
stay on your PC; keep the folder until Claude confirms the results are read.

## Cleanup (only after Claude confirms)

You can delete `data\checkpoints\` and `results\runs\_inprogress\` (leftovers from
interrupted runs).
