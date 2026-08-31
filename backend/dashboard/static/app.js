const FILTERS = ["period", "category", "brand", "product", "retailer", "region", "lever"];
const FILTER_LABELS = {
  period: "Period",
  category: "Category",
  brand: "Brand",
  product: "Product / SKU",
  retailer: "Retailer",
  region: "Region",
  lever: "Commercial lever",
};
const KPI_ORDER = [
  ["sales_value", "Sales value"],
  ["sales_volume", "Sales volume"],
  ["sales_quantity", "Sales quantity"],
  ["price_per_kg", "Price/kg"],
  ["growth_pct", "Growth %"],
  ["addressable_value", "Addressable opportunity value"],
  ["addressable_volume", "Addressable opportunity volume"],
];

const state = {
  filters: {
    period: "all",
    category: "all",
    brand: "all",
    product: "all",
    retailer: "all",
    region: "all",
    lever: "all",
    top_n: 3,
  },
  view: "overview",
  data: null,
  sort: {},
};

const $ = (id) => document.getElementById(id);

function money(value) {
  if (value == null || Number.isNaN(value)) return "Not available";
  return `R${Number(value).toLocaleString("en-ZA", { maximumFractionDigits: 0 })}`;
}

function number(value, digits = 1) {
  if (value == null || Number.isNaN(value)) return "Not available";
  return Number(value).toLocaleString("en-ZA", { maximumFractionDigits: digits });
}

function metricText(metric, kind) {
  if (!metric || metric.available === false || metric.value == null || Number.isNaN(metric.value)) {
    return "Not available";
  }
  if (kind === "money") return money(metric.value);
  if (kind === "pct") return `${Number(metric.value).toFixed(1)}%`;
  return number(metric.value);
}

function rawText(value, kind) {
  if (value && typeof value === "object" && "available" in value) return metricText(value, kind);
  if (value == null || value === "" || Number.isNaN(value)) return "Not available";
  if (kind === "money") return money(value);
  if (kind === "pct") return `${Number(value).toFixed(1)}%`;
  if (typeof value === "number") return number(value);
  return String(value);
}

function queryString() {
  const params = new URLSearchParams();
  for (const key of FILTERS) {
    const value = state.filters[key];
    if (value && value !== "all") params.set(key, value);
  }
  params.set("top_n", String(state.filters.top_n));
  return params.toString();
}

async function load() {
  const response = await fetch(`/api/dashboard?${queryString()}`);
  if (!response.ok) throw new Error(`Dashboard API ${response.status}`);
  state.data = await response.json();
  render();
}

function optionLabel(value) {
  if (value === "all") return "All";
  return value;
}

function renderFilters() {
  const grid = $("filter-grid");
  const options = state.data.options;
  grid.innerHTML = FILTERS.map((key) => {
    const choices = options[key] || ["all"];
    const selected = state.filters[key];
    const html = choices
      .map((item) => `<option value="${escapeAttr(item)}" ${item === selected ? "selected" : ""}>${escapeHtml(optionLabel(item))}</option>`)
      .join("");
    return `<label>${FILTER_LABELS[key]}<select data-filter="${key}">${html}</select></label>`;
  }).join("");
  grid.querySelectorAll("select").forEach((node) => {
    node.addEventListener("change", () => onFilter(node.dataset.filter, node.value));
  });
  document.querySelectorAll(".topn-btn").forEach((btn) => {
    btn.classList.toggle("is-on", Number(btn.dataset.topn) === state.filters.top_n);
  });
}

function cascadeReset(changed) {
  const order = ["category", "brand", "product"];
  if (changed === "category") {
    state.filters.brand = "all";
    state.filters.product = "all";
  } else if (changed === "brand") {
    state.filters.product = "all";
  } else if (["retailer", "region", "period"].includes(changed)) {
    const options = state.data?.options || {};
    for (const key of ["brand", "product", "retailer", "region"]) {
      if (key === changed) continue;
      const allowed = options[key] || [];
      if (state.filters[key] !== "all" && !allowed.includes(state.filters[key])) {
        state.filters[key] = "all";
      }
    }
  }
  void order;
}

