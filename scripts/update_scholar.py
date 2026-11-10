"""Refresh verified Google Scholar counts for publications already listed on the site."""

from datetime import datetime, timezone
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import tempfile
import unicodedata
from urllib.parse import parse_qs, urlencode, urlsplit
from urllib.request import Request, urlopen
from xml.etree.ElementTree import Element, SubElement


ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
URL = "https://scholar.google.com/citations"
VOID = set("area base br col embed hr img input link meta param source track wbr".split())


class Document(HTMLParser):
    """Build only the lightweight HTML tree needed for the public profile tables."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Element("document")
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        node = SubElement(self.stack[-1], tag, {key: value or "" for key, value in attrs})
        if tag not in VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        for idx in range(len(self.stack) - 1, 0, -1):
            if self.stack[idx].tag == tag:
                del self.stack[idx:]
                break

    def handle_data(self, data):
        node = self.stack[-1]
        if len(node):
            node[-1].tail = (node[-1].tail or "") + data
        else:
            node.text = (node.text or "") + data


def text_of(node):
    return "".join(node.itertext()).strip() if node is not None else ""


def normalize(text):
    return "".join(c for c in unicodedata.normalize("NFKD", text.casefold()) if c.isalnum())


def integer(text):
    if not re.fullmatch(r"[0-9]+(?:,[0-9]{3})*", text):
        raise ValueError("Google Scholar returned an unreadable citation count.")
    return int(text.replace(",", ""))


def class_link(row, name):
    return next((a for a in row.iter("a") if name in a.get("class", "").split()), None)


def query_field(href, key):
    parts = urlsplit(href)
    if parts.netloc and parts.hostname != "scholar.google.com":
        return ""
    return parse_qs(parts.query).get(key, [""])[0]


def extract(html, site, previous, checked):
    document = Document()
    document.feed(html)
    root = document.root
    name = text_of(root.find(".//*[@id='gsc_prf_in']"))
    if normalize(name) != normalize(site["person"]["name"]):
        raise ValueError("Google Scholar did not return the requested author profile.")
    totals = {}
    labels = {"Citations": "citations", "h-index": "h_index", "i10-index": "i10_index"}
    for row in root.findall(".//*[@id='gsc_rsb_st']//tr"):
        cells = row.findall("td")
        if len(cells) >= 2 and text_of(cells[0]) in labels:
            totals[labels[text_of(cells[0])]] = integer(text_of(cells[1]))
    if totals.keys() != set(labels.values()):
        raise ValueError("Google Scholar did not return all three profile totals.")

    by_title = {normalize(p["title"]): p["id"] for p in site["papers"]}
    previous_papers = previous.get("papers", {})
    by_id = {value["work_id"]: key for key, value in previous_papers.items() if value.get("work_id")}
    observed = {}
    profile_id = query_field(site["person"]["scholar"], "user")
    for row in root.findall(".//*[@id='gsc_a_b']/tr"):
        title = class_link(row, "gsc_a_at")
        if title is None:
            continue
        work_id = query_field(title.get("href", ""), "citation_for_view")
        if not re.fullmatch(re.escape(profile_id) + r":[A-Za-z0-9_-]+", work_id):
            raise ValueError("Unexpected Scholar publication identifier.")
        key = by_title.get(normalize(text_of(title))) or by_id.get(work_id)
        if key not in by_title.values():
            continue
        count_link = class_link(row, "gsc_a_ac")
        if count_link is None:
            raise ValueError("An indexed paper is missing its citation cell.")
        count = text_of(count_link)
        cluster = query_field(count_link.get("href", ""), "cites")
        if key in observed:
            raise ValueError("A curated title matched multiple Scholar records.")
        observed[key] = {"work_id": work_id, "count": integer(count) if count else None,
                         "cluster": cluster if cluster.isdigit() else None, "checked_at": checked}
    if not observed:
        raise ValueError("Google Scholar did not return any of the listed publications.")
    retained = {key: previous_papers[key] for key in by_title.values() if key in previous_papers}
    return {"checked_at": checked, "profile": site["person"]["scholar"], **totals, "papers": {**retained, **observed}}


def main():
    site = json.loads((DATA / "site.json").read_text(encoding="utf-8"))
    path = DATA / "scholar.json"
    previous = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    user = query_field(site["person"]["scholar"], "user")
    request = Request(URL + "?" + urlencode({"user": user, "hl": "en", "pagesize": 100}), headers={
        "User-Agent": "Mozilla/5.0 (compatible; academic homepage citation check; +https://ttanddd.github.io/)",
        "Accept-Language": "en-US,en;q=0.8",
    })
    with urlopen(request, timeout=30) as response:
        if urlsplit(response.geturl()).hostname != "scholar.google.com":
            raise ValueError("Google Scholar returned an unexpected destination.")
        html = response.read().decode("utf-8")
    checked = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    result = extract(html, site, previous, checked)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n", dir=DATA, delete=False) as staged:
        staged.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    Path(staged.name).replace(path)
    print(f"Verified {len(result['papers'])} listed papers. Profile citations: {result['citations']}. Checked {checked}.")


if __name__ == "__main__":
    main()
