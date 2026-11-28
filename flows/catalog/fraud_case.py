from flows.common import Flow, GROUP, color, set_step


def ca_an_giang():
    f = Flow("thienla-ca-du-vay", "Ca thật: dụ vay rồi chuyển tiền giải ngân")
    f.group, f.look = (GROUP, "iso")
    f.meta(
        subtitle="Kịch bản Công an An Giang cảnh báo 09/11/2026 — và chỗ Thiên La chen vào.",
        duration="2 phút",
        level="Ca demo",
        learn=[
            "eKYC không chặn được khi chính chủ tự vay",
            "Luật dòng tiền coi nạn nhân là kẻ gian",
            "AI ghép tin báo + dòng tiền để nhận ra nạn nhân",
        ],
    )
    s = f.start()
    bait = f.process(
        "Mồi nhử",
        step=1,
        icon="mail",
        badge="vé máy bay rẻ",
        explain="Kẻ gian tiếp cận qua quảng cáo vé máy bay giá rẻ, hoặc giả cơ quan chức năng yêu cầu xác thực định danh.",
    )
    app = f.process(
        "Nạn nhân cài ví, tự vay",
        step=2,
        icon="user",
        explain="Được hướng dẫn cài ví/app tài chính (bài nêu Home Credit, Viettel Money, MoMo), tự đăng ký vay.",
    )
    ekyc = f.decision(
        "eKYC khuôn mặt đạt?",
        step=3,
        explain="Đạt — vì chính chủ tự vay. eKYC không có lỗi nào để bắt.",
    )
    disb = f.process("Giải ngân về ví chính chủ", step=4, icon="check")
    xfer = f.process(
        "Chuyển hết cho kẻ lừa",
        step=5,
        icon="alert",
        badge="10–60 phút",
        explain="Viện cớ 'xác minh giao dịch, nộp phí, hoàn tiền'. Nạn nhân chuyển toàn bộ tiền vay rồi bị cắt liên lạc.",
    )
    rule = f.decision(
        "Luật: chuyển ≥80% trong 1h?",
        step=6,
        explain="Luật dòng tiền gắn cờ — nhưng coi đây là KẺ GIAN. Đo trên dữ liệu: gắn cờ 26.169 hồ sơ, coi 20/28 nạn nhân là kẻ gian.",
    )
    report = f.process(
        "Tin báo + tin tự kể",
        step=7,
        icon="mail",
        explain="Người khác đã báo tài khoản nhận này; chính nạn nhân kể lại vào Lá chắn ('tôi vừa vay rồi chuyển cho…').",
    )
    ai = f.decision(
        "AI: kẻ gian hay nạn nhân?",
        step=8,
        explain="Hồ sơ sạch + tín hiệu kỹ thuật bình thường + chuyển hết cho tài khoản đã bị báo + có tin tự kể bị lừa + nhiều người vừa vay cùng chuyển về 1 tài khoản → NẠN NHÂN của cùng 1 đường dây.",
    )
    help_ = f.process(
        "Hỗ trợ nạn nhân",
        step=9,
        icon="check",
        explain="Không đưa vào danh sách đen. Liên hệ hỗ trợ, tư vấn trình báo công an, cảnh báo khách khác.",
    )
    block = f.process(
        "Phong toả tài khoản lừa",
        step=9,
        icon="lock",
        explain="Đề nghị ngân hàng phong toả 3 tài khoản nhận; tài khoản này đã nhận tiền từ 8 người vừa vay.",
    )
    e = f.end()
    set_step(f, e, 10)
    for nid, c in ((bait, "#f4b47e"), (xfer, "#f4b47e"), (ai, "#cdb8ec"), (help_, "#b8e0c2")):
        color(f, nid, c)
    f.link(s, bait)
    f.link(bait, app)
    f.link(app, ekyc)
    f.link(ekyc, disb, "đạt")
    f.link(disb, xfer)
    f.link(xfer, rule)
    f.link(rule, report, "gắn cờ: 'kẻ gian' ✗")
    f.link(report, ai)
    f.link(ai, help_, "nạn nhân")
    f.link(ai, block, "đường dây")
    f.link(help_, e)
    f.link(block, e)
    f.narrate(1, "Mồi nhử", "Quảng cáo vé máy bay rẻ, hoặc giả cơ quan chức năng.", badge="CA THẬT")
    f.narrate(2, "Nạn nhân tự vay", "Kẻ gian không cần chiếm ví — nạn nhân tự làm mọi bước.")
    f.narrate(
        3,
        "eKYC đạt",
        "Chính chủ tự vay thì eKYC luôn đạt.",
        note="Không công cụ eKYC nào chặn được bước này.",
        note_type="warn",
    )
    f.narrate(4, "Giải ngân", "Tiền về ví chính chủ của nạn nhân.")
    f.narrate(
        5,
        "Chuyển hết",
        "Ca ngày 03/11/2026 ở An Giang: mất 120 triệu, vẫn phải tự trả nợ.",
        badge="THIỆT HẠI",
    )
    f.narrate(
        6,
        "Luật dòng tiền",
        "Có gắn cờ — nhưng gắn nhầm vai: nạn nhân thành kẻ gian, cùng hơn 26 nghìn hồ sơ khác.",
        note_type="warn",
        badge="VẤN ĐỀ",
    )
    f.narrate(7, "Tin báo", "Tài khoản nhận đã bị người khác báo; nạn nhân tự kể lại vào Lá chắn.")
    f.narrate(
        8,
        "AI ghép tín hiệu",
        "Nhiều hồ sơ sạch cùng dồn tiền về 1 tài khoản bị báo → đây là nạn nhân của 1 đường dây.",
        badge="AI",
    )
    f.narrate(
        9,
        "Hành động kép",
        "Hỗ trợ nạn nhân + đề nghị phong toả tài khoản lừa, chặn người tiếp theo.",
    )
    f.narrate(
        10,
        "Nguồn",
        "Công an tỉnh An Giang, 'Cảnh báo thủ đoạn lừa đảo dụ dỗ vay tiền qua ứng dụng tài chính trực tuyến', 09/11/2026.",
        note="https://congan.angiang.gov.vn/canh-bao-thu-doan-lua-dao-du-do-vay-tien-qua-ung-dung-tai-chinh-truc-tuyen",
    )
    return f