async function onFilter(key, value) {
  state.filters[key] = value;
  if (key === "category") {
    state.filters.brand = "all";
    state.filters.product = "all";
  } else if (key === "brand") {
    state.filters.product = "all";
  }
  await load();
  const options = state.data.options;
  for (const child of ["brand", "product", "retailer", "region"]) {
    if (state.filters[child] !== "all" && !(options[child] || []).includes(state.filters[child])) {
      state.filters[child] = "all";
    }
  }
}

function renderQuality() {
  const q = state.data.quality;
  const items = [
    ["Current period", q.current_period],
    ["POS weeks", q.pos_weeks],
    ["Price/promotion weeks", q.price_promotion_weeks ?? "Not available"],
    ["Social", q.social_status],
    ["Macro", q.macro_status],
    ["QA", q.qa_status || "Not available"],
    ["SKU identity", q.sku_identity],
  ];
  $("quality").innerHTML =
    items.map(([label, value]) => `<span class="chip"><strong>${escapeHtml(String(label))}:</strong> ${escapeHtml(String(value))}</span>`).join("") +
    `<span class="chip">${escapeHtml((q.limitations || [])[0] || "")}</span>`;
}

function renderStory() {
  const story = state.data.story;
  const labels = state.data.labels || {};
  $("story").innerHTML = `
    <p class="eyebrow">Executive story · ${escapeHtml(story.dominant_lever || "")}</p>
    <h2>${escapeHtml(story.headline || "")}</h2>
    <p>${escapeHtml(story.subheadline || "")}</p>
    <p><strong>Why this matters.</strong> ${escapeHtml(story.key_insight || "")}</p>
    <p><strong>Recommended stance.</strong> ${escapeHtml(story.commercial_implication || "")}</p>
    <p class="disclaimer">${escapeHtml(story.disclaimer || "")}</p>
    <div class="kinds">
      ${["FACT", "OBSERVATION", "OPPORTUNITY", "RECOMMENDATION"].map((kind) => `<span class="kind ${kind}">${kind} · ${escapeHtml(labels[kind] || "")}</span>`).join("")}
    </div>
  `;
}

function renderContext() {
  const macro = state.data.macro || {};
  const social = state.data.social || {};
  $("macro").innerHTML = macro.included
    ? `<h3>Macro context · supporting only</h3>
       <p><span class="kind OBSERVATION">OBSERVATION</span></p>
       <p><strong>POS story is not replaced by this signal.</strong></p>
       <p>${escapeHtml(macro.signal || "Not available")}</p>
       <p>${escapeHtml(macro.evidence || "")}</p>
       <p class="disclaimer">${escapeHtml(macro.disclaimer || "")}</p>`
    : `<h3>Macro context</h3><p>Not available</p>`;
  const connected = social.status && social.status !== "Not connected";
  $("social").innerHTML = connected
    ? `<h3>Social intelligence</h3>
       <p><span class="kind OBSERVATION">OBSERVATION</span> ${escapeHtml(social.status)}</p>
       <p>${escapeHtml(social.detail || "")}</p>
       <p class="disclaimer">Social context does not cause POS gaps and is not a sales driver.</p>`
    : `<h3>Social intelligence</h3><p><strong>Not connected</strong></p><p class="disclaimer">${escapeHtml(social.detail || "No live social source is connected.")}</p>`;
}

function renderKpis() {
  const kpis = state.data.kpis;
  const extra = kpis.price_per_volume
    ? `<article class="kpi"><div class="label">Price / volume unit</div><div class="value ${kpis.price_per_volume.available ? "" : "na"}">${escapeHtml(metricText(kpis.price_per_volume, "money"))}</div><div class="meta">FACT · not price/kg</div></article>`
    : "";
  $("kpis").innerHTML =
    KPI_ORDER.map(([key, label]) => {
      const metric = kpis[key] || { available: false };
      const kind = key.includes("value") || key === "price_per_kg" ? "money" : key.includes("pct") ? "pct" : "num";
      const text = metricText(metric, kind);
      return `<article class="kpi">
        <div class="label">${escapeHtml(label)}</div>
        <div class="value ${metric.available ? "" : "na"}">${escapeHtml(text)}</div>
        <div class="meta">${escapeHtml(metric.kind || "")} · ${escapeHtml(metric.unit || "")}</div>
      </article>`;
    }).join("") + extra;
}

