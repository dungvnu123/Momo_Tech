# AI cho sự kiện trực tiếp từ app khách

Luồng mới dùng PostgreSQL hiện tại: app khách ghi nghiệp vụ → outbox → graph
cập nhật từng sự kiện → tổng hợp cụm → AI sàng lọc → Agent điều tra → lưu case.
Giữ một InvestigationAgent kế thừa BaseAgent và workflow LangGraph đang có.

## Code theo chức năng

| Module | Trách nhiệm |
|---|---|
| `app/backend/events/schema.py` | Migration bổ sung cột/index/bảng, không dựng lại dữ liệu |
| `app/backend/events/wallet.py` | Ghi khoản vay/giao dịch/tin báo và outbox cùng transaction |
| `app/backend/events/store.py` | Sự kiện có khóa chống trùng |
| `app/backend/events/results.py`, `knowledge.py` | Lưu case và liên kết người nhận có trạng thái chưa xác minh, tra cứu theo ngân hàng |
| `app/backend/evidence/loans.py`, `live_transactions.py`, `senders.py` | Đọc khoản vay và KT đúng snapshot, cùng phân trang cho dữ liệu cũ/mới |
| `app/graph/ingestion/` | Project bản ghi, cạnh và nhận định có nguồn, receipt chống phát lại |
| `app/ai/realtime/` | Claim/retry, đọc nguồn, khoanh ứng viên, tính đặc trưng, điều phối AI |
| `app/controller/ai/realtime.py` | API trạng thái, xử lý một sự kiện và thử lại |

`khach.py` gọi các hàm ghi nghiệp vụ; không chứa vòng lặp Agent. Worker được
khởi tạo và đóng theo lifespan ứng dụng trong `backend/routes.py`. Worker dùng
kết nối PostgreSQL riêng. Simulator cũng phát sự kiện nhưng không gọi LLM.

## Dữ liệu và bằng chứng

- Khoản vay mới giữ `loan_id` và `app_id`. KT giữ `loan_id` và ngữ cảnh lúc
  kiểm tra; khoản vay phát sinh sau không thay ý nghĩa giao dịch đã ghi.
- `get_transfer`, `money_flow`, `cluster_money_flow`, `account_senders` và
  timeline đọc thêm dữ liệu trực tiếp. Mã nguồn gồm `khach_transfers:KT…`
  và `khach_loans:KL…`; giữ tương thích giao dịch CK và hồ sơ cũ.
- Tổng hợp backend dùng khoản vay gắn với giao dịch gây cảnh báo; nếu không
  có giao dịch tập trung thì dùng khoản giải ngân mới nhất tới cutoff.
  Đây không phải thống kê tổng mọi khoản vay trong lịch sử.
- `done` mới cộng vào tổng tiền đã chuyển. `held` hiện riêng ở held_amount,
  held_transfer_count và trang bằng chứng. Graph dùng SENT_TO cho done,
  TRANSFER_ATTEMPT cho held; khoản vay dùng node Loan và HAS_LOAN.
- Snapshot khóa theo thời điểm và sequence của outbox để không đọc sự kiện
  tới sau ngay cả khi trùng giây. Dữ liệu cũ chưa có outbox dùng cutoff thời gian.
- Tin báo AI lưu cả kết quả có kiểu, trích đoạn và canonical_indicators có
  phạm vi ngân hàng/ví. Chỉ sau đối chiếu nguồn mới tạo MENTIONS. Tin từ kênh
  chính thức đã xác thực không cần gọi lại LLM. Một tin trong hộp thư chỉ lưu
  một report dù người dùng gửi lại yêu cầu báo tin.
- Tin báo cũ chỉ khớp dãy số được ghi là chưa xác định ngân hàng. App mới
  tách exact_report_count và unscoped_report_count; khớp số chưa rõ ngân hàng
  hoặc liên kết vụ việc AI chưa xác minh không tự trở thành căn cứ hold.
- Vai trò và đánh giá cụm vẫn unverified. Tin tự báo lịch sử không tự chứng
  minh lời kể nói về KT/khoản vay hiện tại. Người xử lý cần đối chiếu nguồn.

## Xử lý nền

Migration tự chạy khi mount backend có các bảng app khách. Không chạy lại
`build.py` để nâng cấp: lệnh build xóa schema nghiệp vụ và chỉ dành để reset demo.
Không tự backfill mọi giao dịch lịch sử thành sự kiện mới.

