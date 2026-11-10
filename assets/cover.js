// A decorative wind field for the cover. The drawing pauses once the cover is off screen.
(() => {
  const canvas = document.querySelector(".flow");
  const context = canvas?.getContext("2d");
  if (!context) return;
  const cover = canvas.parentElement;
  const motion = matchMedia("(prefers-reduced-motion: reduce)");
  let width = 0, height = 0, gradient;
  let inView = true, frame = 0, previous = 0, elapsed = 0;

  function profile(x, line, group, phase) {
    const wave = Math.sin(x * 5.5 + phase * .12 + group * .7);
    const ripple = Math.sin(x * 9.8 - phase * .10 + line * 1.6 + group);
    const middle = .82 - .43 * x + .095 * wave + .025 * ripple;
    const spread = .048 + .135 * Math.pow(Math.sin(x * 4.8 - .3 + group * .65), 2);
    return height * (middle + (group ? -.23 : 0) + line * spread);
  }

  function draw() {
    context.clearRect(0, 0, width, height);
    const n = width < 600 ? 32 : 47;
    const step = Math.max(6, Math.ceil(width / 120));
    for (let group = 0; group < 2; group++) {
      for (let line = 0; line < n; line++) {
        const t = line / (n - 1) * 2 - 1;
        context.beginPath();
        for (let px = -step; px <= width + step; px += step) {
          const y = profile(px / width, t, group, elapsed);
          if (px === -step) context.moveTo(px, y);
          else context.lineTo(px, y);
        }
        context.strokeStyle = gradient;
        context.globalAlpha = (group ? .44 : .86) * (.48 + .49 * Math.sin((line / n) * Math.PI));
        context.lineWidth = line % 8 === 0 ? 1.1 : .72;
        context.stroke();
      }
    }
    // Small tracers drift on the same curves, with the centre kept quiet behind the profile.
    for (let i = 0; i < 25; i++) {
      const x = (i * .381966 + elapsed * (.006 + (i % 4) * .0018)) % 1;
      const edge = Math.min(1, Math.max(0, (Math.abs(x - .5) - .17) * 3.5));
      if (!edge) continue;
      const t = 2 * ((i * .618) % 1) - 1;
      context.globalAlpha = edge * (.35 + (i % 4) * .14);
      context.fillStyle = i % 5 === 0 ? "#e7caa0" : "#b1ebf1";
      context.beginPath();
      context.arc(x * width, profile(x, t, i % 2, elapsed), i % 5 === 0 ? 1.8 : 1.2, 0, 2 * Math.PI);
      context.fill();
    }
    context.globalAlpha = 1;
  }

  function tick(time) {
    if (!frame) return;
    if (!previous || time - previous >= 42) {
      elapsed += previous ? Math.min((time - previous) / 1000, .10) : 0;
      previous = time;
      draw();
    }
    frame = requestAnimationFrame(tick);
  }
  function updatePlayback() {
    if (frame) cancelAnimationFrame(frame);
    frame = previous = 0;
    if (inView && !document.hidden) {
      draw();
      if (!motion.matches) frame = requestAnimationFrame(tick);
    }
  }
  function resize() {
    const bounds = cover.getBoundingClientRect();
    width = Math.max(1, bounds.width);
    height = Math.max(1, bounds.height);
    const scale = Math.min(devicePixelRatio || 1, 1.6);
    canvas.width = Math.round(width * scale);
    canvas.height = Math.round(height * scale);
    context.setTransform(scale, 0, 0, scale, 0, 0);
    gradient = context.createLinearGradient(0, 0, width, 0);
    for (const [position, color] of [[0,"#68c5cd"],[.15,"#86c4d1"],[.36,"#6fa6bc48"],[.5,"#6899b21a"],[.66,"#90b8c05b"],[.86,"#8cb7c0"],[1,"#d2c19e"]]) {
      gradient.addColorStop(position, color);
    }
    updatePlayback();
  }
  resize();
  if ("ResizeObserver" in window) new ResizeObserver(resize).observe(cover);
  else window.addEventListener("resize", resize, {passive:true});
  if ("IntersectionObserver" in window) {
    new IntersectionObserver(([entry]) => {
      inView = entry.isIntersecting;
      updatePlayback();
    }).observe(cover);
  }
  document.addEventListener("visibilitychange", updatePlayback);
  motion.addEventListener?.("change", updatePlayback);
})();
