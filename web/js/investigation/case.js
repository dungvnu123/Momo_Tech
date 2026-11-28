const V = { fraud_ring: ["Nghi vấn gian lận", "v-scam"], victims: ["Có dấu hiệu bị hại", "v-warn"], benign: ["Chưa thấy bất thường", "v-safe"], inconclusive: ["Chưa đủ căn cứ", "v-suspicious"] };
function showCase(c, cached) {
  const incomplete = c.status && c.status !== "completed";
  const clusterLevels = { suspicious: ["Cụm đáng điều tra", "v-warn"], no_pattern_observed: ["Chưa thấy mẫu bất thường trong dữ liệu đã đọc", "v-safe"], insufficient_data: ["Chưa đủ dữ liệu đánh giá cụm", "v-suspicious"] };
  const [t, cls] = incomplete ? ["Phiên điều tra chưa hoàn thành", "v-suspicious"] : c.cluster_assessment ? clusterLevels[c.cluster_assessment.level] : V[c.verdict];
  cy?.nodes().removeClass("hl"); c.victims.forEach((x) => cy?.$id(x).addClass("victim"));
  $("#case").className = "case";
  const certainty = incomplete ? "Chưa có kết luận mới. Hãy thử lại hoặc kiểm tra kết nối AI." : c.cluster_assessment ? "Nhận định chưa xác minh · đánh giá cụm và vai trò từng hồ sơ được trình bày riêng." : c.verdict === "inconclusive" ? "Vai trò người vay chưa xác định; xem đánh giá giao dịch bên dưới." : `Mức tự đánh giá của model: ${Math.round(c.confidence * 100)}% · chưa hiệu chuẩn`;
  const recommendation = { allow: "Không đề xuất cảnh báo thêm", warn: "Đề xuất cảnh báo khách", hold: "Đề xuất tạm giữ để xác minh", review: "Cần người kiểm tra" };
  $("#case").innerHTML = `<div class="verdict ${cls}">${t}<small>${certainty}${c.mode === "mock" ? " · giả lập" : ""}${cached ? " · đã lưu" : ""}</small></div>
    ${c.summary ? `<p>${esc(c.summary)}</p>` : ""}
    ${renderCaseAssessments(c, esc)}
    ${(c.transaction_assessments || []).map((a) => `<div class="transaction-assessment"><h3>${esc(recommendation[a.recommendation] || a.recommendation)} · ${esc(a.transfer_id)}</h3><p>${esc(a.reason)}</p>${a.evidence?.length ? `<ul>${a.evidence.map((e) => `<li>${esc(e.claim)} <small>[${esc(e.source)}]</small></li>`).join("")}</ul>` : ""}<small>Đề xuất để người có thẩm quyền xem xét, chưa thực hiện giữ tiền.</small></div>`).join("")}
    ${!c.cluster_assessment && c.members.length ? `<p><b>Hồ sơ nghi liên quan:</b> ${c.members.map((x) => `<span class="tag hot">${x}</span>`).join("")}</p>` : ""}
    ${!c.cluster_assessment && c.victims.length ? `<p><b>Hồ sơ có dấu hiệu bị hại:</b> ${c.victims.map((x) => `<span class="tag">${x}</span>`).join("")}</p>` : ""}
    ${c.evidence?.length ? `<h3>Bằng chứng đã đọc</h3><ul class="reasons">${c.evidence.map((x) => `<li>${esc(typeof x === "string" ? x : x.claim)}</li>`).join("")}</ul>` : ""}
    ${c.benign_explanation ? `<h3>Giải thích vô hại đã cân nhắc</h3><p>${esc(c.benign_explanation)}</p>` : ""}
    ${c.missing_information?.length ? `<h3>Thông tin còn thiếu</h3><ul class="reasons">${c.missing_information.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>` : ""}
    <h3>Việc cần làm</h3><ul class="reasons">${c.actions.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>`;
  document.querySelectorAll("[data-assessment-app]").forEach((button) => {
    button.onclick = () => openDossier(button.dataset.assessmentApp, c.as_of);
  });
}
