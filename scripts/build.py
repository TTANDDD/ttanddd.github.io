"""Render English and Chinese editions of the academic homepage."""

from collections import Counter
from datetime import datetime, timedelta, timezone
from html import escape
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
ORIGIN = "https://ttanddd.github.io"
DATA = json.loads((ROOT / "data/site.json").read_text(encoding="utf-8"))
LABELS = json.loads((ROOT / "data/interface.json").read_text(encoding="utf-8"))
SCHOLAR = json.loads((ROOT / "data/scholar.json").read_text(encoding="utf-8"))
PERSON = DATA["person"]
LINK_LABELS = {"Project": "project", "Code": "code", "Paper": "paper"}
SECTIONS = [("about", "about"), ("research", "research"), ("publications", "pubs"), ("background", "background")]


def h(value):
    return escape(str(value), quote=True)


def external(label, url, css_class="", lang=""):
    language = f' lang="{lang}"' if lang else ""
    return (f'<a class="{h(css_class)}" href="{h(url)}" target="_blank" rel="noopener noreferrer"{language}>'
            f'{h(label)}<span class="out" aria-hidden="true">↗</span></a>')


def links(items, t):
    if not items:
        return ""
    anchors = (external(t[LINK_LABELS[key]] if key in LINK_LABELS else key, url, "text-link") for key, url in items)
    return '<div class="resource-links">' + "".join(anchors) + "</div>"


def language_link(locale):
    t = LABELS[locale]
    target = "./zh/" if locale == "en" else "../"
    return (f'<a class="language" data-language href="{target}" lang="{t["otherLang"]}" '
            f'hreflang="{t["otherLang"]}" aria-label="{h(t["switch"])}">{h(t["other"])}</a>')


def navigation(t):
    return "".join(f'<a href="#{anchor}" data-nav="{anchor}">{h(t[key])}</a>' for anchor, key in SECTIONS)


def project_card(project, locale, base):
    t = LABELS[locale]
    name = h(project["name"])
    return f"""<article class="project-card">
      <a class="project-art" href="{h(project['links'][0][1])}" target="_blank" rel="noopener noreferrer" aria-label="{name} · {h(t['project'])}">
        <img src="{base}assets/media/{h(project['image'])}" alt="{h(project['alt'][locale])}" width="840" height="500" loading="lazy" decoding="async">
      </a>
      <div class="project-body"><p class="project-field">{h(project['category'][locale])}</p>
        <h3>{name}</h3><p class="project-note">{h(project['description'][locale])}</p>{links(project['links'],t)}
      </div></article>"""


def paper_figure(figure, locale, base):
    t = LABELS[locale]
    number = t["figure"].format(n=figure["number"])
    caption = figure["caption"][locale]
    url = f'{base}assets/media/papers/{h(figure["file"])}'
    return f"""<figure class="paper-figure">
        <a class="figure-open" href="{url}" data-figure data-credit="{h(figure['credit'])}" data-license="{h(figure['license'])}" aria-label="{h(t['zoom'])} · {h(number)} · {h(caption)}">
          <img src="{url}" alt="{h(caption)}" width="{figure['width']}" height="{figure['height']}" loading="lazy" decoding="async"><span class="zoom-corner" aria-hidden="true">⤢</span>
        </a>
        <figcaption><span class="figure-number">{h(number)}</span><span class="figure-caption">{h(caption)}</span>
          {external(t['source'],figure['source'],'figure-source')}</figcaption>
      </figure>"""


def paper_entry(paper, locale, base):
    t = LABELS[locale]
    status = paper["status"]
    authors = h(paper["authors"]).replace("Hailong Qu", "<strong>Hailong Qu</strong>")
    title = paper["title"] if locale == "en" else paper["zh_title"]
    original = f'<p class="original-title" lang="en">{h(paper["title"])}</p>' if locale == "zh" else ""
    year = f'<time class="paper-year">{paper["year"]}</time>' if paper.get("year") else ""
    venue = f'<cite lang="en">{h(paper["venue"])}</cite>'
    if paper.get("citation"):
        venue += f'<span class="vol">, {h(paper["citation"])}</span>'
    meta = [venue,h(t[paper["role"]]),h(t[status + "State"])]
    if paper.get("top"):
        meta.append(f'<span class="rank" title="{h(t["tierHelp"])}">{h(t["tier"])}</span>')
    record = SCHOLAR["papers"].get(paper["id"], {})
    if record.get("count") is not None:
        if record.get("cluster"):
            dest = "https://scholar.google.com/scholar?cites=" + record["cluster"]
        else:
            dest = PERSON["scholar"] + "&view_op=view_citation&citation_for_view=" + record["work_id"]
        meta.append(external(t["cited"].format(n=record["count"]), dest, "cited"))
    separator = '<span class="sep" aria-hidden="true">·</span>'
    figures = "".join(paper_figure(fig,locale,base) for fig in paper["figures"])
    return f"""<article class="paper" id="paper-{h(paper['id'])}" data-status="{h(status)}">
      <div class="paper-title"><h4>{h(title)}</h4>{year}</div>{original}
      <p class="paper-note">{h(paper['note'][locale])}</p><p class="authors" lang="en">{authors}</p>
      <p class="paper-meta">{separator.join(meta)}</p>{links(paper['links'],t)}
      <div class="figure-grid">{figures}</div>
    </article>"""


