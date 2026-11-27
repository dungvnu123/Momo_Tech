// path: web/app.js — giao diện Thiên La (JS thuần, không build)
const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const vnd = (n) => Number(n).toLocaleString("vi-VN") + " đ";
const num = (n) => Number(n).toLocaleString("vi-VN");
const api = async (path, body) => {
  const r = await fetch("api/" + path, body ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) } : {});
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || r.statusText);
  return r.json();
};

// ── tab ───────────────────────────────────────────────────────────────────────────
const loaded = {};
function show(tab) {
  document.querySelectorAll(".tabs button").forEach((b) => b.classList.toggle("on", b.dataset.tab === tab));
  document.querySelectorAll(".tab").forEach((s) => s.classList.toggle("on", s.id === tab));
  if (!loaded[tab]) { loaded[tab] = true; ({ overview, shield, transfer, net })[tab](); }
  try { localStorage.setItem("tab", tab); } catch {}
}
document.querySelectorAll(".tabs button").forEach((b) => (b.onclick = () => show(b.dataset.tab)));

// ── tổng quan ─────────────────────────────────────────────────────────────────────
function heroNet() {
  const g = $(".hero-net g"); let h = "";
  const pts = Array.from({ length: 18 }, (_, i) => [20 + (i % 6) * 32 + (i % 2) * 8, 20 + Math.floor(i / 6) * 45 + (i % 3) * 6]);
  pts.forEach((a, i) => pts.slice(i + 1).forEach((b) => { if (Math.hypot(a[0] - b[0], a[1] - b[1]) < 52) h += `<line x1="${a[0]}" y1="${a[1]}" x2="${b[0]}" y2="${b[1]}" stroke="white" stroke-opacity=".45"/>`; }));
  pts.forEach((p, i) => (h += `<circle cx="${p[0]}" cy="${p[1]}" r="${[3, 8, 12].includes(i) ? 6 : 3.5}" fill="${[3, 8, 12].includes(i) ? "#ffd1e8" : "white"}"/>`));
  g.innerHTML = h;
}
async function overview() {
  heroNet();
  const [o, m] = await Promise.all([api("overview"), api("metrics")]);
  $("#mode").textContent = o.ai_mode === "mock" ? "Chế độ chưa cắm AI (giả lập bằng luật)" : "AI: " + o.ai_mode;
  const steps = [[o.events, "sự kiện xử lý theo thời gian"], [o.candidates, "hồ sơ có tín hiệu (lưới rộng)"], [o.clusters, "cụm có quan hệ"],
                 [o.alerts, `cảnh báo (${o.alert_clusters} cụm, ${o.transfer_holds} giao dịch giữ)`, true],
                 [m.cases ? m.cases.fraud_flagged : "—", "hồ sơ kết luận kẻ gian", true]];
  $("#funnel").innerHTML = steps.map(([n, t, ai]) => `<div class="step ${ai ? "ai" : ""}"><b>${typeof n === "number" ? num(n) : n}</b><span>${t}</span></div>`).join("");
  if (!m.fraud) return;
  $("#compare").innerHTML = `
    <div class="stat bad"><h3>Luật cố định (gộp 5 luật)</h3><div class="big">${num(m.rules_baseline.n)}</div>hồ sơ bị gắn cờ · coi <b>${m.rules_baseline.victims_as_fraud}/${m.victims}</b> nạn nhân là kẻ gian</div>
    <div class="stat"><h3>Lớp ứng viên của Thiên La</h3><div class="big">${m.candidate.fraud}/${m.fraud}</div>gian lận · ${m.candidate.victims}/${m.victims} nạn nhân lọt vào lưới (không bỏ sót)</div>
    <div class="stat good" id="stat-last"><h3>Kết luận cuối của Thám tử</h3><div class="big">${num(m.cases.fraud_flagged)}</div>hồ sơ kết luận kẻ gian · đúng <b>${m.cases.fraud_hit}/${m.fraud}</b>, nhầm ${m.cases.benign_as_fraud} vô hại, ${m.cases.victims_as_fraud} nạn nhân · nhận ra <b>${m.cases.victims_hit}/${m.victims}</b> nạn nhân</div>`;
  const dur = (h) => h == null ? "chưa phát hiện" : h < 1 ? `${Math.round(h * 60)} phút` : h < 48 ? `${h} giờ` : `${Math.round(h / 24)} ngày`;
  $("#ttd").innerHTML = `<table class="ttd"><tr><th>Nhóm</th><th>Hồ sơ đầu tiên</th><th>Cảnh báo đầu tiên</th><th>Sau</th></tr>
    ${m.time_to_alert.map((r) => `<tr><td>${r.group} · ${esc(r.name)}</td><td>${fmtTs(r.first_seen)}</td><td>${r.first_alert ? fmtTs(r.first_alert) : "—"}</td>
      <td class="speed ${r.hours != null && r.hours <= 3 ? "fast" : "slow"}">${dur(r.hours)}</td></tr>`).join("")}</table>`;
}