Worker bật mặc định bằng `AI_REALTIME_ENABLED=1`; đặt 0 để chỉ ghi hàng đợi và
xử lý thủ công qua API. Mỗi worker xử lý tuần tự, ngân sách mặc định tối đa
6 sự kiện cần AI/phút. Một Agent vẫn tối đa 12 tool call và các timeout hiện có.

Claim bằng SKIP LOCKED và lease 5 phút, tối đa 3 lần thử. Lease hết hạn được
khôi phục; lỗi cuối ghi failed. Thiếu model giữ waiting_for_model, không giả
kết luận AI bằng luật. Simulation chỉ cập nhật graph, ghi rõ không điều tra AI.
Lỗi Agent lưu trace đã che định danh trong kết quả công việc; không ghi đè
case cũ. Case completed đã lưu được dùng lại nếu công việc phải chạy lại.
Gọi provider có thể được thử lại sau lỗi; không cam kết chỉ gọi API một lần
khi tiến trình dừng giữa chừng.

Khoanh cụm bằng quan hệ graph và ứng viên từ backend, tối đa 100 hồ sơ; nếu
bị giới hạn thì đưa cờ vào snapshot/coverage cho Agent nêu rõ. Không nạp toàn
graph vào prompt. Đặc trưng realtime chưa đánh giá đầy đủ eKYC và quá hạn,
được ghi thiếu trong bản tổng hợp; không tự điền 0 để coi an toàn.

Agent dùng BackendAgentTools tại cutoff. Graph phục vụ trí nhớ và quan hệ;
GraphTools tổng hợp theo khoản vay mới nhất đã project. Pipeline theo lô cũ
vẫn là snapshot riêng từ các bảng nguồn lịch sử, không thay worker realtime.

Kết quả mới ghi `cases`, `alerts`, `ai_case_recipients`. Liên kết người nhận
đúng ngân hàng từ vụ việc suspicious có thể cảnh báo lần chuyển sau, nhưng
không tự được ghi vào `ring_accounts` như đường dây đã xác minh. Bảng
ring_accounts cũ vẫn là chỉ mục dựng sẵn từ build/demo, chưa phải quy trình
xác minh của con người. Chưa thêm màn hình duyệt/xác minh vụ việc.

Worker chỉ đề xuất, không đổi số dư hay quyết định chặn tiền. Trạng thái held
trong app ví vẫn là cơ chế demo của backend. API callback qua ngân hàng thật,
huấn luyện model online và worker phân tán quy mô lớn chưa nằm trong luồng này.

## API và kiểm tra

Các API dùng phiên đội rủi ro hoặc khóa service, không dùng cookie khách:

| Method | Path | Chức năng |
|---|---|---|
| GET | `/api/ai/realtime/events?limit=20` | Trạng thái, lỗi và kết quả công việc; không trả nội dung tin thô |
| POST | `/api/ai/realtime/process` | Xử lý tối đa một sự kiện đang sẵn sàng |
| POST | `/api/ai/realtime/events/{event_id}/retry` | Đưa failed/waiting trở lại hàng đợi; không tranh công việc đang chạy |

```powershell
uv sync --locked
docker compose up -d db
# Cấu hình DATABASE_URL và Gemini trong .env; backend đã có dữ liệu.
uv run uvicorn app.main:app --host 127.0.0.1 --port 4420
uv run python -m unittest discover -s tests -q
```

App khách ở `/vi/`. Vay → chuyển theo tình huống demo → sang Lưới & Thám tử
xem cảnh báo/case và mở bằng chứng KT/KL. Giao diện tự đọc trạng thái công việc
để cập nhật case. Feature Flow: `/flows/#/thienla-ai-realtime`.

Kiểm thử PostgreSQL riêng bao gồm API đầu-cuối, held/done, gắn đúng khoản
vay, sự kiện cùng giây, rollback/outbox, phát lại, lease, thiếu model, xác
thực và phân biệt ngân hàng; toàn bộ 175 test qua. Lượt Gemini mô phỏng ngày 28/11/2026 đã chạy
triage → Agent completed sau 9 tool call ở lượt kiểm tra cuối: cụm suspicious, vai trò possible_victim
chưa xác minh và KT1 được đề xuất review. Đây là kiểm tra tích hợp một ca,
không phải đo độ chính xác phát hiện lừa đảo. Artifact local không commit:
`data/realtime-ai-trial/result.json`.
