# Agent điều tra

`InvestigationAgent` kế thừa `BaseAgent`, mở rộng workflow LangGraph thành
`model → tool → model`, kết thúc bằng `submit_case`. Điểm vào hiện là một
`app_id`, có thể kèm `cluster_id` đã được lưu. AI sàng lọc và các tool nghiệp
vụ đã có trong [pipeline AI](ai_pipeline.md); chưa tự tạo cụm từ toàn bộ graph.

```text
app/agents/investigation/
├── agent.py        # kế thừa base, chạy phiên riêng và stream SSE
├── workflow.py     # điều phối model/tool, ngân sách, kiểm tra bằng chứng
├── schemas.py      # input, kết luận, sự kiện gọi tool và kết quả phiên
├── prompt.md       # hướng dẫn điều tra và phân biệt nạn nhân
├── demo.py         # model giả chỉ dùng khi chọn demo hoặc test
└── __main__.py     # CLI chạy demo hoặc Gemini thật
```

Các tool đọc graph vẫn nằm ở `app/tools/`. Gemini adapter nằm tại
`app/services/gemini_client.py`, hợp đồng model/tool tại `tool_llm.py`.

## Test không cần API key

Cần có `data/graph.db` đã dựng theo [hướng dẫn graph](data_graph.md).

```powershell
uv sync --locked
uv run python -m app.agents.investigation --app-id HS00001 --demo
uv run python -m app.agents.investigation --app-id HS00001 --demo --stream
```

Nếu uv chưa nằm trong PATH, dùng `.\.tools\bin\uv.exe` thay `uv`.
Demo gọi thật các tool trên SQLite local theo thứ tự: đọc hồ sơ, dòng tiền,
quan hệ thiết bị, bằng chứng rồi submit. Model lựa chọn tool được mô phỏng,
kết luận luôn `inconclusive`; demo không đo chất lượng suy luận hoặc phát
hiện gian lận và không gửi dữ liệu tới dịch vụ ngoài.

## Gemini thật

Copy `.env.example` thành `.env`, điền key riêng của bạn:

```dotenv
LLM_API_KEY=<your-key>
LLM_MODEL_NAME=gemini-3.5-flash-lite
```

Ứng dụng tự đọc `.env` tại gốc repository, không ghi đè biến môi trường đã
có. `.env` được Git bỏ qua. Không đưa key vào prompt, mã nguồn hoặc tài liệu.
SDK dùng API Gemini mặc định của Google; dữ liệu tool đã lọc và che định danh
được gửi tới model để điều tra. Chạy thật có thể phát sinh chi phí API.

```powershell
uv run python -m app.agents.investigation --app-id HS00001
uv run uvicorn app.main:app --reload
```

API `POST /api/investigations` gọi thẳng một InvestigationAgent; không cần
`agent_id` hoặc API list agent. Các endpoint `/api/v1/agents` cũ được giữ để
tránh thay đổi hành vi của phần base đã có.

```json
{
  "app_id": "HS00001",
  "conversation_id": "conv-001",
  "streamResponse": false
}
```

API trả JSON gồm `run_id`, `app_id`, `status`, `reason`, `case`, `steps`.
Đặt `streamResponse=true` để nhận SSE: `started`, `model_step`, `tool_result`,
`done`. Event `done` chứa cùng cấu trúc kết quả như chế độ JSON. Không stream
nội dung suy nghĩ hoặc văn bản tự do của model. Lỗi trong phiên trả kết quả
`status=failed`, kết luận `inconclusive`; caller cần kiểm tra cả status và
verdict. Nếu thiếu client/model hoặc database, API trả `503` trước khi stream.

## Ràng buộc

- Tối đa 12 lần gọi tool, tính cả `submit_case`, gồm cả lần gọi sai. Batch
  vượt ngân sách bị chặn trước khi thực thi. Terminal tool phải gọi riêng.
- ID lần gọi tool phải duy nhất trong phiên. Kết quả trả về model giữ đúng
  ID của lời gọi gốc. Gemini adapter giữ nguyên nội dung phản hồi của model,
  gồm metadata chữ ký, khi gửi lịch sử ở lượt tiếp theo; tắt tự thực thi
  function trong SDK để ngân sách luôn do workflow kiểm soát.
- Mặc định timeout 30 giây cho một lần gọi và 180 giây cho toàn phiên. Hủy
  caller truyền xuống model; truy vấn SQLite chạy trong thread chỉ đọc có
  thể hoàn tất sau khi caller hủy nhưng không có tác dụng ghi dữ liệu.
- Mỗi phiên tạo GraphTools riêng, không trộn ID thay thế hoặc bằng chứng
  giữa các lần điều tra. Chỉ đưa dữ liệu của phiên hiện tại vào model;
  không nhận system prompt tùy ý hoặc tái sử dụng history của phiên khác.
- Mỗi `evidence.source` phải trỏ tới `tool_call_id` đọc dữ liệu thành công
  trong phiên này. `members`/`victims` chỉ chứa app_id đã quan sát trong đầu
  ra tool và không chồng lấn. Kết luận xác định phải có bằng chứng.
  Kết quả tool có trường `tool_call_id` hiển thị rõ cho model. Nếu nộp sai,
  phản hồi chỉ ra trường sai và các nguồn hợp lệ, không lặp lại giá trị nhạy cảm.
- Kiểm tra trên chỉ xác minh cấu trúc và nguồn tham chiếu, không chứng minh
  rằng suy luận của LLM đúng. Prompt yêu cầu cân nhắc giả thuyết vô hại;
  việc model thực sự làm tốt cần được đánh giá riêng.
- Hết lượt, timeout, lỗi model hoặc chỉ trả văn bản thay vì gọi tool đều
  không tạo kết luận gian lận thay thế. `actions` chỉ là đề xuất, không có
  tool thực hiện phong tỏa hay thao tác bên ngoài.

Chưa có xác thực/phân quyền hoặc lưu phiên vào database. Đây là API phục vụ
kiểm tra nền tảng; chưa phải luồng ra quyết định tự động trong môi trường thật.

## Kiểm thử tự động

```powershell
uv run python -m unittest discover -s tests -v
```

Các test dùng model giả và mock SDK, không gọi API và không cần key. Bao gồm
tool loop, giới hạn ngân sách, bằng chứng giả hoặc từ tool lỗi, app_id chưa
quan sát, timeout, cancellation, SSE, concurrency, API và metadata Gemini.

Đã kiểm tra riêng Gemini thật với một hồ sơ mô phỏng: phiên hoàn tất bằng
`submit_case` sau 5 lần gọi tool, không có lần nộp kết luận bị từ chối trong
lượt kiểm tra cuối. Kết quả local nằm ở `data/investigation-live.json` và
không commit. Đây là xác nhận tích hợp, không phải chỉ số chất lượng mô hình.
