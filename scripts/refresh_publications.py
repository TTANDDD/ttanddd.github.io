"""Refresh the public homepage from scholarly registries and OpenAlex."""

from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import time
from urllib.error import HTTPError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from publication_watch import (
    HEADERS, apply_publication, arxiv_record, crossref_record, has_author, identifiers,
    normalize, plain, same_title,
)
from update_scholar import write_json


DATA = Path(__file__).resolve().parents[1] / "data"
OPENALEX = "https://api.openalex.org/works"
CROSSREF = "https://api.crossref.org/works"
DATACITE = "https://api.datacite.org/dois"
OA_FIELDS = "id,doi,title,type,cited_by_count,authorships,is_retracted"
REGISTRY_ERRORS = (OSError, ValueError, KeyError, TypeError)


def request(url, *, html=False):
    headers = dict(HEADERS)
    if url.startswith(OPENALEX) and os.environ.get("OPENALEX_API_KEY"):
        headers["Authorization"] = "Bearer " + os.environ["OPENALEX_API_KEY"]
    for attempt in range(3):
        try:
            with urlopen(Request(url, headers=headers), timeout=20) as response:
                return response.read().decode("utf-8") if html else json.load(response)
        except OSError as error:
            delay = 2 ** (attempt + 1)
            if isinstance(error, HTTPError):
                if error.code not in (408, 429, 500, 502, 503, 504):
                    raise
                retry = error.headers.get("Retry-After", "")
                if retry.isdigit():
                    delay = max(delay, int(retry))
            if attempt == 2 or delay > 15:
                raise
            time.sleep(delay)


def doi(value):
    value = (value or "").strip().lower().removeprefix("https://doi.org/")
    return value if re.fullmatch(r'10\.\d{4,9}/[^\s"<>]+', value) else ""


def arxiv_id(value):
    match = re.fullmatch(r"10\.48550/arxiv\.(\d{4}\.\d{4,5})", value)
    return match[1] if match else ""


def paper_doi(paper):
    # When a journal and preprint are linked, the journal is the citation record.
    for label, link in paper["links"]:
        if label == "DOI" and link.startswith("https://doi.org/") and doi(link):
            return doi(link)
    return next(("10.48550/arxiv." + x[6:] for x in sorted(identifiers(paper))
                 if x.startswith("arxiv:")), "")


def oa_works(filter_value):
    works = []
    page = 1
    while True:
        params = {"filter": filter_value, "select": OA_FIELDS, "per_page": 100}
        if page > 1:
            params["page"] = page
        query = urlencode(params)
        result = request(OPENALEX + "?" + query)
        rows = result["results"]
        works.extend(rows)
        if len(works) >= result["meta"]["count"]:
            return works
        if not rows:
            raise ValueError("Incomplete OpenAlex page")
        page += 1


def lookup_dois(dois):
    keys = sorted(set(filter(None, dois)))
    result = []
    for start in range(0, len(keys), 40):
        result.extend(oa_works("doi:" + "|".join(keys[start:start + 40])))
    return result


def related_works(listed_works, person):
    # One researcher can be split across OpenAlex author IDs. Use these as search
    # leads only; membership of a cluster never establishes authorship.
    groups = set()
    for work in listed_works:
        for author in work["authorships"]:
            entry = author["author"]
            if has_author([author.get("raw_author_name") or entry.get("display_name") or ""], person):
                match = re.fullmatch(r"https://openalex\.org/(A\d+)", entry.get("id") or "")
                if match:
                    groups.add(match[1])
    return oa_works("author.id:" + "|".join(sorted(groups))) if groups else []


def oa_candidate(work, person):
    names, own_institutions = [], set()
    for author in work["authorships"]:
        name = author.get("raw_author_name") or author["author"].get("display_name") or ""
        names.append(name)
        if has_author([name], person):
            own_institutions.update(normalize(i["display_name"]) for i in author.get("institutions", [])
                                    if i.get("display_name"))
    if work.get("is_retracted") or not has_author(names, person):
        return None
    return {"doi": doi(work.get("doi")), "title": work.get("title") or "",
            "authors": names, "institutions": own_institutions}


