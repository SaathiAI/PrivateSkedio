const appUrl =
  window.location.hostname === "localhost" ||
  window.location.hostname === "127.0.0.1"
    ? "http://localhost:5173/"
    : "https://app.skedio.ai/";

document.querySelectorAll(".app-link").forEach((link) => {
  link.setAttribute("href", appUrl);
});

const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

if (!prefersReducedMotion.matches) {
  document.documentElement.classList.add("js-motion");

  const heroVisual = document.querySelector(".hero-visual");
  const atmosphere = document.querySelector(".hero-atmosphere");

  if (heroVisual && atmosphere) {
    for (let index = 0; index < 18; index += 1) {
      const star = document.createElement("span");
      star.className = "hero-star";
      star.style.left = `${6 + Math.random() * 88}%`;
      star.style.top = `${4 + Math.random() * 88}%`;
      star.style.setProperty("--twinkle-delay", `${Math.random() * 4.2}s`);
      star.style.setProperty("--twinkle-duration", `${3.4 + Math.random() * 3.2}s`);
      star.style.setProperty("--star-size", `${1.5 + Math.random() * 3.2}px`);
      atmosphere.appendChild(star);
    }

    const updateParallax = (event) => {
      const rect = heroVisual.getBoundingClientRect();
      const relativeX = (event.clientX - rect.left) / rect.width - 0.5;
      const relativeY = (event.clientY - rect.top) / rect.height - 0.5;
      heroVisual.style.setProperty("--hero-x", `${relativeX * 22}px`);
      heroVisual.style.setProperty("--hero-y", `${relativeY * 18}px`);
    };

    const resetParallax = () => {
      heroVisual.style.setProperty("--hero-x", "0px");
      heroVisual.style.setProperty("--hero-y", "0px");
    };

    heroVisual.addEventListener("pointermove", updateParallax);
    heroVisual.addEventListener("pointerleave", resetParallax);
  }

  const revealTargets = [
    ".hero-copy > *",
    ".hero-window",
    ".hero-satellite",
    ".feature-card",
    ".window-card",
    ".product-points article",
    ".workflow-card",
    ".cta-panel",
    ".footer-brand",
    ".footer-links a",
  ]
    .flatMap((selector) => [...document.querySelectorAll(selector)]);

  revealTargets.forEach((element, index) => {
    element.setAttribute("data-reveal", "");
    element.style.setProperty("--reveal-delay", String(index % 6));
  });

  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        entry.target.classList.add("is-visible");
        observer.unobserve(entry.target);
      });
    },
    {
      threshold: 0.16,
      rootMargin: "0px 0px -8% 0px",
    },
  );

  revealTargets.forEach((element) => observer.observe(element));
}