// ── lá chắn ───────────────────────────────────────────────────────────────────────
const VERDICT = { scam: ["Lừa đảo", "Đừng chuyển tiền"], suspicious: ["Đáng ngờ", "Cần xác minh thêm"], safe: ["An toàn", "Không thấy dấu hiệu lừa"] };
async function shield() {
  const samples = await api("shield/samples");
  $("#shield-samples").innerHTML = samples.map((s, i) => `<button class="chip" data-i="${i}">${esc(s.label)}</button>`).join("");
  $("#shield-samples").onclick = (e) => { const i = e.target.dataset.i; if (i !== undefined) { $("#shield-text").value = samples[i].text; runShield(); } };
  $("#shield-go").onclick = runShield;
}
async function runShield() {
  const text = $("#shield-text").value.trim(); if (!text) return;
  const out = $("#shield-out"); out.classList.remove("empty"); out.innerHTML = `<p class="muted">Đang phân tích…</p>`;
  try {
    const r = await api("shield/analyze", { text });
    const [t, sub] = VERDICT[r.verdict];
    const ind = r.indicators, all = [...ind.accounts.map((x) => "TK " + x), ...ind.phones.map((x) => "SĐT/ví " + x), ...ind.urls.map((x) => "Link " + x)];
    out.innerHTML = `<div class="verdict v-${r.verdict}">${t}<small>${sub}${r.reporter_is_victim ? " · người gửi có vẻ là nạn nhân" : ""}</small></div>
      ${r.times_reported ? `<p><span class="tag hot">Đã có ${r.times_reported} người báo cùng dấu vết</span></p>` : ""}
      <h3>Vì sao</h3><ul class="reasons">${r.reasons.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>
      ${all.length ? `<h3>Dấu vết trích được</h3><p>${all.map((x) => `<span class="tag">${esc(x)}</span>`).join("")}</p>` : ""}
      <div class="advice">${esc(r.advice)}</div>`;
  } catch (e) { out.innerHTML = `<p class="muted">Chưa phân tích được: ${esc(e.message)}</p>`; }
}

// ── chuyển tiền ───────────────────────────────────────────────────────────────────
const DECISION = { hold: ["Tạm giữ giao dịch", "Chờ khách xác nhận / đội rủi ro xem"], warn: ["Cảnh báo trước khi chuyển", "Khách vẫn tự quyết"], allow: ["Cho phép", "Không làm phiền khách"] };
async function transfer() {
  const items = await api("transfer/samples");
  $("#transfer-list").innerHTML = items.map((t, i) => `<button class="item" data-i="${i}">
      <div class="row"><span>${esc(t.to_name)}</span><span>${vnd(t.amount)}</span></div>
      <small>${esc(t.to_bank)} · ${esc(t.to_id)} · ${t.minutes_after_disbursal} phút sau giải ngân khoản ${vnd(t.loan_amount)}${t.note ? ` · “${esc(t.note)}”` : ""}</small><br>
      <span class="tag">${esc(t.label)}</span></button>`).join("");
  $("#transfer-list").onclick = async (e) => {
    const b = e.target.closest(".item"); if (!b) return;
    document.querySelectorAll("#transfer-list .item").forEach((x) => x.classList.toggle("on", x === b));
    const r = await api("transfer/check", { transfer_id: items[b.dataset.i].transfer_id }), c = r.context, out = $("#transfer-out");
    const [t, sub] = DECISION[r.decision];
    out.classList.remove("empty");
    out.innerHTML = `<div class="verdict v-${r.decision}">${t}<small>${sub}</small></div>
      ${r.message_for_customer ? `<div class="phone"><h4>Thông báo trong ứng dụng ví</h4>${esc(r.message_for_customer)}</div>` : ""}
      <h3>Lý do</h3><ul class="reasons">${(r.reasons.length ? r.reasons : ["Không có dấu hiệu bất thường."]).map((x) => `<li>${esc(x)}</li>`).join("")}</ul>
      <h3>Ngữ cảnh người nhận</h3><dl class="kv">
        <dt>Trong danh bạ</dt><dd>${c.recipient_in_contacts ? `có${c.contact_saved_minutes_ago != null && c.contact_saved_minutes_ago < 1440 ? ` — vừa lưu ${c.contact_saved_minutes_ago} phút trước` : ""}` : "không"}</dd>
        <dt>Đã từng chuyển</dt><dd>${c.prior_transfers_to_recipient} lần</dd>
        <dt>SIMO (NHNN)</dt><dd>${c.simo_flag ? "<b style='color:var(--red)'>gắn cờ nghi gian lận</b>" : "không"}</dd>
        <dt>Tin báo</dt><dd>${c.times_reported} lượt</dd>
        ${c.to_wallet_age_days ? `<dt>Tuổi ví nhận</dt><dd>${c.to_wallet_age_days} ngày</dd>` : ""}
      </dl><p class="note">Danh bạ được so khớp ngay trên máy khách, chỉ gửi lên cờ có/không và thời điểm lưu.</p>`;
  };
}

