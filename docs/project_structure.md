# Cấu trúc code theo chức năng

```text
app/
├── main.py                    # app factory, đăng ký controller và middleware
├── db/
│   ├── config.py              # cấu hình kết nối và môi trường
│   ├── connection.py          # kết nối, transaction, thao tác SQL
│   ├── routing.py             # ánh xạ schema và database test
│   ├── rows.py                # định dạng dòng kết quả
│   ├── schema.py              # kiểm tra bảng/cột/schema
│   └── statements.py          # tham số SQL và tương thích câu lệnh
├── security/
│   ├── config.py              # chính sách, cookie, giới hạn và header
│   ├── sessions.py            # phiên đội rủi ro
│   ├── customers.py           # PIN và phiên khách
│   ├── rate_limit.py          # IP và giới hạn lượt gọi
│   └── policy.py              # quyền truy cập theo từng app
├── backend/
│   ├── wallet/                # auth, profile, inbox, loans, recipients,
│   │                         # transfers, decisions, persistence, runtime
│   ├── simulation/            # runner, scenarios, constants, routes
│   ├── integration/           # adapter cho reports, transfers, investigation
│   ├── mock_ai/               # luật mô phỏng tách theo từng chức năng
│   ├── events/                # schema và outbox
│   ├── knowledge/             # chuyển đổi tin báo, tra cứu người nhận
│   ├── cases/                 # lưu vụ việc và liên kết bằng chứng
│   ├── evidence/              # dữ liệu tool theo snapshot, cutoff và nguồn
│   ├── http/                  # API đội rủi ro theo từng màn hình
│   ├── agent_tools.py         # điều phối tool backend
│   ├── store.py               # truy vấn nghiệp vụ
│   └── routes.py              # ghép backend, web và Feature Flow
├── ai/
│   ├── shield/                # phân tích tin báo
│   ├── entities/              # hợp nhất thực thể
│   ├── triage/                # tổng hợp và sàng lọc cụm
│   ├── transfer/              # đánh giá giao dịch
│   ├── realtime/              # worker xử lý sự kiện mới
│   ├── pipeline/              # xử lý theo lô
│   ├── evaluation/            # đánh giá từng giai đoạn
│   ├── common/                # schema nền, runner/cache và validation chung
│   └── service.py             # giao diện gọi các service
├── agents/investigation/      # Agent, workflow, schema, prompt, kiểm tra nguồn
├── engine/                    # state machine lịch sử, events và tiêu đề cảnh báo
├── graph/                     # store, builder, ai_store và ingestion
├── tools/                     # graph_tools, schemas, views và handlers
├── controller/                # API AI và Agent
├── core/                      # config, clock, HTTP, logging, OpenAPI
└── middleware/                # request context, service key, web security

web/
├── app.js                     # khởi động màn đội rủi ro
├── js/
│   ├── core.js, auth.js, navigation.js
│   ├── overview.js, shield.js, transfers.js, simulation.js, replay.js
│   └── investigation/         # state, queue, graph, runner, case, evidence
└── vi/
    ├── vi.js                  # khởi động app khách
    └── js/                    # core, auth, profile, inbox, loans, transfers, history

flows/
├── build_flows.py              # lệnh dựng toàn bộ luồng
├── registry.py                 # danh sách builder
├── common.py                   # helper trình bày chung
├── catalog/                    # mỗi chủ đề một builder
└── backend_agent.py, batch_ai.py, realtime_ai.py

tests/realtime/
├── clients.py, fixtures.py
└── test_wallet.py, test_worker.py, test_evidence.py, test_isolation.py
```

Mỗi module giữ một trách nhiệm. Các file `__init__.py` chỉ công bố giao diện
package hoặc ghép các thành phần. Những file AI cũ chỉ xuất lại import đã
được bỏ; caller dùng trực tiếp `ai/shield`, `ai/triage`, `ai/entities`,
`ai/transfer` và `ai/common`.

Ví khách nhận `WalletContext` riêng khi tạo app, gồm store và adapter của app
đó. Simulator nhận cùng context; không có `khach.tools`, `khach.adapter` hoặc
singleton simulator dùng chung giữa các app.

Để debug một tin báo từ app khách:

`backend/wallet/inbox.py → backend/wallet/decisions.py → backend/integration/reports.py → ai/shield/service.py`

Để debug giao dịch:

`backend/wallet/transfers.py → backend/wallet/persistence.py → backend/events/store.py → ai/realtime/service.py`

Để debug kết quả Agent:

`backend/integration/investigation.py → agents/investigation/workflow.py → backend/agent_tools.py → backend/evidence/`

Các URL API, hợp đồng request/response, schema Agent/tool, nội dung prompt và
quy tắc nghiệp vụ được đối chiếu với bản trước khi tổ chức lại. Frontend vẫn
dùng JavaScript thuần; HTML nạp các file theo thứ tự phụ thuộc, app.js/vi.js
chỉ khởi động sau khi các chức năng đã được nạp.

## Middleware dùng cho việc gì?

Middleware xử lý phần chung của HTTP, không chạy logic phân tích AI.

- `RequestContextMiddleware`: nhận `X-Request-ID` hợp lệ hoặc tạo UUID,
  lưu vào `request.state.request_id` và trả cùng ID trong response header.
  Ghi log thời gian, mã trạng thái, method và tên operation. Không ghi body,
  query string, key Gemini hay header xác thực. Route được ghi là template
  do router cung cấp; operation là tên module/hàm để định vị code.
- `ServiceKeyMiddleware`: nếu cấu hình `APP_API_KEY`, các đường dẫn
  `/api/*` yêu cầu `X-API-Key` đúng. Sai hoặc thiếu key trả `401` trước khi
  gọi model. Khi bật đăng nhập web, cho phép phiên cookie hợp lệ và những
  API web công khai (login, Lá chắn, thống kê). `/health` vẫn truy cập được;
  Swagger/OpenAPI mở khi local không bật mật khẩu và tắt khi bật mật khẩu.
- `WebSecurityMiddleware`: phiên web, giới hạn lượt gọi theo IP và header
  bảo mật. Các API hồ sơ và AI điều tra cần cookie hoặc khóa service khi
  đặt `THIENLA_PASSWORD`. Bộ đếm theo app; SSE chuyển tiếp ngay từng chunk.
  Đăng nhập/me/logout nằm trong `backend/http/auth.py`, ký phiên ở `security/sessions.py`.
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
