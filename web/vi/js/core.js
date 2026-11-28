const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const vnd = (n) => Number(n).toLocaleString("vi-VN") + " đ";
const digits = (s) => String(s).replace(/\D/g, "");
const fmtTs = (ts) => `${ts.slice(11, 16)} ${ts.slice(8, 10)}/${ts.slice(5, 7)}`;
async function api(path, body) {
  const r = await fetch("../api/khach/" + path, body !== undefined ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) } : {});
  if (r.status === 401 && path !== "login") { go("login"); throw new Error("Phiên đã hết, đăng nhập lại"); }
  const d = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(typeof d.detail === "string" ? d.detail : "Dữ liệu không hợp lệ");
  return d;
}
function go(screen) {
  document.querySelectorAll(".screen").forEach((s) => s.classList.toggle("on", s.id === "s-" + screen));
  ({ home, inbox, history, loan: loanScreen })[screen]?.();
}
document.addEventListener("click", (e) => { const b = e.target.closest("[data-go]"); if (b) go(b.dataset.go); });
