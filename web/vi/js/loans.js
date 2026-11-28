function loanScreen() { if (ME) $("#loan-amt").value = ME.loan.amount; }
$("#loan-form").onsubmit = async (e) => {
  e.preventDefault();
  try { await api("loan", { amount: Number(digits($("#loan-amt").value)) }); go("home"); } catch (err) { alert(err.message); }
};
