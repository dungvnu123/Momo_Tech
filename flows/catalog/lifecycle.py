from flows.common import Flow, GROUP, color, set_step


def vong_doi():
    f = Flow("thienla-vong-doi-ho-so", "Vòng đời 1 hồ sơ vay — mỗi bước là 1 bảng có mốc thời gian")
    f.group = GROUP
    f.meta(
        subtitle="Nộp → eKYC → duyệt → giải ngân → chuyển tiền → đến hạn → trả hoặc quá hạn. Quá hạn tính TẠI từng thời điểm.",
        duration="dữ liệu",
        level="Nền tảng",
        learn=[
            "Không có cột 'quá hạn' chốt sẵn — tính từ lịch trả + các lần trả",
            "Mỗi bước để lại dấu vết riêng: eKYC, dòng tiền, tin báo",
            "Bộ máy chỉ được thấy bước đã xảy ra tới thời điểm đang xét",
        ],
    )
    s = f.start()
    sub = f.process(
        "Nộp hồ sơ",
        step=1,
        icon="user",
        badge="applications",
        explain="applied_at + thông tin khai báo + tín hiệu kỹ thuật lúc nộp: thiết bị, IP (di động/nhà/VPN/datacenter), tuổi SIM, giả lập, thời gian điền đơn.",
    )
    ekyc = f.process(
        "eKYC khuôn mặt",
        step=2,
        icon="lock",
        badge="ekyc_sessions",
        explain="Mỗi lần thử là 1 dòng: thời điểm, thiết bị, liveness, máy bị hook/root, đạt/trượt. Liveness sát ngưỡng + thử nhiều lần + máy mới gắn ví = dấu hiệu vượt eKYC.",
    )
    ok = f.decision(
        "Duyệt?",
        step=3,
        explain="decided_at + decision (APPROVED/REJECTED). Hồ sơ chưa có quyết định = đang chờ.",
    )
    rej = f.process("Từ chối", step=4, explain="Dừng ở đây.")
    disb = f.process(
        "Giải ngân về ví chính chủ",
        step=4,
        icon="check",
        badge="disbursed_at",
        explain="Tiền luôn về tài khoản/ví đứng tên khách (đối chiếu hợp đồng mẫu). Kỳ hạn 3 tháng, lãi 36%/năm.",
    )
    xfer = f.process(
        "Chuyển tiền đi",
        step=5,
        icon="api",
        badge="wallet_transfers",
        explain="Mỗi lần chuyển: thời điểm, người nhận, số tiền, ghi chú + ngữ cảnh người nhận (danh bạ & lúc lưu số, đã từng chuyển chưa, SIMO, ví nhận bao nhiêu ngày tuổi).",
    )
    due = f.process(
        "Đến hạn kỳ 1, 2, 3",
        step=6,
        icon="clock",
        badge="repayment_schedule",
        explain="Mỗi kỳ 1 dòng: ngày đến hạn, gốc, lãi.",
    )
    paid = f.decision(
        "Đã trả?", step=7, explain="repayments: mỗi lần trả 1 dòng (thời điểm, số tiền, kênh)."
    )
    good = f.process("Trả đúng / trễ ít", step=8, icon="check")
    fpd = f.process(
        "Quá hạn ngay kỳ đầu",
        step=8,
        icon="alert",
        badge="hậu kiểm",
        explain="Đến hạn kỳ 1 + 10 ngày chưa trả → tín hiệu 'fpd'. Đứng riêng = rủi ro tín dụng; nằm trong cụm có quan hệ thì làm cụm nặng thêm.",
    )
    rep = f.process(
        "Tin báo lừa đảo",
        step=5,
        icon="mail",
        badge="scam_reports",
        explain="Bất kỳ lúc nào: khách gửi tin nghi lừa hoặc kể bị lừa. Chỉ có chữ thô — AI trích tài khoản/ví/hotline.",
    )
    e = f.end()
    set_step(f, e, 9)
    for nid, c in ((ekyc, "#cdb8ec"), (xfer, "#f4b47e"), (fpd, "#f4b47e"), (rep, "#f4b47e")):
        color(f, nid, c)
    f.link(s, sub)
    f.link(sub, ekyc)
    f.link(ekyc, ok)
    f.link(ok, rej, "không")
    f.link(ok, disb, "có")
    f.link(disb, xfer)
    f.link(disb, due)
    f.link(due, paid)
    f.link(paid, good, "có")
    f.link(paid, fpd, "không")
    f.link(s, rep)
    f.link(good, e)
    f.link(fpd, e)
    f.link(rej, e)
    f.link(xfer, e)
    f.link(rep, e)
    f.narrate(1, "Nộp hồ sơ", "Bảng applications: 200.000 hồ sơ từ 01/06 tới 25/11/2026.")
    f.narrate(
        2,
        "eKYC",
        "Bảng ekyc_sessions: mỗi lần thử 1 dòng.",
        note="Nhận ra khuôn mặt giả là việc của nhà cung cấp eKYC; Thiên La bắt BỐI CẢNH quanh phiên eKYC.",
    )
    f.narrate(
        3,
        "Quyết định",
        "Có mốc decided_at → đếm được 'hồ sơ đang chờ' tại đúng thời điểm, không dùng trạng thái cuối.",
    )
    f.narrate(
        4,
        "Giải ngân",
        "Mục đích 'hoàn ứng vốn tự có' → tiền là của khách, không kiểm soát được sau giải ngân.",
    )
    f.narrate(5, "Dòng tiền + tin báo", "Hai nguồn dấu vết chính: tiền đi đâu, và ai báo gì.")
    f.narrate(6, "Lịch trả", "3 kỳ, mỗi kỳ 1 dòng.")
    f.narrate(
        7, "Trả hay không", "Quá hạn = ngày đang xét − ngày đến hạn của kỳ đầu tiên chưa trả."
    )
    f.narrate(
        8,
        "Hậu kiểm",
        "Quá hạn ngay kỳ đầu là dấu vết DUY NHẤT của kẻ gian lẻ loi — bắt sau, không bắt trước được.",
        badge="TRUNG THỰC",
    )
    return f
