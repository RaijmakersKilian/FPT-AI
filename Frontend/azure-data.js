// Loads the drone videos straight from Azure Blob Storage (the "videos"
// container) and populates the timeline thumbnails + the main player.
//
// No SDK needed — talks to the Blob REST API with fetch. Requires azure-config.js
// (window.AZURE_CONFIG) loaded first. Plain script so it works under Live Server
// and when served by the backend.
//
// Azure setup needed for this to work from the browser:
//   1. Container access: anonymous "Container" level (for listing), OR set a
//      container SAS token with Read+List in azure-config.js.
//   2. CORS on the storage account (Blob service): allow your origin, GET,
//      headers *, exposed headers *. Without CORS the list fetch is blocked.
(function () {
  const cfg = window.AZURE_CONFIG;
  if (!cfg || !cfg.account || cfg.account.startsWith('<')) {
    console.warn('[azure-data] window.AZURE_CONFIG missing/blank — copy azure-config.example.js to azure-config.js and fill it in');
    showEmpty('Azure not configured yet (Frontend/azure-config.js).');
    return;
  }

  const BASE = `https://${cfg.account}.blob.core.windows.net`;
  const SAS = cfg.sasToken ? cfg.sasToken.replace(/^\?/, '') : '';
  const VIDEO_EXT = /\.(mp4|mov|avi|mkv|webm)$/i;

  function blobUrl(container, name) {
    const path = name.split('/').map(encodeURIComponent).join('/');
    const u = `${BASE}/${container}/${path}`;
    return SAS ? `${u}?${SAS}` : u;
  }

  async function listBlobs(container) {
    let url = `${BASE}/${container}?restype=container&comp=list`;
    if (SAS) url += `&${SAS}`;
    let resp;
    try {
      resp = await fetch(url);
    } catch (e) {
      console.warn('[azure-data] list fetch failed (often CORS — add a CORS rule on the storage account):', e);
      showEmpty('Could not reach Azure (check CORS on the storage account).');
      return [];
    }
    if (!resp.ok) {
      console.warn(`[azure-data] list "${container}" -> HTTP ${resp.status}. ` +
        'If 403/404: enable anonymous "Container" access or set a SAS token with List permission.');
      showEmpty(`Azure list failed (HTTP ${resp.status}). Enable anonymous "Container" access or add a SAS token.`);
      return [];
    }
    const xml = await resp.text();
    const doc = new DOMParser().parseFromString(xml, 'application/xml');
    return Array.from(doc.getElementsByTagName('Blob'))
      .map((b) => {
        const n = b.getElementsByTagName('Name')[0];
        return n ? n.textContent : null;
      })
      .filter(Boolean);
  }

  const elMainVideo = () => document.getElementById('main-video');
  const elTitle = () => document.getElementById('main-video-title');
  const elThumbs = () => document.getElementById('thumbs');

  function showEmpty(msg) {
    const wrap = elThumbs();
    if (wrap) {
      wrap.innerHTML =
        `<div class="thumb-empty" style="padding:16px;color:#93a1b8;font-size:13px;line-height:1.5">${msg}</div>`;
    }
  }

  function playVideo(name) {
    const url = blobUrl(cfg.videosContainer, name);
    const v = elMainVideo();
    if (v) {
      try { v.pause(); } catch (e) {}
      v.src = url;
      v.load();
    }
    const t = elTitle();
    if (t) t.textContent = `Video: ${name}`;
  }

  function buildThumbs(videos) {
    const wrap = elThumbs();
    if (!wrap) return;
    wrap.innerHTML = '';
    videos.forEach((name) => {
      const url = blobUrl(cfg.videosContainer, name);
      const el = document.createElement('div');
      el.className = 'thumb';
      el.dataset.name = name;
      el.innerHTML =
        `<div class="frame"><video class="thumb-video" muted playsinline preload="metadata" src="${url}#t=0.5"></video></div>` +
        `<div class="date">${name}</div>`;
      el.addEventListener('click', () => {
        wrap.querySelectorAll('.thumb').forEach((t) => t.classList.remove('active'));
        el.classList.add('active');
        playVideo(name);
      });
      wrap.appendChild(el);
    });
  }

  async function init() {
    const wrap = elThumbs();
    const all = await listBlobs(cfg.videosContainer);
    const videos = all.filter((n) => VIDEO_EXT.test(n));
    if (!videos.length) {
      if (wrap && !wrap.querySelector('.thumb-empty')) {
        showEmpty(`No videos in the Azure “${cfg.videosContainer}” container yet. Upload .mp4 files.`);
      }
      return;
    }
    buildThumbs(videos);
    const first = wrap && wrap.querySelector('.thumb');
    if (first) first.classList.add('active');
    playVideo(videos[0]);
    console.info(`[azure-data] loaded ${videos.length} video(s) from Azure`);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();

  window.AzureData = { listBlobs, blobUrl };
})();
