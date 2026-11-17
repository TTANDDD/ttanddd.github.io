# Hailong Qu

[Academic homepage](https://ttanddd.github.io/) · [中文](https://ttanddd.github.io/zh/)

Edit `data/site.json` for public publications, figures, and projects. Interface text lives in `data/interface.json`. Run `python scripts/build.py` to render both editions, then commit the generated HTML. The paper figures link to their original articles. Click a figure for the full image, credit and source.

GitHub Actions refreshes the site daily at 08:17 Beijing time (00:17 UTC). To run a check immediately, open **Refresh citations and public publications** and choose **Run workflow**. The same commands run locally with Python 3.10 or later:

```sh
python -B scripts/refresh_publications.py
python -B scripts/update_scholar.py --skip-if-current --defer-if-blocked
python -B scripts/build.py
```

The refresh looks for newly indexed works in OpenAlex author groups linked to the listed papers, recent ranked Crossref journal deposits, and arXiv records deposited in DataCite. Crossref article metadata or the arXiv abstract page verifies each new entry. A matching full name requires two known collaborators, or one known collaborator plus a matching institution on the author's own byline. An explicit registry link can identify a journal version of an existing arXiv paper. The site lists published articles and public arXiv preprints. SSRN postings and private submissions are outside its publication list. Registry indexing can lag publication, and ambiguous author matches are counted in the run summary.

Google Scholar supplies all citation counts displayed on the website, including profile citations, h-index, i10-index and per-paper counts. Each displayed snapshot carries its verification date. If Scholar returns HTTP 403 or 429, the routine retains the last verified Scholar snapshot and its date. OpenAlex author records support public-paper discovery and verification. Temporary registry failures appear in the Actions summary. The discovery routine accepts an optional `OPENALEX_API_KEY` repository secret for installations that need higher API limits.

The workflow saves `data/scholar.json`, discovery data in `data/openalex.json`, verified changes to `data/site.json`, and both language editions in one commit.

GitHub Pages serves the root of the main branch. Image credits appear alongside the figures and in the footer. Font licenses are in `assets/fonts/`.
