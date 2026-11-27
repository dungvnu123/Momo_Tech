# Cấu trúc theo chức năng và middleware

```text
app/
├── backend/
│   ├── http/         # shield, transfer, alerts, live, metrics và helper chung
│   ├── integration.py # đổi hợp đồng web sang AIService và InvestigationAgent
│   ├── agent_tools.py # tool giới hạn theo thời điểm cảnh báo, che định danh
│   ├── store.py      # truy vấn dữ liệu nghiệp vụ của backend
│   ├── mock_ai.py    # chỉ dùng dựng dữ liệu/kết quả mẫu offline
│   └── routes.py     # đăng ký API, static web và Feature Flow
├── ai/
│   ├── shield/       # schemas.py, service.py, prompt.md, indicators.py
│   ├── entities/     # schemas.py, service.py, prompt.md, candidates.py
│   ├── triage/       # schemas.py, service.py, prompt.md, features.py
│   ├── transfer/     # schemas.py, service.py, prompt.md
│   ├── common/       # schema nền, runner/cache, kiểm tra ID dùng chung
│   ├── pipeline/     # reports.py, entities.py, triage.py
│   ├── evaluation/   # từng giai đoạn chấm điểm và runner tổng hợp báo cáo
│   └── service.py    # ghép các service, giữ giao diện gọi chung
├── controller/
│   ├── ai/           # shield.py, entities.py, triage.py, transfer.py
│   └── investigations.py
├── tools/
│   ├── handlers/     # applications, relations, money, reports, entities,
│   │                 # clusters, timeline, evidence
│   ├── graph_tools.py
│   ├── schemas.py
│   └── views.py      # che dữ liệu và quản lý ID thay thế theo phiên
├── graph/
│   ├── ai_store/     # lưu tin báo, quyết định thực thể, cụm và metadata riêng
│   ├── builder.py
│   └── store.py
├── agents/investigation/
├── core/             # cấu hình môi trường, HTTP errors, logging, OpenAPI
├── middleware/       # request_context.py, api_key.py
└── main.py           # khởi tạo và gắn các thành phần
```

Mỗi chức năng AI có schema, xử lý và prompt của mình. `AIService` chỉ ghép
các service và dùng chung runner/cache. Các file như `ai/schemas.py`,
`ai/features.py`, `ai/runner.py` chỉ xuất lại tên cho code đang dùng import cũ;
logic thực tế nằm ở folder chức năng. Không sao chép logic giữa hai chỗ.

Để debug một request phân tích tin báo, đi theo:
`controller/ai/shield.py → ai/shield/service.py → ai/common/runner.py`.
Để debug truy vấn tool, đi theo:
`tools/graph_tools.py → tools/handlers/<chức năng>.py → graph/store.py`
hoặc module tương ứng trong `graph/ai_store/`.

## Middleware dùng cho việc gì?

Middleware xử lý phần chung của HTTP, không chạy logic phân tích AI.

- `RequestContextMiddleware`: nhận `X-Request-ID` hợp lệ hoặc tạo UUID,
  lưu vào `request.state.request_id` và trả cùng ID trong response header.
  Ghi log thời gian, mã trạng thái, method và tên operation. Không ghi body,
  query string, key Gemini hay header xác thực. Route được ghi là template
  do router cung cấp; operation là tên module/hàm để định vị code.
- `ServiceKeyMiddleware`: nếu cấu hình `APP_API_KEY`, các đường dẫn
  `/api/*` yêu cầu `X-API-Key` đúng. Sai hoặc thiếu key trả `401` trước khi
  gọi model. `/health`, `/docs`, `/openapi.json` vẫn truy cập được.
- Lỗi ngoài dự kiến dùng handler trong `core/http.py`: response `500`
  chỉ có thông báo chung và request ID, không trả nguyên văn exception.

Middleware viết bằng ASGI, chuyển tiếp các chunk SSE ngay khi có dữ liệu,
không gom toàn bộ stream. Log JSON dùng logger `app.requests`, cấu hình một
lần trong app factory; gọi create_app nhiều lần không thêm handler trùng.

## Bật khóa service cho backend gọi AI

Thêm vào `.env` rồi khởi động lại service:

```dotenv
APP_API_KEY=<your-internal-service-key>
```

Backend gửi header `X-API-Key` với khóa này. Trong Swagger, bấm **Authorize**
để nhập khóa khi đã bật cấu hình. OpenAPI chỉ khai báo tên header, không có
giá trị khóa. Để `APP_API_KEY` rỗng thì giữ chế độ local không yêu cầu key.

`APP_API_KEY` bảo vệ đường gọi backend → AI. `LLM_API_KEY` dùng riêng cho AI
→ Gemini; không dùng cùng một khóa cho hai mục đích. Cơ chế hiện tại không
thay thế đăng nhập, phân quyền người dùng hoặc giới hạn sử dụng ở backend.
CORS cần cấu hình theo origin frontend khi tích hợp giao diện, không mở
wildcard trong bản nền tảng này.

## Kiểm tra sau khi tách

```powershell
uv run python -m unittest discover -s tests -q
```

Đã đối chiếu schema đầu vào/đầu ra, schema tool, nội dung prompt và hợp đồng
request/response API với bản trước refactor. Đường dẫn API giữ nguyên;
Swagger được chia nhóm theo chức năng. Kết quả AI hợp lệ trong cache vẫn
đọc được sau khi chuyển folder. Lượt kiểm tra refactor không gọi Gemini.
