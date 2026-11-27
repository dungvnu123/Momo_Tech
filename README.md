# Momo_Tech — Thiên La

**Trợ lý AI truy vết đường dây gian lận và lừa đảo tín dụng** cho đội rủi ro của các công ty cho vay qua ví điện tử.

> “Một người bị lừa báo tin, cả đường dây lộ diện.”

Chủ đề dự thi: **Chống lừa đảo** (chính) · An ninh mạng · Trợ lý AI.

## Tài liệu
- [docs/project_structure.md](docs/project_structure.md) — cấu trúc theo chức năng và middleware.
- [docs/system_design.md](docs/system_design.md) — thiết kế hệ thống, đánh giá, đối chiếu thủ đoạn thực tế 2026 (có nguồn).
- [docs/Thien_La_gioi_thieu.docx](docs/Thien_La_gioi_thieu.docx) — bản giới thiệu đề tài.
- [docs/huong_dan_su_dung.md](docs/huong_dan_su_dung.md) — **hướng dẫn sử dụng** đầy đủ (app khách, màn đội rủi ro, vận hành, xử lý sự cố).
- HDSD 1 trang A4 để nộp: `uv run --with pymupdf python docs/tools/make_hdsd.py --link <địa chỉ>` → `docs/hdsd/HDSD_Thien_La.pdf`
  (chứa tài khoản dùng thử nên **không commit**).

## Chạy

Hạ tầng: **PostgreSQL 16 trong Docker** + web app FastAPI. Cấu hình ở `.env` (chép từ `.env.example`, **không commit**).
Mọi dữ liệu nằm trong Postgres: schema `public` (nghiệp vụ, cảnh báo, app khách), `graph` (đồ thị bằng chứng), `ai_cache`
(bộ nhớ đệm AI). Lớp [app/db.py](app/db.py) ánh xạ tên "database" kiểu cũ (`thienla.db`, `data/graph.db`) sang schema.

```bash
cp .env.example .env               # đổi POSTGRES_PASSWORD, THIENLA_PASSWORD, THIENLA_SECRET, DEMO_PIN; điền LLM_API_KEY nếu dùng Gemini
docker compose up -d db            # Postgres ở 127.0.0.1:5433
uv sync --locked
uv run python -X utf8 gen_data.py  # sinh dữ liệu mô phỏng → data/
uv run python -X utf8 build.py     # nạp Postgres + bộ máy realtime + điều tra trước + tài khoản khách demo (~15 giây)
uv run python -m app.graph build --replace   # đồ thị bằng chứng cho API /api/investigations (tuỳ chọn)
uv run uvicorn app.main:app --host 127.0.0.1 --port 4420
# hoặc chạy app trong container:  docker compose --profile app up -d --build
```

`build.py` **xoá sạch schema `public` rồi dựng lại** — cũng là cách đặt lại dữ liệu demo về ban đầu.

| Địa chỉ | Dành cho |
|---|---|
| http://localhost:4420 | **Đội rủi ro** (đăng nhập bằng `THIENLA_PASSWORD`): Tổng quan, Lá chắn, Chuyển tiền, Lưới & Thám tử (hàng đợi realtime, đồ thị, dòng thời gian hồ sơ, điều tra) |
| http://localhost:4420/vi/ | **App ví của khách** (demo): đăng nhập SĐT + PIN (`DEMO_PIN`), xem ví/khoản vay, hộp tin, báo lừa đảo, vay nhanh, tra cứu người nhận, chuyển tiền |
| http://localhost:4420/flows/ | Luồng trình chiếu (Feature Flow) |
| http://localhost:4420/docs | Swagger (tắt khi đặt mật khẩu) |

**AI:** có `LLM_API_KEY` → Lá chắn, kiểm tra chuyển tiền và Thám tử gọi **Gemini** (Agent kế thừa `BaseAgent`, tối đa
12 tool call, kiểm chứng nguồn). Chưa có key → các chức năng đó tự rơi về **bản luật** ([app/backend/mock_ai.py](app/backend/mock_ai.py)),
ghi rõ `mode` trên giao diện — demo vẫn chạy được. `build.py` luôn dựng cảnh báo và kết luận mẫu bằng luật (không gọi LLM);
bấm **Điều tra** để chạy Gemini và thay kết luận mẫu. Chi tiết: [docs/backend_integration.md](docs/backend_integration.md).

