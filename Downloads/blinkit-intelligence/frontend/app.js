// ─── Config ───────────────────────────────────────────────────────────────────
const API = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
  ? 'http://localhost:8000/api'
  : '/api';  // same-origin when deployed

// ─── Pagination state ─────────────────────────────────────────────────────────
let catState    = { nextUrl: null, loaded: 0 };
let searchState = { nextUrl: null, nextPayload: null, loaded: 0 };
let lastLookup  = null;  // for Track button

// ─── Nav ──────────────────────────────────────────────────────────────────────
document.querySelectorAll('.nav-item').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.nav-item').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById('view-' + btn.dataset.view).classList.add('active');
    if (btn.dataset.view === 'dashboard') loadDashboard();
    if (btn.dataset.view === 'tracked')   loadTracked();
    if (btn.dataset.view === 'alerts')    loadAlerts();
    if (btn.dataset.view === 'zipcodes')  loadZipcodes();
  });
});

// ─── Health check ─────────────────────────────────────────────────────────────
async function checkHealth() {
  const dot = document.querySelector('.status-dot');
  const lbl = document.getElementById('api-status');
  try {
    const r = await fetch(API + '/health');
    if (r.ok) {
      dot.className = 'status-dot ok';
      lbl.innerHTML = '<span class="status-dot ok"></span> API connected';
      loadDashboard();
    } else throw new Error();
  } catch {
    dot.className = 'status-dot err';
    lbl.innerHTML = '<span class="status-dot err"></span> API offline';
  }
}

// ─── API helpers ──────────────────────────────────────────────────────────────
async function apiFetch(path, opts = {}) {
  const r = await fetch(API + path, {
    headers: { 'Content-Type': 'application/json', ...opts.headers },
    ...opts
  });
  const data = await r.json();
  if (!r.ok) throw new Error(data.detail || r.statusText);
  return data;
}

// ─── UI helpers ───────────────────────────────────────────────────────────────
const fmt = p => p != null ? '₹' + parseFloat(p).toFixed(2) : '—';
const disc = (mrp, sp) => mrp && sp && mrp > sp ? Math.round(((mrp-sp)/mrp)*100) : 0;

function loading(el, msg) {
  el.innerHTML = `<div class="loading-row"><div class="loader"></div>${msg}</div>`;
}

function errBox(el, msg) {
  el.innerHTML = `<div class="error-box">⚠ ${msg}</div>`;
}

function empty(el, icon, msg) {
  el.innerHTML = `<div class="empty-state"><div class="ei">${icon}</div>${msg}</div>`;
}

function alertTypeBadge(t) {
  const map = {
    price_drop:         '<span class="badge green">Price drop</span>',
    price_increase:     '<span class="badge amber">Price up</span>',
    back_in_stock:      '<span class="badge blue">Back in stock</span>',
    out_of_stock:       '<span class="badge red">Out of stock</span>',
    competitor_stockout:'<span class="badge yellow">Comp. stockout</span>',
  };
  return map[t] || `<span class="badge">${t}</span>`;
}

// ─── Dashboard ────────────────────────────────────────────────────────────────
async function loadDashboard() {
  try {
    const [products, zipcodes, alerts] = await Promise.all([
      apiFetch('/products/tracked'),
      apiFetch('/zipcodes'),
      apiFetch('/alerts?limit=10'),
    ]);
    document.getElementById('stat-products').textContent = products.data.length;
    document.getElementById('stat-zipcodes').textContent = zipcodes.data.length;
    document.getElementById('stat-alerts').textContent   = alerts.data.length;
    const drops = alerts.data.filter(a => a.alert_type === 'price_drop').length;
    document.getElementById('stat-drops').textContent = drops;

    const el = document.getElementById('dash-alerts');
    if (!alerts.data.length) { empty(el, '🔔', 'No alerts yet'); return; }
    renderAlertsTable(el, alerts.data);
  } catch(e) {
    errBox(document.getElementById('dash-alerts'), e.message);
  }
}