def publication_groups(locale, base):
    output = []
    for field in DATA["fields"]:
        key = h(field["id"])
        papers = "".join(paper_entry(p, locale, base) for p in DATA["papers"] if p["field"] == field["id"])
        output.append(f'<section class="paper-group" data-field="{key}" aria-labelledby="field-{key}">'
                      f'<h3 id="field-{key}">{h(field["name"][locale])}</h3><div class="paper-list">{papers}</div></section>')
    return "\n".join(output)


def publication_filters(t):
    counts = Counter(paper["status"] for paper in DATA["papers"])
    counts["all"] = len(DATA["papers"])
    return "".join(f'<button type="button" data-filter="{key}" aria-pressed="{str(key=="all").lower()}">'
                   f'{h(t[key])}<span class="tab-count">{counts[key]}</span></button>' for key in ("all","published","preprint"))


def metrics(locale):
    t = LABELS[locale]
    checked = datetime.fromisoformat(SCHOLAR["checked_at"].replace("Z","+00:00")).astimezone(timezone(timedelta(hours=8)))
    stamp = checked.strftime("%b %d, %Y") if locale == "en" else f"{checked.year} 年 {checked.month} 月 {checked.day} 日"
    stats = "".join(f'<div><dt>{h(t[key])}</dt><dd>{SCHOLAR[key]}</dd></div>' for key in ("citations","h_index","i10_index"))
    return (f'<aside class="scholar-metrics" aria-label="{h(t["stats"])}">{external(t["stats"],SCHOLAR["profile"],"metrics-link")}'
            f'<dl>{stats}</dl><p>{h(t["checked"])} <time datetime="{h(SCHOLAR["checked_at"])}">{h(stamp)}</time></p></aside>')


def education(locale):
    t = LABELS[locale]
    items = []
    for entry in DATA["degrees"]:
        end = entry["end"] or t["present"]
        items.append(f'<li><span class="period">{h(entry["year"])} – {h(end)}</span>'
                     f'<h3>{h(entry["institution"][locale])}</h3><p>{h(entry["degree"][locale])}</p></li>')
    return "".join(items)


def image_credits(t):
    urls = DATA["credits"]
    items = [
        h(t["avatarCredit"]) + " " + external(t["stats"],PERSON["scholar"]),
        h(t["cadCredit"]) + " " + external(t["spec"], urls["cad"]),
        h(t["spatialCredit"]) + " " + " ".join([external(t["table"],urls["spatial"]),external("CC BY 4.0",urls["license"]),external(t["carla"],urls["carla"])]),
        h(t["figCreditNote"]),
    ]
    return "".join(f"<li>{item}</li>" for item in items)


