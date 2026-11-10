// Switch between the two pre-rendered editions without navigating the document.
(() => {
  "use strict";
  const root = document.documentElement;
  const regions = [".skip", ".cover-rail", ".cover-core", ".cover-foot", ".topbar", "main", "footer", ".figure-viewer"];
  const metadata = ['meta[name="description"]', 'meta[property="og:title"]', 'meta[property="og:description"]',
                    'meta[property="og:url"]', 'meta[property="og:locale"]'];
  const editions = new Map();
  let requestNumber = 0;

  function getEdition(path) {
    if (!editions.has(path)) {
      const request = fetch(path, {credentials:"same-origin", cache:"no-cache"}).then(async response => {
        if (!response.ok) throw Error("Edition unavailable");
        const doc = new DOMParser().parseFromString(await response.text(), "text/html");
        const lang = path === "/zh/" ? "zh-CN" : "en";
        if (doc.documentElement.lang !== lang || !regions.every(selector => doc.querySelector(selector))) {
          throw Error("Incomplete edition");
        }
        return doc;
      }).catch(error => {
        editions.delete(path);
        throw error;
      });
      editions.set(path, request);
    }
    return editions.get(path);
  }

  function readingPosition() {
    const bar = document.querySelector(".topbar").getBoundingClientRect();
    const edge = bar.top <= 1 ? bar.bottom + 8 : 0;
    let marker = document.getElementById("home");
    let top = marker.getBoundingClientRect().top;
    for (const node of document.querySelectorAll("main [id], #footer")) {
      if (!node.getClientRects().length) continue;
      const y = node.getBoundingClientRect().top;
      if (y <= edge + 1 && y >= top) {
        marker = node;
        top = y;
      }
    }
    const hashTarget = document.getElementById(location.hash.slice(1));
    const hashIsCurrent = hashTarget && (Math.abs(hashTarget.getBoundingClientRect().top - edge) < 32 ||
                          hashTarget === marker || (hashTarget.matches(".paper") && hashTarget.contains(marker)));
    return {id:marker.id, top, scroll:scrollY, hash:hashIsCurrent ? location.hash : "",
            atBottom:scrollY + innerHeight >= document.documentElement.scrollHeight - 2};
  }

  function restorePosition(position) {
    const marker = document.getElementById(position.id);
    let top = position.scroll;
    if (position.atBottom) top = root.scrollHeight;
    else if (marker) top = scrollY + marker.getBoundingClientRect().top - position.top;
    window.scrollTo({top, behavior:"instant"});
  }

  async function switchEdition(path, trigger) {
    const number = ++requestNumber;
    if (root.lang === (path === "/zh/" ? "zh-CN" : "en")) return;
    const notice = document.getElementById("language-notice");
    notice.hidden = true;
    trigger?.setAttribute("aria-busy", "true");
    let source;
    try {
      source = await getEdition(path);
    } catch {
      if (number === requestNumber) {
        notice.textContent = root.lang === "en" ? "Chinese could not be loaded. Please try again." : "英文版加载失败，请再试一次。";
        notice.hidden = false;
      }
      return;
    } finally {
      trigger?.removeAttribute("aria-busy");
    }
    if (number !== requestNumber) return;

    // Measure after the fetch, so reading or scrolling during a slow connection is respected.
    const position = readingPosition();
    const openDetails = [...document.querySelectorAll("details[open]")].map(detail => detail.id);
    const openFigure = document.querySelector(".figure-viewer[open] [data-full]")?.href;
    const menuOpen = document.querySelector(".menu").getAttribute("aria-expanded") === "true";
    const focusArea = trigger?.closest(".cover-rail") ? ".cover-rail" : ".topbar";
    root.style.overflowAnchor = "none";
    if (trigger) {
      const url = new URL(path, location.origin);
      url.search = location.search;
      url.hash = position.hash;
      history.replaceState(history.state, "", url);
    }
    root.lang = source.documentElement.lang;
    document.title = source.title;
    document.querySelector('link[rel="canonical"]').href = source.querySelector('link[rel="canonical"]').getAttribute("href");
    for (const selector of metadata) document.querySelector(selector).content = source.querySelector(selector).content;
    for (const selector of regions) {
      const content = source.querySelector(selector).cloneNode(true);
      const current = document.querySelector(selector);
      if (selector === ".figure-viewer") current.replaceWith(content);
      else current.replaceChildren(...content.childNodes);
    }
    for (const id of openDetails) {
      const detail = document.getElementById(id);
      if (detail) detail.open = true;
    }
    document.dispatchEvent(new Event("site:localechange"));
    if (menuOpen) {
      document.getElementById("nav").classList.add("is-open");
      document.querySelector(".menu").setAttribute("aria-expanded", "true");
    }
    if (trigger) document.querySelector(focusArea + " [data-language]").focus({preventScroll:true});
    restorePosition(position);
    if (openFigure) [...document.querySelectorAll("[data-figure]")].find(link => link.href === openFigure)?.click();
    root.style.removeProperty("overflow-anchor");
  }

  function preload(event) {
    const link = event.target.closest?.("[data-language]");
    if (link) getEdition(new URL(link.href).pathname).catch(() => {});
  }
  document.addEventListener("pointerover", preload);
  document.addEventListener("focusin", preload);
  document.addEventListener("click", event => {
    const link = event.target.closest("[data-language]");
    if (!link || event.defaultPrevented || event.button !== 0 || event.ctrlKey || event.metaKey || event.altKey || event.shiftKey) return;
    event.preventDefault();
    switchEdition(new URL(link.href).pathname, link);
  });
  window.addEventListener("popstate", () => switchEdition(location.pathname, null));
})();
