from flows.common import Flow, GROUP, color, set_step


def app_khach():
    f = Flow("thienla-app-khach", "App ví khách: tin lừa → vay → chuyển → tạm giữ → đội rủi ro")
    f.group, f.look = (GROUP, "iso")
    f.meta(
        subtitle="Kịch bản đầu-cuối trên /vi/ — mọi lần chuyển đi qua đúng 1 bộ kiểm tra với ngữ cảnh thật tại lúc chuyển.",
        duration="3 phút",
        level="Ca demo",
        learn=[
            "Chặn ở lúc tiền rời ví — trước khi mất tiền",
            "Tin chính thức (kênh đã xác thực) không bị báo nhầm",
            "Tạm giữ / báo lừa đều thành cảnh báo cho đội rủi ro ngay",
        ],
    )
    s = f.start()
    msg = f.process(
        "Tin nhắn lạ trong hộp tin",
        step=1,
        icon="mail",
        badge="6 tình huống",
        explain="Dụ vay rồi chuyển (tài khoản bị báo / SIMO / mới tinh) · giả thu hồi nợ · link giả đòi OTP · người thân nhờ chuyển gấp.",
    )
    loan = f.process(
        "Vay nhanh",
        step=2,
        icon="check",
        explain="Khoản vay giải ngân về ví chính chủ — mốc thời gian để đo 'vay xong mấy phút thì chuyển'.",
    )
    follow = f.process(
        "Làm theo hướng dẫn",
        step=3,
        icon="user",
        badge="đóng vai nạn nhân",
        explain="Form chuyển tiền tự điền theo tin: số tài khoản, tên, số tiền, nội dung; có thể bị dặn 'lưu số vào danh bạ'.",
    )
    ctx = f.process(
        "Dựng ngữ cảnh lúc chuyển",
        step=4,
        icon="gear",
        explain="Phút từ lúc giải ngân · tỉ lệ khoản vay/số dư · người nhận khác tên · có trong danh bạ + lưu bao lâu · đã từng chuyển chưa · SIMO · số tin báo đã có · nội dung.",
    )
    chk = f.decision(
        "check_transfer",
        step=5,
        explain="ai.check_transfer — cùng 1 hàm cho app khách, bộ mô phỏng và dữ liệu lịch sử.",
    )
    ok = f.process(
        "Cho phép",
        step=6,
        icon="check",
        explain="Người nhận quen / giao dịch bình thường — không làm phiền.",
    )
    warn = f.process(
        "Khoan đã!",
        step=6,
        icon="alert",
        explain="Có dấu hiệu nhưng có thể là thật (vd người thân nhờ gấp) → khách đọc lý do, Huỷ hoặc Vẫn chuyển.",
    )
    hold = f.process(
        "Tạm giữ",
        step=6,
        icon="lock",
        badge="tiền chưa rời ví",
        explain="Tài khoản bị báo/SIMO, trả 'nợ' vào TK cá nhân, hoặc vay xong chuyển hết cho người lạ chưa quen + dấu hiệu khác.",
    )
    rep = f.process(
        "Báo lừa đảo",
        step=7,
        icon="mail",
        explain="Lá chắn phân tích tin; tin từ kênh chính thức đã xác thực → An toàn, không cảnh báo.",
    )
    q = f.process(
        "Hàng đợi đội rủi ro",
        step=8,
        icon="laptop",
        badge="LV…",
        explain="Cảnh báo trực tiếp hiện đầu hàng đợi (tự làm mới) → đồ thị, dòng thời gian, điều tra.",
    )
    e = f.end()
    set_step(f, e, 9)
    for nid, c in (
        (msg, "#f4b47e"),
        (chk, "#cdb8ec"),
        (hold, "#f4b47e"),
        (warn, "#f6d58e"),
        (ok, "#b8e0c2"),
    ):
        color(f, nid, c)
    f.link(s, msg)
    f.link(msg, loan)
    f.link(loan, follow)
    f.link(follow, ctx)
    f.link(ctx, chk)
    f.link(chk, ok, "an toàn")
    f.link(chk, warn, "đáng ngờ")
    f.link(chk, hold, "lừa rõ")
    f.link(msg, rep, "khách tự báo")
    f.link(hold, q)
    f.link(rep, q, "nếu là lừa")
    f.link(ok, e)
    f.link(warn, e)
    f.link(q, e)
    f.narrate(
        1,
        "Tin lừa",
        "3 khách demo, mỗi người 2 tình huống lừa có thật + tin chính thức của FinVay.",
        badge="CA THẬT",
    )
    f.narrate(2, "Vay", "Kẻ lừa dụ vay — eKYC vẫn đạt vì chính chủ tự vay.")
    f.narrate(3, "Làm theo", "Nút 'Làm theo hướng dẫn' để giám khảo tự đóng vai nạn nhân.")
    f.narrate(4, "Ngữ cảnh", "Tất cả là dữ liệu tại ĐÚNG lúc chuyển — không biết tương lai.")
    f.narrate(
        5,
        "Bộ kiểm tra",
        "Gemini quyết định chính; luật (app/backend/mock_ai/) chỉ được nâng mức, và thay thế khi chưa cấu hình AI.",
        badge="AI",
    )
    f.narrate(
        6,
        "3 kết quả",
        "Đã chạy thử: 5 ca lừa → tạm giữ, ca người thân nhờ gấp → cảnh báo, chuyển cho người thân quen → cho phép.",
    )
    f.narrate(7, "Báo lừa", "Báo nhầm tin chính thức vẫn ra An toàn — không làm phiền đội rủi ro.")
    f.narrate(8, "Đội rủi ro", "Cảnh báo có mã LV…, mức Khẩn với giao dịch tạm giữ.")
    return f
