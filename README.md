# Momo_Tech — Thiên La

**Trợ lý AI truy vết đường dây gian lận và lừa đảo tín dụng** cho đội rủi ro của các công ty cho vay qua ví điện tử.

> “Một người bị lừa báo tin, cả đường dây lộ diện.”

Chủ đề dự thi: **Chống lừa đảo** (chính) · An ninh mạng · Trợ lý AI.

## Tài liệu
- [docs/system_design.md](docs/system_design.md) — thiết kế hệ thống, đánh giá, đối chiếu thủ đoạn thực tế 2026 (có nguồn).
- [docs/Thien_La_gioi_thieu.docx](docs/Thien_La_gioi_thieu.docx) — bản giới thiệu đề tài.

## Luồng trình chiếu (feature-flow)
Dựng bằng [feature-flow](https://github.com/hoangvunghi/feature-flow), quản lý môi trường bằng `uv`:

```bash
uv sync
uv run python flows/build_flows.py                       # → docs/flows/*.json
FF_FLOWS_DIR=docs/flows uv run uvicorn feature_flow.server:app --port 4404
# PowerShell: $env:FF_FLOWS_DIR="docs/flows"; uv run uvicorn feature_flow.server:app --port 4404
```

Mở http://localhost:4404, chọn nhóm **Thiên La**, bấm ▶ Trình chiếu:
- `thienla-kien-truc`: từ 200.000 hồ sơ tới đường dây (khối 3D).
- `thienla-ca-du-vay`: ca thật Công an An Giang cảnh báo 09/11/2026, ca demo chính.
- `thienla-agent-dieu-tra`: vòng điều tra của agent.

## Dữ liệu mô phỏng
Toàn bộ là dữ liệu giả (thương hiệu “FinVay” hư cấu). Thư mục `data/` không commit — sinh lại bằng seed cố định:

```bash
python gen_data.py
```

Kết quả: `data/applications.csv` (200.000 hồ sơ), `data/wallet_transfers.csv`, `data/scam_reports.csv`, `data/ground_truth.json`, kèm tự kiểm tra và bảng baseline luật. Chỉ dùng thư viện chuẩn Python 3.10+.

## Trạng thái
- [x] Sinh dữ liệu mô phỏng + baseline luật
- [x] Tài liệu thiết kế
- [ ] Lá chắn, Lưới, Sàng lọc AI, Thám tử
- [ ] Giao diện, triển khai online
