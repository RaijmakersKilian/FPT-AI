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
