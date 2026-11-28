from feature_flow import Flow


def realtime_ai_pipeline():
    flow = Flow("thienla-ai-realtime", "App khách → sự kiện → graph → Agent")
    flow.group = "Thiên La"
    flow.meta(
        subtitle="Luồng PostgreSQL trực tiếp; giữ nguồn, thời điểm và trạng thái chưa xác minh.",
        duration="3 phút",
        level="AI trực tiếp",
    )
    steps = [
        (
            "Backend ghi nghiệp vụ",
            "Khoản vay KL…, giao dịch KT… hoặc tin báo TBL… và ai_events được ghi cùng transaction. KT giữ loan_id/ngữ cảnh gốc; không suy đoán theo khoản vay mới nhất khi đọc lại.",
        ),
        (
            "Worker nhận sự kiện",
            "PostgreSQL lease + SKIP LOCKED, tối đa 3 lần thử, có khôi phục khi tiến trình dừng. Thiếu model giữ waiting_for_model; mô phỏng chỉ cập nhật graph, không gọi LLM.",
        ),
        (
            "Cập nhật graph có nguồn",
            "Chỉ ghi node/cạnh liên quan sự kiện. Receipt chống phát lại. Tin báo được kiểm tra trích đoạn và ngân hàng trước khi tạo MENTIONS. held là TRANSFER_ATTEMPT; chỉ done là SENT_TO.",
        ),
        (
            "Tổng hợp và sàng lọc",
            "Đọc cụm có giới hạn, cutoff và số thứ tự sự kiện. Tool tổng hợp theo khoản vay được gắn, không cộng held vào dòng tiền. Gemini triage quyết định skip/investigate; phần bị giới hạn được ghi rõ.",
        ),
        (
            "Agent điều tra",
            "InvestigationAgent kế thừa BaseAgent, giữ workflow hiện tại và giới hạn 12 tool call. Đọc đúng KT…, KL… và tin báo; tách đánh giá cụm, vai trò cá nhân và đề xuất giao dịch.",
        ),
        (
            "Lưu kết quả về backend",
            "Chỉ case completed được lưu. Liên kết người nhận gắn ngân hàng và trạng thái unverified; không tự biến thành danh sách đen đã xác minh. Web đọc case/bằng chứng và tự cập nhật; worker không thực thi chặn tiền.",
        ),
    ]
    previous = flow.start()
    for index, (title, body) in enumerate(steps, 1):
        node = flow.process(title, step=index, explain=body)
        flow.link(previous, node)
        flow.narrate(index, title, body)
        previous = node
    flow.link(previous, flow.end())
    return flow
