// Timeline thumbnail selection + pagination
const thumbsContainer = document.getElementById('thumbs');
const thumbs = document.querySelectorAll('#thumbs .thumb');
const dotsContainer = document.getElementById('timeline-dots');
const mainVideo = document.getElementById('main-video');
const titleEl = document.getElementById('main-video-title');

const PAGE_SIZE = 5;
const totalPages = Math.ceil(thumbs.length / PAGE_SIZE);
let currentPage = 0;

// Rebuild dots based on actual page count
if (dotsContainer) {
  dotsContainer.innerHTML = '';
  for (let i = 0; i < totalPages; i++) {
    const dot = document.createElement('i');
    if (i === 0) dot.classList.add('on');
    dotsContainer.appendChild(dot);
  }
}
const dots = dotsContainer ? dotsContainer.querySelectorAll('i') : [];

function goToPage(page) {
  currentPage = page;
  // Scroll thumbs container to the right position
  const firstThumbOfPage = thumbs[page * PAGE_SIZE];
  if (firstThumbOfPage) {
    thumbsContainer.scrollTo({ left: firstThumbOfPage.offsetLeft, behavior: 'smooth' });
  }
  // Update dots
  dots.forEach((d, i) => d.classList.toggle('on', i === page));
  // Update arrow states
  const prevBtn = document.getElementById('timeline-prev');
  const nextBtn = document.getElementById('timeline-next');
  if (prevBtn) prevBtn.disabled = page === 0;
  if (nextBtn) nextBtn.disabled = page === totalPages - 1;
}

document.getElementById('timeline-prev')?.addEventListener('click', () => {
  if (currentPage > 0) goToPage(currentPage - 1);
});
document.getElementById('timeline-next')?.addEventListener('click', () => {
  if (currentPage < totalPages - 1) goToPage(currentPage + 1);
});

function activateThumbnail(t, i) {
  thumbs.forEach((x) => x.classList.remove('active'));
  t.classList.add('active');

  // Update page dots based on which page this thumb belongs to
  const page = Math.floor(i / PAGE_SIZE);
  dots.forEach((d, j) => d.classList.toggle('on', j === page));

  const src      = t.dataset && t.dataset.src;
  const name     = t.dataset && t.dataset.name;
  const coverage = t.dataset && t.dataset.coverage;

  if (src && mainVideo) {
    try { mainVideo.pause(); } catch (e) {}
    mainVideo.src = src;
    mainVideo.load();
    mainVideo.play().catch(() => {});
  }
  if (titleEl) {
    titleEl.textContent = name ? `Video: ${name}` : 'Video';
  }

  if (coverage) {
    if (typeof window.loadCoverage === 'function')     window.loadCoverage(coverage);
    if (typeof window.loadCoverageData === 'function') window.loadCoverageData(coverage);
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

// initialize first page
goToPage(0);

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
    if (format !== 'pdf') {
      alert(`Export as ${format.toUpperCase()} will be connected to the database later.`);
    }
    // PDF is handled by pdf.js
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
