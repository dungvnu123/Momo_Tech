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
