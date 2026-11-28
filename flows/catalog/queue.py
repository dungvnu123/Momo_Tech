from flows.common import Flow, GROUP, set_step


def hang_doi():
    f = Flow("thienla-hang-doi", "Đội rủi ro dùng hàng đợi điều tra")
    f.group = GROUP
    f.meta(
        subtitle="Từ 347 cảnh báo tới quyết định: lọc → chọn → xem đồ thị → xem dòng thời gian hồ sơ → điều tra → hành động.",
        duration="2 phút",
        level="Hướng dẫn",
        learn=[
            "Bắt đầu từ mức Khẩn + có hồ sơ đang chờ giải ngân",
            "Dòng thời gian hồ sơ cho thấy đúng thứ tự sự việc",
            "Quyết định cuối luôn là của con người",
        ],
    )
    s = f.start()
    flt = f.process(
        "Lọc",
        step=1,
        icon="gear",
        explain="Biểu đồ theo ngày + khung giờ (đêm 0–6h đáng xem), mức Khẩn/Cao/Trung bình, loại (cụm / giao dịch giữ), kết luận, độ tin cậy ≥, tìm mã. Sắp xếp: ưu tiên, mới nhất, tin cậy, quy mô.",
    )
    pick = f.process(
        "Chọn cảnh báo",
        step=2,
        icon="alert",
        explain="Mỗi dòng: giờ, mức, tiêu đề, thanh độ tin cậy, số hồ sơ đang chờ, số tin báo, kết luận đã điều tra sẵn.",
    )
    g = f.process(
        "Đồ thị cụm",
        step=3,
        icon="chart",
        explain="Hồ sơ + điểm dùng chung (thiết bị, tham chiếu, nơi nhận tiền, dải IP/lô SIM). Viền vàng = đang chờ giải ngân. Diễn biến cụm theo thời gian ở trên.",
    )
    tl = f.process(
        "Dòng thời gian hồ sơ",
        step=4,
        icon="file",
        explain="Bấm 1 hồ sơ: nộp → eKYC từng lần → duyệt → giải ngân → từng lần chuyển (cờ SIMO, ngoài danh bạ) → đến hạn/trả → tin báo → cảnh báo, kèm 'quá hạn N ngày' TẠI lúc cảnh báo.",
    )
    inv = f.process(
        "Điều tra",
        step=5,
        icon="api",
        explain="Agent chạy từng bước, chỉ thấy dữ liệu tới lúc cảnh báo; ra kết luận: đường dây / nạn nhân / vô hại / chưa đủ căn cứ.",
    )
    dec = f.decision("Con người quyết định", step=6)
    a1 = f.process(
        "Chặn + phong toả",
        step=7,
        icon="lock",
        explain="Dừng giải ngân hồ sơ đang chờ, đề nghị phong toả tài khoản gom, theo dõi thiết bị/SĐT.",
    )
    a2 = f.process(
        "Hỗ trợ nạn nhân",
        step=7,
        icon="user",
        explain="Liên hệ, tư vấn trình báo, KHÔNG đưa vào danh sách đen.",
    )
    a3 = f.process(
        "Đóng, ghi nhãn",
        step=7,
        icon="check",
        explain="Vô hại → ghi nhãn để đo lại độ chính xác hằng tuần.",
    )
    e = f.end()
    set_step(f, e, 8)
    f.link(s, flt)
    f.link(flt, pick)
    f.link(pick, g)
    f.link(g, tl)
    f.link(tl, inv)
    f.link(inv, dec)
    f.link(dec, a1, "đường dây")
    f.link(dec, a2, "nạn nhân")
    f.link(dec, a3, "vô hại")
    f.link(a1, e)
    f.link(a2, e)
    f.link(a3, e)
    f.narrate(1, "Lọc", "Mặc định: mỗi cụm 1 dòng, sắp theo ưu tiên.")
    f.narrate(2, "Chọn", "Ưu tiên cảnh báo Khẩn có hồ sơ đang chờ — còn chặn kịp tiền.")
    f.narrate(3, "Đồ thị", "Bấm đúp nền hoặc ⤢ Vừa khung để căn lại.")
    f.narrate(4, "Dòng thời gian", "Xem đúng thứ tự: vay xong mấy phút thì tiền đi đâu.")
    f.narrate(
        5,
        "Điều tra",
        "Cảnh báo dựng sẵn dùng luật mô phỏng. Khi bấm Điều tra, backend/integration/ gọi Agent và Gemini thật.",
        note="Mốc bản giả lập: 58/58 kẻ gian, 0 nạn nhân bị nhầm, nhưng nhầm 298 hồ sơ vô hại — AI phải cắt phần này.",
        note_type="warn",
    )
    f.narrate(
        6, "Quyết định", "Agent chỉ đề xuất, không có quyền hành động thật.", badge="NGUYÊN TẮC"
    )
    f.narrate(7, "Hành động + nhãn", "Mỗi quyết định thành nhãn để đo lại precision/recall.")
    return f
