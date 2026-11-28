const VERDICT = { scam: ["Lừa đảo", "Đừng chuyển tiền"], suspicious: ["Đáng ngờ", "Cần xác minh thêm"], safe: ["An toàn", "Không thấy dấu hiệu lừa"] };
async function shield() {
  $("#shield-go").onclick = runShield;
  const container = $("#shield-samples");
  try {
    const samples = await api("shield/samples");
    container.innerHTML = samples.map((s, i) => `<button class="chip" data-i="${i}">${esc(s.label)}</button>`).join("");
    container.onclick = (e) => { const i = e.target.closest("[data-i]")?.dataset.i; if (i !== undefined && samples[i]) { $("#shield-text").value = samples[i].text; runShield(); } };
  } catch (e) {
    container.innerHTML = `<p class="muted">Chưa tải được tin mẫu. Bạn vẫn có thể nhập tin nhắn để kiểm tra. <button class="chip" id="shield-retry">Thử tải lại</button></p>`;
    $("#shield-retry").onclick = shield;
  }
}
async function runShield() {
  const button = $("#shield-go");
  if (button.disabled) return;
  const text = $("#shield-text").value.trim();
  const out = $("#shield-out"); out.classList.remove("empty");
  if (!text) { out.innerHTML = `<p class="muted">Vui lòng nhập nội dung tin nhắn cần kiểm tra.</p>`; return; }
  button.disabled = true;
  out.innerHTML = `<p class="muted">Đang phân tích…</p>`;
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
  finally { button.disabled = false; }
}