// ── lưới & thám tử: hàng đợi cảnh báo theo thời gian ─────────────────────────────────
const SIG = { ref_hub: "tham chiếu chung", ip_block: "dải IP VPN", sim_block: "lô SIM mới", emulator: "giả lập", ekyc: "eKYC bất thường",
              fast_out_stranger: "rút tiền cho người lạ", shared_recipient: "nơi nhận chung", device_hub: "thiết bị chung", simo: "SIMO" };
const SEV = { khan: "Khẩn", cao: "Cao", tb: "Trung bình" };
const VERD = { fraud_ring: ["Đường dây", "hot"], victims: ["Nạn nhân", ""], benign: ["Vô hại", ""] };
const F = { day: "", sev: new Set(), kind: "", verdict: "", min_conf: 0, latest: true, q: "", sort: "priority" };
const fmtTs = (ts) => `${ts.slice(11, 16)} · ${ts.slice(8, 10)}/${ts.slice(5, 7)}`;
let cy, current, liveES;

async function net() {
  const days = await api("alerts/days");
  const max = Math.max(...days.map((d) => d.n), 1);
  $("#days").innerHTML = days.map((d) => `<button data-day="${d.day}" title="${d.day}: ${d.n} cảnh báo (${d.khan} khẩn)">
      ${["tb", "cao", "khan"].map((k) => `<i class="${k}" style="height:${(d[k] / max) * 100}%"></i>`).join("")}</button>`).join("");
  $("#days").onclick = (e) => { const b = e.target.closest("button"); if (b) setDay(b.dataset.day); };
  $("#day-all").onclick = () => setDay("");
  document.querySelectorAll(".chip.sev").forEach((b) => (b.onclick = () => { b.classList.toggle("on"); F.sev.has(b.dataset.sev) ? F.sev.delete(b.dataset.sev) : F.sev.add(b.dataset.sev); loadAlerts(); }));
  $("#f-kind").onchange = (e) => { F.kind = e.target.value; loadAlerts(); };
  $("#f-verdict").onchange = (e) => { F.verdict = e.target.value; loadAlerts(); };
  $("#f-conf").oninput = (e) => { F.min_conf = +e.target.value; $("#f-conf-v").textContent = Math.round(F.min_conf * 100) + "%"; };
  $("#f-conf").onchange = loadAlerts;
  $("#f-latest").onchange = (e) => { F.latest = e.target.checked; loadAlerts(); };
  let tq; $("#f-q").oninput = (e) => { clearTimeout(tq); tq = setTimeout(() => { F.q = e.target.value.trim(); loadAlerts(); }, 300); };
  $("#f-sort").onchange = (e) => { F.sort = e.target.value; loadAlerts(); };
  $("#alert-list").onclick = (e) => { const b = e.target.closest(".item"); if (b) openAlert(b.dataset.id, b); };
  $("#investigate").onclick = () => runInvestigate(current);
  $("#live-btn").onclick = toggleLive;
  await loadAlerts(true);
}
function setDay(day) {
  F.day = day;
  document.querySelectorAll("#days button").forEach((b) => b.classList.toggle("on", b.dataset.day === day));
  $("#day-all").classList.toggle("sel", !day);
  $("#day-chip").hidden = !day; $("#day-chip").textContent = day ? `Ngày ${day.slice(8, 10)}/${day.slice(5, 7)}/${day.slice(0, 4)}` : "";
  loadAlerts();
}
function alertItem(a, fresh) {
  const v = VERD[a.verdict];
  return `<button class="item${fresh ? " fresh" : ""}" data-id="${a.alert_id}">
    <div class="row"><span class="t">${fmtTs(a.ts)}</span><span class="sev-b sev-${a.severity}">${SEV[a.severity]}</span></div>
    <div class="ttl">${esc(a.title)}</div>
    <div class="bar" title="Độ tin cậy ${Math.round(a.conf * 100)}%"><i style="width:${Math.round(a.conf * 100)}%"></i></div>
    <small>${a.cid || "giao dịch"} · ${a.size} hồ sơ${a.n_pending ? ` · <b>${a.n_pending} chờ giải ngân</b>` : ""}${a.n_reports ? ` · ${a.n_reports} tin báo` : ""} · tin cậy ${Math.round(a.conf * 100)}%</small>
    <div>${v ? `<span class="tag ${v[1]}">${v[0]}</span>` : `<span class="tag">Chưa điều tra</span>`}${a.signals.slice(0, 3).map((k) => `<span class="tag">${SIG[k] || k}</span>`).join("")}</div></button>`;
}
async function loadAlerts(openFirst) {
  const p = new URLSearchParams({ sort: F.sort, latest: F.latest, limit: 150 });
  if (F.day) p.set("day", F.day);
  if (F.sev.size) p.set("severity", [...F.sev].join(","));
  if (F.kind) p.set("kind", F.kind);
  if (F.verdict) p.set("verdict", F.verdict);
  if (F.min_conf) p.set("min_conf", F.min_conf);
  if (F.q) p.set("q", F.q);
  const r = await api("alerts?" + p);
  $("#list-sub").textContent = `${num(r.total)} cảnh báo${r.total > r.items.length ? ` · hiện ${r.items.length} đầu` : ""}`;
  $("#alert-list").innerHTML = r.items.map((a) => alertItem(a)).join("") || `<p class="muted">Không có cảnh báo khớp bộ lọc.</p>`;
  if (openFirst && r.items[0]) openAlert(r.items[0].alert_id, $("#alert-list .item"));
}

