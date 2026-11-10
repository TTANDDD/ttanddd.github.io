(() => {
  "use strict";
  const root = document.documentElement;
  root.classList.add("js");
  const systemTheme = window.matchMedia("(prefers-color-scheme: dark)");
  let pageListeners;

  function savedTheme() {
    try { return localStorage.getItem("hq-theme"); } catch { return null; }
  }

  function bindPage() {
    pageListeners?.abort();
    pageListeners = new AbortController();
    const signal = pageListeners.signal;
    function on(target, name, listener, options = {}) {
      target.addEventListener?.(name, listener, {...options, signal});
    }

    const themeButton = document.querySelector("[data-theme-button]");
    function applyTheme(theme) {
      root.dataset.theme = theme;
      themeButton.setAttribute("aria-pressed", String(theme === "dark"));
      document.querySelector('meta[name="theme-color"]').content = theme === "dark" ? "#20241e" : "#faf8f2";
    }
    applyTheme(savedTheme() || root.dataset.theme || (systemTheme.matches ? "dark" : "light"));
    on(themeButton, "click", () => {
      const next = root.dataset.theme === "dark" ? "light" : "dark";
      applyTheme(next);
      try { localStorage.setItem("hq-theme", next); } catch {}
    });
    on(systemTheme, "change", () => {
      if (!savedTheme()) applyTheme(systemTheme.matches ? "dark" : "light");
    });

    const menuButton = document.querySelector(".menu");
    const nav = document.getElementById("nav");
    function closeMenu() {
      nav.classList.remove("is-open");
      menuButton.setAttribute("aria-expanded", "false");
    }
    on(menuButton, "click", () => {
      menuButton.setAttribute("aria-expanded", String(nav.classList.toggle("is-open")));
    });
    on(nav, "click", closeMenu);
    on(document, "click", event => {
      if (!event.target.closest(".topbar")) closeMenu();
    });
    on(document, "keydown", event => {
      if (event.key === "Escape" && nav.classList.contains("is-open")) {
        closeMenu();
        menuButton.focus();
      }
    });
    on(window.matchMedia("(min-width: 701px)"), "change", closeMenu);

    const filters = document.querySelector("[data-filters]");
    const choices = [...filters.querySelectorAll("button[data-filter]")];
    const allowed = new Set(choices.map(button => button.dataset.filter));
    const groups = [...document.querySelectorAll(".paper-group")];
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
      for (const button of choices) button.setAttribute("aria-pressed", String(button.dataset.filter === status));
      countText.textContent = countText.dataset.template.replace("{n}", String(count));
      if (updateUrl) {
        const url = new URL(location.href);
        if (status === "all") url.searchParams.delete("status");
        else url.searchParams.set("status", status);
        history.replaceState(history.state, "", url);
      }
    }
    filters.hidden = false;
    choices.forEach(button => on(button, "click", () => selectFilter(button.dataset.filter, true)));
    const initialFilter = new URL(location.href).searchParams.get("status");
    selectFilter(initialFilter, Boolean(initialFilter && !allowed.has(initialFilter)));
    on(window, "popstate", () => selectFilter(new URL(location.href).searchParams.get("status"), false));

    const navItems = [...nav.querySelectorAll("[data-nav]")];
    const sections = navItems.map(a => document.getElementById(a.dataset.nav));
    let scheduled = false;
    function setCurrent() {
      if (signal.aborted) return;
      const y = window.innerHeight * .26 + 30;
      let current = sections[0];
      for (const section of sections) if (section.getBoundingClientRect().top <= y) current = section;
      for (const a of navItems) {
        if (a.dataset.nav === current.id) a.setAttribute("aria-current", "location");
        else a.removeAttribute("aria-current");
      }
      scheduled = false;
    }
    function scheduleCurrent() {
      if (!scheduled) { scheduled = true; requestAnimationFrame(setCurrent); }
    }
    on(window, "scroll", scheduleCurrent, {passive:true});
    on(window, "resize", scheduleCurrent);
    setCurrent();

    const viewer = document.querySelector(".figure-viewer");
    if (typeof viewer.showModal !== "function") return;
    const viewerImage = viewer.querySelector(".viewer-image");
    const closeButton = viewer.querySelector("[data-close]");
    let opener;
    for (const link of document.querySelectorAll("[data-figure]")) {
      on(link, "click", event => {
        if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
        event.preventDefault();
        opener = link;
        const figure = link.closest("figure");
        const caption = figure.querySelector(".figure-caption").textContent;
        viewer.querySelector("#viewer-title").textContent = figure.querySelector(".figure-number").textContent;
        const frame = link.querySelector(".figure-frame").cloneNode(true);
        frame.querySelector("img").loading = "eager";
        viewer.style.setProperty("--figure-ratio", figure.style.getPropertyValue("--figure-ratio"));
        viewerImage.replaceChildren(frame);
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
    on(closeButton, "click", () => viewer.close());
    on(viewer, "click", event => {
      if (event.target !== viewer) return;
      const rect = viewer.getBoundingClientRect();
      if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) viewer.close();
    });
    on(viewer, "close", () => {
      viewerImage.replaceChildren();
      opener?.focus({preventScroll:true});
    });
  }

  bindPage();
  document.addEventListener("site:localechange", bindPage);
})();
