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
  const empty = document.querySelector("[data-empty]");
  const countText = document.querySelector("[data-result-count]");
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
    empty.hidden = count !== 0;
    countText.textContent = countText.dataset.template.replace("{n}",String(count));
    if (updateUrl) {
      const url = new URL(window.location.href);
      if (status === "all") url.searchParams.delete("status"); else url.searchParams.set("status",status);
      window.history.replaceState(null,"",url);
    }
  }
  filters.hidden = false;
  choices.forEach(button => button.addEventListener("click", () => selectFilter(button.dataset.filter,true)));
  document.querySelector("[data-reset]").addEventListener("click", () => {
    selectFilter("all",true);
    choices[0].focus();
  });
  selectFilter(new URL(window.location.href).searchParams.get("status"),false);
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
})();
