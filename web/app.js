const grid = document.querySelector("#beachGrid");
const summary = document.querySelector("#summary");
const updatedAt = document.querySelector("#updatedAt");
const cityFilter = document.querySelector("#cityFilter");
const refreshButton = document.querySelector("#refreshButton");
let expandedBeachId = null;
let selectedCity = "all";
let isRefreshing = false;

const fallbackData = {
  generated_at: new Date().toISOString(),
  beaches: []
};
let currentData = fallbackData;

function normalizeCity(city) {
  return String(city || "").trim();
}

function cityFilterOptions(beaches) {
  const cities = [...new Set(beaches.map((beach) => normalizeCity(beach.city)).filter(Boolean))];
  return ["all", ...cities.sort((a, b) => a.localeCompare(b, "pt-BR"))];
}

function cityFilterLabel(city) {
  if (city === "all") {
    return "Todos";
  }

  return city === "Vitoria" ? "Vitória" : city;
}

function displayCity(city) {
  return city === "Vitoria" ? "Vitória" : city;
}

function filteredBeaches(beaches) {
  if (selectedCity === "all") {
    return beaches;
  }

  return beaches.filter((beach) => normalizeCity(beach.city) === selectedCity);
}

function classificationClass(classification) {
  return classification.toLowerCase().normalize("NFD").replace(/\p{Diacritic}/gu, "");
}

function componentBar(label, value) {
  return `
    <div class="metric">
      <span>${label}</span>
      <strong>${Math.round(value)}</strong>
      <div class="bar"><i style="width: ${Math.max(0, Math.min(100, value))}%"></i></div>
    </div>
  `;
}

function formatPercent(value) {
  return `${Math.round(Number(value) || 0)}%`;
}

function weatherWarnings(signals) {
  if (Array.isArray(signals.weather_warnings)) {
    return signals.weather_warnings;
  }

  const probability = Number(signals.precipitation_probability_percent) || 0;
  if (probability >= 60) {
    return [`Alta chance de chuva: ${formatPercent(probability)}`];
  }
  if (probability >= 35) {
    return [`Chance moderada de chuva: ${formatPercent(probability)}`];
  }
  return [];
}

function weatherAlert(signals) {
  const warnings = weatherWarnings(signals);
  if (!warnings.length) {
    return "";
  }

  return `<div class="weather-alert">${warnings.map((warning) => `<span>${warning}</span>`).join("")}</div>`;
}

function bathingSummary(signals) {
  if (!signals.bathing_points_total) {
    return "Sem dado oficial";
  }

  return `${signals.bathing_points_proper}/${signals.bathing_points_total} pontos próprios`;
}

function bathingPenaltyText(signals) {
  const penalty = Number(signals.bathing_index_penalty) || 0;
  if (penalty <= 0) {
    return "Somente sinalização";
  }

  return `Desconto no índice: -${formatNumber(penalty)}`;
}

function bathingPanel(signals) {
  const total = Number(signals.bathing_points_total) || 0;
  const severity = signals.bathing_severity || "unknown";

  return `
    <section class="bathing-panel ${severity}">
      <div>
        <span>Balneabilidade</span>
        <strong>${signals.bathing_status}</strong>
      </div>
      <div class="bathing-score">
        <strong>${total ? bathingSummary(signals) : "Fonte sem pontos publicados"}</strong>
      </div>
    </section>
  `;
}

function formatNumber(value, digits = 1) {
  const number = Number(value);
  return Number.isFinite(number) ? number.toFixed(digits) : "0.0";
}

function detailItem(label, value) {
  return `
    <div class="detail-item">
      <span>${label}</span>
      <strong>${value}</strong>
    </div>
  `;
}

function statusClass(status) {
  return String(status || "sem dado").toLowerCase().normalize("NFD").replace(/\p{Diacritic}/gu, "").replace(/\s+/g, "-");
}

