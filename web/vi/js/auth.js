let DEMO = [];
fetch("../api/khach/demo").then((r) => r.json()).then((d) => {
  DEMO = d;
  if (d.length) $("#demo-phones").innerHTML = (d[0]?.pin ? '<span class="muted">Chế độ demo: bấm 1 khách để đăng nhập luôn.</span>' : "")
    + d.map((x, i) => `<a href="#" class="persona" data-i="${i}"><b>${esc(x.name)}</b> · ${esc(x.phone)}<small>${esc(x.scenario || "")}</small></a>`).join("");
}).catch(() => {});
$("#demo-phones").onclick = (e) => {
  const a = e.target.closest("[data-i]"); if (!a) return;
  e.preventDefault();
  const x = DEMO[a.dataset.i];
  $("#l-phone").value = x.phone;
  if (x.pin) { $("#l-pin").value = x.pin; $("#login-form").requestSubmit(); } else $("#l-pin").focus();   // demo: tự điền PIN + đăng nhập
};
$("#login-form").onsubmit = async (e) => {
  e.preventDefault();
  try { await api("login", { phone: digits($("#l-phone").value), pin: digits($("#l-pin").value) }); $("#l-pin").value = ""; $("#l-err").hidden = true; go("home"); }
  catch (err) { $("#l-err").hidden = false; $("#l-err").textContent = err.message; }
};
$("#logout").onclick = async () => { await api("logout", {}); go("login"); };