// ─── Product Lookup ───────────────────────────────────────────────────────────
async function lookupProduct() {
  const pid = document.getElementById('l-pid').value.trim();
  const zip = document.getElementById('l-zip').value.trim();
  const el  = document.getElementById('lookup-result');
  if (!pid || !zip) { errBox(el, 'Enter Product ID and Zipcode'); return; }
  loading(el, 'Fetching product...');
  document.getElementById('track-btn').style.display = 'none';
  try {
    const res = await apiFetch(`/products/fetch?product_id=${pid}&zipcode=${zip}`);
    lastLookup = { pid, zip };
    renderProductCard(el, res.data, pid, zip);
    document.getElementById('track-btn').style.display = 'inline-block';
  } catch(e) {
    errBox(el, e.message);
  }
}

async function trackProduct() {
  if (!lastLookup) return;
  const { pid, zip } = lastLookup;
  const btn = document.getElementById('track-btn');
  btn.disabled = true; btn.textContent = 'Tracking...';
  try {
    await apiFetch('/products/track', {
      method: 'POST',
      body: JSON.stringify({ product_id: pid, zipcode: zip })
    });
    btn.textContent = '✓ Tracked';
    btn.className = 'btn success';
  } catch(e) {
    btn.textContent = '+ Track'; btn.disabled = false;
    alert('Error: ' + e.message);
  }
}

function renderProductCard(el, d, pid, zip) {
  const d_pct = disc(d.mrp, d.selling_price);
  el.innerHTML = `
    <div class="card">
      <div class="product-header">
        ${d.image_url
          ? `<img class="product-img" src="${d.image_url}" onerror="this.style.display='none'">`
          : `<div class="product-img-ph">🛒</div>`}
        <div class="product-meta">
          <h3>${d.product_name || '—'}</h3>
          <p>${[d.brand].filter(Boolean).join(' · ')}</p>
          <div class="badge-row">
            ${d.in_stock ? '<span class="badge green">In stock</span>' : '<span class="badge red">Out of stock</span>'}
            ${d_pct ? `<span class="badge green">${d_pct}% off</span>` : ''}
          </div>
        </div>
      </div>
      <div class="price-row">
        <div class="pi"><span class="pl">Selling price</span><span class="pv">${fmt(d.selling_price)}</span></div>
        <div class="pi"><span class="pl">MRP</span><span class="pv mrp">${fmt(d.mrp)}</span></div>
        ${d.mrp && d.selling_price && d.mrp > d.selling_price
          ? `<div class="pi"><span class="pl">You save</span><span class="pv save">${fmt(d.mrp - d.selling_price)}</span></div>` : ''}
      </div>
      ${(d.variants||[]).length ? `
        <div class="section-title">Variants (${d.variants.length})</div>
        <div class="variants-list">
          ${d.variants.map(v => {
            const vp = v.price?.sale_price || v.selling_price || v.mrp;
            const vm = v.mrp || v.price?.mrp;
            return `<div class="variant-row">
              <span class="vn">${v.name || v.pack_size || '—'}</span>
              <span class="vp">${fmt(vp)}</span>
              ${vm && vm !== vp ? `<span class="vm">${fmt(vm)}</span>` : ''}
            </div>`;
          }).join('')}
        </div>` : ''}
      <div class="meta-footer">ID: ${pid} · Zipcode: ${zip} · ${new Date().toLocaleTimeString()}</div>
      <details class="raw-toggle"><summary>Raw response</summary><pre>${JSON.stringify(d, null, 2)}</pre></details>
    </div>`;
}

// ─── Category Browse ───────────────────────────────────────────────────────────
async function browseCategory(reset) {
  const catid = document.getElementById('c-catid').value.trim();
  const zip   = document.getElementById('c-zip').value.trim();
  const el    = document.getElementById('cat-result');
  const pg    = document.getElementById('cat-pg');
  if (!catid || !zip) { errBox(el, 'Enter Category ID and Zipcode'); return; }
  if (reset) { catState = { nextUrl: null, loaded: 0 }; el.innerHTML = ''; loading(el, 'Loading...'); }
  try {
    const params = new URLSearchParams({ cat_id: catid, zipcode: zip });
    if (catState.nextUrl) params.set('next_page_url', catState.nextUrl);
    const res = await apiFetch('/category?' + params);
    if (reset) el.innerHTML = '';
    renderProductGrid(res.data, el);
    catState.nextUrl = res.next_url || null;
    catState.loaded += res.data.length;
    if (!res.data.length && reset) { empty(el, '📦', 'No products found'); pg.style.display='none'; return; }
    pg.style.display = catState.nextUrl ? 'flex' : 'none';
    document.getElementById('cat-count').textContent = `${catState.loaded} products loaded`;
  } catch(e) { errBox(el, e.message); }
}

