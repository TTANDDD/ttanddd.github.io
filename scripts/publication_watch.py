"""Verify Scholar discoveries against public article metadata before publishing."""

from copy import deepcopy
from hashlib import sha256
from html import unescape
from html.parser import HTMLParser
import json
import re
import unicodedata
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import Request, urlopen


SCAN_VERSION = 1
HEADERS = {"User-Agent": "Hailong-Qu-Homepage/1.0 (mailto:tiyudi789520@gmail.com)"}
FIELDS = [
    ("agents", r"\b(agent|agents|multimodal|spatial reasoning)\b", "Engineering agents & spatial reasoning", "工程智能体与空间推理"),
    ("wind", r"\b(wind|turbine|turbines|wake|wakes)\b", "Wind energy engineering", "风能工程"),
    ("structures", r"\b(uhpc|concrete|frp|beam|beams|structural|composite materials)\b", "Structural engineering & composite materials", "结构工程与复合材料"),
    ("built-environment", r"\b(indoor|co2|air quality|building ventilation)\b", "Built environment & air quality", "建筑环境与空气质量"),
    ("electrical", r"\b(electrical|power grid|power line|power lines|transmission line|transmission lines|insulator|insulators)\b", "Electrical engineering", "电气工程"),
    ("medical", r"\b(fracture|fractures|medical|clinical|pediatric|radiograph|radiographs)\b", "Medical imaging & healthcare", "医学影像与医疗健康"),
    ("food-environment", r"\b(grain|food safety|postharvest|ozone|voc)\b", "Food & environmental science", "食品与环境科学"),
    ("ai-science", r"", "AI for Science", "AI for Science"),
]


def normalize(value):
    return "".join(c for c in unicodedata.normalize("NFKD", value.casefold()) if c.isalnum())


def plain(value):
    return " ".join(unescape(re.sub(r"<[^>]+>", "", value)).split())


def same_title(left, right):
    a, b = normalize(left), normalize(right)
    return bool(a and b) and a == b


def has_author(names, person):
    expected = {normalize(person["name"]), normalize(" ".join(reversed(person["name"].split())))}
    return any(normalize(name) in expected for name in names)


def fetch(url):
    with urlopen(Request(url, headers=HEADERS), timeout=25) as response:
        return response.read()


def crossref_record(work, title, person):
    if work.get("type") not in ("journal-article", "proceedings-article"):
        return None
    titles = work.get("title", [])
    names = [plain(" ".join((a.get("given", ""), a.get("family", ""))))
             for a in work.get("author", [])]
    doi = work.get("DOI", "").lower()
    venues = work.get("container-title", [])
    if (not titles or not same_title(plain(titles[0]), title) or not has_author(names, person)
            or not re.fullmatch(r"10\.\d{4,9}/\S+", doi) or not venues):
        return None
    dates = [work.get(key, {}).get("date-parts", [])
             for key in ("published-online", "published", "published-print", "issued")]
    years = [parts[0][0] for parts in dates if parts and parts[0]]
    if not years or not isinstance(years[0], int):
        return None
    # A registered DOI for a dataset or an unpublished accepted manuscript is insufficient.
    if not work.get("published") and not work.get("published-online") and not work.get("published-print"):
        return None
    citation = ", ".join(str(v) for v in (work.get("volume"), work.get("article-number") or work.get("page")) if v)
    return {"title": plain(titles[0]), "authors": names, "year": years[0],
            "status": "published", "venue": plain(venues[0]), "citation": citation,
            "doi": doi, "url": "https://doi.org/" + doi, "source": "Crossref"}


