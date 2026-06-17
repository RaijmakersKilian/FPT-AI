// Client-side PDF export of the dashboard (no backend needed).
// Uses html2canvas (snapshot) + jsPDF (PDF), both loaded via CDN in Dashboard.html.
// Exposed as window.exportDashboardPdf(); thumbnails.js calls it from the EXPORT menu.
(function () {
  async function exportDashboardPdf() {
    const jsPDFctor = window.jspdf && window.jspdf.jsPDF;
    if (!window.html2canvas || !jsPDFctor) {
      alert('PDF libraries are still loading — try again in a second.');
      return;
    }

    const target = document.querySelector('body');
    const btn = document.getElementById('export-btn');
    if (btn) btn.classList.add('exporting');

    try {
      const canvas = await window.html2canvas(target, {
        scale: 2,
        backgroundColor: getComputedStyle(document.body).backgroundColor || '#0c1124',
        useCORS: true,
        logging: false,
        windowWidth: document.documentElement.scrollWidth,
        windowHeight: document.documentElement.scrollHeight,
      });

      const img = canvas.toDataURL('image/png');
      const pdf = new jsPDFctor({ orientation: 'landscape', unit: 'pt', format: 'a4' });
      const pageW = pdf.internal.pageSize.getWidth();
      const pageH = pdf.internal.pageSize.getHeight();
      const margin = 24;
      const ratio = Math.min((pageW - margin * 2) / canvas.width, (pageH - margin * 2) / canvas.height);
      const w = canvas.width * ratio;
      const h = canvas.height * ratio;

      pdf.setFontSize(13);
      pdf.text('GOT Bridge — Construction Progress Report', margin, margin);
      pdf.setFontSize(9);
      pdf.text(new Date().toLocaleString(), pageW - margin, margin, { align: 'right' });
      pdf.addImage(img, 'PNG', (pageW - w) / 2, margin + 8, w, h);

      pdf.save(`bridge-progress-report-${new Date().toISOString().slice(0, 10)}.pdf`);
    } catch (err) {
      console.error('[export] PDF failed:', err);
      alert('PDF export failed: ' + (err && err.message ? err.message : err));
    } finally {
      if (btn) btn.classList.remove('exporting');
    }
  }

  window.exportDashboardPdf = exportDashboardPdf;
})();