function bathingPointsList(points) {
  if (!Array.isArray(points) || !points.length) {
    return `<p class="empty-detail">Não há pontos oficiais publicados para esta praia nas fontes automatizadas.</p>`;
  }

  return `
    <div class="bathing-counts">
      <span>${points.filter((point) => point.status === "Próprio").length} próprios</span>
      <span>${points.filter((point) => point.status === "Impróprio").length} impróprios</span>
      <span>${points.filter((point) => point.status === "Interditado").length} interditados</span>
    </div>
    <div class="bathing-points">
      ${points.map((point) => `
        <article class="bathing-point">
          <div>
            <strong>${point.point_id || "Ponto"}</strong>
            <span>${point.location || "Local não informado"}</span>
            ${point.subdivision ? `<small>${point.subdivision}</small>` : ""}
            ${point.valid_until ? `<small>Validade/referência: ${point.valid_until}</small>` : ""}
            ${point.source ? `<a href="${point.source}" target="_blank" rel="noreferrer">Fonte</a>` : ""}
          </div>
          <mark class="status ${statusClass(point.status)}">${point.status}</mark>
        </article>
      `).join("")}
    </div>
  `;
}

function cardDetails(beach) {
  const signals = beach.signals;
  const components = beach.components;
  const location = [beach.neighborhood, displayCity(beach.city)].filter(Boolean).join(" - ");

  return `
    <section class="details" id="details-${beach.id}" aria-label="Detalhes de ${beach.name}">
    
    <div class="detail-group">
    <h3>Clima e mar</h3>
    <div class="detail-list">
    ${detailItem("Temperatura", `${formatNumber(signals.temperature_c)} °C`)}
    ${detailItem("Chuva agora", `${formatNumber(signals.precipitation_mm)} mm`)}
    ${detailItem("Chance de chuva nas prox. 5 horas", formatPercent(signals.precipitation_probability_percent))}
    ${detailItem("Vento", `${formatNumber(signals.wind_kmh)} km/h`)}
    ${detailItem("UV", formatNumber(signals.uv_index))}
    ${detailItem("Ondas", `${formatNumber(signals.wave_height_m)} m`)}
    </div>
    </div>
    
    <div class="detail-group">
      <h3>Índice</h3>
      <div class="detail-list">
        ${detailItem("Sentimento", formatNumber(components.sentiment))}
        ${detailItem("Avaliações", formatNumber(components.ratings))}
        ${detailItem("Percepção pública", formatNumber(components.public_perception))}
        ${detailItem("Clima", formatNumber(components.weather))}
      </div>
    </div>

      <div class="detail-group">
        <h3>Sinais</h3>
        <div class="detail-list">
          ${detailItem("Textos analisados", signals.posts_analyzed)}
          ${detailItem("Termos positivos", signals.positive_terms)}
          ${detailItem("Termos negativos", signals.negative_terms)}
          ${detailItem("Local", location)}
          ${detailItem("Latitude", formatNumber(beach.coordinates.latitude, 4))}
          ${detailItem("Longitude", formatNumber(beach.coordinates.longitude, 4))}
        </div>
      </div>

      <div class="detail-group">
        <h3>Pontos de balneabilidade</h3>
        ${bathingPointsList(signals.bathing_points)}
      </div>
    </section>
  `;
}

