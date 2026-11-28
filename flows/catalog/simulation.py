from flows.common import Flow, GROUP, set_step


def mo_phong():
    f = Flow("thienla-mo-phong", "Bộ mô phỏng hoạt động trực tiếp")
    f.group = GROUP
    f.meta(
        subtitle="app/backend/simulation/ — tự sinh khoản vay + chuyển tiền ngẫu nhiên để hệ thống 'đang sống' khi demo.",
        duration="kỹ thuật",
        level="Chi tiết",
        learn=[
            "Đi qua ĐÚNG luồng của app khách — không có đường tắt",
            "Nhãn kịch bản chỉ để đo, bộ kiểm tra không nhìn thấy",
            "Đo 2 con số: lừa bị chặn / bình thường bị làm phiền",
        ],
    )
    s = f.start()
    tick = f.process(
        "Mỗi nhịp (0,5–30 giây)",
        step=1,
        icon="clock",
        explain="Đội rủi ro bật/tắt và chọn nhịp; SIM_AUTOSTART=1 để bật sẵn. Tự dừng sau 2.000 sự kiện.",
    )
    which = f.decision(
        "Vay hay chuyển?",
        step=2,
        explain="40% khoản vay mới (khách ngẫu nhiên trong 200.000 hồ sơ); còn lại: 1 người vừa vay chuyển tiền.",
    )
    loan = f.process(
        "Khoản vay mới",
        step=3,
        icon="check",
        explain="2–20 triệu, giải ngân về ví chính chủ, ghi mốc thời gian.",
    )
    kind = f.decision(
        "Chọn kịch bản",
        step=3,
        explain="Bình thường 72% (rút về TK chính chủ, người nhà, trả tiền phòng/mua hàng) · bị dụ vay 13% · giả thu nợ 8% · người thân nhờ gấp 7%.",
    )
    exe = f.process(
        "khach.execute_transfer",
        step=4,
        icon="api",
        explain="Cùng hàm với app khách: dựng ngữ cảnh → ai.check_transfer → ghi giao dịch; tạm giữ → cảnh báo LV….",
    )
    conf = f.decision(
        "Cảnh báo?", step=5, explain="Khách mô phỏng đọc cảnh báo: một nửa huỷ, một nửa vẫn chuyển."
    )
    cnt = f.process(
        "Bộ đếm + dòng hoạt động",
        step=6,
        icon="chart",
        explain="Khoản vay · giao dịch · cho phép / cảnh báo / tạm giữ · lừa bị chặn / tổng · bình thường bị làm phiền · 15 sự kiện gần nhất.",
    )
    e = f.end()
    set_step(f, e, 7)
    f.link(s, tick)
    f.link(tick, which)
    f.link(which, loan, "vay")
    f.link(which, kind, "chuyển")
    f.link(kind, exe)
    f.link(exe, conf)
    f.link(conf, cnt, "không / đã xử lý")
    f.link(loan, cnt)
    f.link(cnt, tick, "nhịp tiếp ↺")
    f.link(cnt, e, "tắt")
    f.narrate(1, "Nhịp", "Truy vấn DB chạy ở luồng riêng — web không bị đứng.")
    f.narrate(
        2, "Vay hay chuyển", "Chỉ người vừa vay mới chuyển — đúng hình dạng 'vay xong chuyển đi'."
    )
    f.narrate(3, "Kịch bản", "Nhãn kịch bản không được đưa vào bộ kiểm tra.", badge="CÔNG BẰNG")
    f.narrate(4, "Kiểm tra", "Giao dịch tạm giữ hiện trên hàng đợi với chữ '(mô phỏng)'.")
    f.narrate(5, "Khách quyết", "Cảnh báo không chặn cứng — khách vẫn được quyền chuyển.")
    f.narrate(6, "Đo", "Một lần chạy ~20 giây: lừa bị chặn 8/8, bình thường bị làm phiền 0.")
    return f