class MetaTags(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.values = {}

    def handle_starttag(self, tag, attributes):
        values = dict(attributes)
        if tag == "meta" and values.get("name") and values.get("content"):
            self.values.setdefault(values["name"], []).append(values["content"])


def arxiv_record(html, arxiv_id, title, person):
    parser = MetaTags()
    parser.feed(html)
    values = parser.values
    titles = values.get("citation_title", [])
    names = values.get("citation_author", [])
    identities = values.get("citation_arxiv_id", [])
    dates = values.get("citation_date", [])
    if (not titles or not same_title(titles[0], title) or not has_author(names, person)
            or not identities or re.sub(r"v\d+$", "", identities[0]) != arxiv_id or not dates):
        return None
    year = re.match(r"\d{4}", dates[0])
    if not year:
        return None
    return {"title": plain(titles[0]), "authors": names, "year": int(year[0]),
            "status": "preprint", "venue": "arXiv", "citation": "",
            "arxiv_id": arxiv_id, "version": identities[0], "doi": values.get("citation_doi", [""])[0],
            "url": "https://arxiv.org/abs/" + arxiv_id, "source": "arXiv"}


def public_record(record, existing, person):
    """Return only a title-and-full-author match from an article registry or arXiv."""
    errors = 0
    preprint = None
    links = existing.get("links", []) if existing else []
    arxiv_links = [url for _, url in links if urlsplit(url).hostname == "arxiv.org"]
    identity = re.search(r"(?:arxiv:|arxiv\.org/abs/)(\d{4}\.\d{4,5})(?:v\d+)?",
                         record["venue"] + " " + " ".join(arxiv_links), re.I)
    if identity:
        try:
            arxiv_id = identity[1]
            preprint = arxiv_record(fetch("https://arxiv.org/abs/" + arxiv_id).decode("utf-8"),
                                    arxiv_id, record["title"], person)
        except (HTTPError, URLError, TimeoutError, UnicodeDecodeError):
            errors += 1
    doi_links = [urlsplit(url).path.lstrip("/") for _, url in links
                 if urlsplit(url).hostname in ("doi.org", "dx.doi.org")]
    doi = (preprint or {}).get("doi") or (doi_links[0] if doi_links else "")
    if doi and re.fullmatch(r"10\.\d{4,9}/\S+", doi):
        endpoint = "https://api.crossref.org/works/" + quote(doi, safe="")
    else:
        endpoint = "https://api.crossref.org/works?" + urlencode({
            "query.title": record["title"], "query.author": person["name"],
            "rows": 5, "mailto": person["email"]})
    try:
        message = json.loads(fetch(endpoint))["message"]
        works = message.get("items", []) if "items" in message else [message]
        matches = [value for work in works
                   if (value := crossref_record(work, record["title"], person))]
        distinct = {value["doi"]: value for value in matches}
        if len(distinct) == 1:
            result = next(iter(distinct.values()))
            if preprint:
                result["arxiv_id"] = preprint["arxiv_id"]
            return result, errors
    except HTTPError as error:
        if error.code != 404:
            errors += 1
    except (URLError, TimeoutError, UnicodeDecodeError, json.JSONDecodeError, KeyError):
        errors += 1
    return preprint, errors


def identifiers(paper):
    output = set()
    for _, url in paper.get("links", []):
        parsed = urlsplit(url)
        if parsed.hostname in ("doi.org", "dx.doi.org"):
            output.add("doi:" + parsed.path.lstrip("/").lower())
        elif parsed.hostname == "arxiv.org":
            output.add("arxiv:" + re.sub(r"v\d+$", "", parsed.path.removeprefix("/abs/")))
    return output


def sync_publications(records, site, previous, checked):
    updated = deepcopy(site)
    papers = updated["papers"]
    by_id = {value.get("work_id"): key for key, value in previous.get("papers", {}).items()}
    scan = {"version": SCAN_VERSION, "checked_at": checked, "observed_count": len(records),
            "added": [], "updated": [], "unverified_count": 0, "source_errors": 0}
    for record in records:
        existing = next((p for p in papers if p["id"] == by_id.get(record["work_id"])
                         or same_title(p["title"], record["title"])), None)
        old = previous.get("papers", {}).get(existing["id"], {}) if existing else {}
        changed = existing and old.get("listed_title") and any(
            old.get("listed_" + key) != record[key] for key in ("title", "venue", "year"))
        if existing and existing.get("status") != "preprint" and not changed:
            continue
        metadata, errors = public_record(record, existing, site["person"])
        scan["source_errors"] += errors
        if metadata is None:
            if not existing or changed:
                scan["unverified_count"] += 1
            continue
        source_ids = {"doi:" + metadata["doi"].lower()} if metadata.get("doi") else set()
        if metadata.get("arxiv_id"):
            source_ids.add("arxiv:" + metadata["arxiv_id"])
        if not existing:
            existing = next((p for p in papers if source_ids & identifiers(p)
                             or same_title(p["title"], metadata["title"])), None)
        if existing and existing["status"] == "published" and metadata["status"] == "preprint":
            continue
        if existing:
            before = deepcopy(existing)
            if not same_title(existing["title"], metadata["title"]):
                existing["title"] = metadata["title"]
                existing.pop("zh_title", None)
            if existing["venue"] != metadata["venue"]:
                existing.pop("top", None)
            for key in ("venue", "year", "status", "citation"):
                if key != "citation" or metadata[key] or key in existing:
                    existing[key] = metadata[key]
            # Preserve author roles, descriptions and figures; do not invent new rankings.
            label = "DOI" if metadata["status"] == "published" else "arXiv"
            pair = [label, metadata["url"]]
            if pair not in existing["links"]:
                existing["links"].insert(0, pair)
            if existing != before:
                existing["public_source"] = {"registry": metadata["source"],
                                             "url": metadata["url"], "verified_at": checked}
                scan["updated"].append(existing["id"])
            continue
        field = next(f for f in FIELDS if not f[1] or re.search(f[1], metadata["title"], re.I))
        if not any(f["id"] == field[0] for f in updated["fields"]):
            updated["fields"].append({"id": field[0], "name": {"en": field[2], "zh": field[3]}})
        key = "pub-" + sha256(metadata["url"].encode()).hexdigest()[:12]
        new = {"id": key, "field": field[0], "status": metadata["status"],
               "year": metadata["year"], "title": metadata["title"],
               "venue": metadata["venue"], "authors": ", ".join(metadata["authors"]),
               "citation": metadata["citation"],
               "links": [["DOI" if metadata["status"] == "published" else "arXiv", metadata["url"]]],
               "figures": [], "public_source": {"registry": metadata["source"],
                   "url": metadata["url"], "verified_at": checked}}
        if has_author(metadata["authors"][:1], site["person"]):
            new["role"] = "first"
        if metadata.get("arxiv_id") and metadata["status"] == "published":
            new["links"].append(["arXiv", "https://arxiv.org/abs/" + metadata["arxiv_id"]])
        papers.insert(0, new)
        scan["added"].append(key)
    scan["status"] = "partial" if scan["source_errors"] else "complete"
    return updated, scan
