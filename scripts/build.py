"""Generate the static academic homepage from the public research records."""

from collections import Counter, defaultdict
from html import escape
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
ORIGIN = "https://ttanddd.github.io"
DATA = json.loads((ROOT / "data/site.json").read_text(encoding="utf-8"))
PERSON = DATA["person"]
STATUS = {"published": "Published", "accepted": "Accepted", "preprint": "Public preprint"}
ROLES = {"first": "First author", "cofirst": "Co-first author, listed second"}
DESCRIPTION = (
    "Hailong Qu is a PhD student at Chongqing University working on AI for Science, "
    "engineering agents, offshore wind energy and indoor air quality."
)


def h(value):
    return escape(str(value), quote=True)


def external(label, url, css_class="", aria_label=""):
    aria = f' aria-label="{h(aria_label)}"' if aria_label else ""
    return (
        f'<a class="{h(css_class)}" href="{h(url)}" target="_blank" rel="noopener noreferrer"{aria}>'
        f'{h(label)}<span class="out" aria-hidden="true">↗</span></a>'
    )


def resource_links(links):
    if not links:
        return ""
    anchors = [external("Project site" if label == "Project" else label, url, "text-link")
               for label, url in links]
    return '<div class="resource-links">' + "".join(anchors) + "</div>"


def project_card(project):
    name = h(project["name"])
    return f"""<article class="project-card">
      <a class="project-art" href="{h(project['links'][0][1])}" target="_blank" rel="noopener noreferrer" aria-label="View the {name} project">
        <img src="./assets/media/{h(project['image'])}" alt="{h(project['alt'])}" width="840" height="500" loading="lazy">
      </a>
      <div class="project-body"><p class="project-field">{h(project['category'])}</p>
        <h3>{name}</h3><p class="project-note">{h(project['description'])}</p>
        {resource_links(project['links'])}
      </div></article>"""


def paper_entry(paper):
    status = paper["status"]
    authors = h(paper["authors"]).replace("Hailong Qu", "<strong>Hailong Qu</strong>")
    year = f'<time class="paper-year">{h(paper["year"])}</time>' if paper.get("year") else ""
    venue = f'<cite>{h(paper["venue"])}</cite>'
    if paper.get("citation"):
        venue += f'<span class="vol">, {h(paper["citation"])}</span>'
    metadata = [venue, h(ROLES[paper["role"]]), f'<span class="paper-state">{h(STATUS[status])}</span>']
    if paper.get("top"):
        metadata.append('<span class="rank" title="2026 Xinrui ranking, best tier across major and minor categories">Xinrui tier 1 · TOP</span>')
    separator = '<span class="sep" aria-hidden="true">·</span>'
    return f"""<article class="paper" id="paper-{h(paper['id'])}" data-status="{h(status)}">
      <div class="paper-title"><h4>{h(paper['title'])}</h4>{year}</div>
      <p class="paper-note">{h(paper['note'])}</p><p class="authors">{authors}</p>
      <p class="paper-meta">{separator.join(metadata)}</p>{resource_links(paper['links'])}
    </article>"""


def publication_groups():
    papers_by_field = defaultdict(list)
    for paper in DATA["papers"]:
        papers_by_field[paper["field"]].append(paper_entry(paper))
    output = []
    for field in DATA["fields"]:
        key = h(field["id"])
        papers = "".join(papers_by_field[field["id"]])
        output.append(f'<section class="paper-group" data-field="{key}" aria-labelledby="field-{key}">'
                      f'<h3 id="field-{key}">{h(field["name"])}</h3><div class="paper-list">{papers}</div></section>')
    return "\n".join(output)


def publication_filters():
    counts = Counter(paper["status"] for paper in DATA["papers"])
    counts["all"] = len(DATA["papers"])
    tabs = {"all": "All", "published": "Journal articles", "accepted": "Accepted",
            "preprint": "Preprints", "review": "Under review"}
    buttons = []
    for key, label in tabs.items():
        active = "true" if key == "all" else "false"
        count = f'<span class="tab-count">{counts[key]}</span>' if key != "review" else ""
        buttons.append(f'<button type="button" data-filter="{key}" aria-pressed="{active}">{label}{count}</button>')
    return "".join(buttons)


def navigation():
    links = [("about", "About"), ("research", "Research"), ("publications", "Publications"), ("background", "Background")]
    return "".join(f'<a href="#{key}" data-nav="{key}">{name}</a>' for key, name in links)


def education():
    items = []
    for entry in DATA["degrees"]:
        end = entry["end"] or "present"
        items.append(f'<li><span class="period">{h(entry["year"])} – {h(end)}</span>'
                     f'<h3>{h(entry["institution"])}</h3><p>{h(entry["degree"])}</p></li>')
    return "".join(items)


def image_credits():
    links = DATA["credits"]
    items = [
        'Block Island Wind Farm photograph by Dennis Schroeder / NREL, 2016. ' + external("Source photograph", links["wind"]),
        'Original drawing based on the dimensions of the EngiWorld CAD tube-sheet task. ' + external("Task specification", links["cad"]),
        'CARLA views adapted from Table 8 of SpatialWorld by Hongcheng Gao, Hailong Qu et al. (2026). The two views were cropped, resized and combined. '
        + " ".join([external("Table 8", links["spatial"]), external("CC BY 4.0", links["license"]), external("CARLA asset licenses", links["carla"])]),
    ]
    return "".join(f"<li>{item}</li>" for item in items)