def datacite_preprints(person):
    family_first = ", ".join(reversed(person["name"].split()))
    rows = []
    page = 1
    while True:
        query = urlencode({"prefix": "10.48550", "query": 'creators.name:"' + family_first + '"',
                           "page[size]": 100, "page[number]": page})
        payload = request(DATACITE + "?" + query)
        for item in payload["data"]:
            work = item["attributes"]
            key = doi(item["id"])
            ident = arxiv_id(key)
            if (not ident or work.get("state") != "findable"
                    or work.get("url") != "https://arxiv.org/abs/" + ident):
                continue
            authors = [a.get("name", "") for a in work.get("creators", [])]
            if has_author(authors, person) and work.get("titles"):
                rows.append({"doi": key, "authors": authors, "institutions": set(),
                             "title": plain(work["titles"][0]["title"])})
                for link in work.get("relatedIdentifiers", []):
                    if (link.get("relatedIdentifierType") == "DOI"
                            and link.get("relationType") in ("IsPreprintOf", "IsVersionOf")
                            and doi(link.get("relatedIdentifier")) and not arxiv_id(doi(link["relatedIdentifier"]))):
                        rows.append({**rows[-1], "doi": doi(link["relatedIdentifier"]), "arxiv_id": ident})
        if page >= payload["meta"]["totalPages"]:
            return rows
        page += 1


def recent_crossref(person, since):
    query = urlencode({"query.author": '"' + person["name"] + '"', "filter": "type:journal-article,from-created-date:" + since,
                       "rows": 75, "select": "DOI,title,author", "mailto": person["email"]})
    candidates = []
    for work in request(CROSSREF + "?" + query)["message"]["items"]:
        authors = [plain(a.get("given", "") + " " + a.get("family", "")) for a in work.get("author", [])]
        if work.get("title") and has_author(authors, person):
            own = {normalize(aff["name"]) for a, name in zip(work["author"], authors) if has_author([name], person)
                   for aff in a.get("affiliation", []) if aff.get("name")}
            candidates.append({"doi": doi(work["DOI"]), "title": plain(work["title"][0]),
                               "authors": authors, "institutions": own})
    return candidates


def name_key(name):
    # Compare names from registries with different given/family ordering.
    return tuple(sorted(normalize(w) for w in re.findall(r"[^\W_]+", name, re.UNICODE)))


def collaborators(authors, person):
    return {name_key(n) for n in authors if len(name_key(n)) > 1
            and normalize(n) != "etal" and not has_author([n], person)}


def identity_anchors(site, works):
    people, institutions = set(), set()
    curated = {paper_doi(p): p for p in site["papers"] if not p["id"].startswith("pub-")}
    for paper in curated.values():
        people.update(collaborators(paper["authors"].split(","), site["person"]))
    for work in works:
        if doi(work.get("doi")) in curated and (entry := oa_candidate(work, site["person"])):
            people.update(collaborators(entry["authors"], site["person"]))
            institutions.update(entry["institutions"])
    return people, institutions


def corroborated(names, own_institutions, person, anchors):
    people, institutions = anchors
    shared = collaborators(names, person) & people
    return has_author(names, person) and (len(shared) >= 2 or bool(shared and own_institutions & institutions))


def official_metadata(entry, person, today):
    key = entry["doi"]
    ident = arxiv_id(key)
    if ident:
        page = request("https://arxiv.org/abs/" + ident, html=True)
        return arxiv_record(page, ident, entry["title"], person)
    try:
        work = request(CROSSREF + "/" + quote(key, safe="/") + "?" + urlencode({"mailto": person["email"]}))["message"]
    except HTTPError as error:
        if error.code == 404:
            return None
        raise
    if doi(work.get("DOI")) != key:
        return None
    # A linked arXiv journal version may have a revised title.
    title = plain(work["title"][0]) if entry.get("arxiv_id") and work.get("title") else entry["title"]
    metadata = crossref_record(work, title, person)
    parts = next((work[k]["date-parts"][0] for k in ("published-online", "published", "published-print")
                  if work.get(k, {}).get("date-parts")), [])
    if not metadata or not parts or date(*(parts + [1, 1])[:3]) > today:
        return None
    if entry.get("arxiv_id"):
        metadata["arxiv_id"] = entry["arxiv_id"]
    return metadata


def citation_snapshot(site, works, previous, checked):
    by_doi = {}
    for work in works:
        key, url, count = doi(work.get("doi")), work.get("id") or "", work.get("cited_by_count")
        if (not key or not re.fullmatch(r"https://openalex\.org/W\d+", url)
                or type(count) is not int or count < 0 or not oa_candidate(work, site["person"])):
            continue
        if key in by_doi and by_doi[key]["work"] != url:
            raise ValueError("A DOI matched multiple OpenAlex records")
        by_doi[key] = {"doi": key, "work": url, "count": count}
    papers = {}
    previously_indexed = previous.get("papers", {})
    for p in site["papers"]:
        key = paper_doi(p)
        if key in by_doi:
            papers[p["id"]] = by_doi[key]
        elif key and previously_indexed.get(p["id"], {}).get("doi") == key:
            raise ValueError("A previously indexed DOI was absent; retaining its dated snapshot")
    if not papers:
        raise ValueError("No verified OpenAlex citation records were returned")
    counts = sorted({r["work"]: r["count"] for r in papers.values()}.values(), reverse=True)
    return {"source": "OpenAlex", "checked_at": checked, "citations": sum(counts),
            "h_index": sum(count >= rank for rank, count in enumerate(counts, 1)),
            "i10_index": sum(count >= 10 for count in counts), "papers": papers}