// ─── Search ────────────────────────────────────────────────────────────────────
async function doSearch(reset) {
  const kw  = document.getElementById('s-kw').value.trim();
  const zip = document.getElementById('s-zip').value.trim();
  const el  = document.getElementById('search-result');
  const pg  = document.getElementById('search-pg');
  if (!kw || !zip) { errBox(el, 'Enter keyword and zipcode'); return; }
  if (reset) { searchState = { nextUrl: null, nextPayload: null, loaded: 0 }; el.innerHTML = ''; loading(el, `Searching "${kw}"...`); }
  try {
    let res;
    if (!searchState.nextUrl) {
      res = await apiFetch(`/search?keyword=${encodeURIComponent(kw)}&zipcode=${zip}`);
    } else {
      res = await apiFetch('/search/next', {
        method: 'POST',
        body: JSON.stringify({ keyword: kw, zipcode: zip, next_page_url: searchState.nextUrl, next_page_payload: searchState.nextPayload })
      });
    }
    if (reset) el.innerHTML = '';
    renderProductGrid(res.data, el);
    searchState.nextUrl     = res.next_url || null;
    searchState.nextPayload = res.next_payload || null;
    searchState.loaded     += res.data.length;
    if (!res.data.length && reset) { empty(el, '🔍', `No results for "${kw}"`); pg.style.display='none'; return; }
    pg.style.display = searchState.nextUrl ? 'flex' : 'none';
    document.getElementById('search-count').textContent = `${searchState.loaded} results`;
  } catch(e) { errBox(el, e.message); }
}

// ─── Product grid renderer ────────────────────────────────────────────────────
function renderProductGrid(products, container) {
  if (!products.length) return;
  let grid = container.querySelector('.products-grid');
  if (!grid) { grid = document.createElement('div'); grid.className = 'products-grid'; container.appendChild(grid); }
  for (const p of products) {
    const d_pct = disc(p.mrp, p.selling_price);
    const card  = document.createElement('div');
    card.className = 'mini-card';
    card.innerHTML = `
      ${p.image_url ? `<img src="${p.image_url}" loading="lazy" onerror="this.style.display='none'">` : `<div class="mc-ph">🛒</div>`}
      <div class="mc-name">${p.product_name || '—'}</div>
      <div class="mc-pr">
        <span class="mc-price">${fmt(p.selling_price)}</span>
        ${p.mrp && p.mrp !== p.selling_price ? `<span class="mc-mrp">${fmt(p.mrp)}</span>` : ''}
        ${d_pct ? `<span class="mc-disc">${d_pct}%</span>` : ''}
      </div>
      ${!p.in_stock ? `<div class="mc-oos">Out of stock</div>` : ''}`;
    grid.appendChild(card);
  }
}

// ─── Tracked Products ─────────────────────────────────────────────────────────
async function loadTracked() {
  const el = document.getElementById('tracked-result');
  loading(el, 'Loading tracked products...');
  try {
    const res = await apiFetch('/products/tracked');
    if (!res.data.length) { empty(el, '◉', 'No products tracked yet. Use Product Lookup to start tracking.'); return; }
    el.innerHTML = res.data.map(p => `
      <div class="card" style="display:flex;align-items:center;gap:14px">
        ${p.image_url ? `<img class="product-img" src="${p.image_url}" onerror="this.style.display='none'">` : `<div class="product-img-ph">🛒</div>`}
        <div style="flex:1">
          <div style="font-weight:500;color:var(--text)">${p.product_name}</div>
          <div style="font-size:12px;color:var(--text2);margin-top:3px">${p.brand || ''} · ID: ${p.product_id}</div>
        </div>
        <button class="btn" onclick="viewHistory('${p.product_id}')">History</button>
        <button class="btn danger" onclick="untrackProduct('${p.product_id}', this)">Remove</button>
      </div>`).join('');
  } catch(e) { errBox(el, e.message); }
}

async function untrackProduct(pid, btn) {
  btn.disabled = true; btn.textContent = '...';
  try {
    await apiFetch('/products/untrack', { method: 'POST', body: JSON.stringify({ product_id: pid }) });
    btn.closest('.card').remove();
  } catch(e) { btn.disabled = false; btn.textContent = 'Remove'; alert(e.message); }
}