function renderCharts() {
  const trends = state.data.trends || {};
  const note = trends.note || "";
  const specs = [
    ["sales_value", "Sales value", "money"],
    ["sales_volume", "Sales volume", "num"],
    ["price_per_volume", "Price / volume unit", "money"],
    ["growth_pct", "Growth %", "pct"],
  ];
  $("charts").innerHTML = specs
    .map(([key, title, kind]) => {
      const points = trends[key] || [];
      return `<article class="chart-card">
        <h3>${escapeHtml(title)}</h3>
        <div class="note">${escapeHtml(note)}</div>
        ${drawChart(points, kind)}
      </article>`;
    })
    .join("");
  $("charts").querySelectorAll("[data-tip]").forEach((node) => {
    node.addEventListener("mouseenter", showTip);
    node.addEventListener("mouseleave", hideTip);
    node.addEventListener("mousemove", moveTip);
  });
}

function drawChart(points, kind) {
  if (!points.length) return `<p class="empty">Not available</p>`;
  const values = points.map((item) => (item.available ? item.value : null)).filter((item) => item != null);
  if (!values.length) return `<p class="empty">Not available</p>`;
  const width = 320;
  const height = 160;
  const pad = 28;
  const min = Math.min(...values, 0);
  const max = Math.max(...values);
  const span = max - min || 1;
  const coords = points.map((item, index) => {
    const x = pad + (index * (width - pad * 2)) / Math.max(points.length - 1, 1);
    const y = item.available ? height - pad - ((item.value - min) / span) * (height - pad * 2) : null;
    return { ...item, x, y };
  });
  const line = coords
    .filter((item) => item.y != null)
    .map((item, index) => `${index === 0 ? "M" : "L"}${item.x.toFixed(1)},${item.y.toFixed(1)}`)
    .join(" ");
  const dots = coords
    .map((item) => {
      if (item.y == null) return "";
      const label = `${item.period}: ${rawText(item.value, kind)}`;
      return `<circle class="dot" cx="${item.x}" cy="${item.y}" r="4" data-tip="${escapeAttr(label)}"></circle>`;
    })
    .join("");
  const axis = points
    .map((item, index) => {
      const x = pad + (index * (width - pad * 2)) / Math.max(points.length - 1, 1);
      return `<text x="${x}" y="${height - 8}" text-anchor="middle" font-size="9" fill="#5c6e7a">${escapeHtml(item.period.slice(5))}</text>`;
    })
    .join("");
  return `<svg class="chart" viewBox="0 0 ${width} ${height}" role="img">${axis}<path class="line" d="${line}"></path>${dots}</svg>`;
}

function renderActions() {
  const actions = state.data.top_actions || [];
  $("rank-hint").textContent =
    state.filters.top_n === 3
      ? "Top 3 uses Commercial Brain action selection (diversity constraints preserved)."
      : "Top 10 uses Commercial Brain priority ranking. Scores are not recalculated here.";
  $("top-actions").innerHTML = actions
    .map(
      (item) => `<button type="button" class="action" data-id="${escapeAttr(item.opportunity_id || "")}">
        <div class="rank">Action ${item.rank} · ${escapeHtml(item.lever)} · <span class="confidence ${escapeAttr(item.confidence)}">${escapeHtml(item.confidence)}</span></div>
        <h3>${escapeHtml(item.headline)}</h3>
        <p>${escapeHtml(item.product)} · ${escapeHtml(item.retailer)} · ${escapeHtml(item.region)}</p>
        <p>Addressable ${money(item.addressable_value)} / ${number(item.addressable_volume)} units</p>
        <p class="disclaimer">${escapeHtml(item.why || "")}</p>
      </button>`
    )
    .join("") || `<p class="empty">No Commercial Brain actions match the current filters.</p>`;
  $("top-actions").querySelectorAll(".action").forEach((node) => {
    node.addEventListener("click", () => openDetail(node.dataset.id));
  });
}

function sortableHeader(key, label) {
  return `<th data-sort="${key}">${escapeHtml(label)}</th>`;
}

