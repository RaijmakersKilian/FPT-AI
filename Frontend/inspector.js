async function populateInspector() {
  let categories = [];
  let summary    = null;

  try {
    const r = await fetch('/api/coverage/data');
    if (!r.ok) throw new Error(r.status);
    const data = await r.json();
    summary = data.summary || null;

    if (data.results) {
      // Per-type (coverage_per_type.py): { group, n_elements, coverage }
      categories = data.results.map(row => {
        const en = (row.group.match(/\[(.+?)\]/) || [])[1] || row.group;
        return {
          name: en,
          meta: `${row.n_elements} el · ${(row.coverage * 100).toFixed(0)}%`,
          pct:  row.coverage,
        };
      });
    } else if (data.segments) {
      // Per-segment (coverage_analysis.py): { seg, from_m, to_m, coverage_pct }
      categories = data.segments.map(s => ({
        name: `Segment ${s.seg + 1}`,
        meta: `${s.from_m.toFixed(0)}–${s.to_m.toFixed(0)} m · ${s.coverage_pct}%`,
        pct:  s.coverage_pct / 100,
      }));
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
