// Rendering stays separate from network/controller code. All source text is escaped.
function renderCaseEvidence(evidence, item, escape) {
  const step = (item.tool_steps || []).find((s) => s.tool_call_id === evidence.source);
  const data = step?.result?.data;
  const ids = evidence.record_ids || [];
  let source = data;
  if (data && ids.length) {
    source = {
      records: [...(data.application_summaries || []), ...(data.transfers || []), ...(data.reports || [])]
        .filter((r) => ids.includes(r.record_id)),
      as_of: data.as_of, coverage: data.coverage,
    };
  }
  return `<details class="case-evidence"><summary>${escape(evidence.claim)} <small>· Xem nguồn ${escape(evidence.source)}</small></summary>
    ${ids.length ? `<p>Mã bản ghi: ${ids.map(escape).join(", ")}</p>` : ""}
    ${step ? `<p>Tool: ${escape(step.name)}</p><pre>${escape(JSON.stringify(source, null, 2))}</pre>` :
      `<p>Chưa có dấu vết tool trong kết quả này; cần mở trace của phiên để kiểm chứng.</p>`}</details>`;
}

function renderCaseAssessments(item, escape) {
  if (!item.cluster_assessment) return "";
  const cluster = item.cluster_assessment;
  const roles = { suspected_participant: "Nghi liên quan phối hợp", possible_victim: "Có dấu hiệu bị hại",
    no_adverse_evidence: "Chưa thấy bằng chứng bất lợi", undetermined: "Chưa xác định vai trò" };
  const assessments = item.application_assessments || [];
  const assessed = assessments.filter((a) => a.assessment_status !== "not_assessed");
  const pending = assessments.filter((a) => a.assessment_status === "not_assessed");
  const profile = (app) => item.as_of ? `<button class="chip" data-assessment-app="${escape(app)}">Xem hồ sơ ${escape(app)}</button>` : escape(app);
  return `<section class="cluster-assessment"><h3>Đánh giá cụm · chưa xác minh</h3><p>${escape(cluster.reason)}</p>
    ${cluster.evidence.map((e) => renderCaseEvidence(e, item, escape)).join("")}
    ${cluster.limitations?.length ? `<h4>Giới hạn bằng chứng</h4><ul>${cluster.limitations.map((s) => `<li>${escape(s)}</li>`).join("")}</ul>` : ""}</section>
    <section class="application-assessments"><h3>Vai trò từng hồ sơ</h3><p>Đã đánh giá riêng ${assessed.length}/${assessments.length} hồ sơ. Các nhận định bên dưới đều chưa xác minh.</p>
    ${assessed.map((a) => `<article class="application-assessment"><h4>${profile(a.app_id)} · ${escape(roles[a.role] || a.role)}</h4>
      <p>${escape(a.reason)}</p>${a.evidence.map((e) => renderCaseEvidence(e, item, escape)).join("")}
      ${a.missing_information?.length ? `<p><b>Cần xác minh:</b></p><ul>${a.missing_information.map((s) => `<li>${escape(s)}</li>`).join("")}</ul>` : ""}</article>`).join("")}
    ${pending.length ? `<details class="unassessed-applications"><summary>${pending.length} hồ sơ chưa được đánh giá riêng</summary>
      <p>Chưa gán vai trò dựa vào rủi ro chung của cụm.</p>${pending.map((a) => `<p>${profile(a.app_id)} · Chưa đánh giá</p>`).join("")}</details>` : ""}</section>`;
}
