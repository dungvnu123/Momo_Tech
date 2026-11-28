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
