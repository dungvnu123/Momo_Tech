// path: web/vi/vi.js — app ví phía khách (demo). JS thuần; phiên là cookie HttpOnly do server đặt.
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

// ── đăng nhập ───────────────────────────────────────────────────────────────────
let DEMO = [];
fetch("../api/khach/demo").then((r) => r.json()).then((d) => {
  DEMO = d;
  if (d.length) $("#demo-phones").innerHTML = (d[0]?.pin ? '<span class="muted">Chế độ demo: bấm 1 khách để đăng nhập luôn.</span>' : "")
    + d.map((x, i) => `<a href="#" class="persona" data-i="${i}"><b>${esc(x.name)}</b> · ${esc(x.phone)}<small>${esc(x.scenario || "")}</small></a>`).join("");
}).catch(() => {});
$("#demo-phones").onclick = (e) => {
  const a = e.target.closest("[data-i]"); if (!a) return;
  e.preventDefault();
  const x = DEMO[a.dataset.i];
  $("#l-phone").value = x.phone;
  if (x.pin) { $("#l-pin").value = x.pin; $("#login-form").requestSubmit(); } else $("#l-pin").focus();   // demo: tự điền PIN + đăng nhập
};
$("#login-form").onsubmit = async (e) => {
  e.preventDefault();
  try { await api("login", { phone: digits($("#l-phone").value), pin: digits($("#l-pin").value) }); $("#l-pin").value = ""; $("#l-err").hidden = true; go("home"); }
  catch (err) { $("#l-err").hidden = false; $("#l-err").textContent = err.message; }
};
$("#logout").onclick = async () => { await api("logout", {}); go("login"); };

// ── trang chủ ───────────────────────────────────────────────────────────────────
let ME;
async function home() {
  ME = await api("me");
  $("#h-name").textContent = ME.name;
  $("#h-balance").textContent = vnd(ME.balance);
  $("#h-phone").textContent = "Ví " + ME.phone;
  $("#h-unread").hidden = !ME.unread; $("#h-unread").textContent = ME.unread;
  const L = ME.loan, mins = Math.round((Date.now() - new Date(L.disbursed_at + "+07:00")) / 60000);
  $("#h-loan").innerHTML = `<b>Khoản vay ${L.live ? "vừa nhận" : "hiện tại"}</b>
    <div class="kv"><span>Số tiền</span><b>${vnd(L.amount)}</b></div>
    <div class="kv"><span>Giải ngân</span><span>${fmtTs(L.disbursed_at)}${L.live && mins < 600 ? ` · ${mins} phút trước` : ""}</span></div>
    ${ME.next_due ? `<div class="kv"><span>Kỳ ${ME.next_due.term_no} đến hạn</span><span>${ME.next_due.due_date.split("-").reverse().join("/")} · ${vnd(ME.next_due.total_due)}</span></div>` : ""}
    <p class="muted small">Danh bạ: ${ME.contacts.map((c) => esc(c.name)).join(", ") || "trống"}</p>`;
}

// ── hộp tin ───────────────────────────────────────────────────────────────────
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

// ── vay ─────────────────────────────────────────────────────────────────────────
function loanScreen() { if (ME) $("#loan-amt").value = ME.loan.amount; }
$("#loan-form").onsubmit = async (e) => {
  e.preventDefault();
  try { await api("loan", { amount: Number(digits($("#loan-amt").value)) }); go("home"); } catch (err) { alert(err.message); }
};

// ── chuyển tiền ─────────────────────────────────────────────────────────────────
const DEC = { hold: ["Giao dịch đang tạm giữ", "v-hold"], warn: ["Cảnh báo trước khi chuyển", "v-warn"], allow: ["Chuyển thành công", "v-allow"] };
let PENDING_TX;
function txBody(confirm) {
  return { to_type: document.querySelector("[name=to_type]:checked").value, to_id: digits($("#tx-id").value), to_bank: $("#tx-bank").value.trim() || "MoMo",
           to_name: $("#tx-name").value.trim(), amount: Number(digits($("#tx-amt").value)), note: $("#tx-note").value.trim(),
           save_contact: $("#tx-save").checked, confirm };
}
async function sendTx(body) {
  try {
    const r = await api("transfer", body), [t, cls] = DEC[r.decision];
    PENDING_TX = r.needs_confirm ? { ...body, confirm: true, save_contact: false } : null;
    $("#r-box").innerHTML = `<div class="verdict ${cls}"><h2>${r.needs_confirm ? "Khoan đã!" : t}</h2>
        ${r.message_for_customer ? `<p>${esc(r.message_for_customer)}</p>` : ""}
        ${r.reasons.length ? `<ul class="reasons">${r.reasons.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>` : ""}
        ${r.status === "held" ? "<p><b>Tiền chưa rời ví.</b> Đội rủi ro đã nhận cảnh báo và sẽ liên hệ bạn.</p>" : ""}
        <p class="score">Thiên La chấm rủi ro <b>${r.risk_score}/100</b> trong ${r.latency_ms} ms · ${esc(r.mode || "")}</p></div>
      ${r.needs_confirm ? `<div class="card"><b>Có ai đang gọi điện / nhắn tin hướng dẫn bạn chuyển khoản này không?</b>
          <div class="row2"><button class="btn danger" id="r-coached">Có, có người hướng dẫn</button><button class="btn ghost" id="r-force">Không, tôi tự chuyển</button></div>
          <button class="btn ghost" data-go="home">Huỷ giao dịch</button></div>`
                        : `<button class="btn" data-go="home">Về trang chủ</button>`}`;
    go("result");
    $("#r-force")?.addEventListener("click", () => sendTx(PENDING_TX));
    $("#r-coached")?.addEventListener("click", () => sendTx({ ...PENDING_TX, coached: true }));
  } catch (err) { alert(err.message); }
}
$("#tx-look").onclick = async () => {
  const box = $("#tx-look-r");
  try {
    const r = await api("lookup?to_id=" + encodeURIComponent(digits($("#tx-id").value)) + "&to_type=" + encodeURIComponent(document.querySelector("[name=to_type]:checked").value) + "&to_bank=" + encodeURIComponent($("#tx-bank").value.trim()));
    box.innerHTML = r.risky ? `<div class="verdict v-hold"><b>Cảnh báo người nhận</b><ul class="reasons">${r.labels.map((x) => `<li>${esc(x)}</li>`).join("")}</ul></div>`
                            : `<p class="score">Chưa có dữ liệu xấu về người nhận này — vẫn cần chắc chắn bạn biết họ.</p>`;
  } catch (err) { box.textContent = err.message; }
};
$("#tx-form").onsubmit = (e) => { e.preventDefault(); sendTx(txBody(false)); };

// ── lịch sử ─────────────────────────────────────────────────────────────────────
async function history() {
  const rows = await api("transfers");
  const ST = { done: ["xong", "ok"], held: ["tạm giữ", "bad"] };
  $("#history").innerHTML = rows.map((t) => `<div class="msg"><b><span>${esc(t.to_name)} <span class="tag ${ST[t.status][1]}">${ST[t.status][0]}</span></span><small>${fmtTs(t.ts)}</small></b>
      <p>${vnd(t.amount)} · ${esc(t.to_bank)} ${esc(t.to_id)}${t.note ? " · " + esc(t.note) : ""}</p></div>`).join("") || '<p class="muted">Chưa có giao dịch.</p>';
}

// mở lại phiên cũ nếu còn hạn
api("me").then(() => go("home")).catch(() => {});
