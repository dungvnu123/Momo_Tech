# Thiên La — Hướng dẫn sử dụng

> Bản 1 trang để nộp kèm: `docs/hdsd/HDSD_Thien_La.pdf` (dựng bằng `uv run --with pymupdf python docs/tools/make_hdsd.py --link <địa chỉ>`).
> Tài liệu này là bản đầy đủ cho người dùng thử, đội rủi ro và người vận hành.

Thiên La có **3 cửa vào**:

| Địa chỉ | Dành cho | Đăng nhập |
|---|---|---|
| `/` | Đội rủi ro của ngân hàng cho vay và nền tảng ví | Mật khẩu `THIENLA_PASSWORD` (chế độ demo tự đăng nhập) |
| `/vi/` | Khách vay — app ví mô phỏng | SĐT + PIN 6 số (chế độ demo: bấm tên khách là vào) |
| `/flows/` | Ai cũng xem được — luồng trình chiếu kiến trúc, ca thật, bộ máy realtime | Không |

Toàn bộ dữ liệu là **mô phỏng** (200.000 hồ sơ, thương hiệu "FinVay" hư cấu). Không có dữ liệu khách hàng thật.

---

## 1. App ví của khách (`/vi/`)

### Đăng nhập
Trang đăng nhập liệt kê 3 khách demo cùng tình huống của từng người. Chế độ demo: bấm vào một khách là đăng nhập luôn. Chế độ thường: nhập SĐT + PIN.

### Trang chủ
Số dư ví · khoản vay hiện tại (hoặc vừa nhận) · kỳ trả tới · danh bạ. 4 nút: **Chuyển tiền**, **Vay nhanh**, **Hộp tin** (có số tin chưa đọc), **Lịch sử**.

### Hộp tin
- Tin có nhãn **chính thức** đến từ kênh brandname đã xác thực của FinVay. Tin từ số lạ / Zalo không có nhãn.
- Bấm một tin để đọc, rồi:
  - **⚑ Báo lừa đảo** — Lá chắn phân tích: *Lừa đảo / Đáng ngờ / An toàn*, lý do, số người đã báo cùng tài khoản, lời khuyên. Tin bị báo là lừa sẽ thành **cảnh báo trên hàng đợi đội rủi ro**.
  - **Làm theo hướng dẫn** — đóng vai nạn nhân: form chuyển tiền tự điền đúng số tài khoản, tên, số tiền, nội dung theo tin nhắn.

### Vay nhanh
Mô phỏng một khoản vay vừa giải ngân về ví (tối đa 20 triệu) — để thử kịch bản "vay rồi bị dụ chuyển đi".

### Chuyển tiền
Chọn ngân hàng/ví, nhập số tài khoản, tên, số tiền, nội dung; có ô **Lưu người nhận vào danh bạ** (kẻ lừa hay dặn làm việc này). Kết quả:

| Kết quả | Ý nghĩa | Khách làm gì |
|---|---|---|
| **Chuyển thành công** | Không có dấu hiệu bất thường | — |
| **Khoan đã!** (cảnh báo) | Có dấu hiệu, nhưng có thể là giao dịch thật | Đọc lý do → **Huỷ** hoặc **Vẫn chuyển** |
| **Giao dịch đang tạm giữ** | Dấu hiệu lừa rõ | Tiền **chưa rời ví**; đội rủi ro đã nhận cảnh báo và sẽ liên hệ |

### Ba khách demo và tình huống

| Khách | Tình huống ① (tin mới nhất) | Tình huống ② | Cách thử |
|---|---|---|---|
| Khách 1 | Dụ vay rồi chuyển — tài khoản nhận đã bị nhiều người báo | Giả bên thu hồi nợ: "quá hạn, nộp phí phạt vào tài khoản công ty" | ① Vay nhanh → Làm theo hướng dẫn → Chuyển → **tạm giữ**. ② Làm theo hướng dẫn → Chuyển → **tạm giữ** (FinVay chỉ thu nợ trong app) |
| Khách 2 | Dụ vay rồi chuyển — tài khoản nhận bị SIMO gắn cờ | Link giả "tất toán giảm 50% lãi" đòi nhập OTP | ① như trên → **tạm giữ**. ② **Báo lừa đảo** → Lá chắn chỉ ra link giả + đòi OTP |
| Khách 3 | Dụ vay rồi chuyển — tài khoản mới tinh, bị dặn "lưu số vào danh bạ" | "Mẹ" nhắn Zalo nhờ chuyển gấp 3 triệu vì đang cấp cứu | ① → **tạm giữ** (số vừa lưu vài phút trước là dấu hiệu, không phải bằng chứng tin cậy). ② làm **trước khi vay**: → **Khoan đã!** — khuyên gọi điện xác minh người thân |

Thử thêm: **báo một tin chính thức** → ra **An toàn** (hệ thống không báo nhầm). **Chuyển cho người thân trong danh bạ** → thành công, không bị làm phiền.

---

## 2. Màn đội rủi ro (`/`)

| Tab | Dùng để |
|---|---|
| **Tổng quan** | Phễu xử lý (sự kiện → hồ sơ có tín hiệu → cụm → cảnh báo → kết luận), so với luật cố định, bảng **thời gian phát hiện** từng đường dây |
| **Lá chắn** | Dán bất kỳ tin nhắn/link/số tài khoản nghi lừa; có tin mẫu |
| **Chuyển tiền** | 5 giao dịch mẫu trong dữ liệu → xem nền tảng ví xử lý ra sao + ngữ cảnh người nhận (danh bạ, lịch sử, SIMO) |
| **Lưới & Thám tử** | Mô phỏng hoạt động · hàng đợi cảnh báo · đồ thị · dòng thời gian hồ sơ · điều tra |