**Lúc chuyển tiền (app khách):** mỗi giao dịch được chấm điểm rủi ro 0–100 kèm thời gian xử lý. Người nhận nằm trong
**đường dây đã điều tra** (bảng `ring_accounts`: nhận tiền từ ≥ 2 hồ sơ của cùng 1 vụ), trong SIMO hoặc đã bị báo → tạm giữ.
Cảnh báo kèm câu hỏi "có ai đang hướng dẫn bạn chuyển không?" — trả lời *có* → tạm giữ. Người nhận quen / khoản nhỏ không
tín hiệu → đường nhanh, không gọi AI.

**Chế độ trình diễn:** đặt `DEMO_AUTOFILL=1` → màn đội rủi ro tự đăng nhập, app khách bấm 1 SĐT demo là vào luôn.
Chế độ này **trả mật khẩu cho trình duyệt** — chỉ bật khi demo.

**Mô phỏng hoạt động:** tab Lưới & Thám tử → **▶ Bật mô phỏng** (hoặc `SIM_AUTOSTART=1`): tự sinh khoản vay + chuyển tiền
ngẫu nhiên, phần lớn bình thường, một phần là lừa — đếm số vụ lừa bị chặn và số giao dịch bình thường bị làm phiền.
Mô phỏng luôn dùng bản luật (không tốn lượt gọi AI).

**Kịch bản demo đầu-cuối:** đăng nhập app khách → mở tin nhắn lạ trong hộp tin → vay nhanh → chuyển tiền theo tin →
giao dịch bị **tạm giữ** kèm lý do → "Báo lừa đảo" → sang màn đội rủi ro, cảnh báo `LV…` hiện trên hàng đợi.

## Kiểm tra

```bash
uv run python -m unittest discover -s tests          # 161 test, chạy trên database <tên>_test riêng, tự dọn
uv run python -X utf8 build.py && python tests/smoke.py .env   # server đang chạy ở :4420 — 62 phép thử API đầu-cuối
```

Test đơn vị cần để trống `THIENLA_PASSWORD`, `DEMO_AUTOFILL`, `APP_API_KEY`, `LLM_API_KEY` (đặt rỗng khi chạy).

## Luồng trình chiếu

Dựng lại bằng `uv run python -X utf8 flows/build_flows.py`, mở `/flows/`, chọn nhóm **Thiên La**, bấm ▶ Trình chiếu:
- `thienla-kien-truc`: từ 200.000 hồ sơ tới đường dây (khối 3D).
- `thienla-ca-du-vay`: ca thật Công an An Giang cảnh báo 09/11/2026, ca demo chính.
- `thienla-agent-dieu-tra`, `thienla-backend-agent-pipeline`, `thienla-ai-batch-pipeline`: vòng điều tra của agent, pipeline backend → agent, pipeline AI theo lô.
- `thienla-vong-doi-ho-so`, `thienla-realtime`, `thienla-hang-doi`: vòng đời hồ sơ, bộ máy realtime, cách dùng hàng đợi.
- `thienla-app-khach`, `thienla-mo-phong`, `thienla-ha-tang`: app khách đầu-cuối, bộ mô phỏng, hạ tầng + bảo mật.

## Dữ liệu mô phỏng
Toàn bộ là dữ liệu giả (thương hiệu “FinVay” hư cấu). Thư mục `data/` không commit — sinh lại bằng seed cố định
(`uv run gen_data.py`): 200.000 hồ sơ + eKYC, lịch trả, lần trả, chuyển tiền, tin báo, `ground_truth.json` (chỉ dùng để chấm điểm).

## Trạng thái

