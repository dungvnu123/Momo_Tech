const DEC_VI = { allow: "cho phép", warn: "cảnh báo", hold: "tạm giữ", cancelled: "khách huỷ", loan: "vay", error: "lỗi" };
let simHolds = -1;
async function simRender(s) {
  const st = s.stats || {}, n = (k) => num(st[k] || 0);
  $("#sim-btn").textContent = s.running ? "⏸ Tắt mô phỏng" : "▶ Bật mô phỏng";
  $("#sim-btn").classList.toggle("on", s.running);
  $("#sim-stats").innerHTML = `<div>Khoản vay<b>${n("loans")}</b></div><div>Giao dịch<b>${n("transfers")}</b></div>
    <div>Cho phép<b>${n("dec_allow")}</b></div><div>Cảnh báo / huỷ<b>${num((st.dec_warn || 0) + (st.dec_cancelled || 0))}</b></div>
    <div class="good">Lừa bị chặn<b>${n("scam_blocked")}/${n("scam_total")}</b></div><div class="bad">Bình thường bị làm phiền<b>${n("benign_flagged")}</b></div>`;
  $("#sim-feed").innerHTML = (s.recent || []).map((e) => `<li><time>${e.ts.slice(11, 19)}</time><span class="dec ${e.decision}">${DEC_VI[e.decision] || e.decision}</span>
      <span>${esc(e.text)}${e.kind ? ` <span class="k">· kịch bản: ${esc(e.kind)}</span>` : ""}</span></li>`).join("");
  if (simHolds >= 0 && (st.dec_hold || 0) !== simHolds && !liveES) loadAlerts();   // có giao dịch bị giữ → hàng đợi tải lại ngay
  simHolds = st.dec_hold || 0;
}
function simInit() {
  $("#sim-btn").onclick = async () => {
    const s = await api("sim");
    simRender(await api(s.running ? "sim/stop" : "sim/start", s.running ? {} : { interval: Number($("#sim-speed").value) }));
  };
  api("sim").then(simRender).catch(() => {});
  setInterval(async () => {
    if (!$("#net").classList.contains("on") || document.hidden) return;
    try { simRender(await api("sim")); } catch {}
  }, 2000);
}