const COLOR = { app: "#a50064", dev: "#7b5ea7", ref: "#2f80c0", rcv: "#d6334f", ip: "#c77700", sim: "#c77700" };
async function openAlert(id, btn) {
  current = id;
  document.querySelectorAll("#alert-list .item").forEach((x) => x.classList.toggle("on", x === btn));
  const d = await api("alerts/" + id), a = d.alert;
  $("#cl-title").textContent = a.title;
  $("#cl-sub").textContent = `${fmtTs(a.ts)} · ${a.cid || "giao dịch " + a.transfer_id} · ${SEV[a.severity]} · ${d.money_flow} · ${a.reason}`;
  $("#history").innerHTML = d.history.length > 1 ? "Diễn biến cụm: " + d.history.map((h) => `<span class="${h.alert_id === id ? "cur" : ""}" title="${esc(h.title)}">${fmtTs(h.ts)}</span>`).join("") : "";
  $("#investigate").disabled = false;
  $("#log").innerHTML = "";
  if (d.case) showCase(d.case, true); else { $("#case").className = "case empty"; $("#case").textContent = "Bấm “Điều tra” để agent xem xét — chỉ dùng dữ liệu tới thời điểm cảnh báo."; }
  cy?.destroy();
  cy = cytoscape({ container: $("#graph"), elements: d.graph, layout: { name: "cose", animate: false, padding: 24 },
    style: [
      { selector: "node", style: { "background-color": (n) => COLOR[n.data("kind")] || "#999", label: "data(label)", "font-size": 9,
          "text-wrap": "wrap", color: "#2b1a24", "text-valign": "bottom", "text-margin-y": 4, width: 16, height: 16, "font-family": "Be Vietnam Pro" } },
      { selector: "node[kind='app']", style: { width: 24, height: 24, "border-width": 3, "border-color": "#fff" } },
      { selector: "node[status='PENDING']", style: { "border-color": "#ffb020" } },
      { selector: "edge", style: { width: 1.5, "line-color": "#e8b5cf", "curve-style": "bezier" } },
      { selector: ".hl", style: { "border-width": 4, "border-color": "#d82d8b" } },
      { selector: ".victim", style: { "background-color": "#1c8a5a" } },
    ] });
  if (d.case) d.case.victims.forEach((x) => cy.$id(x).addClass("victim"));
  $("#dossier").hidden = true;
  cy.on("tap", "node[kind='app']", (e) => openDossier(e.target.id(), a.ts));
}
async function openDossier(appId, asOf) {
  const r = await api(`apps/${appId}?as_of=${encodeURIComponent(asOf)}`), p = r.profile, box = $("#dossier");
  box.hidden = false;
  box.innerHTML = `<header><div><b>${esc(p.app_id)} · ${esc(p.full_name)}</b>
      <span class="dpd ${r.dpd ? "bad" : "ok"}">${r.dpd ? `quá hạn ${r.dpd} ngày` : "chưa quá hạn"}</span>
      <div class="muted" style="margin:2px 0 0">SĐT/ví ${esc(p.phone)} · CCCD ${esc(p.cccd)} · ví ${p.wallet_age_days} ngày tuổi · eKYC ${p.ekyc_attempts} lần (liveness ${p.liveness_score})
      · điền đơn ${p.fill_time_sec} giây — <i>tính tới ${fmtTs(asOf)}</i></div></div><button aria-label="Đóng" id="dossier-x">×</button></header>
    <ol class="tl">${r.events.map((e) => `<li class="${e.type}"><time>${fmtTs(e.ts)}</time><b>${esc(e.title)}</b>${e.detail ? `<small>${esc(e.detail)}</small>` : ""}</li>`).join("")}</ol>`;
  $("#dossier-x").onclick = () => (box.hidden = true);
  box.scrollIntoView({ behavior: "smooth", block: "nearest" });
}
function runInvestigate(id) {
  $("#investigate").disabled = true; $("#log").innerHTML = "";
  const es = new EventSource(`api/alerts/${id}/investigate`);
  es.onmessage = (m) => {
    const ev = JSON.parse(m.data);
    if (ev.type === "step") {
      $("#log").insertAdjacentHTML("beforeend", `<li><b>${ev.tool ? "Tool · " + esc(ev.tool) : "Giả thuyết"}</b><p>${esc(ev.thought)}</p>${ev.result ? `<p class="muted">→ ${esc(ev.result)}</p>` : ""}</li>`);
      cy?.nodes("[kind='app']").addClass("hl");
    } else if (ev.type === "case") { es.close(); showCase(ev.case); $("#investigate").disabled = false; }
  };
  es.onerror = () => { es.close(); $("#investigate").disabled = false; };
}
const V = { fraud_ring: ["Đường dây gian lận", "v-scam"], victims: ["Nạn nhân bị lừa", "v-warn"], benign: ["Vô hại", "v-safe"], inconclusive: ["Chưa đủ căn cứ", "v-suspicious"] };
function showCase(c, cached) {
  const [t, cls] = V[c.verdict];
  cy?.nodes().removeClass("hl"); c.victims.forEach((x) => cy?.$id(x).addClass("victim"));
  $("#case").className = "case";
  $("#case").innerHTML = `<div class="verdict ${cls}">${t}<small>${c.ring_type ? esc(c.ring_type) + " · " : ""}tin cậy ${Math.round(c.confidence * 100)}%${c.mode === "mock" ? " · giả lập" : ""}${cached ? " · đã điều tra sẵn" : ""}</small></div>
    ${c.members.length ? `<p><b>Kẻ gian:</b> ${c.members.map((x) => `<span class="tag hot">${x}</span>`).join("")}</p>` : ""}
    ${c.victims.length ? `<p><b>Nạn nhân cần bảo vệ:</b> ${c.victims.map((x) => `<span class="tag">${x}</span>`).join("")}</p>` : ""}
    <h3>Việc cần làm</h3><ul class="reasons">${c.actions.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>`;
}

