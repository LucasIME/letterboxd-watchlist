const grid = document.getElementById("grid");
const empty = document.getElementById("empty");
const countEl = document.getElementById("count");
const statusEl = document.getElementById("status");
const searchEl = document.getElementById("search");
const serviceEl = document.getElementById("service");
const regionEl = document.getElementById("region");
const refreshBtn = document.getElementById("refresh");
const progressWrap = document.getElementById("progress-wrap");
const progressBar = document.getElementById("progress-bar");

const tmdbOk = document.body.dataset.tmdbOk === "yes";
const defaultRegion = document.body.dataset.defaultRegion || "GB";
const defaultService = document.body.dataset.defaultService || "";
let pollTimer = null;

function posterUrl(path) {
  return path ? `https://image.tmdb.org/t/p/w342${path}` : null;
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

// Name of the currently selected service (for the badge), or null.
function selectedServiceName() {
  const opt = serviceEl.selectedOptions[0];
  if (!opt || opt.value === "__all__" || opt.value === "any") return null;
  return opt.textContent;
}

function render(films) {
  grid.innerHTML = "";
  if (!films.length) {
    empty.textContent = tmdbOk
      ? "No films match. Try a different service/region, or hit Refresh if you haven't loaded data yet."
      : "TMDB credentials aren't set. Add them to .env, then restart and Refresh.";
    empty.classList.remove("hidden");
    return;
  }
  empty.classList.add("hidden");

  const svcName = selectedServiceName();
  const frag = document.createDocumentFragment();
  for (const f of films) {
    const card = document.createElement("div");
    card.className = "card";

    const url = posterUrl(f.poster_path);
    const lbUrl = `https://letterboxd.com/film/${f.slug}/`;
    const provNames = (f.providers || []).map((p) => p.name);
    const highlight = svcName && provNames.includes(svcName);

    card.innerHTML = `
      <a href="${lbUrl}" target="_blank" rel="noopener">
        ${highlight ? `<span class="badge">${escapeHtml(svcName.toUpperCase())}</span>` : ""}
        <div class="poster" ${url ? `style="background-image:url('${url}')"` : ""}>
          ${url ? "" : escapeHtml(f.title || f.slug)}
        </div>
        <div class="title">${escapeHtml(f.title || f.slug)}</div>
        <div class="year">${f.year || ""}</div>
      </a>
      ${provNames.length ? `<div class="providers">${escapeHtml(provNames.join(" · "))}</div>` : ""}
    `;
    frag.appendChild(card);
  }
  grid.appendChild(frag);
}

function populateRegions(regions) {
  const cur = regionEl.value || defaultRegion;
  const avail = regions.filter((r) => r.available);
  const other = regions.filter((r) => !r.available);

  const optionHtml = (r) =>
    `<option value="${r.code}">${escapeHtml(r.name)} (${r.code})</option>`;

  regionEl.innerHTML = `
    ${avail.length ? `<optgroup label="Films available here">${avail.map(optionHtml).join("")}</optgroup>` : ""}
    ${other.length ? `<optgroup label="Other regions">${other.map(optionHtml).join("")}</optgroup>` : ""}
  `;
  regionEl.value = regions.some((r) => r.code === cur) ? cur : defaultRegion;
}

function populateServices(services, preferValue) {
  const want = preferValue ?? serviceEl.value;
  const opts = [
    `<option value="__all__">All films</option>`,
    `<option value="any">Any service</option>`,
    ...services.map(
      (s) => `<option value="${s.id}">${escapeHtml(s.name)}</option>`
    ),
  ];
  serviceEl.innerHTML = opts.join("");
  // Keep prior choice if still offered, else fall back to default service, else "All".
  if ([...serviceEl.options].some((o) => o.value === String(want))) {
    serviceEl.value = String(want);
  } else if ([...serviceEl.options].some((o) => o.value === String(defaultService))) {
    serviceEl.value = String(defaultService);
  } else {
    serviceEl.value = "__all__";
  }
}

async function loadOptions(preferService) {
  const region = regionEl.value || defaultRegion;
  const res = await fetch(`/api/options?region=${encodeURIComponent(region)}`);
  const data = await res.json();
  if (!regionEl.options.length) populateRegions(data.regions);
  populateServices(data.services, preferService);
}

async function loadFilms() {
  const params = new URLSearchParams();
  params.set("region", regionEl.value || defaultRegion);
  const svc = serviceEl.value;
  if (svc && svc !== "__all__") params.set("service", svc);
  const q = searchEl.value.trim();
  if (q) params.set("q", q);

  const res = await fetch(`/api/films?${params}`);
  const data = await res.json();
  render(data.films);
  const c = data.counts;
  countEl.textContent = `${c.matched} shown · ${c.enriched}/${c.total} checked`;
}

async function poll() {
  const res = await fetch("/api/status");
  const s = await res.json();
  statusEl.classList.toggle("error", s.phase === "error");

  if (s.running) {
    progressWrap.classList.remove("hidden");
    const pct = s.total ? Math.round((s.done / s.total) * 100) : 0;
    progressBar.style.width = `${pct}%`;
    statusEl.textContent = s.total ? `${s.message} (${s.done}/${s.total})` : s.message;
    refreshBtn.disabled = true;
  } else {
    refreshBtn.disabled = false;
    if (pollTimer) {
      clearInterval(pollTimer);
      pollTimer = null;
      progressBar.style.width = "100%";
      setTimeout(() => progressWrap.classList.add("hidden"), 600);
      statusEl.textContent = s.message || "";
      await loadOptions();
      await loadFilms();
      return;
    }
    statusEl.textContent = s.phase === "error" ? s.message : "";
  }
  await loadFilms();
}

async function startRefresh(force) {
  const res = await fetch(`/api/refresh${force ? "?force=1" : ""}`, { method: "POST" });
  const data = await res.json();
  if (data.error) {
    statusEl.classList.add("error");
    statusEl.textContent = data.error;
    return;
  }
  if (!pollTimer) pollTimer = setInterval(poll, 1000);
  poll();
}

refreshBtn.addEventListener("click", () => startRefresh(false));
serviceEl.addEventListener("change", loadFilms);
regionEl.addEventListener("change", async () => {
  // Services depend on region — repopulate them (keeping the choice if possible).
  await loadOptions(serviceEl.value);
  await loadFilms();
});

let searchDebounce;
searchEl.addEventListener("input", () => {
  clearTimeout(searchDebounce);
  searchDebounce = setTimeout(loadFilms, 200);
});

(async function init() {
  regionEl.value = defaultRegion; // seed before first options fetch
  await loadOptions(defaultService);
  await loadFilms();

  const res = await fetch("/api/status");
  const s = await res.json();
  if (s.running) {
    if (!pollTimer) pollTimer = setInterval(poll, 1000);
  } else if (tmdbOk && s.counts.enriched === 0) {
    startRefresh(false);
  }
})();