async function viewHistory(pid) {
  const zip = prompt('Enter zipcode for history:', '380015');
  if (!zip) return;
  try {
    const res = await apiFetch(`/products/history?product_id=${pid}&zipcode=${zip}&limit=10`);
    if (!res.data.length) { alert('No history found for this product + zipcode.'); return; }
    const rows = res.data.map(s => `${new Date(s.snapshotted_at).toLocaleDateString()} — ${fmt(s.selling_price)} ${s.in_stock ? '✓' : '✗'}`).join('\n');
    alert(`Price history for ${pid} @ ${zip}:\n\n${rows}`);
  } catch(e) { alert(e.message); }
}

// ─── Alerts ───────────────────────────────────────────────────────────────────
async function loadAlerts() {
  const el = document.getElementById('alerts-result');
  loading(el, 'Loading alerts...');
  try {
    const res = await apiFetch('/alerts?limit=100');
    if (!res.data.length) { empty(el, '🔔', 'No alerts yet. Start tracking products to receive alerts.'); return; }
    renderAlertsTable(el, res.data);
  } catch(e) { errBox(el, e.message); }
}

function renderAlertsTable(el, alerts) {
  el.innerHTML = `
    <div class="card" style="padding:0;overflow:hidden">
      <table class="alerts-table">
        <thead>
          <tr>
            <th>Product</th><th>Zipcode</th><th>Type</th>
            <th>Old price</th><th>New price</th><th>Change</th><th>When</th>
          </tr>
        </thead>
        <tbody>
          ${alerts.map(a => `
            <tr>
              <td>${a.product_id}</td>
              <td>${a.zipcode}</td>
              <td>${alertTypeBadge(a.alert_type)}</td>
              <td>${fmt(a.old_price)}</td>
              <td>${fmt(a.new_price)}</td>
              <td>${a.change_percent != null
                    ? `<span style="color:${a.change_percent < 0 ? 'var(--green)' : 'var(--red)'}">
                         ${a.change_percent > 0 ? '+' : ''}${parseFloat(a.change_percent).toFixed(1)}%
                       </span>`
                    : '—'}</td>
              <td>${new Date(a.triggered_at).toLocaleString()}</td>
            </tr>`).join('')}
        </tbody>
      </table>
    </div>`;
}

// ─── Zipcodes ─────────────────────────────────────────────────────────────────
async function loadZipcodes() {
  const el = document.getElementById('zipcodes-result');
  loading(el, 'Loading zipcodes...');
  try {
    const res = await apiFetch('/zipcodes');
    if (!res.data.length) { empty(el, '⊕', 'No zipcodes added yet'); return; }
    el.innerHTML = `<div class="zipcode-list">${res.data.map(z => `
      <div class="zipcode-pill">
        <span>${z.zipcode}${z.city ? ' — ' + z.city : ''}</span>
        <span class="zp-del" onclick="removeZipcode('${z.zipcode}', this)">✕</span>
      </div>`).join('')}</div>`;
  } catch(e) { errBox(el, e.message); }
}

async function addZipcode() {
  const zip   = document.getElementById('z-zip').value.trim();
  const city  = document.getElementById('z-city').value.trim();
  const state = document.getElementById('z-state').value.trim();
  if (!zip) return;
  try {
    await apiFetch('/zipcodes', { method: 'POST', body: JSON.stringify({ zipcode: zip, city, state }) });
    document.getElementById('z-zip').value = '';
    document.getElementById('z-city').value = '';
    document.getElementById('z-state').value = '';
    loadZipcodes();
  } catch(e) { alert(e.message); }
}

async function removeZipcode(zip, el) {
  try {
    await apiFetch(`/zipcodes/${zip}`, { method: 'DELETE' });
    el.closest('.zipcode-pill').remove();
  } catch(e) { alert(e.message); }
}

// ─── Enter key support ────────────────────────────────────────────────────────
document.addEventListener('keydown', e => {
  if (e.key !== 'Enter') return;
  const active = document.querySelector('.view.active')?.id;
  if (active === 'view-lookup')   lookupProduct();
  if (active === 'view-category') browseCategory(true);
  if (active === 'view-search')   doSearch(true);
});

// ─── Init ─────────────────────────────────────────────────────────────────────
checkHealth();