function render(data) {
  currentData = data;
  const allBeaches = data.beaches || [];
  const options = cityFilterOptions(allBeaches);
  if (!options.includes(selectedCity)) {
    selectedCity = "all";
  }

  const beaches = filteredBeaches(allBeaches);
  const best = beaches[0];
  const average = beaches.reduce((sum, beach) => sum + beach.index, 0) / Math.max(1, beaches.length);

  updatedAt.textContent = `Gerado em ${new Intl.DateTimeFormat("pt-BR", {
    dateStyle: "short",
    timeStyle: "short"
  }).format(new Date(data.generated_at))}`;

  cityFilter.innerHTML = options.map((city) => `
    <button
      type="button"
      class="${city === selectedCity ? "active" : ""}"
      data-city="${city}"
      aria-pressed="${city === selectedCity}"
    >
      ${cityFilterLabel(city)}
    </button>
  `).join("");

  summary.innerHTML = `
    <article>
      <span>Melhor índice</span>
      <strong>${best ? best.name : "Sem dados"}</strong>
      <small>${best ? `${best.index} pontos` : "Gere data/latest_index.json"}</small>
    </article>
    <article>
      <span>Média geral</span>
      <strong>${average.toFixed(1)}</strong>
      <small>escala de 0 a 100</small>
    </article>
    <article>
      <span>Praias monitoradas</span>
      <strong>${beaches.length}</strong>
      <small>${selectedCity === "all" ? "Vitória, Vila Velha e Serra" : selectedCity}</small>
    </article>
  `;

  grid.innerHTML = beaches.map((beach) => {
    const isExpanded = beach.id === expandedBeachId;

    return `
    <article class="card ${isExpanded ? "expanded" : ""}" data-beach-id="${beach.id}" tabindex="0" aria-expanded="${isExpanded}" aria-controls="details-${beach.id}">
      <header>
        <div>
          <h2>${beach.name}</h2>
          <p>${[beach.neighborhood, displayCity(beach.city)].filter(Boolean).join(" - ")}</p>
        </div>
        <span class="badge ${classificationClass(beach.classification)}">${beach.classification}</span>
      </header>

      <div class="score">
        <strong>${beach.index}</strong>
        <span>/100</span>
      </div>

      <div class="metrics">
        ${componentBar("Percepção pública", beach.components.public_perception)}
        ${componentBar("Clima", beach.components.weather)}
      </div>

      ${weatherAlert(beach.signals)}
      ${bathingPanel(beach.signals)}

      <footer>
        <span>${beach.signals.posts_analyzed} textos</span>
        <span>${beach.signals.temperature_c}°C</span>
        <span>Chance de chuva: ${formatPercent(beach.signals.precipitation_probability_percent)}</span>
        <span>${beach.signals.wind_kmh} km/h</span>
      </footer>

      <button class="details-toggle" type="button" aria-expanded="${isExpanded}" aria-controls="details-${beach.id}">
        ${isExpanded ? "Ocultar detalhes" : "Ver detalhes"}
      </button>

      ${isExpanded ? cardDetails(beach) : ""}
    </article>
  `;
  }).join("");
}

async function loadLatestIndex() {
  const response = await fetch(`../data/latest_index.json?ts=${Date.now()}`, {
    cache: "no-store"
  });

  if (!response.ok) {
    return fallbackData;
  }

  return response.json();
}

function setRefreshState(refreshing, message = "") {
  isRefreshing = refreshing;
  refreshButton.disabled = refreshing;
  refreshButton.textContent = refreshing ? "Atualizando..." : "Atualizar";
}

async function refreshIndex() {
  if (isRefreshing) {
    return;
  }

  setRefreshState(true, "Atualizando dados e recalculando o índice...");

  try {
    const response = await fetch("../api/regenerate", {
      method: "POST"
    });

    if (!response.ok) {
      throw new Error(`Falha ao atualizar índice (${response.status})`);
    }

    const result = await response.json();
    const data = await loadLatestIndex();
    render(data);
    setRefreshState(false, result.message || "Índice atualizado com sucesso.");
  } catch (error) {
    console.error(error);
    setRefreshState(false, "Não foi possível atualizar agora.");
  }
}

refreshButton.addEventListener("click", refreshIndex);

loadLatestIndex()
  .then(render)
  .catch(() => render(fallbackData));

cityFilter.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-city]");
  if (!button) {
    return;
  }

  selectedCity = button.dataset.city;
  expandedBeachId = null;
  render(currentData);
});

grid.addEventListener("click", (event) => {
  if (event.target.closest(".details")) {
    return;
  }

  const card = event.target.closest(".card");
  if (!card) {
    return;
  }

  expandedBeachId = expandedBeachId === card.dataset.beachId ? null : card.dataset.beachId;
  render(currentData);
});

grid.addEventListener("keydown", (event) => {
  if (event.key !== "Enter" && event.key !== " ") {
    return;
  }

  const card = event.target.closest(".card");
  if (!card) {
    return;
  }

  event.preventDefault();
  card.click();
});