function sortRows(rows, key) {
  const dir = state.sort[key] === "asc" ? -1 : 1;
  state.sort[key] = dir === 1 ? "asc" : "desc";
  return [...rows].sort((a, b) => {
    const left = valueAt(a, key);
    const right = valueAt(b, key);
    if (left == null) return 1;
    if (right == null) return -1;
    if (typeof left === "number" && typeof right === "number") return (left - right) * dir;
    return String(left).localeCompare(String(right)) * dir;
  });
}

function valueAt(row, key) {
  const value = row[key];
  if (value && typeof value === "object" && "value" in value) return value.available ? value.value : null;
  return value;
}

function renderOppTable() {
  const rows = state.data.opportunities || [];
  $("opp-table").innerHTML = tableHtml(
    [
      ["rank", "Rank"],
      ["headline", "Headline"],
      ["lever", "Lever"],
      ["product", "Product"],
      ["brand", "Brand"],
      ["retailer", "Retailer"],
      ["region", "Region"],
      ["current_sales", "Current sales"],
      ["addressable_value", "Addressable value"],
      ["addressable_volume", "Addressable volume"],
      ["confidence", "Confidence"],
    ],
    rows,
    (item) => `<tr data-id="${escapeAttr(item.opportunity_id || "")}">
      <td>${item.rank}</td>
      <td>${escapeHtml(item.headline || "")}</td>
      <td>${escapeHtml(item.lever || "")}</td>
      <td>${escapeHtml(item.product || "")}</td>
      <td>${escapeHtml(item.brand || "")}</td>
      <td>${escapeHtml(item.retailer || "")}</td>
      <td>${escapeHtml(item.region || "")}</td>
      <td>${rawText(item.current_sales, "money")}</td>
      <td>${money(item.addressable_value)}</td>
      <td>${number(item.addressable_volume)}</td>
      <td><span class="confidence ${escapeAttr(item.confidence)}">${escapeHtml(item.confidence)}</span></td>
    </tr>`,
    "No opportunities in this slice."
  );
  bindTable("opp-table", rows, renderOppTable, openDetail);
}

function renderCompare(id, rows, extraHint) {
  $(id).innerHTML = tableHtml(
    [
      ["name", "Name"],
      ["sales", "Sales"],
      ["volume", "Volume"],
      ["growth", extraHint === "retailer" ? "Growth %" : "Growth %"],
      [extraHint === "retailer" ? "distribution" : "opportunity_value", extraHint === "retailer" ? "Distribution (median stores)" : "Opportunity value"],
      ["opportunity_value", extraHint === "retailer" ? "Opportunity value" : extraHint === "region" ? "Opportunity value" : "Opportunity value"],
      ["dominant_lever", "Dominant lever"],
    ].filter((item, index, all) => extraHint !== "region" || item[0] !== "distribution" || index === 0)
      .concat(extraHint === "region" ? [["opportunity_value", "Opportunity value"]] : []),
    rows,
    (item) => `<tr>
      <td>${escapeHtml(item.name || "")}</td>
      <td>${rawText(item.sales, "money")}</td>
      <td>${rawText(item.volume)}</td>
      <td>${rawText(item.growth, "pct")}</td>
      ${extraHint === "retailer" ? `<td>${rawText(item.distribution)}</td>` : ""}
      <td>${money(item.opportunity_value)}</td>
      <td>${escapeHtml(item.dominant_lever || "")}</td>
    </tr>`,
    "No regions/retailers in this slice."
  );
}

function renderRegionTable() {
  const headers = [
    ["name", "Region"],
    ["sales", "Sales"],
    ["volume", "Volume"],
    ["growth", "Growth %"],
    ["opportunity_value", "Opportunity value"],
  ];
  const rows = state.data.regions || [];
  $("region-table").innerHTML = tableHtml(
    headers,
    rows,
    (item) => `<tr data-region="${escapeAttr(item.name)}">
      <td>${escapeHtml(item.name)}</td>
      <td>${rawText(item.sales, "money")}</td>
      <td>${rawText(item.volume)}</td>
      <td>${rawText(item.growth, "pct")}</td>
      <td>${money(item.opportunity_value)}</td>
    </tr>`,
    "No regions in this slice."
  );
  $("region-table").querySelectorAll("tr[data-region]").forEach((node) => {
    node.addEventListener("click", async () => {
      state.filters.region = node.dataset.region;
      await load();
    });
  });
  bindSort("region-table", rows, (sorted) => {
    state.data.regions = sorted;
    renderRegionTable();
  });
}

