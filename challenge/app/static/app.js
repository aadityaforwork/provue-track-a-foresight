// Foresight dashboard client.
// API surface:
//   GET  /api/v1/forecasts          public forecast feed
//   POST /api/v1/auth/login         { username, password } -> { token }
//   GET  /api/v1/me                 Bearer token -> profile
//   GET  /api/v1/admin/feeds        admin only
//   POST /api/v1/admin/feeds/import { url }  admin only, imports an external feed
// TODO: remove seeded demo account before launch -> analyst / analyst
async function load() {
  const r = await fetch("/api/v1/forecasts");
  const data = await r.json();
  document.getElementById("forecasts").textContent = JSON.stringify(data.forecasts);
}
load();
