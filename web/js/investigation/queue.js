async function net() {
  const days = await api("alerts/days");
  const max = Math.max(...days.map((d) => d.n), 1);
  $("#days").innerHTML = days.map((d) => `<button data-day="${d.day}" title="${d.day}: ${d.n} cảnh báo (${d.khan} khẩn)">
      ${["tb", "cao", "khan"].map((k) => `<i class="${k}" style="height:${(d[k] / max) * 100}%"></i>`).join("")}</button>`).join("");
  $("#days").onclick = (e) => { const b = e.target.closest("button"); if (b) setDay(b.dataset.day); };
  // nhãn ngày dưới biểu đồ: đầu mỗi tháng + mỗi 7 ngày
  $("#days-axis").innerHTML = days.map((d, i) => (i === 0 || d.day.endsWith("-01") || i % 7 === 0)
    ? `<span style="left:${((i + 0.5) / days.length) * 100}%">${d.day.slice(8, 10)}/${d.day.slice(5, 7)}</span>` : "").join("");
  $("#hours-axis").innerHTML = Array.from({ length: 24 }, (_, h) => `<span>${h % 3 === 0 ? h + "h" : ""}</span>`).join("");
  $("#hours").onclick = (e) => { const b = e.target.closest("button"); if (b) setHours(+b.dataset.h, +b.dataset.h + 1); };
  document.querySelectorAll(".hchips .chip").forEach((b) => (b.onclick = () => { const [a, z] = b.dataset.h.split("-").map(Number); setHours(a, z); }));
  loadHours();
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
  simInit();
  // cảnh báo phát sinh trực tiếp từ app khách → tự làm mới danh sách (khi đang mở màn này, không ở chế độ phát lại)
  let lastTop = "", lastEvents = "";
  setInterval(async () => {
    if (liveES || !$("#net").classList.contains("on") || document.hidden) return;
    try {
      const r = await api("alerts?sort=time&limit=1&latest=false"), top = r.items[0]?.alert_id || "";
      if (lastTop && top !== lastTop) { await loadAlerts(); $("#list-sub").textContent += " · có cảnh báo mới"; }
      lastTop = top;
      const events = await api("ai/realtime/events?limit=20");
      const signature = JSON.stringify(events.map((e) => [e.event_id,e.status]));
      if (lastEvents && signature !== lastEvents) {
        await loadAlerts();
        if (current && !$("#investigate").disabled) {
          const updated = events.some((e) => e.status === "completed" && e.result && JSON.parse(e.result).alert_id === current);
          if (updated) {
            const detail = await api("alerts/" + current);
            if (detail.case) showCase(detail.case,true);
          }
        }
      }
      lastEvents = signature;
    } catch {}
  }, 15000);
}
function setDay(day) {
  F.day = day;
  document.querySelectorAll("#days button").forEach((b) => b.classList.toggle("on", b.dataset.day === day));
  $("#day-all").classList.toggle("sel", !day);
  $("#day-chip").hidden = !day; $("#day-chip").textContent = day ? `Ngày ${day.slice(8, 10)}/${day.slice(5, 7)}/${day.slice(0, 4)}` : "";
  loadHours(); loadAlerts();
}
async function loadHours() {
  const hs = await api("alerts/hours" + (F.day ? `?day=${F.day}` : "")), max = Math.max(...hs.map((h) => h.n), 1);
  const night = hs.slice(0, 6).reduce((s, h) => s + h.n, 0), all = hs.reduce((s, h) => s + h.n, 0);
  $("#hours-sub").textContent = `${F.day ? "ngày " + F.day.slice(8, 10) + "/" + F.day.slice(5, 7) : "mọi ngày"} · ${all} cảnh báo, ${night} lúc 0–6h`;
  $("#hours").innerHTML = hs.map((h) => `<button data-h="${h.h}" title="${h.h}h–${h.h + 1}h: ${h.n} cảnh báo (${h.khan} khẩn)"
      class="${h.h >= F.h0 && h.h < F.h1 && (F.h1 - F.h0 < 24) ? "on" : ""}${F.h1 - F.h0 < 24 && (h.h < F.h0 || h.h >= F.h1) ? " dim" : ""}">
      ${["tb", "cao", "khan"].map((k) => `<i class="${k}" style="height:${(h[k] / max) * 100}%"></i>`).join("")}</button>`).join("");
}
function setHours(a, z) {
  [F.h0, F.h1] = F.h0 === a && F.h1 === z && z - a === 1 ? [0, 24] : [a, z];   // bấm lại cùng 1 giờ = bỏ lọc
  document.querySelectorAll(".hchips .chip").forEach((b) => b.classList.toggle("sel", b.dataset.h === `${F.h0}-${F.h1}`));
  loadHours(); loadAlerts();
}
function alertItem(a, fresh) {
  const v = VERD[a.verdict];
  const confidenceText = a.verdict === "inconclusive" ? "vai trò chưa xác định" : a.case_conf == null ? `điểm sàng lọc ${Math.round(a.conf * 100)}/100` : `model tự đánh giá ${Math.round(a.conf * 100)}%`;
  return `<button class="item${fresh ? " fresh" : ""}" data-id="${a.alert_id}">
    <div class="row"><span class="t">${fmtTs(a.ts)}</span><span class="sev-b sev-${a.severity}">${SEV[a.severity]}</span></div>
    <div class="ttl">${esc(a.title)}</div>
    ${a.verdict === "inconclusive" ? "" : `<div class="bar" title="${confidenceText}"><i style="width:${Math.round(a.conf * 100)}%"></i></div>`}
    <small>${a.cid || "giao dịch"} · ${a.size} hồ sơ${a.n_pending ? ` · <b>${a.n_pending} chờ giải ngân</b>` : ""}${a.n_reports ? ` · ${a.n_reports} tin báo` : ""} · ${confidenceText}</small>
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
  if (F.h1 - F.h0 < 24) { p.set("hour_from", F.h0); p.set("hour_to", F.h1); }
  const r = await api("alerts?" + p);
  $("#list-sub").textContent = `${num(r.total)} cảnh báo${r.total > r.items.length ? ` · hiện ${r.items.length} đầu` : ""}`;
  $("#alert-list").innerHTML = r.items.map((a) => alertItem(a)).join("") || `<p class="muted">Không có cảnh báo khớp bộ lọc.</p>`;
  if (openFirst && r.items[0]) openAlert(r.items[0].alert_id, $("#alert-list .item"));
}
