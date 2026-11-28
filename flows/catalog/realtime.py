from flows.common import Flow, GROUP, color, set_step


def realtime():
    f = Flow("thienla-realtime", "Bộ máy realtime: từ 1 sự kiện tới 1 cảnh báo")
    f.group, f.look = (GROUP, "iso")
    f.meta(
        subtitle="app/engine/engine.py — 741.593 sự kiện xử lý theo đúng thứ tự thời gian trong ~8 giây, sinh 347 cảnh báo.",
        duration="kỹ thuật",
        level="Chi tiết",
        learn=[
            "Chỉ cập nhật cụm bị chạm tới — không tính lại từ đầu",
            "Không nhìn trước tương lai: mọi quyết định chỉ dùng dữ liệu đã xảy ra",
            "AI chỉ được gọi khi cụm vượt ngưỡng — giữ chi phí và tốc độ",
        ],
    )
    s = f.start()
    ev = f.process(
        "Sự kiện tới",
        step=1,
        icon="queue",
        badge="5 loại",
        explain="Nộp hồ sơ · chuyển tiền · tin báo · trả nợ · kiểm tra quá hạn kỳ 1 (lịch hẹn giờ của chính hệ thống). Bản thi: phát lại theo thời gian; chạy thật: đọc hàng đợi sự kiện.",
    )
    kind = f.decision("Là chuyển tiền?", step=2)
    chk = f.process(
        "Cảnh báo lúc chuyển tiền",
        step=3,
        icon="lock",
        badge="< 1 giây",
        explain="Ngữ cảnh khoản vay vừa giải ngân + người nhận (danh bạ, lịch sử, SIMO, số tin báo ĐÃ có tới giờ) → cho phép / cảnh báo / tạm giữ.",
    )
    hold = f.decision("Tạm giữ?", step=4)
    al1 = f.process(
        "Cảnh báo giao dịch",
        step=5,
        icon="alert",
        badge="60 lần",
        explain="Vào hàng đợi với mức Khẩn.",
    )
    upd = f.process(
        "Cập nhật đồ thị",
        step=3,
        icon="chart",
        badge="union-find",
        explain="Nối hồ sơ qua điểm dùng chung: thiết bị, SĐT tham chiếu, dải IP VPN, lô SIM mới, nơi nhận tiền (đã siết: ≤2h, ≥30% khoản vay, chưa từng chuyển), máy mở ví nhận, tài khoản/hotline trong tin báo. Dữ liệu chỉ thêm, không xoá → nối thêm rất rẻ.",
    )
    ev2 = f.process(
        "Đánh giá cụm vừa đổi",
        step=4,
        icon="gear",
        explain="Đếm tín hiệu của cụm: tham chiếu chung ≥5, thiết bị chung ≥5, nơi nhận chung, cùng quá hạn kỳ đầu, IP/SIM/giả lập, eKYC bất thường, SIMO, tin báo; số hồ sơ đang chờ TẠI thời điểm này.",
    )
    tri = f.decision(
        "AI sàng lọc: đáng điều tra?",
        step=5,
        explain="ai.triage_clusters — nhận bản tóm tắt số liệu (không PII), trả quyết định + độ tin cậy + lý do.",
    )
    chg = f.decision(
        "Có bằng chứng mới?",
        step=6,
        explain="So với lần cảnh báo trước của cùng cụm: thêm tín hiệu, thêm tin báo, lớn thêm, đổi số hồ sơ chờ. Không đổi → im lặng, tránh spam.",
    )
    al2 = f.process(
        "Cảnh báo cụm",
        step=7,
        icon="alert",
        badge="mức + ưu tiên",
        explain="Mức Khẩn/Cao/Trung bình; ưu tiên = mức × 10 + tin cậy × 10 + quy mô + 2 × hồ sơ đang chờ. Giữ mã cụm cũ khi 2 cụm nhập lại → diễn biến liền mạch.",
    )
    q = f.process("Hàng đợi điều tra", step=8, icon="laptop")
    e = f.end()
    set_step(f, e, 9)
    for nid, c in ((chk, "#f4b47e"), (tri, "#cdb8ec"), (al1, "#f4b47e"), (al2, "#f4b47e")):
        color(f, nid, c)
    f.link(s, ev)
    f.link(ev, kind)
    f.link(kind, chk, "có")
    f.link(chk, hold)
    f.link(hold, al1, "có")
    f.link(hold, upd, "không")
    f.link(kind, upd, "không")
    f.link(upd, ev2)
    f.link(ev2, tri)
    f.link(tri, chg, "có")
    f.link(tri, e, "không")
    f.link(chg, al2, "có")
    f.link(chg, e, "không")
    f.link(al1, q)
    f.link(al2, q)
    f.link(q, e)
    f.narrate(
        1,
        "Sự kiện",
        "Mọi thứ thành 1 dòng sự kiện có thời gian.",
        note="Bản thi phát lại dữ liệu theo đồng hồ tua nhanh; code xử lý giống hệt khi chạy thật.",
    )
    f.narrate(2, "Phân luồng", "Chuyển tiền đi cả 2 đường: kiểm tra ngay + cập nhật đồ thị.")
    f.narrate(
        3,
        "Chặn tại chỗ / nối đồ thị",
        "Kiểm tra chuyển tiền chỉ dùng tin báo đã có TỚI GIỜ — nạn nhân đầu tiên chưa có ai báo.",
    )
    f.narrate(4, "Đánh giá", "Chỉ tính lại cụm vừa bị chạm.")
    f.narrate(5, "AI sàng lọc", "Gọi AI theo nhu cầu, không theo từng sự kiện.", badge="AI")
    f.narrate(6, "Chống spam", "Cụm không có gì mới thì không báo lại.")
    f.narrate(
        7,
        "Cảnh báo",
        "Đo được (seed chuẩn): A 18 phút, E/H ~45 phút, D 1 ngày, G 1 ngày, B 1 ngày, F 4 ngày, C 27 ngày.",
    )
    f.narrate(8, "Hàng đợi", "Lọc theo ngày, khung giờ, mức độ, kết luận, độ tin cậy.")
    return f
