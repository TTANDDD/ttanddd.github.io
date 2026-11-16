# Hailong Qu

[Academic homepage](https://ttanddd.github.io/) · [中文](https://ttanddd.github.io/zh/)

Edit `data/site.json` for public publications, figures, and projects. Interface text lives in `data/interface.json`. Run `python scripts/build.py` to render both editions, then commit the generated HTML. The paper figures link to their original articles. Click a figure for the full image, credit and source.

GitHub Actions refreshes the site daily at 08:17 Beijing time (00:17 UTC). To run a check immediately, open **Refresh citations and public publications** and choose **Run workflow**. The same commands run locally with Python 3.10 or later:

```sh
python -B scripts/refresh_publications.py
python -B scripts/build.py
```

The refresh looks for newly indexed works in OpenAlex author groups linked to the listed papers, recent ranked Crossref journal deposits, and arXiv records deposited in DataCite. Crossref article metadata or the arXiv abstract page verifies each new entry. A matching full name requires two known collaborators, or one known collaborator plus a matching institution on the author's own byline. An explicit registry link can identify a journal version of an existing arXiv paper. The site lists published articles and public arXiv preprints. SSRN postings and private submissions are outside its publication list. Registry indexing can lag publication, and ambiguous author matches are counted in the run summary.

OpenAlex supplies citation counts by DOI. The total, h-index and i10-index use the distinct indexed works on the homepage. The page shows coverage, the date of the citation snapshot, and a separately dated Google Scholar snapshot. A missing previously indexed record retains the prior citation snapshot and verification date. Temporary source failures appear in the Actions summary. The routine accepts an optional `OPENALEX_API_KEY` repository secret for installations that need higher API limits.

The workflow saves `data/openalex.json`, any verified changes to `data/site.json`, and both language editions in one commit. The Google Scholar snapshot in `data/scholar.json` retains its own source and date. Scheduled runs use the public registry APIs.

GitHub Pages serves the root of the main branch. Image credits appear alongside the figures and in the footer. Font licenses are in `assets/fonts/`.