def refresh(site, previous, checked):
    today = date.fromisoformat(checked[:10])
    person, updated = site["person"], deepcopy(site)
    problems, candidates = [], {}
    unavailable = set()
    scan = {"checked_at": checked, "added": [], "updated": [], "unconfirmed": 0}

    def read(source, operation):
        try:
            return operation()
        except REGISTRY_ERRORS as error:
            detail = "HTTP " + str(error.code) if isinstance(error, HTTPError) else type(error).__name__
            problems.append(source + " (" + detail + ")")
            unavailable.add(source)
            return []

    listed = {paper_doi(p) for p in site["papers"]}
    listed_works = read("OpenAlex DOI lookup", lambda: lookup_dois(listed))
    matches = read("OpenAlex author groups", lambda: related_works(listed_works, person))
    works = listed_works + matches
    anchors = identity_anchors(site, works)
    for work in matches:
        if work.get("type") in ("article", "preprint", "proceedings-article") and (entry := oa_candidate(work, person)) and entry["doi"]:
            candidates[entry["doi"]] = entry
    last_scan = previous.get("publication_scan", {}).get("last_complete") or checked
    since = min(today - timedelta(days=14), date.fromisoformat(last_scan[:10]) - timedelta(days=2))
    supplements = read("Crossref recent deposits", lambda: recent_crossref(person, since.isoformat()))
    supplements += read("DataCite arXiv search", lambda: datacite_preprints(person))
    for entry in supplements:
        key = entry["doi"]
        if key:
            entry["institutions"].update(candidates.get(key, {}).get("institutions", set()))
            candidates[key] = entry

    for key, entry in candidates.items():
        if key in listed or key.startswith("10.2139/ssrn."):
            continue
        linked = next((p for p in updated["papers"] if entry.get("arxiv_id")
                       and "arxiv:" + entry["arxiv_id"] in identifiers(p)), None)
        known = linked or next((p for p in updated["papers"] if same_title(p["title"], entry["title"])), None)
        if known and known["status"] == "published" and not linked:
            continue
        if not linked and not corroborated(entry["authors"], entry["institutions"], person, anchors):
            scan["unconfirmed"] += 1
            continue
        before = len(problems)
        metadata = read("Publication verification", lambda: official_metadata(entry, person, today))
        if metadata and (linked or corroborated(metadata["authors"], entry["institutions"], person, anchors)):
            apply_publication(updated, metadata, scan, known)
        elif len(problems) == before:
            scan["unconfirmed"] += 1
    new_dois = {paper_doi(p) for p in updated["papers"]} - listed - {doi(w.get("doi")) for w in works}
    if new_dois:
        works.extend(read("New DOI lookup", lambda: lookup_dois(new_dois)))
    if not works and {"OpenAlex DOI lookup", "Crossref recent deposits", "DataCite arXiv search"} <= unavailable:
        raise RuntimeError("Public registries unavailable; saved homepage data retained")
    scan["unavailable_sources"] = sorted(unavailable)
    scan["status"] = "partial" if problems else "complete"
    if not problems:
        scan["last_complete"] = checked
    elif previous.get("publication_scan", {}).get("last_complete"):
        scan["last_complete"] = previous["publication_scan"]["last_complete"]
    try:
        snapshot = citation_snapshot(updated, works, previous, checked)
    except ValueError as error:
        if not previous.get("papers"):
            raise
        problems.append(str(error))
        snapshot = {k: v for k, v in previous.items() if k != "publication_scan"}
    snapshot["publication_scan"] = scan
    return updated, snapshot, problems


def main():
    path = DATA / "openalex.json"
    previous = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    site = json.loads((DATA / "site.json").read_text(encoding="utf-8"))
    checked = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    updated, snapshot, problems = refresh(site, previous, checked)
    if site != updated:
        write_json(DATA / "site.json", updated)
    write_json(path, snapshot)
    scan = snapshot["publication_scan"]
    report = (f"OpenAlex: {snapshot['citations']} citations across {len(snapshot['papers'])}/{len(updated['papers'])} "
              f"listed papers (verified {snapshot['checked_at']}). Publication scan: {scan['status']}; "
              f"{len(scan['added'])} added, {len(scan['updated'])} updated. "
              f"Name matches without sufficient evidence: {scan['unconfirmed']}.")
    print(report)
    if problems:
        print("::warning title=Registry refresh incomplete::" + ", ".join(sorted(set(problems))))
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as out:
            out.write(report + "\n\n" + "\n".join(sorted(set(problems))) + "\n")


if __name__ == "__main__":
    main()
