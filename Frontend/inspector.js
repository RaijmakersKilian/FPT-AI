async function populateInspector() {
  let categories = [];
  let summary    = null;

  try {
    const r = await fetch('/api/coverage/data');
    if (!r.ok) throw new Error(r.status);
    const data = await r.json();
    summary = data.summary || null;

    if (data.results) {
      // Per-type: prefer [Dutch  [English]] mapped names; also include unmapped Missing items
      const mapped = new Map();
      for (const row of data.results) {
        const m = row.group.match(/^(.+?)\s+\[(.+?)\]$/);
        if (m) {
          // Mapped group — deduplicate by English name
          const key = m[2];
          if (!mapped.has(key)) {
            mapped.set(key, { name: m[1], n_elements: 0, coverage_sum: 0, count: 0 });
          }
          const g = mapped.get(key);
          g.n_elements   += row.n_elements;
          g.coverage_sum += row.coverage;
          g.count        += 1;
        } else if (row.coverage < 0.30) {
          // Unmapped but Missing — show with cleaned raw name
          const raw = row.group.split(':')[0].trim();
          if (!raw || raw === ':') continue;
          const key = raw;
          if (!mapped.has(key)) {
            mapped.set(key, { name: raw, n_elements: 0, coverage_sum: 0, count: 0 });
          }
          const g = mapped.get(key);
          g.n_elements   += row.n_elements;
          g.coverage_sum += row.coverage;
          g.count        += 1;
        }
      }
      categories = [...mapped.values()].map(g => ({
        name: g.name,
        meta: `${g.n_elements} el · ${(g.coverage_sum / g.count * 100).toFixed(0)}%`,
        pct:  g.coverage_sum / g.count,
      }));
    } else if (data.segments) {
      // Per-segment (coverage_analysis.py): { seg, from_m, to_m, coverage_pct }
      const n = data.segments.length;
      categories = data.segments.map(s => {
        let label;
        if (s.seg === 0)     label = 'Linker oever';
        else if (s.seg === n - 1) label = 'Rechter oever';
        else                 label = `Overspanning ${s.seg}`;
        return {
          name: label,
          meta: `${Math.round(s.from_m)}–${Math.round(s.to_m)} m · ${s.coverage_pct}%`,
          pct:  s.coverage_pct / 100,
        };
      });
    }
  } catch (e) {
    console.warn('Coverage data niet geladen:', e);
  }

  if (categories.length === 0) return;

  // ── Vul Construction Inspector ──
  const container = document.getElementById('inspector-categories');
  if (container) {
    container.innerHTML = categories.map(cat => {
      const pct = Math.min(100, Math.round(cat.pct * 100));
      const cls = cat.pct >= 0.80 ? 'built' : cat.pct >= 0.30 ? 'partial' : 'missing';
      return `
        <div class="cat">
          <div class="cat-row">
            <span class="cat-name">${cat.name}</span>
            <span class="cat-meta">${cat.meta}</span>
          </div>
          <div class="bar"><i class="bar-${cls}" style="width:${pct}%"></i></div>
        </div>`;
    }).join('');
  }

  // ── Vul Overall Progress ──
  if (summary) {
    const total = summary.built + summary.partial + summary.missing;
    const pctEl = document.querySelector('.op-pct');
    if (pctEl) pctEl.textContent = `${summary.total_coverage_pct}%`;
    const secEl = document.querySelector('.op-sections');
    if (secEl) secEl.textContent = `${summary.built}/${total}`;
  }
}

document.addEventListener('DOMContentLoaded', populateInspector);
