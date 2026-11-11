# Hailong Qu

[Academic homepage](https://ttanddd.github.io/) · [中文](https://ttanddd.github.io/zh/)

Edit `data/site.json` for public publications, figures, and projects. Interface text lives in `data/interface.json`. Run `python scripts/build.py` to render both editions, then commit the generated HTML. The paper figures link to their original articles. Click a figure for the full image, credit and source.

The Google Scholar workflow is scheduled daily at 00:17 UTC (08:17 in China); GitHub may start scheduled runs later. It first checks whether a verified snapshot already exists for the current date in China, so a delayed cloud run does not repeat a successful local update. Otherwise it reads the all-time metrics from the public author profile and matches citation counts to the curated publication list. A missing citation count is left blank. A successful fetch commits `data/scholar.json` with the rendered pages and requests a GitHub Pages build. You can also run the workflow from the repository’s Actions tab.

The Actions summary distinguishes `current` (already checked today), `refreshed` (new data verified), and `deferred` (Scholar returned HTTP 403/429 and the previous verified snapshot was retained). A deferred run produces a warning and does not change counts, verification dates, or generated pages. It does not mean that a fresh fetch succeeded. Other request errors, incomplete or invalid profiles, and build or push errors still fail the workflow. Running `python scripts/update_scholar.py` without the cloud flags continues to fail on any refused request, allowing the local task scheduler to retry.

A local fallback can run `python scripts/refresh_if_stale.py` from a machine with repository write access. It checks the date of the public snapshot before contacting Scholar, works in a temporary clone when needed, and verifies the resulting public update.

GitHub Pages serves the root of the main branch. Image credits appear alongside the figures and in the footer. Font licenses are in `assets/fonts/`.
