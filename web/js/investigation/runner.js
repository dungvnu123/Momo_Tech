function runInvestigate(id) {
  $("#investigate").disabled = true; $("#log").innerHTML = "";
  const es = new EventSource(`api/alerts/${id}/investigate`);
  es.onmessage = (m) => {
    const ev = JSON.parse(m.data);
    if (ev.type === "step") {
      $("#log").insertAdjacentHTML("beforeend", `<li><b>${ev.tool ? "Tool · " + esc(ev.tool) : "Giả thuyết"}</b><p>${esc(ev.thought)}</p>${ev.result ? `<p class="muted">→ ${esc(ev.result)}</p>` : ""}</li>`);
      cy?.nodes("[kind='app']").addClass("hl");
    } else if (ev.type === "case") { es.close(); showCase(ev.case); $("#investigate").disabled = false; }
  };
  es.onerror = () => { es.close(); $("#investigate").disabled = false; };
}
