(() => {
  "use strict";
  const root = document.documentElement;
  root.classList.add("js");

  const themeButton = document.querySelector("[data-theme-button]");
  const systemTheme = window.matchMedia("(prefers-color-scheme: dark)");
  function savedTheme() {
    try { return localStorage.getItem("hq-theme"); } catch { return null; }
  }
  function applyTheme(theme) {
    root.dataset.theme = theme;
    themeButton.setAttribute("aria-pressed", String(theme === "dark"));
    document.querySelector('meta[name="theme-color"]').content = theme === "dark" ? "#20241e" : "#faf8f2";
  }
  applyTheme(savedTheme() || (systemTheme.matches ? "dark" : "light"));
  themeButton.addEventListener("click", () => {
    const next = root.dataset.theme === "dark" ? "light" : "dark";
    applyTheme(next);
    try { localStorage.setItem("hq-theme", next); } catch {}
  });
  systemTheme.addEventListener?.("change", () => {
    if (!savedTheme()) applyTheme(systemTheme.matches ? "dark" : "light");
  });

  const menuButton = document.querySelector(".menu");
  const nav = document.getElementById("nav");
  function closeMenu() {
    nav.classList.remove("is-open");
    menuButton.setAttribute("aria-expanded","false");
  }
  menuButton.addEventListener("click", () => {
    const open = nav.classList.toggle("is-open");
    menuButton.setAttribute("aria-expanded", String(open));
  });
  nav.addEventListener("click", closeMenu);
  document.addEventListener("click", (event) => {
    if (!event.target.closest(".topbar")) closeMenu();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && nav.classList.contains("is-open")) {
      closeMenu();
      menuButton.focus();
    }
  });
  window.matchMedia("(min-width: 701px)").addEventListener?.("change", closeMenu);

  const filters = document.querySelector("[data-filters]");
  const choices = [...filters.querySelectorAll("button[data-filter]")];
  const allowed = new Set(choices.map(el => el.dataset.filter));
  const groups = [...document.querySelectorAll(".paper-group")];
  const countText = document.querySelector("[data-result-count]");
  const languageLinks = [...document.querySelectorAll("[data-language]")];
  for (const link of languageLinks) {
    const base = link.href;
    function syncLocale() {
      const target = new URL(base);
      const url = new URL(location.href);
      const status = url.searchParams.get("status");
      if (allowed.has(status) && status !== "all") target.searchParams.set("status", status);
      const visibleSection = nav.querySelector('[aria-current="location"]')?.dataset.nav;
      const scrolled = document.querySelector(".cover").getBoundingClientRect().bottom <= 85;
      target.hash = url.hash || (scrolled && visibleSection ? "#" + visibleSection : "");
      link.href = target.href;
    }
    link.addEventListener("focus", syncLocale);
    link.addEventListener("click", syncLocale);
    link.addEventListener("pointerenter", syncLocale);
  }
  function selectFilter(key, updateUrl) {
    const status = allowed.has(key) ? key : "all";
    let count = 0;
    for (const group of groups) {
      let groupCount = 0;
      for (const paper of group.querySelectorAll("[data-status]")) {
        const show = status === "all" || paper.dataset.status === status;
        paper.hidden = !show;
        if (show) groupCount++;
      }
      group.hidden = groupCount === 0;
      count += groupCount;
    }
    for (const button of choices) button.setAttribute("aria-pressed",String(button.dataset.filter === status));
    countText.textContent = countText.dataset.template.replace("{n}",String(count));
    if (updateUrl) {
      const url = new URL(window.location.href);
      if (status === "all") url.searchParams.delete("status"); else url.searchParams.set("status",status);
      window.history.replaceState(null,"",url);
    }
  }
  filters.hidden = false;
  choices.forEach(button => button.addEventListener("click", () => selectFilter(button.dataset.filter,true)));
  const initialFilter = new URL(window.location.href).searchParams.get("status");
  selectFilter(initialFilter, Boolean(initialFilter && !allowed.has(initialFilter)));
  window.addEventListener("popstate",() => selectFilter(new URL(window.location.href).searchParams.get("status"),false));

  const navItems = [...nav.querySelectorAll("[data-nav]")];
  const sections = navItems.map(a => document.getElementById(a.dataset.nav));
  let scheduled = false;
  function setCurrent() {
    const y = window.innerHeight * .26 + 30;
    let current = sections[0];
    for (const section of sections) if (section.getBoundingClientRect().top <= y) current = section;
    for (const a of navItems) {
      if (a.dataset.nav === current.id) a.setAttribute("aria-current","location");
      else a.removeAttribute("aria-current");
    }
    scheduled = false;
  }
  function scheduleCurrent() {
    if (!scheduled) { scheduled = true; requestAnimationFrame(setCurrent); }
  }
  window.addEventListener("scroll",scheduleCurrent,{passive:true});
  window.addEventListener("resize",scheduleCurrent);
  setCurrent();

  const viewer = document.querySelector(".figure-viewer");
  if (typeof viewer.showModal !== "function") return;
  const largeImage = viewer.querySelector(".viewer-image img");
  const closeButton = viewer.querySelector("[data-close]");
  let opener;
  for (const link of document.querySelectorAll("[data-figure]")) {
    link.addEventListener("click", event => {
      if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
      event.preventDefault();
      opener = link;
      const figure = link.closest("figure");
      const caption = figure.querySelector(".figure-caption").textContent;
      viewer.querySelector("#viewer-title").textContent = figure.querySelector(".figure-number").textContent;
      largeImage.alt = caption;
      largeImage.src = link.href;
      viewer.querySelector(".viewer-caption").textContent = caption;
      const credit = viewer.querySelector(".viewer-credit");
      credit.textContent = link.dataset.credit;
      if (link.dataset.license) {
        const license = document.createElement("a");
        license.href = link.dataset.license;
        license.target = "_blank";
        license.rel = "noopener noreferrer";
        license.textContent = link.dataset.credit + " ↗";
        credit.replaceChildren(license);
      }
      viewer.querySelector("[data-full]").href = link.href;
      viewer.querySelector("[data-source]").href = figure.querySelector(".figure-source").href;
      viewer.showModal();
      closeButton.focus({preventScroll:true});
    });
  }
  closeButton.addEventListener("click", () => viewer.close());
  viewer.addEventListener("click", event => {
    if (event.target !== viewer) return;
    const rect = viewer.getBoundingClientRect();
    if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) viewer.close();
  });
  viewer.addEventListener("close", () => {
    largeImage.removeAttribute("src");
    opener?.focus({preventScroll:true});
  });
})();
