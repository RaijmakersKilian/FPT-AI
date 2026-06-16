// Loads the drone videos straight from Supabase Storage (the "videos" bucket)
// and populates the timeline thumbnails + the main player. Replaces the old
// hardcoded /Frontend/Video's/... paths.
//
// Requires: supabase-config.js (window.SUPABASE_CONFIG) and the supabase-js UMD
// script, both loaded before this file. Plain script (no module) on purpose so
// it works under Live Server and when served by the backend.
(function () {
  const cfg = window.SUPABASE_CONFIG;
  if (!cfg) {
    console.warn('[supabase-data] window.SUPABASE_CONFIG missing — copy Frontend/supabase-config.example.js to supabase-config.js');
    return;
  }
  if (!window.supabase || !window.supabase.createClient) {
    console.warn('[supabase-data] supabase-js not loaded — check the CDN <script> tag');
    return;
  }

  const sb = window.supabase.createClient(cfg.url, cfg.anonKey);
  const VIDEO_EXT = /\.(mp4|mov|avi|mkv|webm)$/i;

  function publicUrl(bucket, name) {
    return sb.storage.from(bucket).getPublicUrl(name).data.publicUrl;
  }
  async function signedUrl(bucket, name) {
    const { data, error } = await sb.storage.from(bucket).createSignedUrl(name, 3600);
    if (error) { console.warn('[supabase-data] sign url:', error.message); return null; }
    return data && data.signedUrl;
  }
  async function urlFor(bucket, name) {
    return cfg.publicBuckets ? publicUrl(bucket, name) : await signedUrl(bucket, name);
  }

  async function listVideos() {
    const { data, error } = await sb.storage.from(cfg.videosBucket).list('', {
      limit: 1000,
      sortBy: { column: 'name', order: 'asc' },
    });
    if (error) {
      console.warn('[supabase-data] list videos:', error.message);
      return [];
    }
    return (data || []).filter((o) => o.name && VIDEO_EXT.test(o.name));
  }

  const elMainVideo = () => document.getElementById('main-video');
  const elTitle = () => document.getElementById('main-video-title');
  const elThumbs = () => document.getElementById('thumbs');

  async function playVideo(name) {
    const url = await urlFor(cfg.videosBucket, name);
    const v = elMainVideo();
    if (v && url) {
      try { v.pause(); } catch (e) {}
      v.src = url;
      v.load();
    }
    const t = elTitle();
    if (t) t.textContent = `Video: ${name}`;
  }

  async function buildThumbs(videos) {
    const wrap = elThumbs();
    if (!wrap) return;
    wrap.innerHTML = '';
    for (const vobj of videos) {
      const url = await urlFor(cfg.videosBucket, vobj.name);
      const el = document.createElement('div');
      el.className = 'thumb';
      el.dataset.name = vobj.name;
      el.innerHTML =
        `<div class="frame"><video class="thumb-video" muted playsinline preload="metadata" src="${url}#t=0.5"></video></div>` +
        `<div class="date">${vobj.name}</div>`;
      el.addEventListener('click', () => {
        wrap.querySelectorAll('.thumb').forEach((t) => t.classList.remove('active'));
        el.classList.add('active');
        playVideo(vobj.name);
      });
      wrap.appendChild(el);
    }
  }

  async function init() {
    const wrap = elThumbs();
    const videos = await listVideos();
    if (!videos.length) {
      if (wrap) {
        wrap.innerHTML =
          `<div class="thumb-empty" style="padding:16px;color:#93a1b8;font-size:13px;line-height:1.5">` +
          `No videos in Supabase yet.<br>Upload .mp4 files to the “${cfg.videosBucket}” bucket.</div>`;
      }
      console.info('[supabase-data] connected, but the videos bucket is empty');
      return;
    }
    await buildThumbs(videos);
    const first = wrap && wrap.querySelector('.thumb');
    if (first) first.classList.add('active');
    playVideo(videos[0].name);
    console.info(`[supabase-data] loaded ${videos.length} video(s) from Supabase`);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  // exposed for debugging / reuse
  window.SupabaseData = { listVideos, urlFor };
})();
