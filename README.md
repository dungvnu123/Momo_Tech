# Momo_Tech — Thiên La

**Trợ lý AI truy vết đường dây gian lận và lừa đảo tín dụng** cho đội rủi ro của các công ty cho vay qua ví điện tử.

> “Một người bị lừa báo tin, cả đường dây lộ diện.”

Chủ đề dự thi: **Chống lừa đảo** (chính) · An ninh mạng · Trợ lý AI.

## Tài liệu
- [docs/system_design.md](docs/system_design.md) — thiết kế hệ thống, đánh giá, đối chiếu thủ đoạn thực tế 2026 (có nguồn).
- [docs/Thien_La_gioi_thieu.docx](docs/Thien_La_gioi_thieu.docx) — bản giới thiệu đề tài.

## Chạy web app

```bash
uv sync
python gen_data.py                 # sinh dữ liệu mô phỏng → data/
uv run python build.py             # dựng thienla.db: tín hiệu, cụm, tin báo, sàng lọc, điều tra trước (~10 giây)
uv run uvicorn app.main:app --port 4420
```

Mở http://localhost:4420 — 4 màn: **Tổng quan** (phễu + so với luật), **Lá chắn** (dán tin nghi lừa), **Chuyển tiền**
(cảnh báo lúc chuyển sau giải ngân), **Lưới & Thám tử** (cụm, đồ thị, điều tra từng bước). Luồng trình chiếu ở `/flows/`.

**Phần AI** nằm gọn trong [app/ai.py](app/ai.py): 4 hàm `analyze_report`, `check_transfer`, `triage_clusters`,
`investigate`. Hiện là **bản giả lập bằng luật** (`MODE = "mock"`, không gọi model, không đọc đáp án); người làm AI
thay thân 4 hàm, giữ nguyên tên + kiểu trả về (schema ở `docs/system_design.md` mục 5). Tool chỉ đọc cho agent: [app/tools.py](app/tools.py).

Kết quả bản giả lập (mốc để AI phải vượt): kết luận 356 hồ sơ là kẻ gian, đúng 58/58, không nhầm nạn nhân nào, nhưng
**nhầm 298 hồ sơ vô hại**; nhận ra 22/28 nạn nhân.

**Bảo mật:** đặt `THIENLA_PASSWORD` (và `THIENLA_SECRET`, `THIENLA_BEHIND_PROXY=1` khi sau Caddy) trước khi chạy ở nơi
khác máy mình — không đặt thì màn đội rủi ro mở (chế độ dev). Chi tiết: `docs/system_design.md` mục 9.

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
python gen_data.py                          # seed chuẩn → data/
python gen_data.py --seed 7 --out data_seed7  # bộ chấm chéo
```

Dữ liệu nhiều bảng, mọi thứ có mốc thời gian (01/06 → 25/11/2026):

| File | Mỗi dòng | Mốc thời gian |
|---|---|---|
| `applications.csv` | 1 hồ sơ (200.000) | nộp → xong eKYC → duyệt/từ chối → giải ngân; kỳ hạn 3 tháng, lãi 36%/năm |
| `ekyc_sessions.csv` | 1 lần thử eKYC | thời điểm, thiết bị, liveness, máy hook, đạt/trượt |
| `repayment_schedule.csv` | 1 kỳ trả | ngày đến hạn, gốc, lãi |
| `repayments.csv` | 1 lần trả | ngày trả, số tiền, kênh |
| `wallet_transfers.csv` | 1 lần chuyển đi sau giải ngân | thời điểm + ngữ cảnh người nhận (danh bạ, lịch sử, SIMO) |
| `scam_reports.csv` | 1 tin báo | thời điểm, chỉ có chữ thô |
| `ground_truth.json` | đáp án | chỉ dùng để chấm |

Quá hạn **không** là cột chốt sẵn: tính tại từng thời điểm từ lịch trả + các lần trả. Chỉ dùng thư viện chuẩn Python 3.10+.

## Trạng thái
- [x] Sinh dữ liệu mô phỏng + baseline luật
- [x] Tài liệu thiết kế
- [ ] Lá chắn, Lưới, Sàng lọc AI, Thám tử
- [ ] Giao diện, triển khai online
