SIG_VI = {
    "ref_hub": "chung SĐT tham chiếu",
    "device_hub": "dùng chung thiết bị",
    "ip_block": "cùng dải IP VPN/datacenter",
    "sim_block": "SIM cùng lô mới kích hoạt",
    "emulator": "máy giả lập",
    "ekyc": "phiên eKYC bất thường",
    "fast_out_stranger": "rút gần hết tiền vay cho người lạ",
    "shared_recipient": "đổ tiền về cùng tài khoản",
    "simo": "người nhận bị SIMO gắn cờ",
    "fpd_cluster": "cùng quá hạn ngay kỳ đầu",
}


def _title(cause, new, n, n_reports, prev, signals):
    if cause == "fpd" and "fpd_cluster" in new:
        return f"{n} hồ sơ liên quan cùng quá hạn ngay kỳ đầu"
    if cause == "report" and n_reports:
        return f"Tin báo mới nối vào {n} khoản vay — tổng {n_reports} tin báo"
    if "shared_recipient" in new:
        return f"{n} ví vừa vay đã đổ tiền về cùng tài khoản"
    if new:
        return f"{n} hồ sơ: {', '.join((SIG_VI[k] for k in new))}"
    if prev and n > prev[2]:
        return (
            f"Cụm lớn thêm: {n} hồ sơ ({', '.join((SIG_VI[k] for k, v in signals.items() if v))})"
        )
    return f"{n} hồ sơ có thay đổi"
