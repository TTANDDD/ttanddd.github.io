// Scroll easing and restrained, one-time entrances for the reading sections.
(() => {
  "use strict";
  const preference = matchMedia("(prefers-reduced-motion: reduce)");
  let scroller;
  let observer;

  function revealContent() {
    observer?.disconnect();
    document.querySelectorAll(".motion-enter").forEach(node => node.classList.remove("motion-enter"));
    if (preference.matches || !("IntersectionObserver" in window)) return;
    observer = new IntersectionObserver(entries => {
      for (const entry of entries) {
        if (entry.isIntersecting) {
          entry.target.classList.remove("motion-enter");
          observer.unobserve(entry.target);
        }
      }
    }, {threshold: 0, rootMargin: "0px 0px -24px 0px"});
    for (const node of document.querySelectorAll(".overview, .project, .paper, .background section")) {
      if (node.getBoundingClientRect().top < innerHeight) continue;
      node.classList.add("motion-enter");
      observer.observe(node);
    }
  }

  function configure() {
    scroller?.destroy();
    scroller = undefined;
    if (!preference.matches && window.Lenis) {
      scroller = new Lenis({
        autoRaf: true,
        lerp: 0.14,
        smoothWheel: true,
        syncTouch: false,
        anchors: {offset: -80},
        prevent: node => Boolean(node.closest?.(".figure-viewer, .nav.is-open"))
      });
    }
    revealContent();
  }

  configure();
  preference.addEventListener("change", configure);
  document.addEventListener("site:beforelocalechange", () => {
    scroller?.destroy();
    scroller = undefined;
  });
  document.addEventListener("site:localechange", revealContent);
  document.addEventListener("site:positionrestored", () => {
    configure();
  });
})();
