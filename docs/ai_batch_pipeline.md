# Pipeline AI theo lô từ backend

Luồng thử nghiệm đã nối: snapshot backend → graph riêng → phân tích tin báo bằng
AI → hợp nhất thực thể → sàng lọc cụm → Agent điều tra → báo cáo có nguồn.
Giữ một InvestigationAgent kế thừa BaseAgent; không thêm Agent điều phối khác.

## Chạy thử

```powershell
uv run python -X utf8 -m app.ai pipeline --backend-database thienla.db --report-limit 8 --entity-pair-limit 10 --cluster-limit 4 --investigation-limit 2 --output data/pipeline-result.json
```

Đọc key/model từ `.env`; toàn bộ thư viện Python được quản lý bằng uv.
CLI in tiến trình từng stage, lưu báo cáo tổng hợp và thư mục phiên dưới
`data/ai-pipeline/<run_id>/`. Có thể đổi bằng `--runs-dir` hoặc `AI_PIPELINE_DIR`.
Cache dùng chung giữa các phiên cùng thư mục, vẫn kiểm tra model/prompt/input/schema.
Số lượt model đếm lần gọi logic của runner và lượt Agent; chưa đo token, chi phí
thực tế hoặc số lần SDK tự thử lại khi provider lỗi.

Backend có hai API:

- `POST /api/ai/pipeline/run`: nhận giới hạn của lượt thử, đọc đường dẫn backend
  và thư mục output từ cấu hình server; không cho caller chỉ định file bất kỳ.
- `GET /api/ai/pipeline/runs/{run_id}`: đọc lại kết quả đã lưu.

Ví dụ body:

```json
{
  "report_limit": 8,
  "entity_pair_limit": 10,
  "cluster_limit": 4,
  "investigation_limit": 2
}
```

Giới hạn cứng: 12 tin báo, 20 cặp thực thể, 6 cụm, 4 phiên Agent; mỗi phiên
Agent vẫn tối đa 12 tool call. Mỗi app chỉ chạy một pipeline cùng lúc; trùng
trả 409. API chạy theo request, có thể mất vài phút để build graph/gọi model,
chưa phải hệ thống job nền có resume. Khi bật mật khẩu web, cả hai API cần
phiên đăng nhập hoặc khóa service. Giới hạn 2 lượt chạy/phút; đọc kết quả dùng
giới hạn API thông thường, không tiêu lượt chạy.

## Từng bước xử lý

1. Đọc SQLite backend bằng kết nối chỉ đọc trong một transaction. Xuất ba CSV
   nguồn: apps, transfers, reports; loại cột `signals` và `analysis` dựng mẫu.
   Không đọc `cases`, verdict, confidence hay ground_truth để chọn mẫu cho AI.
2. Chọn cụm từ các cảnh báo latest còn trong backend: ưu tiên hai đầu hàng đợi
   và đa dạng tổ hợp tín hiệu, không dùng nhãn đánh giá. Cụm tối đa 100 hồ sơ.
   Có thể chỉ định `cluster_ids` từ danh sách hợp lệ thay cho lựa chọn mặc định.
3. Ưu tiên tin báo cùng người báo hoặc có chuỗi số liên quan nơi nhận của cụm.
   Đây chỉ là blocking sơ bộ trên văn bản; AI mới phân tích và trích đoạn nguồn.
4. Dựng SQLite graph mới trong thư mục phiên. Phân tích từng tin bằng AIService,
   kiểm tra dấu vết có thật trong nguồn, lưu ai_report_analysis và cạnh MENTIONS.
   Lỗi một tin được ghi riêng; không dựng kết quả safe hoặc độ phủ đầy đủ giả.
5. Tạo cặp thực thể có giới hạn trong các cụm đã chọn. AI phân biệt same,
   different, same_household; chỉ same mới hợp nhất, giữ bằng chứng gốc.
6. Tính đặc trưng từ graph vừa bổ sung rồi gọi AI triage theo lô. Note có độ phủ
   phân tích tin báo; ít tin được phân tích không được hiểu là không có lừa đảo.
7. Agent chỉ điều tra cụm investigate, trong ngân sách cấu hình. Skip được ghi
   skipped_by_triage; hết ngân sách là deferred_by_limit. Cả hai đều không tự
   biến thành kết luận benign. Mỗi phiên có trace riêng, trạng thái và nguồn.
8. Lưu result.json gồm giới hạn, hash CSV nguồn, stage/timing, độ phủ, quyết định
   sàng lọc, kết quả Agent, số lượt model/tool và cache hit. Kết quả completed/
   partial/failed mô tả lượt thử trong giới hạn, không khẳng định đã xử lý hết dữ liệu.

Nguồn code chia theo chức năng trong `app/ai/pipeline/`: source.py,
enrichment.py, triage.py, investigations.py, runner.py và schemas.py.

## Phạm vi thời gian và dữ liệu đang dùng

Đây là snapshot toàn bộ dữ liệu có trong backend tại lúc bắt đầu lượt thử.
Agent dùng GraphTools trên graph riêng; không được diễn giải kết quả là quyết
định tại thời điểm một cảnh báo lịch sử. Đường điều tra từ giao diện hiện tại
vẫn dùng BackendAgentTools với cutoff alert.ts.

Pipeline không thay graph, phân tích, cases hay trạng thái giao dịch của bản
backend đang phục vụ giao diện. Endpoint mới là luồng thử theo lô riêng, chưa
thay thế tự động Engine hoặc nút Điều tra. Không tự giữ tiền/liên hệ khách.

## Đánh giá sau khi chạy

`app/ai/evaluation/pipeline.py:score_pipeline` chỉ đọc ground_truth **sau** khi
pipeline kết thúc. Nó đo nhận diện rủi ro/tự báo nạn nhân ở tin đã phân tích,
vai trò được xác định, nhầm nạn nhân thành kẻ gian, tỷ lệ inconclusive, lỗi tool,
cụm bị triage bỏ qua và cụm chưa chạy do giới hạn.

Thử seed mới giúp kiểm tra pipeline trên số liệu khác, nhưng vẫn cùng cơ chế
sinh dữ liệu mô phỏng. Báo cáo chỉ chấm các ứng viên đã chọn, không công bố
recall trên toàn bộ 200.000 hồ sơ hoặc độ chính xác ở dữ liệu thực tế.

Lượt thử đã đo: [ai_pipeline_trial.md](ai_pipeline_trial.md).
