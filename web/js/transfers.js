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
