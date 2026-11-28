const COLOR = { app: "#a50064", dev: "#7b5ea7", ref: "#2f80c0", rcv: "#d6334f", ip: "#c77700", sim: "#c77700" };
async function openAlert(id, btn) {
  current = id;
  document.querySelectorAll("#alert-list .item").forEach((x) => x.classList.toggle("on", x === btn));
  const d = await api("alerts/" + id), a = d.alert;
  $("#cl-title").textContent = a.title;
  $("#cl-sub").textContent = `${fmtTs(a.ts)} · ${a.cid || "giao dịch " + a.transfer_id} · ${SEV[a.severity]} · ${d.money_flow} · ${a.reason}`;
  const H = d.history, chip = (h) => `<span class="${h.alert_id === id ? "cur" : ""}" title="${esc(h.title)}">${fmtTs(h.ts)}</span>`;
  const shown = H.length > 8 ? [H[0], null, ...H.slice(-6)] : H;   // gọn: mốc đầu + 6 mốc cuối
  $("#history").innerHTML = H.length > 1 ? `Diễn biến cụm (${H.length} lần): ` + shown.map((h) => h ? chip(h) : `<span>… ${H.length - 7} lần nữa</span>`).join("") : "";
  $("#investigate").disabled = false;
  $("#log").innerHTML = "";
  if (d.case) showCase(d.case, true); else { $("#case").className = "case empty"; $("#case").textContent = "Bấm “Điều tra” để agent xem xét — chỉ dùng dữ liệu tới thời điểm cảnh báo."; }
  cy?.destroy();
  cy = cytoscape({ container: $("#graph"), elements: d.graph, layout: { name: "cose", animate: false, padding: 24 },
    minZoom: 0.3, maxZoom: 3, wheelSensitivity: 0.2,   // không cho zoom ra tới mức đồ thị "biến mất"
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
  cy.on("dbltap", (e) => { if (e.target === cy) fitGraph(); });
}
function fitGraph() { if (cy) { cy.resize(); cy.fit(undefined, 24); } }
// khung đổi kích thước (thu nhỏ cửa sổ, zoom trình duyệt, đổi bố cục) → vẽ lại + căn giữa
new ResizeObserver(() => fitGraph()).observe($("#graph"));
$("#fit").onclick = fitGraph;
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
