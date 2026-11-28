let loginWait = null;
function askLogin() {
  if (loginWait) return loginWait;
  // Chế độ demo (DEMO_AUTOFILL): server trả sẵn mật khẩu → tự đăng nhập, không hiện hộp mật khẩu
  loginWait = fetch("api/me").then((r) => r.json()).then(async (m) => {
    if (!m.demo_password) return manualLogin();
    await api("login", { password: m.demo_password }, true);
    $("#logout").hidden = false; loginWait = null;
  }).catch((e) => { loginWait = null; throw e; });
  return loginWait;
}
function manualLogin() {
  const dlg = $("#login");
  loginWait = new Promise((resolve, reject) => {
    dlg.oncancel = () => { loginWait = null; reject(new Error("Cần đăng nhập để xem phần này")); };   // Esc = huỷ, không treo
    $("#login-form").onsubmit = async (e) => {
      e.preventDefault();
      try {
        await api("login", { password: $("#login-pw").value }, true);
        $("#login-pw").value = ""; $("#login-err").hidden = true; dlg.close(); $("#logout").hidden = false;
        loginWait = null; resolve();
      } catch (err) { $("#login-err").hidden = false; $("#login-err").textContent = err.message; }
    };
  });
  dlg.showModal();
  return loginWait;
}
$("#logout").onclick = async () => { await api("logout", {}); location.reload(); };
api("me").then((m) => { $("#logout").hidden = !(m.auth_required && m.logged_in); }).catch(() => {});
