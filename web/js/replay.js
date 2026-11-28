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
