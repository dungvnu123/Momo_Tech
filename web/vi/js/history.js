async function history() {
  const rows = await api("transfers");
  const ST = { done: ["xong", "ok"], held: ["tạm giữ", "bad"] };
  $("#history").innerHTML = rows.map((t) => `<div class="msg"><b><span>${esc(t.to_name)} <span class="tag ${ST[t.status][1]}">${ST[t.status][0]}</span></span><small>${fmtTs(t.ts)}</small></b>
      <p>${vnd(t.amount)} · ${esc(t.to_bank)} ${esc(t.to_id)}${t.note ? " · " + esc(t.note) : ""}</p></div>`).join("") || '<p class="muted">Chưa có giao dịch.</p>';
}
