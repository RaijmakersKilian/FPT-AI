async function populateInspector() {
  let categories = [];
  let summary    = null;

  try {
    const r = await fetch('/api/coverage/data');
    if (!r.ok) throw new Error(r.status);
    const data = await r.json();
    summary = data.summary || null;

    if (data.results) {
      const grouped = new Map();

      for (const row of data.results) {
        const { key, name } = _parseGroup(row.group);
        if (!key) continue;

        if (!grouped.has(key)) {
          grouped.set(key, { name, n_elements: 0, coverage_sum: 0, count: 0 });
        }
        const g = grouped.get(key);
        g.n_elements   += row.n_elements;
        g.coverage_sum += row.coverage;
        g.count        += 1;
      }

      categories = [...grouped.values()]
        .map(g => ({
          name: g.name,
          meta: `${g.n_elements} el · ${(g.coverage_sum / g.count * 100).toFixed(0)}%`,
          pct:  g.coverage_sum / g.count,
        }))
        .sort((a, b) => a.pct - b.pct || a.name.localeCompare(b.name));

    } else if (data.segments) {
      const n = data.segments.length;
      categories = data.segments.map(s => {
        let label;
        if (s.seg === 0)          label = 'Start Abutment';
        else if (s.seg === n - 1) label = 'End Abutment';
        else                      label = `Span ${s.seg}`;
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

// Extraheert een leesbare naam en groeperingssleutel uit een BIM-groepnaam.
function _parseGroup(group) {
  if (!group) return { key: null, name: null };
  if (group === ':') return { key: null, name: null };

  // "Vietnamese naam  [English key]" → English naam tonen, groeperen op English
  const bracketM = group.match(/^(.+?)\s+\[(.+?)\]$/);
  if (bracketM) {
    return { key: bracketM[2].trim(), name: bracketM[2].trim() };
  }

  // "TypeCode:Beschrijving:" of "TypeCode:TypeCode:" (BIM interne namen)
  if (group.includes(':')) {
    const parts = group.split(':').map(p => p.trim()).filter(Boolean);
    if (parts.length === 0) return { key: null, name: null };
    const code = parts[0];
    // Als alle delen gelijk zijn, toon gewoon de code
    const desc = parts.find(p => p !== code) || code;
    return { key: code, name: desc };
  }

  return { key: group, name: group };
}

document.addEventListener('DOMContentLoaded', populateInspector);
