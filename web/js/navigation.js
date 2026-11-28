const loaded = {};
function show(tab) {
  document.querySelectorAll(".tabs button").forEach((b) => b.classList.toggle("on", b.dataset.tab === tab));
  document.querySelectorAll(".tab").forEach((s) => s.classList.toggle("on", s.id === tab));
  if (!loaded[tab]) { loaded[tab] = true; ({ overview, shield, transfer, net })[tab](); }
  try { localStorage.setItem("tab", tab); } catch {}
}
document.querySelectorAll(".tabs button").forEach((b) => (b.onclick = () => show(b.dataset.tab)));
