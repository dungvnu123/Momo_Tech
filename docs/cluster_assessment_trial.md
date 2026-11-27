# Kiểm thử tổng hợp dòng tiền và đánh giá hai cấp

Ngày 27/11/2026. Toàn bộ dữ liệu mô phỏng; seed 20261129. Backend riêng có
200.000 hồ sơ, 78.008 giao dịch, 105 tin báo; không thay dữ liệu giao diện.
Không đọc đáp án để chọn ứng viên, gửi đầu vào hay xây prompt.

## Kiểm tra code và giao diện

161 unit/integration test qua, gồm tổng không đổi khi phân trang, người nhận
chung, mã nguồn, thiếu tên, cutoff thời gian, bảo vệ người tự báo bị lừa,
từ chối bằng chứng của hồ sơ khác, tự sửa submission, trace/API có xác thực
và tương thích case cũ. JavaScript qua kiểm tra cú pháp. Kiểm tra render bằng
Node và Edge: mở đúng mã bản ghi/số tiền, escape nội dung, hiển thị mức nghi
vấn cụm độc lập verdict cũ, số đã đánh giá và phần chưa đánh giá, không gắn 50%.

## Chạy model thật

| Lượt | Kết quả |
|---|---|
| Schema mới với Gemini | Chấp nhận schema submit_case |
| Pipeline đầu tiên | Phân tích 8 tin, 10 cặp thực thể; dừng ở triage vì ServerError phía provider |
| Pipeline thử lại | 4 cụm/29 hồ sơ; 1 skip, 1 deferred; 1 Agent completed, 1 hết 12 call do sửa nguồn chưa thành công |
| Hai Agent sau sửa hướng dẫn/phản hồi lỗi | 2/2 completed, đều cluster suspicious; 4 và 8 tool call, tổng 1 lỗi nguồn được sửa thành công |
| Backend → Agent | Completed; cluster suspicious, vai trò người vay vẫn inconclusive; giữ giới hạn mock/khớp ngân hàng chưa xác minh |

Hai Agent chạy lại dùng graph đã bổ sung của lượt pipeline, không dựng lại
từ đầu. Đây là lượt kiểm tra sửa lỗi trên mẫu đã xem, **không phải lượt chấm
độc lập mới** và không thay kết quả pipeline ban đầu. Sửa lỗi mang tính hợp
đồng: phải dẫn record_ids từ đúng tool_call_id; thông tin thiếu của một hồ
sơ phải nằm trong missing_information của chính hồ sơ đó. Không nới kiểm
tra nguồn, không tự đổi verdict/confidence.

Hai phiên cuối đã đánh giá riêng 9/20 hồ sơ: 6 suspected_participant, 3
undetermined; 11 not_assessed được hiển thị rõ. Theo nhãn mô phỏng chỉ đọc
ở bước chấm sau cùng, 6 hồ sơ nghi liên quan trùng nhóm gian lận, không có
nạn nhân trong mẫu ứng viên này. Mọi vai trò vẫn unverified. Không đủ mẫu
để kết luận về bảo vệ nạn nhân, tỷ lệ báo nhầm thực tế hay recall toàn bộ
200.000 hồ sơ. Một cụm vẫn chỉ đánh giá riêng 1/12 hồ sơ; cần lượt đọc bổ
sung nếu muốn phủ hết cụm lớn. Không coi chưa đánh giá là an toàn.

Pipeline thử lại phân tích đúng cờ rủi ro và tự báo nạn nhân của 8/8 tin đã
chọn theo nhãn mô phỏng; chỉ bao phủ 8/105 tin. Không dùng việc giảm tỷ lệ
inconclusive ở mức cụm để khẳng định đã cải thiện xác định vai trò cá nhân.

Artifact local không commit:

- `data/assessment-trial-20261129/pipeline-result.json`: lượt provider lỗi.
- `pipeline-retry-result.json`, `pipeline-score.json`: pipeline thử lại.
- `checked-C00066.json`, `checked-C00114.json`: hai phiên sau sửa.
- `agent-recheck-result.json`, `agent-recheck-score.json`: chấm riêng lượt sửa.
- `backend-case.json`: đường backend với cutoff cảnh báo.
- Graph/nguồn/trace trong `data/assessment-ai-runs/`.
