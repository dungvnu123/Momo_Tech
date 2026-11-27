"""Bounded AI enrichment preview, separate from historical alert investigation."""
from feature_flow import Flow


def batch_ai_pipeline():
    f = Flow("thienla-ai-batch-pipeline", "Pipeline AI theo lô: backend → graph → Agent")
    f.group = "Thiên La"
    f.meta(subtitle="Luồng thử nghiệm trên snapshot riêng; giữ nguyên dữ liệu đang phục vụ giao diện.",
           duration="4 phút", level="Chạy thử AI", learn=[
               "Đầu vào chọn từ backend, không dùng đáp án để chọn mẫu cho AI",
               "Phân tích tin báo và thực thể được ghi vào graph trước khi sàng lọc",
               "Skip, chưa chạy và inconclusive là ba trạng thái khác nhau",
           ])
    start = f.start()
    items = [
        ("Backend nhận yêu cầu chạy lô", "POST /api/ai/pipeline/run hoặc CLI app.ai pipeline. Mặc định: 8 tin báo, 10 cặp thực thể, 4 cụm, 2 phiên điều tra. Không cho HTTP caller chọn đường dẫn file. Khi bật mật khẩu, cần cookie hoặc khóa service.", "server"),
        ("Snapshot nguồn và chọn ứng viên", "Đọc backend trong transaction chỉ đọc, xuất apps/transfers/reports; bỏ signals và analysis giả lập. Chọn cụm latest theo ưu tiên và đa dạng tín hiệu. Không đọc cases, verdict hay ground_truth để chọn mẫu cho AI.", "database"),
        ("Dựng graph riêng cho phiên", "Thư mục theo run_id chứa CSV nguồn có hash và graph.db mới. Snapshot gồm toàn bộ dữ liệu backend hiện có; đây không phải quyết định tại thời điểm một cảnh báo lịch sử. Không ghi đè graph hay cases đang phục vụ web.", "chart"),
        ("AI phân tích tin báo", "Ưu tiên tin liên quan người báo/nơi nhận của cụm; blocking chỉ là chọn sơ bộ. Gemini phân tích và trích dấu vết có thật trong nguồn. Ghi ai_report_analysis và cạnh MENTIONS. Tin lỗi được ghi riêng, độ phủ luôn nêu indexed/total.", "mail"),
        ("AI hợp nhất thực thể", "Sinh cặp có giới hạn trong các cụm đã chọn. Same mới tạo ResolvedPerson/RESOLVED_AS; same_household giữ khác người. Quyết định phải khớp dữ liệu gốc, không xóa Person gốc.", "user"),
        ("AI sàng lọc cụm", "Tính đặc trưng từ graph vừa bổ sung: thiết bị/tham chiếu chung, dòng tiền, tin báo, định danh và phần dữ liệu còn thiếu. Gemini trả skip/investigate. Skip không tự trở thành benign.", "gear"),
        ("Agent điều tra cụm được giữ", "InvestigationAgent kế thừa BaseAgent dùng GraphTools trên graph riêng. cluster_money_flow tổng hợp toàn bộ giao dịch của cụm, kèm nguồn và độ phủ. Kết quả tách đánh giá cụm khỏi vai trò từng hồ sơ; mọi vai trò unverified và dẫn đúng app_id/record_id. Hồ sơ chưa đánh giá ghi rõ not_assessed. Vẫn tối đa 12 tool call/phiên. Cụm vượt ngân sách được ghi deferred_by_limit.", "api"),
        ("Lưu báo cáo và đánh giá sau chạy", "result.json giữ trạng thái stage, timing, coverage, cache hit, trace và kết quả từng cụm. GET /api/ai/pipeline/runs/{run_id}; thêm /traces/{cluster_id} để đối chiếu tool nguồn. Chấm riêng mức nghi vấn cụm, vai trò đã đánh giá/chưa đánh giá và verdict cũ. Chỉ module sau chạy đọc đáp án; không tuyên bố recall toàn bộ 200.000 hồ sơ.", "file"),
    ]
    previous = start
    for step, (title, body, icon) in enumerate(items, 1):
        node = f.process(title, step=step, icon=icon, explain=body)
        f.link(previous, node)
        f.narrate(step, title, body)
        previous = node
    end = f.end()
    f.nodes[-1].step = 9
    f.link(previous, end)
    f.narrate(9, "Đọc giới hạn của kết quả", "Completed là hoàn thành lượt thử trong giới hạn. Partial có thể do tin lỗi hoặc cụm chưa chạy; failed là stage lỗi. Kết quả inconclusive phải được tính vào đánh giá, không sửa nhãn để làm đẹp số liệu. Đề xuất chỉ phục vụ người kiểm tra.")
    return f
