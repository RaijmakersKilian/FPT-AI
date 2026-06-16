// Dynamic 4D Progress chart — fetches real coverage data from /api/coverage/timeline

const MONTH_SHORT = ['Jan','Feb','Mrt','Apr','Mei','Jun','Jul','Aug','Sep','Okt','Nov','Dec'];

function fmtLabel(dateStr) {
  // "2023-11-18" → "Nov '23"
  const [y, m] = dateStr.split('-');
  return `${MONTH_SHORT[+m - 1]} '${y.slice(2)}`;
}

async function renderChart() {
  const svg = document.querySelector('.chart-wrap svg');
  if (!svg) return;

  let entries;
  try {
    const r = await fetch('/api/coverage/timeline');
    if (!r.ok) throw new Error(r.status);
    ({ entries } = await r.json());
  } catch (e) {
    console.warn('Timeline niet geladen:', e);
    return;
  }
  if (!entries || entries.length === 0) return;

  // ── Coördinaten ──────────────────────────────────────────────────────────────
  const X1 = 52, X2 = 542, Y1 = 56, Y2 = 224;
  const W = X2 - X1, H = Y2 - Y1;
  const n = entries.length;

  const xOf = i => X1 + (i / (n - 1)) * W;
  const yOf = pct => Y2 - (pct / 100) * H;

  const pts = entries.map((e, i) => ({ x: xOf(i), y: yOf(e.total_coverage_pct), pct: e.total_coverage_pct, date: e.date }));

  // ── Helpers ───────────────────────────────────────────────────────────────────
  const ns = 'http://www.w3.org/2000/svg';
  const el = (tag, attrs) => {
    const e = document.createElementNS(ns, tag);
    Object.entries(attrs).forEach(([k, v]) => e.setAttribute(k, v));
    return e;
  };

  // Clear existing dynamic content, keep <defs>
  [...svg.children].forEach(c => { if (c.tagName !== 'defs') c.remove(); });

  // ── Defs: gradients ──────────────────────────────────────────────────────────
  const defs = svg.querySelector('defs') || svg.appendChild(el('defs', {}));
  defs.innerHTML = `
    <linearGradient id="ga" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%"   stop-color="#0066ff" stop-opacity="0.18"/>
      <stop offset="100%" stop-color="#0066ff" stop-opacity="0.02"/>
    </linearGradient>`;

  // ── Grid ─────────────────────────────────────────────────────────────────────
  const grid = el('g', {});

  // Horizontal lines + Y labels at 0, 25, 50, 75, 100%
  [0, 25, 50, 75, 100].forEach(pct => {
    const y = yOf(pct);
    const line = el('line', { x1: X1, y1: y, x2: X2, y2: y, stroke: '#e8edf5', 'stroke-width': '1' });
    grid.appendChild(line);
    const txt = el('text', { x: X1 - 6, y: y + 4, 'font-family': 'Inter', 'font-size': '11', fill: '#93a1b8', 'text-anchor': 'end' });
    txt.textContent = `${pct}%`;
    grid.appendChild(txt);
  });

  svg.appendChild(grid);

  // ── Area fill ─────────────────────────────────────────────────────────────────
  const areaPoints = pts.map(p => `${p.x},${p.y}`).join(' ')
    + ` ${X2},${Y2} ${X1},${Y2}`;
  svg.appendChild(el('polygon', { fill: 'url(#ga)', points: areaPoints }));

  // ── Line ─────────────────────────────────────────────────────────────────────
  const linePoints = pts.map(p => `${p.x},${p.y}`).join(' ');
  svg.appendChild(el('polyline', {
    fill: 'none', stroke: '#0066ff', 'stroke-width': '2.8',
    'stroke-linecap': 'round', 'stroke-linejoin': 'round',
    points: linePoints,
  }));

  // ── Dots + tooltips ───────────────────────────────────────────────────────────
  pts.forEach(p => {
    const outer = el('circle', { cx: p.x, cy: p.y, r: '5', fill: '#0066ff' });
    const inner = el('circle', { cx: p.x, cy: p.y, r: '2.2', fill: '#fff' });
    const tip   = el('title', {});
    tip.textContent = `${fmtLabel(p.date)}: ${p.pct}%`;
    outer.appendChild(tip);
    svg.appendChild(outer);
    svg.appendChild(inner);
  });

  // ── X labels ─────────────────────────────────────────────────────────────────
  const xLabelGroup = el('g', { 'font-family': 'Inter', 'font-size': '10.5', fill: '#93a1b8', 'text-anchor': 'middle' });

  // Show every label but rotate if too crowded
  pts.forEach(p => {
    const txt = el('text', { x: p.x, y: Y2 + 16 });
    txt.textContent = fmtLabel(p.date);
    xLabelGroup.appendChild(txt);
  });
  svg.appendChild(xLabelGroup);

  // ── Legend ───────────────────────────────────────────────────────────────────
  const leg = el('g', { 'font-family': 'Inter', 'font-size': '11', fill: '#5a6b85' });
  leg.innerHTML = `
    <line x1="400" y1="268" x2="420" y2="268" stroke="#0066ff" stroke-width="2.5"/>
    <circle cx="410" cy="268" r="3.8" fill="#0066ff"/>
    <circle cx="410" cy="268" r="1.6" fill="white"/>
    <text x="426" y="272">Actual coverage</text>`;
  svg.appendChild(leg);
}

document.addEventListener('DOMContentLoaded', renderChart);
