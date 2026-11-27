# Momo_Tech — Thiên La

**Trợ lý AI truy vết đường dây gian lận và lừa đảo tín dụng** cho đội rủi ro của các công ty cho vay qua ví điện tử.

> “Một người bị lừa báo tin, cả đường dây lộ diện.”

Chủ đề dự thi: **Chống lừa đảo** (chính) · An ninh mạng · Trợ lý AI.

## Tài liệu
- [docs/system_design.md](docs/system_design.md) — thiết kế hệ thống, đánh giá, đối chiếu thủ đoạn thực tế 2026 (có nguồn).
- [docs/Thien_La_gioi_thieu.docx](docs/Thien_La_gioi_thieu.docx) — bản giới thiệu đề tài.

## Dữ liệu mô phỏng
Toàn bộ là dữ liệu giả (thương hiệu “FinVay” hư cấu). Thư mục `data/` không commit — sinh lại bằng seed cố định:

```bash
uv run gen_data.py
```

Kết quả: `data/applications.csv` (200.000 hồ sơ), `data/wallet_transfers.csv`, `data/scam_reports.csv`, `data/ground_truth.json`, kèm tự kiểm tra và bảng baseline luật. Chỉ dùng thư viện chuẩn Python 3.10+.

## Trạng thái
- [x] BaseAgent + LangGraph, AgentManager và controller FastAPI
- [x] Sinh dữ liệu mô phỏng + baseline luật
- [x] Tài liệu thiết kế
- [ ] Lá chắn, Lưới, Sàng lọc AI, Thám tử
- [ ] Giao diện, triển khai online

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
và uvicorn; chưa tích hợp SDK model hoặc agent nghiệp vụ.

Mở `http://127.0.0.1:8000/docs` để xem API. Hiện chỉ đăng ký agent `default`.
Ứng dụng khởi động được khi chưa có API key; gọi agent sẽ trả `503` cho tới khi
truyền LLM client thật vào `create_app()`. Test sử dụng client giả riêng.

Nếu `uv` chưa có trong PATH, bản cục bộ của workspace này nằm tại
`.tools/bin/uv.exe`; ví dụ PowerShell: `.\.tools\bin\uv.exe sync --locked`.
Thư mục `.tools/` không được commit; máy khác cần cài uv trước.

Chi tiết mở rộng nền tảng: [docs/agent_foundation.md](docs/agent_foundation.md).
