from flows.common import Flow, GROUP, color, set_step


def ha_tang():
    f = Flow("thienla-ha-tang", "Hạ tầng và bảo mật: một yêu cầu đi qua những lớp nào")
    f.group, f.look = (GROUP, "iso")
    f.meta(
        subtitle="Docker Compose: PostgreSQL 16 + web app FastAPI (user không phải root). Bí mật chỉ nằm trong .env.",
        duration="kỹ thuật",
        level="Chi tiết",
        learn=[
            "2 loại phiên tách biệt: đội rủi ro và khách",
            "Giới hạn lượt gọi + header bảo mật ở 1 chỗ (middleware)",
            "Chế độ demo bật/tắt bằng cờ, không sửa code",
        ],
    )
    s = f.start()
    br = f.process(
        "Trình duyệt",
        step=1,
        icon="laptop",
        explain="Màn đội rủi ro (/), app ví khách (/vi/), luồng trình chiếu (/flows/).",
    )
    px = f.process(
        "Caddy (HTTPS)",
        step=2,
        icon="balancer",
        explain="Reverse proxy + chứng chỉ tự động khi lên VPS; THIENLA_BEHIND_PROXY=1 để lấy IP thật + cookie Secure.",
    )
    mw = f.process(
        "Middleware bảo mật",
        step=3,
        icon="lock",
        badge="security.guard",
        explain="Giới hạn lượt theo IP (đăng nhập 5/phút…) · chặn API cần đăng nhập · CSP, X-Frame-Options, nosniff, no-referrer · no-store cho API.",
    )
    who = f.decision(
        "Loại phiên?",
        step=4,
        explain="Cookie ký HMAC-SHA256, HttpOnly, SameSite=Strict. Đội rủi ro: mật khẩu (8 giờ). Khách: SĐT + PIN băm scrypt (2 giờ).",
    )
    risk = f.process(
        "API đội rủi ro",
        step=5,
        icon="api",
        explain="Hàng đợi, đồ thị, hồ sơ (đã tối thiểu hoá PII), điều tra, phát realtime, mô phỏng.",
    )
    kh = f.process(
        "API khách",
        step=5,
        icon="user",
        explain="Chỉ dữ liệu của chính SĐT đang đăng nhập; cùng 1 thông báo cho sai SĐT và sai PIN.",
    )
    pub = f.process(
        "Công khai",
        step=5,
        icon="file",
        explain="Lá chắn, tổng quan, chỉ số tổng hợp — không có dữ liệu cá nhân.",
    )
    dbn = f.process(
        "PostgreSQL 16",
        step=6,
        icon="database",
        badge="127.0.0.1:5433",
        explain="Trong Docker, chỉ mở cho máy mình. build.py nạp ~1,3 triệu dòng bằng COPY; dữ liệu mô phỏng 100%.",
    )
    e = f.end()
    set_step(f, e, 7)
    for nid, c in ((mw, "#f4b47e"), (dbn, "#cdb8ec")):
        color(f, nid, c)
    f.link(s, br)
    f.link(br, px)
    f.link(px, mw)
    f.link(mw, who)
    f.link(who, risk, "đội rủi ro")
    f.link(who, kh, "khách")
    f.link(who, pub, "không cần")
    f.link(risk, dbn)
    f.link(kh, dbn)
    f.link(pub, dbn)
    f.link(dbn, e)
    f.narrate(1, "Trình duyệt", "3 cửa vào cho 3 đối tượng.")
    f.narrate(2, "HTTPS", "Bản thi chạy sau Caddy; chạy trên máy thì bỏ qua lớp này.")
    f.narrate(3, "Middleware", "Mọi yêu cầu đều qua đây trước — 1 chỗ để rà soát.", badge="BẢO MẬT")
    f.narrate(
        4,
        "Phiên",
        "Phiên khách không mở được API đội rủi ro và ngược lại.",
        note="DEMO_AUTOFILL=1 trả mật khẩu/PIN cho trình duyệt để tự đăng nhập — chỉ bật khi trình diễn.",
        note_type="warn",
    )
    f.narrate(
        5, "Phân quyền", "Đã thử: khách gọi API đội rủi ro → 401; cookie giả → 401; PIN sai → 401."
    )
    f.narrate(6, "Dữ liệu", "Đặt lại demo = chạy lại build.py (xoá sạch rồi dựng lại ~15 giây).")
    return f
