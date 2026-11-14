# Hailong Qu

[Academic homepage](https://ttanddd.github.io/) · [中文](https://ttanddd.github.io/zh/)

Edit `data/site.json` for public publications, figures, and projects. Interface text lives in `data/interface.json`. Run `python scripts/build.py` to render both editions, then commit the generated HTML. The paper figures link to their original articles. Click a figure for the full image, credit and source.

Scholar updates are manual. To refresh the citation metrics and publication list, select **Refresh Scholar citations and publications** in GitHub Actions and choose **Run workflow**. A successful fetch commits `data/scholar.json`, verified changes to `data/site.json`, and both rendered pages, then requests a GitHub Pages build. The website shows the date of its last verified citation snapshot.

New Scholar records are checked against public Crossref journal/conference article metadata or an arXiv abstract page. Both the title and the author's full name must match. Datasets, unverified candidates, and accepted or submitted manuscripts without a verified public article are not added. Preprints are checked for a journal version and updated in place when verified; DOI/arXiv identities prevent duplicate entries. Disappearing Scholar records do not automatically delete existing publications. The script retains user-written contributions, figures, and author-role annotations. New entries use verified bibliographic metadata and an appropriate research field; they do not invent translations, contribution statements, journal rankings, or images. Both language editions can display the original title until a Chinese translation is supplied.

`publication_scan` in `data/scholar.json` records the scan time, number of observed records, added or updated public IDs, and counts of unresolved candidates or source failures. The Actions summary marks incomplete public metadata checks as partial.

The Actions summary distinguishes `current` (already checked today), `refreshed` (new data verified), and `deferred` (Scholar returned HTTP 403/429 and the previous verified snapshot was retained). Other request errors, incomplete or invalid profiles, and build or push errors fail the workflow.

For a manual local refresh, run `python scripts/refresh_if_stale.py` from a machine with repository write access. It checks the date of the public snapshot before contacting Scholar, works in a temporary clone when needed, and verifies the resulting public update.

GitHub Pages serves the root of the main branch. Image credits appear alongside the figures and in the footer. Font licenses are in `assets/fonts/`.
