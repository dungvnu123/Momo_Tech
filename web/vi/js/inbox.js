let MSGS = [], CUR;
async function inbox() {
  MSGS = await api("inbox");
  $("#inbox").innerHTML = MSGS.map((m, i) => `<button class="msg ${m.is_read ? "" : "unread"}" data-i="${i}">
      <b><span>${esc(m.sender)}${m.kind === "official" ? ' <span class="tag ok">chính thức</span>' : ""}${m.reported_verdict ? ` <span class="tag ${m.reported_verdict === "safe" ? "ok" : "bad"}">đã báo</span>` : ""}</span><small>${fmtTs(m.ts)}</small></b>
      <p>${esc(m.body)}</p></button>`).join("") || '<p class="muted">Chưa có tin nhắn.</p>';
}
$("#inbox").onclick = async (e) => {
  const b = e.target.closest(".msg"); if (!b) return;
  CUR = MSGS[b.dataset.i];
  $("#m-sender").textContent = CUR.sender; $("#m-ts").textContent = fmtTs(CUR.ts); $("#m-body").textContent = CUR.body;
  $("#m-result").innerHTML = ""; $("#m-report").disabled = !!CUR.reported_verdict;
  go("msg"); api(`inbox/${CUR.msg_id}/read`, {}).catch(() => {});
};
const VERDICT = { scam: ["Lừa đảo", "v-hold"], suspicious: ["Đáng ngờ", "v-warn"], safe: ["An toàn", "v-allow"] };
$("#m-report").onclick = async () => {
  $("#m-report").disabled = true;
  try {
    const r = await api(`report/${CUR.msg_id}`, {}), [t, cls] = VERDICT[r.verdict];
    $("#m-result").innerHTML = `<div class="verdict ${cls}"><h2>${t}</h2>${r.times_reported ? `Đã có ${r.times_reported} người báo cùng tài khoản này.` : ""}
      <ul class="reasons">${r.reasons.map((x) => `<li>${esc(x)}</li>`).join("")}</ul><b>${esc(r.advice)}</b></div>`;
  } catch (err) { $("#m-result").innerHTML = `<p class="err">${esc(err.message)}</p>`; $("#m-report").disabled = false; }
};
// Đóng vai nạn nhân: điền sẵn form chuyển tiền theo đúng tin nhắn
$("#m-follow").onclick = () => {
  const body = CUR.body.replace(/(\d)[ .](?=\d)/g, "$1").replace(/(?<=\d)o|o(?=\d)/gi, "0");
  const acc = (body.match(/\b\d{9,16}\b/g) || []).find((n) => !/^0\d{9}$/.test(n) || /(vi|momo)/i.test(body)) || "";
  const bank = (body.match(/\b(ACB|VCB|TCB|MBB|VPB|BIDV|CTG|TPB|STB|VIB)\b/) || [])[1] || "";
  const name = (body.match(/(?:-|chu tk|ten|\()\s*([A-Z][A-Z ]{4,40}[A-Z])/) || [])[1] || "";
  const amt = (CUR.body.match(/(\d{1,3}(?:\.\d{3})+)d/) || [])[1] || "";
  go("transfer");
  $("#tx-id").value = acc; $("#tx-bank").value = bank; $("#tx-name").value = name.trim(); $("#tx-amt").value = amt.replace(/\./g, "");
  $("#tx-note").value = /thu hoi no|qua han|tat toan/i.test(body) ? "tra no FinVay" : /benh vien|gap/i.test(body) ? "chuyen gap cho me"
                      : /xac minh/i.test(body) ? "xac minh ho so" : "chuyen tien";
  $("#tx-save").checked = /danh ba/i.test(body);
  if (!acc) alert("Tin này không có số tài khoản để chuyển — thử nút “Báo lừa đảo”.");
};
