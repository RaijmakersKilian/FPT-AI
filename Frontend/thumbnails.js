// Timeline thumbnail selection + pagination dots
const thumbs = document.querySelectorAll('#thumbs .thumb');
const dots = document.querySelectorAll('.dots i');
thumbs.forEach((t, i) => {
  t.addEventListener('click', () => {
    thumbs.forEach((x) => x.classList.remove('active'));
    dots.forEach((d) => d.classList.remove('on'));
    t.classList.add('active');
    dots[i].classList.add('on');
  });
});

// Export button (placeholder)
document.querySelector('.export-btn').addEventListener('click', () => {
  alert('Export options: PDF report · Excel · IFC snapshot');
});