function renderRetailerTable() {
  const rows = state.data.retailers || [];
  $("retailer-table").innerHTML = tableHtml(
    [
      ["name", "Retailer"],
      ["sales", "Sales"],
      ["volume", "Volume"],
      ["distribution", "Distribution"],
      ["opportunity_value", "Opportunity value"],
    ],
    rows,
    (item) => `<tr data-retailer="${escapeAttr(item.name)}">
      <td>${escapeHtml(item.name)}</td>
      <td>${rawText(item.sales, "money")}</td>
      <td>${rawText(item.volume)}</td>
      <td>${rawText(item.distribution)}</td>
      <td>${money(item.opportunity_value)}</td>
    </tr>`,
    "No retailers in this slice."
  );
  $("retailer-table").querySelectorAll("tr[data-retailer]").forEach((node) => {
    node.addEventListener("click", async () => {
      state.filters.retailer = node.dataset.retailer;
      await load();
    });
  });
  bindSort("retailer-table", rows, (sorted) => {
    state.data.retailers = sorted;
    renderRetailerTable();
  });
}

function renderProducts() {
  const rows = state.data.products || [];
  const cat = state.filters.category;
  const brand = state.filters.brand;
  const crumbs = [`<button type="button" class="crumb" data-level="category">All categories</button>`];
  if (cat !== "all") crumbs.push(`<button type="button" class="crumb" data-level="brand">${escapeHtml(cat)}</button>`);
  if (brand !== "all") crumbs.push(`<span class="crumb">${escapeHtml(brand)}</span>`);
  $("crumbs").innerHTML = crumbs.join("");
  $("crumbs").querySelectorAll("button").forEach((node) => {
    node.addEventListener("click", async () => {
      if (node.dataset.level === "category") {
        state.filters.category = "all";
        state.filters.brand = "all";
        state.filters.product = "all";
      } else {
        state.filters.brand = "all";
        state.filters.product = "all";
      }
      await load();
    });
  });
  $("product-table").innerHTML = tableHtml(
    [
      ["category", "Category"],
      ["brand", "Brand"],
      ["product", "Product / SKU"],
      ["sales_value", "Sales"],
      ["sales_volume", "Volume"],
      ["opportunity_value", "Opportunity value"],
    ],
    rows,
    (item) => `<tr data-product="${escapeAttr(item.product)}" data-brand="${escapeAttr(item.brand || "")}" data-category="${escapeAttr(item.category || "")}">
      <td>${escapeHtml(item.category || "Not available")}</td>
      <td>${escapeHtml(item.brand || "Not available")}</td>
      <td>${escapeHtml(item.product)}</td>
      <td>${rawText(item.sales_value, "money")}</td>
      <td>${rawText(item.sales_volume)}</td>
      <td>${money(item.opportunity_value)}</td>
    </tr>`,
    "No products in this slice."
  );
  $("product-table").querySelectorAll("tr[data-product]").forEach((node) => {
    node.addEventListener("click", async () => {
      if (node.dataset.category) state.filters.category = node.dataset.category;
      if (node.dataset.brand) state.filters.brand = node.dataset.brand;
      state.filters.product = node.dataset.product;
      await load();
    });
  });
}

function renderPrice() {
  const rows = state.data.price || [];
  $("price-table").innerHTML = tableHtml(
    [
      ["product", "Product"],
      ["retailer", "Retailer"],
      ["region", "Region"],
      ["current_price", "Current price"],
      ["price_per_kg", "Price/kg"],
      ["price_difference_pct", "Price difference %"],
      ["price_signal", "Price signal"],
      ["recommendation", "Price recommendation"],
      ["confidence", "Confidence"],
    ],
    rows,
    (item) => `<tr>
      <td>${escapeHtml(item.product || "")}</td>
      <td>${escapeHtml(item.retailer || "")}</td>
      <td>${escapeHtml(item.region || "")}</td>
      <td>${rawText(item.current_price, "money")}</td>
      <td>${rawText(item.price_per_kg)}</td>
      <td>${rawText(item.price_difference_pct, "pct")}</td>
      <td><span class="kind OBSERVATION">PRICE SIGNAL</span> ${escapeHtml(rawText(item.price_signal))}</td>
      <td><span class="kind RECOMMENDATION">PRICE RECOMMENDATION</span> ${escapeHtml(rawText(item.recommendation))}</td>
      <td><span class="confidence ${escapeAttr(item.confidence || "")}">${escapeHtml(item.confidence || "Not available")}</span></td>
    </tr>`,
    "No price architecture rows in this slice."
  );
}

