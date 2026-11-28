const SIG = { ref_hub: "tham chiếu chung", ip_block: "dải IP VPN", sim_block: "lô SIM mới", emulator: "giả lập", ekyc: "eKYC bất thường",
              fast_out_stranger: "rút tiền cho người lạ", shared_recipient: "nơi nhận chung", device_hub: "thiết bị chung", simo: "SIMO" };
const SEV = { khan: "Khẩn", cao: "Cao", tb: "Trung bình" };
const VERD = { fraud_ring: ["Đường dây", "hot"], victims: ["Nạn nhân", ""], benign: ["Vô hại", ""] };
const F = { day: "", sev: new Set(), kind: "", verdict: "", min_conf: 0, latest: true, q: "", sort: "priority", h0: 0, h1: 24 };
const fmtTs = (ts) => `${ts.slice(11, 16)} · ${ts.slice(8, 10)}/${ts.slice(5, 7)}`;
let cy, current, liveES;
