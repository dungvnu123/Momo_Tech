# Nối backend với AI

`app/main.py` khởi tạo AIService, Agent và middleware, sau đó gắn các tính năng
web qua `backend/routes.py` nếu có database nghiệp vụ. Không có database thì các
API AI độc lập vẫn chạy. Truyền đường dẫn database tường minh vào `create_app`
mà file chưa tồn tại sẽ báo lỗi.

| API giao diện | Xử lý AI | Kết quả |
|---|---|---|
| `POST /api/shield/analyze` | `AIService.analyze_report` | Giữ định dạng indicators dạng accounts/phones/urls cho web |
| `POST /api/transfer/check` | Đọc giao dịch theo ID, tạo `TransferCheck` | Giữ decision, reasons và message_for_customer |
| `GET /api/alerts/{aid}/investigate` | `InvestigationAgent` với `BackendAgentTools` | SSE step/case; lưu kết luận nếu Agent hoàn thành |

| `POST /api/khach/transfer` (app ví khách) | `BackendAI.check_transfer` qua `khach.ai_transfer` | Gemini quyết định; luật chỉ được nâng mức; thêm `risk_score` 0–100, `latency_ms`, `mode` |
| `POST /api/khach/report/{id}` (app ví khách) | `BackendAI.analyze_report` | Tin từ kênh chính thức đã xác thực không gọi AI |

Chưa cấu hình Gemini (`LLM_API_KEY` trống) → `BackendAI` tự rơi về bản luật
(`backend/mock_ai/`) cho cả 3 hàm `analyze_report` / `check_transfer` /
`investigate`, ghi `mode = "luật (chưa cấu hình AI)"`. Riêng `POST /api/investigations`
(đọc graph) vẫn trả `503`.

`backend/integration/` chỉ chuyển đổi hợp đồng. Các prompt, validation và
vòng lặp model/tool vẫn ở module AI và Agent hiện có. `backend/http/` chia theo
chức năng để debug từng API; không đặt nghiệp vụ AI vào middleware.

## Thời gian và bằng chứng

Agent từ cảnh báo đọc snapshot tới `alert.ts`: giao dịch, tin báo và hồ sơ mới
hơn bị loại. Tool không cho model chạy SQL hay truyền một thời điểm khác. Chỉ
trả trường cần thiết, dùng token ngẫu nhiên cho nơi nhận tiền, bỏ tên/địa chỉ/
CCCD/nội dung tin báo. Các trang trả tối đa 50 bản ghi; số lượng và cờ truncated
cho biết dữ liệu bị giới hạn. Danh sách hồ sơ trong cụm tối đa 100 ID trả về.

Các đánh giá tin báo dựng sẵn được ghi `annotation_mode=mock`. Bằng chứng nạn
nhân được kèm theo các lần đọc để bộ kiểm tra kết luận không cho xếp người tự
báo bị lừa thành kẻ gian. Agent phải dẫn tool_call_id hợp lệ của chính phiên
chạy, vẫn phải thử giải thích vô hại và có thể kết luận inconclusive.

Phiên lỗi/timeout không ghi đè kết luận đã có. Phiên hoàn thành ghi kết luận
vào bảng cases và cập nhật cảnh báo để giao diện đọc lại. Dữ liệu ground_truth
chỉ dùng ở `/api/metrics`, không đưa vào Agent hay tool.

## Cấu hình và giới hạn

- `THIENLA_DB`: tên dữ liệu nghiệp vụ, mặc định `thienla.db` → schema `public` trong PostgreSQL (xem `app/db/`).
- `THIENLA_DATA`: thư mục CSV và đáp án cho trang đánh giá.
- `GRAPH_DATABASE`: graph PostgreSQL cho API điều tra độc lập; build từ cùng CSV.
- `LLM_API_KEY`, `LLM_MODEL_NAME`: cấu hình Gemini, không commit `.env`.
- `APP_API_KEY`: xác thực ứng dụng gọi API bằng `X-API-Key`.
- `THIENLA_PASSWORD`, `THIENLA_SECRET`: bật đăng nhập đội rủi ro bằng cookie
  HttpOnly/SameSite=Strict có chữ ký và thời hạn 8 giờ. Khi bật mật khẩu,
  backend hồ sơ và các API AI điều tra/thực thể/triage được bảo vệ; phiên web
  hợp lệ hoặc khóa service đúng đều được chấp nhận. Login/me/logout, Lá chắn
  và thống kê tổng hợp vẫn công khai. Nếu chỉ bật khóa service mà không bật
  mật khẩu web, giữ quy tắc `/api/*` cần key như trước.
- `THIENLA_BEHIND_PROXY`: chỉ bật khi reverse proxy do mình quản lý; khi đó
  tin X-Forwarded-For và đặt cookie Secure. Không bật cho local HTTP.

Mật khẩu để trống thì local mở, Swagger vẫn có để test. Khi bật mật khẩu,
Swagger/OpenAPI được tắt. WebSecurityMiddleware dùng ASGI, áp dụng giới hạn
lượt gọi và header bảo mật mà không gom các chunk SSE. Bộ đếm riêng theo app;
khi chạy nhiều worker cần bộ đếm dùng chung. `/flows/` giữ CSP riêng của Feature Flow.