function renderPromo() {
  const rows = state.data.promotion || [];
  $("promo-table").innerHTML = tableHtml(
    [
      ["product", "Product"],
      ["retailer", "Retailer"],
      ["region", "Region"],
      ["promo_observations", "Observations"],
      ["opportunity_value", "Promotion opportunity"],
      ["volume_uplift_pct", "Volume uplift %"],
      ["confidence", "Confidence"],
      ["recommendation", "Recommendation"],
      ["normal_price", "Normal / RSP"],
    ],
    rows,
    (item) => `<tr>
      <td>${escapeHtml(item.product || "")}</td>
      <td>${escapeHtml(item.retailer || "")}</td>
      <td>${escapeHtml(item.region || "")}</td>
      <td>${rawText(item.promo_observations)}</td>
      <td>${rawText(item.opportunity_value, "money")}</td>
      <td>${rawText(item.volume_uplift_pct, "pct")}</td>
      <td><span class="confidence ${escapeAttr(item.confidence || "")}">${escapeHtml(item.confidence || "Not available")}</span></td>
      <td>${escapeHtml(rawText(item.recommendation))}</td>
      <td>${rawText(item.normal_price)}</td>
    </tr>`,
    "No promotion rows in this slice."
  );
}

function renderDistribution() {
  const rows = state.data.distribution || [];
  $("dist-table").innerHTML = tableHtml(
    [
      ["product", "Product"],
      ["retailer", "Retailer"],
      ["region", "Region"],
      ["current_stores", "Current stores"],
      ["benchmark_stores", "Benchmark stores"],
      ["store_gap", "Store gap"],
      ["value_per_store", "Value/store"],
      ["volume_per_store", "Volume/store"],
      ["opportunity_value", "Distribution opportunity"],
      ["confidence", "Confidence"],
    ],
    rows,
    (item) => `<tr>
      <td>${escapeHtml(item.product || "")}</td>
      <td>${escapeHtml(item.retailer || "")}</td>
      <td>${escapeHtml(item.region || "")}</td>
      <td>${rawText(item.current_stores)}</td>
      <td>${rawText(item.benchmark_stores)}</td>
      <td>${rawText(item.store_gap)}</td>
      <td>${rawText(item.value_per_store, "money")}</td>
      <td>${rawText(item.volume_per_store)}</td>
      <td>${rawText(item.opportunity_value, "money")}</td>
      <td><span class="confidence ${escapeAttr(item.confidence || "")}">${escapeHtml(item.confidence || "Not available")}</span></td>
    </tr>`,
    "No distribution rows in this slice."
  );
}

function tableHtml(headers, rows, rowFn, empty) {
  if (!rows.length) return `<tbody><tr><td class="empty">${escapeHtml(empty)}</td></tr></tbody>`;
  return `<thead><tr>${headers.map(([key, label]) => sortableHeader(key, label)).join("")}</tr></thead><tbody>${rows.map(rowFn).join("")}</tbody>`;
}

function bindTable(id, rows, rerender, onRow) {
  $(id).querySelectorAll("tr[data-id]").forEach((node) => {
    node.addEventListener("click", () => onRow(node.dataset.id));
  });
  bindSort(id, rows, (sorted) => {
    state.data.opportunities = sorted;
    rerender();
  });
}

function bindSort(id, rows, apply) {
  $(id).querySelectorAll("th[data-sort]").forEach((node) => {
    node.addEventListener("click", () => apply(sortRows(rows, node.dataset.sort)));
  });
}

