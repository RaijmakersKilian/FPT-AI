// Timeline thumbnail navigation — arrow buttons + page dots
// Works with both hardcoded thumbs and dynamically injected thumbs (azure-data.js).
// Re-initializes automatically via MutationObserver when the thumb list changes.
(function () {
  const track    = document.getElementById('thumbs');
  const prev     = document.getElementById('timeline-prev');
  const next     = document.getElementById('timeline-next');
  const dotsWrap = document.getElementById('timeline-dots');

  if (!track) return;

  const PER_PAGE = 5;

  function thumbEls()    { return Array.from(track.querySelectorAll('.thumb')); }
  function totalPages()  { return Math.max(1, Math.ceil(thumbEls().length / PER_PAGE)); }
  function currentPage() {
    const thumbs = thumbEls();
    if (!thumbs.length) return 0;
    // Find which thumb is closest to the left edge
    const paddingLeft = parseFloat(window.getComputedStyle(track).paddingLeft) || 36;
    const visibleLeft = track.scrollLeft + paddingLeft;
    let closest = 0, minDist = Infinity;
    thumbs.forEach((t, i) => {
      const dist = Math.abs(t.offsetLeft - visibleLeft);
      if (dist < minDist) { minDist = dist; closest = i; }
    });
    return Math.floor(closest / PER_PAGE);
  }

  function scrollToPage(page) {
    const thumbs = thumbEls();
    const firstIdx = page * PER_PAGE;
    const thumb = thumbs[firstIdx];
    if (!thumb) {
      track.scrollTo({ left: track.scrollWidth, behavior: 'smooth' });
      return;
    }
    const paddingLeft = parseFloat(window.getComputedStyle(track).paddingLeft) || 36;
    track.scrollTo({ left: thumb.offsetLeft - paddingLeft, behavior: 'smooth' });
  }

  function buildDots() {
    if (!dotsWrap) return;
    const n = totalPages();
    dotsWrap.innerHTML = '';
    for (let i = 0; i < n; i++) {
      const dot = document.createElement('i');
      dot.addEventListener('click', () => scrollToPage(i));
      dotsWrap.appendChild(dot);
    }
    highlightDot();
  }

  function highlightDot() {
    if (!dotsWrap) return;
    const cur = currentPage();
    Array.from(dotsWrap.children).forEach((d, i) => d.classList.toggle('on', i === cur));
  }

  function updateArrows() {
    if (!prev || !next) return;
    const atStart = track.scrollLeft <= 1;
    const atEnd   = track.scrollLeft >= track.scrollWidth - track.clientWidth - 1;
    const noScroll = track.scrollWidth <= track.clientWidth + 2;
    prev.disabled = atStart;
    next.disabled = atEnd || noScroll;
  }

  let _page = 0;
  if (prev) prev.addEventListener('click', () => { _page = Math.max(0, currentPage() - 1); scrollToPage(_page); });
  if (next) next.addEventListener('click', () => { _page = Math.min(totalPages() - 1, currentPage() + 1); scrollToPage(_page); });

  track.addEventListener('scroll', () => { updateArrows(); highlightDot(); }, { passive: true });
  window.addEventListener('resize', () => { buildDots(); updateArrows(); });

  // Re-initialize when azure-data.js injects or replaces thumbnails
  new MutationObserver(() => { buildDots(); updateArrows(); }).observe(track, { childList: true });

  buildDots();
  updateArrows();
})();


// Export dropdown
(function () {
  const exportMenu    = document.getElementById('export-menu');
  const exportBtn     = document.getElementById('export-btn');
  const exportOptions = document.querySelectorAll('.export-option');

  function close() {
    if (!exportMenu || !exportBtn) return;
    exportMenu.classList.remove('open');
    exportBtn.setAttribute('aria-expanded', 'false');
  }

  function toggle() {
    if (!exportMenu || !exportBtn) return;
    const open = exportMenu.classList.contains('open');
    if (open) { close(); } else {
      exportMenu.classList.add('open');
      exportBtn.setAttribute('aria-expanded', 'true');
    }
  }

  if (exportBtn) exportBtn.addEventListener('click', (e) => { e.stopPropagation(); toggle(); });

  exportOptions.forEach((opt) => {
    opt.addEventListener('click', (e) => {
      e.stopPropagation();
      close();
    });
  });

  document.addEventListener('click', (e) => { if (exportMenu && !exportMenu.contains(e.target)) close(); });
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') close(); });
})();
