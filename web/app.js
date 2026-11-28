let start = "overview";
try { start = localStorage.getItem("tab") || start; } catch {}
show(["overview", "shield", "transfer", "net"].includes(start) ? start : "overview");