Đăng nhập đội rủi ro: đặt `THIENLA_PASSWORD` và `THIENLA_SECRET` trong `.env`.
Để trống mật khẩu thì chạy local không cần đăng nhập. Khi đặt mật khẩu, API
hồ sơ/điều tra yêu cầu phiên cookie hoặc khóa service hợp lệ; Swagger/OpenAPI
được tắt. Lá chắn và thống kê tổng hợp vẫn công khai, có giới hạn lượt gọi.
Chỉ bật `THIENLA_BEHIND_PROXY=1` khi chạy sau reverse proxy do mình quản lý.

- [x] BaseAgent + LangGraph, AgentManager và controller FastAPI
- [x] Module graph dữ liệu riêng: PostgreSQL (schema `graph`), quan hệ có nguồn bằng chứng và graph con NetworkX
- [x] Agent điều tra kế thừa BaseAgent, gọi tool có giới hạn và client Gemini
- [x] AI phân tích tin báo, hợp nhất thực thể, sàng lọc cụm và đánh giá giao dịch
- [x] Sinh dữ liệu mô phỏng + baseline luật
- [x] Tài liệu thiết kế
- [x] Backend dựng cụm ứng viên, giao diện và luồng điều tra gọi AI
- [x] PostgreSQL + Docker, app ví khách, mô phỏng hoạt động
- [ ] Triển khai online

## Môi trường phát triển

Toàn bộ dự án dùng **uv**, Python **3.12** (xem `.python-version`). Khai báo
thư viện trong `pyproject.toml`, commit `uv.lock` để đồng bộ phiên bản.

```bash
uv sync --locked
uv run uvicorn app.main:app --reload
uv run python -m unittest discover -s tests -v
uv run gen_data.py
```

Thêm thư viện bằng `uv add <package>`, công cụ phát triển bằng
`uv add --dev <package>`. Không dùng `requirements.txt` hoặc cài thư viện trực
tiếp vào môi trường bằng pip. Phần nền tảng dùng FastAPI, Pydantic, LangGraph
và uvicorn. Agent điều tra có Gemini SDK; xem hướng dẫn cấu hình bên dưới.

Mở `http://127.0.0.1:8000/docs` để xem API. Điều tra bằng
`POST /api/investigations` với `app_id`, không cần chọn agent. Ứng dụng khởi
động được khi chưa có key: Lá chắn / kiểm tra chuyển tiền / điều tra cảnh báo rơi về bản luật; riêng `POST /api/investigations` trả `503` nếu thiếu cấu hình Gemini.
API agent mặc định cũ vẫn dùng client được truyền vào `create_app()`.

Nếu `uv` chưa có trong PATH, bản cục bộ của workspace này nằm tại
`.tools/bin/uv.exe`; ví dụ PowerShell: `.\.tools\bin\uv.exe sync --locked`.
Thư mục `.tools/` không được commit; máy khác cần cài uv trước.

Chi tiết mở rộng nền tảng: [docs/agent_foundation.md](docs/agent_foundation.md).

Graph dữ liệu: [docs/data_graph.md](docs/data_graph.md).

Tool truy vấn graph: [docs/graph_tools.md](docs/graph_tools.md).

Tổng hợp dòng tiền, đánh giá cụm và vai trò từng hồ sơ có nguồn kiểm chứng:
[docs/cluster_assessments.md](docs/cluster_assessments.md).

Agent điều tra và cấu hình Gemini: [docs/investigation_agent.md](docs/investigation_agent.md).

Toàn bộ module AI và cách kiểm tra: [docs/ai_pipeline.md](docs/ai_pipeline.md).

Pipeline thử theo lô từ backend, bổ sung graph bằng AI rồi điều tra:
[docs/ai_batch_pipeline.md](docs/ai_batch_pipeline.md). API
`POST /api/ai/pipeline/run` và CLI `uv run python -m app.ai pipeline`
chạy trên bản snapshot riêng, không thay kết quả đang phục vụ giao diện.
Xem [Feature Flow của pipeline theo lô](http://127.0.0.1:4420/flows/#/thienla-ai-batch-pipeline).

```bash
uv run python -m app.agents.investigation --app-id HS00001 --demo --stream
```

```bash
uv run gen_data.py
uv run python -m app.graph build --replace
uv run python -m app.graph inspect app:HS00001 --depth 2
```