def render(locale):
    t = LABELS[locale]
    base, path = ("./", "/") if locale == "en" else ("../", "/zh/")
    lang = t["lang"]
    name, email = h(t["name"]), h(PERSON["email"])
    title = name + (" · Chongqing University" if locale == "en" else " · 重庆大学")
    avatar = base + "assets/media/" + PERSON["avatar"]
    cv = base + ("assets/Hailong-Qu-CV.pdf" if locale=="en" else "assets/Hailong-Qu-CV-zh.pdf")
    return f"""<!doctype html>
<html lang="{lang}">
<head>
  <meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title><meta name="description" content="{h(t['description'])}"><meta name="author" content="{h(PERSON['name'])}">
  <link rel="canonical" href="{ORIGIN}{path}"><link rel="alternate" hreflang="en" href="{ORIGIN}/"><link rel="alternate" hreflang="zh-CN" href="{ORIGIN}/zh/"><link rel="alternate" hreflang="x-default" href="{ORIGIN}/">
  <meta property="og:type" content="website"><meta property="og:title" content="{title}"><meta property="og:description" content="{h(t['description'])}">
  <meta property="og:url" content="{ORIGIN}{path}"><meta property="og:image" content="{ORIGIN}/assets/media/{PERSON['avatar']}"><meta property="og:locale" content="{'en_US' if locale=='en' else 'zh_CN'}">
  <meta name="theme-color" content="#101c29"><link rel="icon" type="image/jpeg" href="{avatar}">
  <link rel="preload" href="{base}assets/fonts/serif-regular.woff2" as="font" type="font/woff2" crossorigin>
  <link rel="preload" href="{base}assets/fonts/sans-regular.woff2" as="font" type="font/woff2" crossorigin>
  <link rel="stylesheet" href="{base}assets/site.css"><script defer src="{base}assets/site.js"></script><script defer src="{base}assets/cover.js"></script>
</head>
<body>
<a class="skip" href="#about">{h(t['skip'])}</a>
<header class="cover" id="home" aria-labelledby="name">
  <canvas class="flow" aria-hidden="true"></canvas>
  <div class="cover-rail"><a href="#home" class="cover-brand">{name}</a>{language_link(locale)}</div>
  <div class="cover-core">
    <div class="portrait"><img src="{avatar}" alt="{h(t['portrait'])}" width="256" height="256" fetchpriority="high"></div>
    <h1 id="name">{name}</h1><p class="cover-role">{h(t['degree'])}</p>
    <p class="cover-focus">{h(t['focus'])}<i></i>{h(t['agents'])}<i></i>{h(t['wind'])}</p>
    <div class="cover-actions"><a class="enter" href="#about">{h(t['enter'])}<span aria-hidden="true">↓</span></a><a href="#publications">{h(t['pubs'])}<span aria-hidden="true">↘</span></a></div>
  </div>
  <div class="cover-foot"><div class="cover-socials">{external(t['stats'],PERSON['scholar'])}{external('GitHub',PERSON['github'])}<a href="mailto:{email}">{h(t['mail'])}</a>{external(t['cv'],cv)}</div></div>
</header>
<div class="topbar"><div class="shell top-inner">
  <a class="brand" href="#home" aria-label="{h(t['home'])}"><span class="brand-name">{name}</span></a>
  <nav id="nav" class="nav" aria-label="{h(t['home'])}">{navigation(t)}</nav>
  <div class="tools">{language_link(locale)}<button class="theme" type="button" data-theme-button aria-label="{h(t['theme'])}" title="{h(t['theme'])}"><span aria-hidden="true"></span></button>
  <button class="menu" type="button" aria-expanded="false" aria-controls="nav"><span>{h(t['menu'])}</span><i aria-hidden="true"></i></button></div>
</div></div>
<main id="main">
<section id="about" class="overview shell" aria-labelledby="about-title"><div><h2 id="about-title">{h(t['about'])}</h2><p class="bio">{h(t['bio'])}</p></div>{metrics(locale)}</section>
<section id="research" class="band research" aria-labelledby="research-title"><div class="shell">
  <div class="section-head"><h2 id="research-title">{h(t['selected'])}</h2><a class="jump" href="#publications">{h(t['browse'])}<span aria-hidden="true">↓</span></a></div>
  <div class="projects">{''.join(project_card(proj,locale,base) for proj in DATA['projects'])}</div>
</div></section>
<section id="publications" class="section shell" aria-labelledby="publications-title">
  <div class="section-head"><h2 id="publications-title">{h(t['pubs'])}</h2></div>
  <div class="filters" data-filters hidden role="group" aria-label="{h(t['filterLabel'])}">{publication_filters(t)}</div>
  <p class="sr-only" data-result-count aria-live="polite" data-template="{h(t['count'])}"></p>
  {publication_groups(locale,base)}
</section>
<div id="background" class="band background"><div class="shell background-grid">
  <section id="experience" aria-labelledby="work-title"><h2 id="work-title">{h(t['work'])}</h2>
    <div class="job"><span class="period">{h(t['date'])}</span><h3>{h(t['company'])}</h3><p class="job-role">{h(t['intern'])}</p>
      <p>{h(t['intern1'])}</p><p>{h(t['intern2'])}</p>
      <div class="report">{external(t['report'],DATA['report'],'text-link')}<span>{h(t['contributor'])}</span></div></div>
  </section>
  <section id="education" aria-labelledby="edu-title"><h2 id="edu-title">{h(t['edu'])}</h2><ol class="degrees">{education(locale)}</ol></section>
</div></div></main>
<footer class="footer shell"><div class="footer-top"><span>© 2026 {name}</span><a href="#home">{h(t['back'])} ↑</a></div>
  <details class="credits"><summary>{h(t['credits'])}</summary><ul>{image_credits(t)}</ul></details>
</footer>
<dialog class="figure-viewer" aria-labelledby="viewer-title">
  <div class="viewer-top"><strong id="viewer-title"></strong><button type="button" data-close>{h(t['close'])} <span aria-hidden="true">×</span></button></div>
  <div class="viewer-image"><img alt=""></div>
  <p class="viewer-caption"></p><p class="viewer-credit" aria-label="{h(t['attribution'])}"></p>
  <div class="viewer-links"><a data-full target="_blank" rel="noopener">{h(t['full'])} ↗</a><a data-source target="_blank" rel="noopener noreferrer">{h(t['source'])} ↗</a></div>
</dialog>
</body></html>
"""


if __name__ == "__main__":
    for locale, path in [("en", ROOT / "index.html"), ("zh", ROOT / "zh/index.html")]:
        path.parent.mkdir(exist_ok=True)
        path.write_text(render(locale), encoding="utf-8", newline="\n")