`build.py` và `engine.py` dùng `backend/mock_ai/` để phát lại toàn bộ dữ liệu
offline và tạo kết quả mẫu nhanh. Không thay hàng trăm lượt dựng mẫu thành gọi
LLM tự động. Các API AI độc lập cho entity resolution và triage vẫn hoạt động;
engine dựng dữ liệu chưa tự gọi hai API này. Thống kê của trang đánh giá gồm
cả kết quả mẫu chưa chạy lại và kết quả Agent đã lưu, không phải độ chính xác
của một lượt đánh giá toàn bộ bằng LLM.

Kiểm tra bằng `uv run python -m unittest discover -s tests -q`. Bộ test tích hợp
tiêm model giả có cấu trúc để kiểm tra hợp đồng HTTP/SSE, lưu case, bảo vệ bằng
key, che dữ liệu và không đọc dữ liệu tương lai; không gửi dữ liệu ra ngoài.

## Đánh giá giao dịch và vai trò người vay

Không có giá trị 50% cố định trong Agent thật: `confidence` do model tự trả,
chưa được hiệu chuẩn thành xác suất. Trước đây tool bỏ cờ SIMO ở chi tiết
giao dịch và không nối tin báo với token nơi nhận; giao diện chỉ hiện kết
luận vai trò cùng phần trăm nên kết quả thiếu hướng xử lý.

Hiện `get_cluster` trả đúng loại cảnh báo và `triggering_transfer_id`;
`get_transfer` trả cờ SIMO, số tiền, ngữ cảnh người nhận, thời gian từ giải
ngân và các tin báo khớp tới `as_of`. `money_flow` giữ những trường này,
trả aggregate toàn bộ cùng chi tiết phân trang. Tin báo được nối với token
người nhận; ngân hàng là một phần định danh người nhận khi truy ngược.
Khớp số tài khoản trong tin báo không có ngân hàng vẫn được ghi là chưa
xác minh, không âm thầm gộp các ngân hàng thành một tài khoản.

Kết quả có `transaction_assessments` cho từng giao dịch được đánh giá:
`transfer_id`, `recommendation` (allow/warn/hold/review), lý do và dẫn nguồn.
Với cảnh báo giao dịch, Agent phải đọc và đánh giá đúng giao dịch gây cảnh
báo trước khi nộp kết luận. Backend kiểm tra dẫn nguồn chứa đúng giao dịch;
hold cần SIMO hoặc cảnh báo nơi nhận có phạm vi đã xác minh. Tin báo giả lập
hoặc chỉ khớp số ngân hàng chưa đủ cho hold. Những kiểm tra này không gán
verdict, confidence hoặc tự thực hiện hành động tài chính.

Vai trò người vay vẫn có thể `inconclusive` khi thiếu dữ liệu. Khi đó Agent
phải nêu `missing_information` cụ thể; giao diện hiển thị lý do, bằng chứng,
giả thuyết vô hại và việc cần làm, thay vì trình bày 50% như xác suất gian lận.
Một giao dịch được ghi SIMO có thể cần đề xuất hold/xác minh trong khi vai trò
người chuyển chưa xác định. Lỗi provider/timeout được hiển thị là phiên chưa
hoàn thành, không giả thành nhận định thiếu dữ liệu.

`backend/evidence/` chia việc dựng dữ liệu giao dịch, nối tin báo và kiểm tra
đề xuất xử lý. Prompt cho snapshot backend nằm ở `backend/investigation_prompt.md`.
Schema kết quả dùng chung ở `agents/investigation/schemas.py`; vòng lặp vẫn
thuộc InvestigationAgent kế thừa BaseAgent. Khi gửi schema cho Gemini, bỏ
giới hạn độ dài mảng trong schema provider để tránh vượt giới hạn bộ giải mã;
Pydantic tiếp tục kiểm tra toàn bộ giới hạn và dẫn nguồn ở phía ứng dụng.

## Hợp đồng `TransferCheck` — tín hiệu backend gửi cho AI

Backend (`build_ctx` trong `app/backend/wallet/`, `transfer_ctx` trong `backend/http/transfer.py`) dựng ngữ cảnh,
`BackendAI.check_transfer` chuyển thành `TransferCheck` (`app/ai/transfer/schemas.py`, `extra="forbid"`).
Trường mới đều tuỳ chọn — thiếu thì coi như không có tín hiệu.

| Trường | Nguồn backend | Ý nghĩa |
|---|---|---|
| `recipient_ring_senders` | bảng `ring_accounts` (dựng ở `build.py` từ `cases`) | Số hồ sơ vay trong 1 vụ đường dây **đã điều tra** từng chuyển tiền (khác tên) cho người nhận này; > 0 cho phép hold |
| `share_of_balance` | số tiền / số dư ví khách | 0–1; không gửi số dư tuyệt đối |
| `note_tags` | `mock_ai.note_tags(nội dung CK)` | `fee` / `debt_collection` / `urgent` — **chỉ gửi nhãn**, không gửi chữ khách gõ (test `test_transfer_uses_real_service_and_maps_context` chặn rò dữ liệu riêng) |
| `customer_says_coached` | câu hỏi dừng lại trên app khách | Khách xác nhận có người hướng dẫn chuyển; cho phép hold |

Quy tắc hold của `TransferService`: chỉ khi có SIMO, tin báo người nhận, `recipient_ring_senders > 0`
hoặc `customer_says_coached`. Thêm tín hiệu mới: thêm trường vào `TransferCheck` → điền ở `BackendAI.check_transfer`
→ mô tả trong `app/ai/transfer/prompt.md` → nếu tín hiệu đủ mạnh để hold thì thêm vào `validate` trong `transfer/service.py`.
