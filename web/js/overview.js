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
  $("#mode").textContent = o.ai_mode === "mock" ? "Chế độ chưa cắm AI (giả lập bằng luật)" : "AI: " + o.ai_mode + (o.cached_cases_mode === "mock" ? " · kết quả dựng sẵn: giả lập" : "");
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
