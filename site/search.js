(() => {
  "use strict";

  const form = document.querySelector("#search-form");
  const input = document.querySelector("#search");
  const clear = document.querySelector("#clear-search");
  const shortcut = document.querySelector("#search-shortcut");
  const status = document.querySelector("#results-count");
  const empty = document.querySelector("#empty-state");
  const emptyMessage = document.querySelector("#empty-message");
  const menu = document.querySelector("#category-menu");
  const narrow = window.matchMedia("(max-width: 760px)");
  const normalize = (text) => text.normalize("NFKD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
  const plural = (count, noun) => `${count} ${count === 1 ? noun : noun === "category" ? "categories" : `${noun}s`}`;
  const sections = [...document.querySelectorAll(".tool-section")].map((section) => ({
    element: section,
    resource: section.dataset.kind === "resource",
    nav: [...document.querySelectorAll(".category-link")].find((link) => link.dataset.category === section.id),
    entries: [...section.querySelectorAll(".tool-entry")].map((entry) => ({
      element: entry,
      text: normalize(entry.dataset.search),
    })),
  }));

  function filter(updateUrl = true) {
    const query = input.value.trim();
    const tokens = normalize(query).split(/\s+/).filter(Boolean);
    let toolCount = 0;
    let resourceCount = 0;
    let categoryCount = 0;

    for (const section of sections) {
      let visible = 0;
      for (const entry of section.entries) {
        entry.element.hidden = !tokens.every((token) => entry.text.includes(token));
        if (!entry.element.hidden) visible++;
      }
      section.element.hidden = visible === 0;
      section.nav.hidden = visible === 0;
      section.nav.querySelector(".category-count").textContent = visible;
      section.element.querySelector(".section-count").textContent = plural(visible, section.resource ? "resource" : "tool");
      if (section.resource) resourceCount += visible;
      else {
        toolCount += visible;
        if (visible) categoryCount++;
      }
      if (!visible) section.nav.removeAttribute("aria-current");
    }

    if (query) {
      const resources = resourceCount ? ` and ${plural(resourceCount, "resource")}` : "";
      status.textContent = `${plural(toolCount, "tool")}${resources} found`;
    } else {
      status.textContent = `${plural(toolCount, "tool")} across ${plural(categoryCount, "category")}`;
    }
    const noMatches = toolCount + resourceCount === 0;
    empty.hidden = !noMatches;
    if (noMatches) emptyMessage.textContent = `No results for “${query}”. Try a product name, category or task.`;
    clear.hidden = !query;
    shortcut.hidden = Boolean(query);

    if (updateUrl) {
      const url = new URL(window.location.href);
      if (query) url.searchParams.set("q", query);
      else url.searchParams.delete("q");
      window.history.replaceState(null, "", `${url.pathname}${url.search}${url.hash}`);
    }
  }

  function reset() {
    input.value = "";
    filter();
    input.focus();
  }

  form.hidden = false;
  menu.open = !narrow.matches;
  narrow.addEventListener("change", (event) => { menu.open = !event.matches; });
  input.value = new URL(window.location.href).searchParams.get("q") || "";
  filter(false);
  input.addEventListener("input", () => filter());
  form.addEventListener("submit", (event) => { event.preventDefault(); filter(); });
  clear.addEventListener("click", reset);
  document.querySelector("#reset-search").addEventListener("click", reset);
  input.addEventListener("keydown", (event) => {
    if (event.key === "Escape") { event.preventDefault(); reset(); }
  });
  document.addEventListener("keydown", (event) => {
    if (event.key !== "/" || event.metaKey || event.ctrlKey || event.altKey || event.isComposing) return;
    if (event.target.closest("input, textarea, select, [contenteditable=true], [role=textbox]")) return;
    event.preventDefault();
    input.focus();
  });
  window.addEventListener("popstate", () => {
    input.value = new URL(window.location.href).searchParams.get("q") || "";
    filter(false);
  });
  for (const section of sections) {
    section.nav.addEventListener("click", () => {
      for (const other of sections) other.nav.removeAttribute("aria-current");
      section.nav.setAttribute("aria-current", "location");
      if (narrow.matches) menu.open = false;
    });
  }

  if ("IntersectionObserver" in window) {
    const observer = new IntersectionObserver((entries) => {
      const visible = entries.filter((entry) => entry.isIntersecting && !entry.target.hidden);
      if (!visible.length) return;
      const current = sections.find((section) => section.element === visible[0].target);
      for (const section of sections) section.nav.removeAttribute("aria-current");
      current.nav.setAttribute("aria-current", "location");
    }, { rootMargin: "-210px 0px -50% 0px", threshold: 0 });
    for (const section of sections) observer.observe(section.element);
  }
})();
