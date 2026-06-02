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

// Export button (placeholder)
document.querySelector('.export-btn').addEventListener('click', () => {
  alert('Export options: PDF report · Excel · IFC snapshot');
});