### Lưới & Thám tử — thao tác
1. **Mô phỏng hoạt động trực tiếp**: chọn nhịp (1/2/5 giây mỗi sự kiện) → **▶ Bật mô phỏng**. Hệ thống tự sinh khoản vay + chuyển tiền ngẫu nhiên — phần lớn bình thường (rút về tài khoản chính chủ, chuyển người nhà, trả tiền phòng), một phần là lừa (bị dụ vay, giả thu nợ, người thân nhờ gấp). Ô **Lừa bị chặn** và **Bình thường bị làm phiền** cho biết hệ thống vừa chặn đúng bao nhiêu và làm phiền nhầm bao nhiêu. Tự dừng sau 2.000 sự kiện.
2. **Lọc hàng đợi**: bấm 1 cột ngày (hoặc *Mọi ngày*); bấm 1 cột giờ hoặc khung **Đêm 0–6h / Sáng / Chiều / Tối**; mức **Khẩn / Cao / Trung bình**; loại (cụm hồ sơ / giao dịch tạm giữ); kết luận; **Tin cậy ≥**; tìm mã cụm/hồ sơ; *Mỗi cụm 1 dòng*.
3. **Sắp xếp**: ưu tiên cao nhất (mặc định) / mới nhất / tin cậy cao nhất / cụm lớn nhất.
4. **Chọn 1 cảnh báo** → đồ thị quan hệ (hồ sơ + điểm dùng chung: thiết bị, SĐT tham chiếu, nơi nhận tiền, dải IP/lô SIM; viền vàng = đang chờ giải ngân) + **diễn biến cụm** theo thời gian. **⤢ Vừa khung** hoặc bấm đúp nền để căn lại đồ thị.
5. **Bấm 1 hồ sơ** trên đồ thị → **dòng thời gian**: nộp → eKYC từng lần → duyệt → giải ngân → từng lần chuyển (cờ SIMO / ngoài danh bạ / lần đầu) → đến hạn/trả → tin báo → cảnh báo, kèm **quá hạn N ngày tại lúc cảnh báo**.
6. **Điều tra** → agent chạy từng bước (chỉ thấy dữ liệu tới lúc cảnh báo) → kết luận **Đường dây / Nạn nhân / Vô hại / Chưa đủ căn cứ** + việc cần làm. Quyết định cuối là của người.
7. **▶ Phát realtime**: phát lại cảnh báo từ 01/11 theo đồng hồ tua nhanh.

Cảnh báo mã `LV…` là cảnh báo **trực tiếp** (từ app khách hoặc bộ mô phỏng); hàng đợi tự làm mới khi có cảnh báo mới.

---

## 3. Vận hành

### Chạy lần đầu
```bash
cp .env.example .env              # đổi POSTGRES_PASSWORD, THIENLA_PASSWORD, THIENLA_SECRET, DEMO_PIN
docker compose up -d db
uv sync
python gen_data.py
uv run python build.py
uv run uvicorn app.main:app --port 4420          # hoặc: docker compose --profile app up -d --build
```

### Cờ cấu hình (`.env`)

| Biến | Ý nghĩa |
|---|---|
| `THIENLA_PASSWORD` | Mật khẩu màn đội rủi ro. Bỏ trống = không cần đăng nhập (chỉ dùng trên máy mình) |
| `THIENLA_SECRET` | Khoá ký phiên (`openssl rand -hex 32`). Bỏ trống = sinh ngẫu nhiên mỗi lần khởi động |
| `DEMO_PIN` | PIN chung của 3 khách demo |
| `DEMO_AUTOFILL=1` | Chế độ trình diễn: tự đăng nhập, **trả mật khẩu/PIN cho trình duyệt** — chỉ bật khi demo |
| `SIM_AUTOSTART=1`, `SIM_INTERVAL` | Bật mô phỏng hoạt động ngay khi server chạy, nhịp (giây) |
| `THIENLA_BEHIND_PROXY=1` | Chạy sau Caddy/Nginx: lấy IP thật, cookie Secure |

### Đặt lại dữ liệu demo
`uv run python build.py` — **xoá sạch** schema `public` rồi dựng lại (khoảng 15 giây): số dư, hộp tin, giao dịch của khách demo và mọi cảnh báo `LV…` về như ban đầu.

### Kiểm tra sau khi sửa code
```bash
uv run python build.py            # dữ liệu demo sạch
python tests/smoke.py .env        # ~50 phép thử: API đội rủi ro, 3 khách × 2 tình huống, phân quyền
```

### Xử lý sự cố

| Hiện tượng | Nguyên nhân thường gặp | Cách xử lý |
|---|---|---|
| App báo "PostgreSQL chưa có dữ liệu" | Chưa chạy `build.py` | `uv run python build.py` |
| Không kết nối được DB | Container `db` chưa chạy / sai `DATABASE_URL` | `docker compose up -d db`; kiểm tra cổng 5433 |
| Đăng nhập báo "Quá nhiều yêu cầu" (429) | Giới hạn 5 lần đăng nhập/phút | Đợi 1 phút |
| Khách demo "Số dư không đủ" | Đã chuyển hết khi thử | **Vay nhanh**, hoặc đặt lại dữ liệu demo |
| Đồ thị trống | Zoom quá xa / khung đổi kích thước | **⤢ Vừa khung** hoặc bấm đúp nền đồ thị |
