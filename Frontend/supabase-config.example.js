// ===================================================================
// FPT AI — Frontend Supabase config
// Copy this file to  Frontend/supabase-config.js  and fill in the values.
// supabase-config.js is gitignored — do NOT commit real keys.
//
// IMPORTANT: the frontend is plain static JS (no build step), so it CANNOT
// read backend/.env. These browser-side values live here instead.
// Only ever use the ANON / PUBLIC key here — never the service_role key.
// ===================================================================

window.SUPABASE_CONFIG = {
  // Project URL.
  // WHERE: Supabase Dashboard -> Project Settings -> API -> Project URL.
  url: "https://<project-ref>.supabase.co",

  // anon / public (publishable) key — safe in the browser when RLS is enabled.
  // WHERE: Project Settings -> API -> "Project API keys" -> anon public.
  anonKey: "<anon-public-key>",

  // Storage bucket holding the drone videos.
  // WHERE: Supabase Dashboard -> Storage -> Buckets.
  videosBucket: "videos",

  // Storage bucket holding the 3D models (GLB) / coverage point clouds (PLY).
  modelsBucket: "models",

  // true  -> buckets are Public, frontend uses getPublicUrl()
  // false -> buckets are Private, frontend uses createSignedUrl()
  // WHERE: Storage -> Buckets -> (your bucket) -> Public toggle.
  publicBuckets: true,
};