async function openDetail(id) {
  if (!id) return;
  const response = await fetch(`/api/opportunity?id=${encodeURIComponent(id)}`);
  if (!response.ok) return;
  const item = await response.json();
  $("drawer").hidden = false;
  $("drawer-body").innerHTML = `
    <p class="eyebrow">Opportunity detail · ${escapeHtml(item.lever || "")}</p>
    <h2>${escapeHtml(item.headline || "")}</h2>
    <p><span class="confidence ${escapeAttr(item.confidence)}">${escapeHtml(item.confidence)}</span></p>
    <dl class="kv">
      <dt>Product</dt><dd>${escapeHtml(item.product || "")}</dd>
      <dt>Brand</dt><dd>${escapeHtml(item.brand || "Not available")}</dd>
      <dt>Retailer</dt><dd>${escapeHtml(item.retailer || "")}</dd>
      <dt>Region</dt><dd>${escapeHtml(item.region || "")}</dd>
      <dt>Current sales</dt><dd>${rawText(item.current_sales, "money")}</dd>
      <dt>Addressable value</dt><dd>${money(item.addressable_value)}</dd>
      <dt>Addressable volume</dt><dd>${number(item.addressable_volume)}</dd>
      <dt>Store gap</dt><dd>${rawText(item.store_gap)}</dd>
      <dt>Benchmark stores</dt><dd>${rawText(item.benchmark_stores)}</dd>
      <dt>Value/store</dt><dd>${rawText(item.value_per_store, "money")}</dd>
      <dt>Volume/store</dt><dd>${rawText(item.volume_per_store)}</dd>
      <dt>Double-counting risk</dt><dd>${escapeHtml(item.double_counting_risk || "Not available")}</dd>
    </dl>
    <p><strong>Why this matters.</strong> ${escapeHtml(item.why || "Not available")}</p>
    <p><strong>Recommended action.</strong> ${escapeHtml(item.recommended_action || "Not available")}</p>
    <p class="disclaimer">This is addressable opportunity, not guaranteed incremental sales.</p>
    <h3>Supporting evidence</h3>
    <ul class="evidence">${(item.evidence || []).map((line) => `<li>${escapeHtml(line)}</li>`).join("") || "<li>Not available</li>"}</ul>
  `;
}

function render() {
  $("manufacturer").textContent = `${state.data.manufacturer} commercial story`;
  renderFilters();
  renderQuality();
  renderStory();
  renderContext();
  renderKpis();
  renderCharts();
  renderActions();
  renderOppTable();
  renderRegionTable();
  renderRetailerTable();
  renderProducts();
  renderPrice();
  renderPromo();
  renderDistribution();
}

function setView(view) {
  state.view = view;
  document.querySelectorAll(".view-btn").forEach((btn) => btn.classList.toggle("is-on", btn.dataset.view === view));
  document.querySelectorAll(".panel").forEach((panel) => panel.classList.toggle("is-on", panel.dataset.panel === view));
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function escapeAttr(value) {
  return escapeHtml(value).replaceAll("'", "&#39;");
}

function showTip(event) {
  const tip = $("tooltip");
  tip.hidden = false;
  tip.textContent = event.currentTarget.dataset.tip;
  moveTip(event);
}

function moveTip(event) {
  const tip = $("tooltip");
  tip.style.left = `${event.clientX + 12}px`;
  tip.style.top = `${event.clientY + 12}px`;
}

function hideTip() {
  $("tooltip").hidden = true;
}

$("reset-filters").addEventListener("click", async () => {
  state.filters = { period: "all", category: "all", brand: "all", product: "all", retailer: "all", region: "all", lever: "all", top_n: 3 };
  await load();
});
document.querySelectorAll(".topn-btn").forEach((btn) => {
  btn.addEventListener("click", async () => {
    state.filters.top_n = Number(btn.dataset.topn);
    await load();
  });
});
document.querySelectorAll(".view-btn").forEach((btn) => {
  btn.addEventListener("click", () => setView(btn.dataset.view));
});
$("close-drawer").addEventListener("click", () => {
  $("drawer").hidden = true;
});

load().catch((error) => {
  $("story").innerHTML = `<h2>Dashboard could not load</h2><p>${escapeHtml(error.message)}</p>`;
});
