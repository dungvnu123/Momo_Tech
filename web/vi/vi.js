// mở lại phiên cũ nếu còn hạn
api("me").then(() => go("home")).catch(() => {});