def render():
    name = h(PERSON["name"])
    email = h(PERSON["email"])
    title = f"{name} · Chongqing University"
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title><meta name="description" content="{h(DESCRIPTION)}"><meta name="author" content="{name}">
  <link rel="canonical" href="{ORIGIN}/">
  <meta property="og:type" content="website"><meta property="og:locale" content="en_US">
  <meta property="og:title" content="{title}"><meta property="og:description" content="{h(DESCRIPTION)}">
  <meta property="og:url" content="{ORIGIN}/"><meta property="og:image" content="{ORIGIN}/assets/media/block-island.webp">
  <meta name="theme-color" content="#faf8f2"><link rel="icon" type="image/png" href="./assets/favicon.png">
  <link rel="preload" href="./assets/fonts/serif-regular.woff2" as="font" type="font/woff2" crossorigin>
  <link rel="preload" href="./assets/fonts/sans-regular.woff2" as="font" type="font/woff2" crossorigin>
  <script>try{{const t=localStorage.getItem('hq-theme');if(t==='dark'||t==='light')document.documentElement.dataset.theme=t;else if(matchMedia('(prefers-color-scheme: dark)').matches)document.documentElement.dataset.theme='dark'}}catch(e){{}}</script>
  <link rel="stylesheet" href="./assets/site.css"><script defer src="./assets/site.js"></script>
</head>
<body>
<a class="skip" href="#main">Skip to main content</a>
<header class="topbar"><div class="shell top-inner">
  <a class="brand" href="#about" aria-label="Home"><span aria-hidden="true" class="monogram">hq</span><span class="brand-name">{name}</span></a>
  <nav id="nav" class="nav" aria-label="Main navigation">{navigation()}</nav>
  <div class="tools">
    <button class="theme" type="button" data-theme-button aria-label="Change color theme" title="Change color theme"><span aria-hidden="true"></span></button>
    <button class="menu" type="button" aria-expanded="false" aria-controls="nav"><span>Menu</span><i aria-hidden="true"></i></button>
  </div>
</div></header>
<main id="main">
<section id="about" class="hero shell" aria-labelledby="name">
  <div class="intro"><div class="affiliation"><span aria-hidden="true"></span>Chongqing University</div>
    <h1 id="name">{name}</h1><p class="role">PhD student in Civil Engineering</p>
    <p class="bio">My research in <strong>AI for Science</strong> focuses on how multimodal agents use engineering software and reason about space. I also build models to predict offshore wind turbine loads and indoor air quality.</p>
    <div class="primary-links">{external('Google Scholar', PERSON['scholar'], 'button primary')}<a class="button secondary" href="./assets/Hailong-Qu-CV.pdf" target="_blank" rel="noopener">Public CV<span class="pdf-mark">PDF</span></a></div>
    <div class="contact-line"><a class="plain-link" href="mailto:{email}" aria-label="Email {name}">{email}</a><i aria-hidden="true"></i>{external('GitHub', PERSON['github'], 'plain-link', 'Hailong Qu on GitHub')}</div>
  </div>
  <figure class="hero-figure"><div class="hero-frame"><img src="./assets/media/block-island.webp" alt="Offshore wind turbines above a breaking wave near Block Island, Rhode Island" width="1100" height="850" fetchpriority="high"></div>
    <figcaption><span>Block Island Wind Farm, Rhode Island</span>{external('Dennis Schroeder / NREL', DATA['credits']['wind'])}</figcaption></figure>
</section>
<section id="research" class="band research" aria-labelledby="research-title"><div class="shell">
  <div class="section-head"><h2 id="research-title">Selected research</h2><a class="jump" href="#publications">All publications<span aria-hidden="true">↓</span></a></div>
  <div class="projects">{''.join(project_card(project) for project in DATA['projects'])}</div>
</div></section>
<section id="publications" class="section shell" aria-labelledby="publications-title">
  <div class="section-head"><h2 id="publications-title">Publications</h2></div>
  <div class="filters" data-filters hidden role="group" aria-label="Filter publications">{publication_filters()}</div>
  <p class="sr-only" data-result-count aria-live="polite" data-template="{{n}} publications shown"></p>
  <div data-groups>{publication_groups()}</div>
  <div class="empty" data-empty hidden><p>No manuscripts are listed publicly in this category.</p><button type="button" data-reset class="jump">View public work<span aria-hidden="true">→</span></button></div>
</section>
<div id="background" class="band background"><div class="shell background-grid">
  <section id="experience" aria-labelledby="work-title"><h2 id="work-title">Experience</h2>
    <div class="job"><span class="period">Jun – Nov 2026</span><h3>Zhiman AI</h3><p class="job-role">Engineering AI Research and Development Intern</p>
      <p>Co-designed <strong>EngiWorld</strong>, ran model experiments and evaluated the files agents produced in professional engineering software.</p>
      <p>Designed and tested software-development tasks for <strong>Micius-Flash</strong>, including a CAD hole-pattern plugin and a PySide6 implementation of Blender modeling workflows.</p>
      <div class="report">{external('Micius-Flash technical report', DATA['report'], 'text-link')}<span>Contributor</span></div>
    </div>
  </section>
  <section id="education" aria-labelledby="edu-title"><h2 id="edu-title">Education</h2><ol class="degrees">{education()}</ol></section>
</div></div>
</main>
<footer class="footer shell"><div class="footer-top"><span>© 2026 {name}</span><a href="#about">Back to top ↑</a></div>
  <details class="credits"><summary>Image credits</summary><ul>{image_credits()}</ul></details>
</footer>
</body>
</html>
"""


if __name__ == "__main__":
    (ROOT / "index.html").write_text(render(), encoding="utf-8", newline="\n")