// ── phát realtime ─────────────────────────────────────────────────────────────────
function toggleLive() {
  const btn = $("#live-btn");
  if (liveES) { liveES.close(); liveES = null; btn.classList.remove("on"); btn.textContent = "▶ Phát realtime"; loadAlerts(); return; }
  btn.classList.add("on"); btn.textContent = "⏸ Dừng";
  $("#alert-list").innerHTML = ""; $("#list-sub").textContent = "Đang phát realtime từ 01/11 — cảnh báo hiện ra đúng lúc bộ máy sinh ra.";
  let n = 0;
  liveES = new EventSource(`api/live?start=2026-11-01&day_seconds=${$("#speed").value}`);
  liveES.onmessage = (m) => {
    const d = JSON.parse(m.data);
    $("#clock").textContent = `${d.clock.slice(11, 16)} · ${d.clock.slice(8, 10)}/${d.clock.slice(5, 7)}/${d.clock.slice(0, 4)}`;
    d.alerts.forEach((a) => { n++; $("#alert-list").insertAdjacentHTML("afterbegin", alertItem(a, true)); });
    if (d.alerts.length) $("#list-sub").textContent = `${n} cảnh báo từ 01/11 tới giờ`;
    if (d.done) toggleLive();
  };
}


let start = "overview";
try { start = localStorage.getItem("tab") || start; } catch {}
show(["overview", "shield", "transfer", "net"].includes(start) ? start : "overview");
