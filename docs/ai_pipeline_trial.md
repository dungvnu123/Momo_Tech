# Kết quả lượt thử pipeline đầu tiên

Ngày thử: 27/11/2026. Dữ liệu hoàn toàn mô phỏng, seed `20261128`, khác seed
đã dùng để phát triển prompt trước đó nhưng vẫn cùng cơ chế sinh dữ liệu.
Không chỉnh prompt theo đáp án của lượt thử này.

Backend riêng có 200.000 hồ sơ, 77.771 giao dịch, 105 tin báo, 137 cụm có cảnh
báo latest. Pipeline chọn ứng viên theo ưu tiên và đa dạng tín hiệu trong
backend, không đọc ground_truth để chọn mẫu hoặc tạo đầu vào model.

| Hạng mục | Kết quả đo |
|---|---|
| Phạm vi chọn | 4 cụm, 29 hồ sơ |
| Tin báo phân tích | 8/105; nhận diện đúng có/không rủi ro 8/8 và dấu hiệu tự báo nạn nhân 8/8 |
| Hợp nhất thực thể | Xử lý 10 cặp có giới hạn trong các cụm đã chọn |
| Sàng lọc | 3 investigate, 1 skip; không bỏ qua hồ sơ có vấn đề trong nhãn của mẫu đã chọn |
| Điều tra | Chạy 2 cụm; 1 cụm investigate còn lại deferred_by_limit |
| Kết luận vai trò | 2/2 phiên completed nhưng inconclusive |
| Lỗi tool / bằng chứng không hợp lệ | 0 / 0; cả 2 case có bằng chứng |
| Thời gian toàn lượt | 184,181 giây, gồm dựng graph riêng |
| Lượt model logic | 26; không phải số token hay chi phí thực tế |

Theo nhãn mô phỏng chỉ dùng ở bước chấm, 29 hồ sơ được chọn gồm 27 hồ sơ
gian lận và 2 hồ sơ bình thường; không có nạn nhân trong mẫu ứng viên lần này.
Không hồ sơ nào bị gán nhầm là kẻ gian, nhưng Agent cũng chưa xác định hồ sơ
gian lận nào vì cả hai phiên đều chưa kết luận vai trò. Do đó **không thể coi
việc không gắn nhầm là bằng chứng Agent đã đạt chất lượng phát hiện tốt**.

Các tầng phân tích tin báo, thực thể, graph và sàng lọc đã nối được. Điểm cần
cải tiến tiếp là điều tra ở cấp cụm và cách diễn đạt mức nghi vấn: Agent hiện
thận trọng khi thiếu dữ liệu về ý định/người thực hiện. Cần phân biệt phát
hiện tổ hợp dấu hiệu để người kiểm tra xem xét với khẳng định vai trò cá nhân.
Không sửa nhãn, tự tăng confidence hoặc dùng đáp án để ép kết luận.

Đây là đánh giá có giới hạn trên ứng viên đã chọn, không phải recall trên
200.000 hồ sơ hay độ chính xác trên dữ liệu giao dịch thực tế. Tin báo được
phân tích một phần; sự vắng mặt của tin báo trong graph không chứng minh an toàn.

Artifact local, không commit dữ liệu:

- `data/pipeline-holdout-20261128/pipeline-result.json`
- `data/pipeline-holdout-20261128/pipeline-score.json`
- Phiên `58c51e0e5b8f45bfa8b687cf32c886ee` trong `data/ai-pipeline-holdout/`,
  gồm CSV/hash nguồn, graph, result và trace từng Agent.
