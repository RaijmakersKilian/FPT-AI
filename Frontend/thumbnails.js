// Timeline thumbnail selection + pagination dots
const thumbs = document.querySelectorAll('#thumbs .thumb');
const dots = document.querySelectorAll('.dots i');
const mainVideo = document.getElementById('main-video');
const titleEl = document.getElementById('main-video-title');

function activateThumbnail(t, i) {
  thumbs.forEach((x) => x.classList.remove('active'));
  dots.forEach((d) => d.classList.remove('on'));
  t.classList.add('active');
  if (dots[i]) dots[i].classList.add('on');

  const src = t.dataset && t.dataset.src;
  const name = t.dataset && t.dataset.name;
  if (src && mainVideo) {
    try {
      mainVideo.pause();
    } catch (e) {}
    mainVideo.src = src;
    mainVideo.load();
    mainVideo.play().catch(() => {});
  }
  if (titleEl) {
    titleEl.textContent = name ? `Video: ${name}` : 'Video';
  }
}

thumbs.forEach((t, i) => {
  t.addEventListener('click', () => activateThumbnail(t, i));
});

// initialize from active thumb (if any)
const initial = document.querySelector('#thumbs .thumb.active');
if (initial) {
  const idx = Array.from(thumbs).indexOf(initial);
  if (idx >= 0) activateThumbnail(initial, idx);
}

// Export dropdown
const exportMenu = document.getElementById('export-menu');
const exportBtn = document.getElementById('export-btn');
const exportOptions = document.querySelectorAll('.export-option');

function closeExportMenu() {
  if (!exportMenu || !exportBtn) return;
  exportMenu.classList.remove('open');
  exportBtn.setAttribute('aria-expanded', 'false');
}

function toggleExportMenu() {
  if (!exportMenu || !exportBtn) return;
  const isOpen = exportMenu.classList.contains('open');
  if (isOpen) {
    closeExportMenu();
  } else {
    exportMenu.classList.add('open');
    exportBtn.setAttribute('aria-expanded', 'true');
  }
}

if (exportBtn) {
  exportBtn.addEventListener('click', (event) => {
    event.stopPropagation();
    toggleExportMenu();
  });
}

exportOptions.forEach((option) => {
  option.addEventListener('click', (event) => {
    event.stopPropagation();
    const format = option.dataset.format || 'unknown';
    closeExportMenu();
    if (format === 'pdf' && typeof window.exportDashboardPdf === 'function') {
      window.exportDashboardPdf();
    } else {
      alert(`Export as ${format.toUpperCase()} is not available yet.`);
    }
  });
});

document.addEventListener('click', (event) => {
  if (exportMenu && !exportMenu.contains(event.target)) {
    closeExportMenu();
  }
});

document.addEventListener('keydown', (event) => {
  if (event.key === 'Escape') {
    closeExportMenu();
  }
});

// Video timeline carousel: overlay arrows + page dots scroll the single-row strip.
(function () {
  const track = document.getElementById('thumbs');
  const prev = document.getElementById('thumb-prev');
  const next = document.getElementById('thumb-next');
  const dotsWrap = document.getElementById('thumb-dots');
  if (!track || !prev || !next) return;

  const pageStep = () => Math.max(160, Math.round(track.clientWidth * 0.8));
  const pageCount = () => Math.max(1, Math.round(track.scrollWidth / Math.max(1, track.clientWidth)));
  const currentPage = () => Math.round(track.scrollLeft / Math.max(1, track.clientWidth));

  function buildDots() {
    if (!dotsWrap) return;
    const n = pageCount();
    dotsWrap.innerHTML = '';
    if (n <= 1) return; // nothing to page through
    for (let i = 0; i < n; i++) {
      const dot = document.createElement('i');
      dot.addEventListener('click', () =>
        track.scrollTo({ left: i * track.clientWidth, behavior: 'smooth' }));
      dotsWrap.appendChild(dot);
    }
    highlight();
  }
  function highlight() {
    if (!dotsWrap) return;
    const cur = currentPage();
    Array.from(dotsWrap.children).forEach((d, i) => d.classList.toggle('on', i === cur));
  }
  function updateArrows() {
    const max = track.scrollWidth - track.clientWidth - 1;
    const noScroll = track.scrollWidth <= track.clientWidth + 2;
    prev.disabled = noScroll || track.scrollLeft <= 0;
    next.disabled = noScroll || track.scrollLeft >= max;
  }

  prev.addEventListener('click', () => track.scrollBy({ left: -pageStep(), behavior: 'smooth' }));
  next.addEventListener('click', () => track.scrollBy({ left: pageStep(), behavior: 'smooth' }));
  track.addEventListener('scroll', () => { updateArrows(); highlight(); }, { passive: true });
  window.addEventListener('resize', () => { buildDots(); updateArrows(); });

  // Build once now and again whenever azure-data.js injects the thumbnails.
  buildDots();
  updateArrows();
  new MutationObserver(() => { buildDots(); updateArrows(); }).observe(track, { childList: true });
})();
