const grid = document.getElementById("grid");
const empty = document.getElementById("empty");
const countEl = document.getElementById("count");
const statusEl = document.getElementById("status");
const searchEl = document.getElementById("search");
const mubiEl = document.getElementById("mubi-only");
const refreshBtn = document.getElementById("refresh");
const progressWrap = document.getElementById("progress-wrap");
const progressBar = document.getElementById("progress-bar");

const tmdbOk = document.body.dataset.tmdbOk === "yes";
let pollTimer = null;

function posterUrl(path) {
  return path ? `https://image.tmdb.org/t/p/w342${path}` : null;
}

function providerNames(providers) {
  const flat = (providers.flatrate || []).concat(providers.free || []);
  return flat.map((p) => p.name);
}

function render(films) {
  grid.innerHTML = "";
  if (!films.length) {
    empty.textContent = tmdbOk
      ? "No films match. Hit Refresh if you haven't loaded availability yet."
      : "TMDB credentials aren't set. Add them to .env, then restart and Refresh.";
    empty.classList.remove("hidden");
    return;
  }
  empty.classList.add("hidden");

  const frag = document.createDocumentFragment();
  for (const f of films) {
    const card = document.createElement("div");
    card.className = "card";

    const url = posterUrl(f.poster_path);
    const lbUrl = `https://letterboxd.com/film/${f.slug}/`;
    const provs = providerNames(f.providers || {});

    card.innerHTML = `
      <a href="${lbUrl}" target="_blank" rel="noopener">
        ${f.on_mubi ? '<span class="badge">MUBI</span>' : ""}
        <div class="poster" ${url ? `style="background-image:url('${url}')"` : ""}>
          ${url ? "" : escapeHtml(f.title || f.slug)}
        </div>
        <div class="title">${escapeHtml(f.title || f.slug)}</div>
        <div class="year">${f.year || ""}</div>
      </a>
      ${provs.length ? `<div class="providers">${escapeHtml(provs.join(" · "))}</div>` : ""}
    `;
    frag.appendChild(card);
  }
  grid.appendChild(frag);
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

async function loadFilms() {
  const params = new URLSearchParams();
  if (mubiEl.checked) params.set("mubi", "1");
  const q = searchEl.value.trim();
  if (q) params.set("q", q);

  const res = await fetch(`/api/films?${params}`);
  const data = await res.json();
  render(data.films);
  const c = data.counts;
  countEl.textContent =
    `${data.films.length} shown · ${c.on_mubi} on Mubi · ${c.enriched}/${c.total} checked`;
}

async function poll() {
  const res = await fetch("/api/status");
  const s = await res.json();

  statusEl.classList.toggle("error", s.phase === "error");

  if (s.running) {
    progressWrap.classList.remove("hidden");
    const pct = s.total ? Math.round((s.done / s.total) * 100) : 0;
    progressBar.style.width = `${pct}%`;
    statusEl.textContent = s.total
      ? `${s.message} (${s.done}/${s.total})`
      : s.message;
    refreshBtn.disabled = true;
  } else {
    refreshBtn.disabled = false;
    if (pollTimer) {
      // Just finished — final reload.
      clearInterval(pollTimer);
      pollTimer = null;
      progressBar.style.width = "100%";
      setTimeout(() => progressWrap.classList.add("hidden"), 600);
      statusEl.textContent = s.message || "";
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
mubiEl.addEventListener("change", loadFilms);

let searchDebounce;
searchEl.addEventListener("input", () => {
  clearTimeout(searchDebounce);
  searchDebounce = setTimeout(loadFilms, 200);
});

// Initial load. If nothing has been enriched yet, kick off a refresh automatically.
(async function init() {
  await loadFilms();
  const res = await fetch("/api/status");
  const s = await res.json();
  if (s.running) {
    if (!pollTimer) pollTimer = setInterval(poll, 1000);
  } else if (tmdbOk && s.counts.enriched === 0) {
    startRefresh(false);
  }
})();
