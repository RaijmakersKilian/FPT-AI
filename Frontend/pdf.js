// PDF Preview — opens a modal showing the report layout.
// Not yet connected to backend; data is read from the live DOM/API.
(function () {
const MONTH_SHORT = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];

function fmtDate(dateStr) {
  const [y, m, d] = dateStr.split('-');
  return `${+d} ${MONTH_SHORT[+m - 1]} ${y}`;
}

// ── Build modal HTML ──────────────────────────────────────────────────────────

function buildModal(timelineEntries, inspectorRows, summary, bimSnapshot, videoTitle) {
  const today = new Date();
  const reportDate = `${today.getDate()} ${MONTH_SHORT[today.getMonth()]} ${today.getFullYear()}`;
  const lastEntry  = timelineEntries[timelineEntries.length - 1];
  const totalPct   = lastEntry ? lastEntry.total_coverage_pct : 0;

  const chartSVG = buildChartSVG(timelineEntries);

  // 3D viewer + inspector side by side
  const snapshotSection = `
    <div style="margin-bottom:32px">
      <div style="font-size:14px;font-weight:700;margin-bottom:12px">3D Coverage View · ${videoTitle}</div>
      <div style="background:#0c1124;border-radius:10px;overflow:hidden;aspect-ratio:16/9;display:flex;align-items:center;justify-content:center;width:100%">
        ${bimSnapshot
          ? `<img src="${bimSnapshot}" style="width:100%;height:100%;object-fit:contain;display:block"/>`
          : `<span style="color:#93a1b8;font-size:12px">3D view not available</span>`}
      </div>
    </div>`;

  // Inspector table rows (for the full element table below)
  const tableRows = inspectorRows.map(r => {
    const pct   = Math.round(r.pct * 100);
    const color = r.pct >= 0.80 ? '#22c55e' : r.pct >= 0.30 ? '#f59e0b' : '#db1515';
    return `
      <tr>
        <td>${r.name}</td>
        <td style="text-align:right">${pct}%</td>
        <td style="width:160px">
          <div style="background:#eef2fb;border-radius:4px;height:8px;overflow:hidden">
            <div style="background:${color};width:${pct}%;height:100%;border-radius:4px"></div>
          </div>
        </td>
        <td style="text-align:center">
          <span style="display:inline-block;padding:2px 8px;border-radius:20px;font-size:10px;font-weight:600;
            background:${r.pct>=0.80?'#dcfce7':r.pct>=0.30?'#fef3c7':'#fee2e2'};color:${color}">
            ${r.pct>=0.80?'Built':r.pct>=0.30?'Partial':'Missing'}</span>
        </td>
      </tr>`;
  }).join('');

  return `
  <div id="pdf-overlay" style="
    position:fixed;inset:0;z-index:1000;
    background:rgba(10,18,40,0.7);
    display:flex;flex-direction:column;align-items:center;
    overflow-y:auto;padding:32px 16px 48px;
  ">
    <!-- Toolbar -->
    <div style="
      width:794px;max-width:100%;display:flex;align-items:center;justify-content:space-between;
      margin-bottom:16px;
    ">
      <span style="color:#fff;font-size:14px;font-weight:600;font-family:Inter,sans-serif">
        PDF Preview — Construction Progress Report
      </span>
      <div style="display:flex;gap:10px">
        <button id="pdf-print-btn" style="
          padding:9px 22px;border-radius:8px;border:none;cursor:pointer;
          background:#0066ff;color:#fff;font-size:13px;font-weight:600;font-family:Inter,sans-serif;
        ">Save as PDF</button>
        <button id="pdf-close-btn" style="
          padding:9px 16px;border-radius:8px;border:1.5px solid rgba(255,255,255,0.25);
          background:transparent;color:#fff;font-size:13px;font-weight:600;font-family:Inter,sans-serif;cursor:pointer;
        ">✕ Close</button>
      </div>
    </div>

    <!-- A4 Document -->
    <div id="pdf-document" style="
      width:794px;max-width:100%;background:#fff;
      border-radius:4px;box-shadow:0 8px 40px rgba(0,0,0,0.4);
      padding:56px 64px;font-family:Inter,'Segoe UI',sans-serif;color:#16203a;
    ">
      <!-- Header -->
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:32px;padding-bottom:20px;border-bottom:2px solid #0066ff">
        <div>
          <div style="font-size:22px;font-weight:800;color:#0066ff;letter-spacing:-0.3px">FPT AI</div>
          <div style="font-size:11px;color:#5a6b85;margin-top:2px;letter-spacing:0.05em">CONSTRUCTION PROGRESS MONITOR</div>
        </div>
        <div style="text-align:right">
          <div style="font-size:14px;font-weight:700">GOT Bridge · XL8</div>
          <div style="font-size:11px;color:#5a6b85;margin-top:2px">Report date: ${reportDate}</div>
        </div>
      </div>

      <!-- Title -->
      <div style="margin-bottom:28px">
        <div style="font-size:20px;font-weight:700;margin-bottom:4px">Construction Progress Report</div>
        <div style="font-size:12px;color:#5a6b85">Based on ${timelineEntries.length} drone survey scans · ${fmtDate(timelineEntries[0]?.date ?? '')} – ${fmtDate(timelineEntries[timelineEntries.length-1]?.date ?? '')}</div>
      </div>

      <!-- KPI row -->
      <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:32px">
        ${[
          { label: 'Overall Coverage', value: `${totalPct}%`, color: '#0066ff' },
          { label: 'Built sections',   value: summary.built,  color: '#22c55e' },
          { label: 'In Progress',      value: summary.partial, color: '#f59e0b' },
          { label: 'Not Started',      value: summary.missing, color: '#db1515' },
        ].map(k => `
          <div style="background:#f8faff;border-radius:10px;padding:16px 20px;border:1px solid #e4eaf4">
            <div style="font-size:11px;color:#5a6b85;font-weight:500;margin-bottom:6px">${k.label}</div>
            <div style="font-size:26px;font-weight:800;color:${k.color}">${k.value}</div>
          </div>`).join('')}
      </div>

      <!-- 3D snapshot -->
      ${snapshotSection}

      <!-- Chart section -->
      <div style="margin-bottom:32px">
        <div style="font-size:14px;font-weight:700;margin-bottom:12px">Coverage over Time</div>
        <div style="background:#f8faff;border-radius:10px;padding:16px;border:1px solid #e4eaf4">
          ${chartSVG}
        </div>
      </div>

      <!-- Page break spacer -->
      <div style="height:120px"></div>

      <!-- Inspector table -->
      <div style="margin-bottom:32px">
        <div style="font-size:14px;font-weight:700;margin-bottom:12px">Construction Elements · Coverage by Type</div>
        <table style="width:100%;border-collapse:collapse;font-size:12px">
          <thead>
            <tr style="background:#f0f5ff">
              <th style="text-align:left;padding:9px 12px;border-radius:6px 0 0 6px;font-weight:600;color:#5a6b85">Element type</th>
              <th style="text-align:right;padding:9px 12px;font-weight:600;color:#5a6b85">Coverage</th>
              <th style="padding:9px 12px;font-weight:600;color:#5a6b85">Progress</th>
              <th style="text-align:center;padding:9px 12px;border-radius:0 6px 6px 0;font-weight:600;color:#5a6b85">Status</th>
            </tr>
          </thead>
          <tbody>${tableRows}</tbody>
        </table>
      </div>

      <!-- Page break spacer -->
      <div style="height:120px"></div>

      <!-- Timeline table -->
      <div style="margin-bottom:32px">
        <div style="font-size:14px;font-weight:700;margin-bottom:12px">Scan Timeline Summary</div>
        <table style="width:100%;border-collapse:collapse;font-size:12px">
          <thead>
            <tr style="background:#f0f5ff">
              <th style="text-align:left;padding:9px 12px;border-radius:6px 0 0 6px;font-weight:600;color:#5a6b85">Date</th>
              <th style="text-align:right;padding:9px 12px;font-weight:600;color:#5a6b85">Coverage</th>
              <th style="text-align:right;padding:9px 12px;font-weight:600;color:#5a6b85">Built</th>
              <th style="text-align:right;padding:9px 12px;font-weight:600;color:#5a6b85">Partial</th>
              <th style="text-align:right;padding:9px 12px;border-radius:0 6px 6px 0;font-weight:600;color:#5a6b85">Missing</th>
            </tr>
          </thead>
          <tbody>
            ${timelineEntries.map((e, i) => `
              <tr style="background:${i % 2 === 0 ? '#fff' : '#f8faff'}">
                <td style="padding:8px 12px">${fmtDate(e.date)}</td>
                <td style="text-align:right;padding:8px 12px;font-weight:600">${e.total_coverage_pct}%</td>
                <td style="text-align:right;padding:8px 12px;color:#22c55e">${e.built}</td>
                <td style="text-align:right;padding:8px 12px;color:#f59e0b">${e.partial}</td>
                <td style="text-align:right;padding:8px 12px;color:#db1515">${e.missing}</td>
              </tr>`).join('')}
          </tbody>
        </table>
      </div>

      <!-- Footer -->
      <div style="border-top:1px solid #e4eaf4;padding-top:16px;display:flex;justify-content:space-between;font-size:10px;color:#93a1b8">
        <span>FPT AI · Construction Progress Monitor</span>
        <span>GOT Bridge XL8 — Confidential</span>
        <span>Generated ${reportDate}</span>
      </div>
    </div>
  </div>`;
}


// ── Mini timeline chart SVG ───────────────────────────────────────────────────

function buildChartSVG(entries) {
  if (!entries.length) return '';
  const W = 666, H = 140, X1 = 40, X2 = W - 10, Y1 = 10, Y2 = H - 28;
  const pw = X2 - X1, ph = Y2 - Y1, n = entries.length;
  const xOf = i => X1 + (i / (n - 1)) * pw;
  const yOf = p => Y2 - (p / 100) * ph;

  const pts   = entries.map((e, i) => [xOf(i), yOf(e.total_coverage_pct), e]);
  const pLine = pts.map(p => `${p[0]},${p[1]}`).join(' ');
  const area  = pLine + ` ${X2},${Y2} ${X1},${Y2}`;

  const gridLines = [0, 25, 50, 75, 100].map(p => {
    const y = yOf(p);
    return `<line x1="${X1}" y1="${y}" x2="${X2}" y2="${y}" stroke="#e8edf5" stroke-width="1"/>
            <text x="${X1 - 4}" y="${y + 4}" font-size="9" fill="#93a1b8" text-anchor="end">${p}%</text>`;
  }).join('');

  const xLabels = pts.map(([x, , e], i) => {
    const [y, m] = e.date.split('-');
    const label = `${MONTH_SHORT[+m - 1]} '${y.slice(2)}`;
    return `<text x="${x}" y="${Y2 + 14}" font-size="9" fill="#93a1b8" text-anchor="middle">${label}</text>`;
  }).join('');

  const circles = pts.map(([x, y, e]) =>
    `<circle cx="${x}" cy="${y}" r="4" fill="#0066ff"/>
     <circle cx="${x}" cy="${y}" r="1.8" fill="white"/>`
  ).join('');

  return `<svg viewBox="0 0 ${W} ${H}" xmlns="http://www.w3.org/2000/svg" style="width:100%;height:auto;display:block">
    <defs>
      <linearGradient id="pdf-ga" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="#0066ff" stop-opacity="0.15"/>
        <stop offset="100%" stop-color="#0066ff" stop-opacity="0.01"/>
      </linearGradient>
    </defs>
    ${gridLines}
    <polygon fill="url(#pdf-ga)" points="${area}"/>
    <polyline fill="none" stroke="#0066ff" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" points="${pLine}"/>
    ${circles}
    ${xLabels}
  </svg>`;
}


// ── Open / close ──────────────────────────────────────────────────────────────

async function openPdfPreview() {
  let timelineEntries = [];
  let summary         = { built: 0, partial: 0, missing: 0 };

  // Capture 3D viewer snapshot
  const bimSnapshot = typeof window.getBimSnapshot === 'function'
    ? window.getBimSnapshot() : null;

  // Read current video title (selected date)
  const videoTitle = document.getElementById('main-video-title')?.textContent || 'Current scan';

  // Read live inspector DOM (already shows the selected date's data)
  const inspectorRows = [];
  document.querySelectorAll('#inspector-categories .cat').forEach(cat => {
    const name    = cat.querySelector('.cat-name')?.textContent?.trim() || '';
    const metaStr = cat.querySelector('.cat-meta')?.textContent?.trim() || '';
    const bar     = cat.querySelector('.bar i');
    const pct     = bar ? parseInt(bar.style.width) / 100 : 0;
    inspectorRows.push({ name, meta: metaStr, pct });
  });

  try {
    const tlRes = await fetch('/api/coverage/timeline');
    if (tlRes.ok) {
      const data = await tlRes.json();
      timelineEntries = data.entries || [];
      // Try to get summary from currently active date
      const activeThumb = document.querySelector('#thumbs .thumb.active');
      const dateKey = activeThumb?.dataset?.coverage;
      if (dateKey) {
        const dr = await fetch(`/api/coverage/data/${dateKey}`);
        if (dr.ok) { const d = await dr.json(); summary = d.summary || summary; }
      }
    }
  } catch (e) {
    console.warn('PDF data laden mislukt:', e);
  }

  document.body.insertAdjacentHTML('beforeend', buildModal(timelineEntries, inspectorRows, summary, bimSnapshot, videoTitle));

  document.getElementById('pdf-close-btn').addEventListener('click', closePdfPreview);
  document.getElementById('pdf-overlay').addEventListener('click', e => {
    if (e.target.id === 'pdf-overlay') closePdfPreview();
  });
  document.getElementById('pdf-print-btn').addEventListener('click', () => savePdf());
}

function closePdfPreview() {
  document.getElementById('pdf-overlay')?.remove();
}

async function loadScript(src) {
  return new Promise((res, rej) => {
    if (document.querySelector(`script[src="${src}"]`)) return res();
    const s = document.createElement('script');
    s.src = src; s.onload = res; s.onerror = rej;
    document.head.appendChild(s);
  });
}

async function savePdf() {
  const btn = document.getElementById('pdf-print-btn');
  if (btn) { btn.textContent = 'Saving…'; btn.disabled = true; }

  try {
    await loadScript('https://cdn.jsdelivr.net/npm/html2canvas@1.4.1/dist/html2canvas.min.js');
    await loadScript('https://cdn.jsdelivr.net/npm/jspdf@2.5.1/dist/jspdf.umd.min.js');

    const doc = document.getElementById('pdf-document');
    const canvas = await html2canvas(doc, { scale: 2, useCORS: true, backgroundColor: '#ffffff' });

    const { jsPDF } = window.jspdf;
    const pdf = new jsPDF({ orientation: 'portrait', unit: 'mm', format: 'a4' });

    const pageW = pdf.internal.pageSize.getWidth();
    const pageH = pdf.internal.pageSize.getHeight();
    const imgW  = pageW;
    const imgH  = (canvas.height / canvas.width) * pageW;

    // Split across multiple pages if content is taller than one A4
    let yOffset = 0;
    while (yOffset < imgH) {
      if (yOffset > 0) pdf.addPage();
      pdf.addImage(canvas.toDataURL('image/jpeg', 0.92), 'JPEG', 0, -yOffset, imgW, imgH);
      yOffset += pageH;
    }

    const today = new Date();
    const stamp = `${today.getFullYear()}${String(today.getMonth()+1).padStart(2,'0')}${String(today.getDate()).padStart(2,'0')}`;
    pdf.save(`GOT_Bridge_XL8_Report_${stamp}.pdf`);
  } catch (e) {
    console.error('PDF opslaan mislukt:', e);
    alert('PDF opslaan mislukt. Controleer de console.');
  } finally {
    if (btn) { btn.textContent = 'Save as PDF'; btn.disabled = false; }
  }
}

// Wire up EXPORT → PDF button
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.export-option').forEach(btn => {
    if (btn.dataset.format === 'pdf') {
      btn.addEventListener('click', e => {
        e.stopPropagation();
        openPdfPreview();
      }, { once: false });
    }
  });
});
})(); // end IIFE
