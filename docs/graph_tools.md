# Tool truy vấn graph

Các tool đọc dữ liệu nằm trong `app/tools/`, dùng `GraphStore`/`AIStore` để
truy vấn PostgreSQL theo ID. Đã gắn vào Agent điều tra; không có endpoint công
khai cho từng tool. Bộ tool hiện có 11 hàm đọc và submit_case ở workflow.

| File | Trách nhiệm |
|---|---|
| `graph_tools.py` | Cổng gọi tool, kiểm tra tham số, mở database chỉ đọc và chuẩn hóa lỗi |
| `schemas.py` | Schema Pydantic, tên và mô tả tool để adapter LLM sử dụng |
| `handlers/` | Các module application, relations, money, evidence, reports, entities, clusters, timeline |
| `views.py` | Chọn trường đầu ra, che dữ liệu cá nhân, ID thay thế và so khớp tên |
| `../graph/store.py`, `../graph/ai_store/` | SQL tra cứu dữ liệu nguồn và nhận định AI theo chức năng |

## Sử dụng

Chạy Python bằng `uv run python`; nếu uv chưa có trên PATH, dùng
`.\.tools\bin\uv.exe run python` trong workspace này.

```python
from app.tools import GraphTools

tools = GraphTools("data/graph.db")

application = tools.get_application("HS00001")
relations = tools.neighbors("app:HS00001", edge_type="USES_DEVICE", limit=20)

if relations["ok"] and relations["data"]["edges"]:
    device_id = relations["data"]["edges"][0]["target"]
    shared = tools.neighbors(device_id, edge_type="USES_DEVICE", direction="incoming")

flow = tools.money_flow("HS00001", limit=20)
if flow["ok"] and flow["data"]["transfers"]:
    edge_id = flow["data"]["transfers"][0]["edge_id"]
    evidence = tools.get_evidence(edge_id)
```

Adapter LLM sau này lấy schema từ `tools.definitions`, nhận tên tool cùng
tham số JSON do model đề xuất rồi gọi:

```python
result = tools.call("neighbors", {
    "node_id": "app:HS00001",
    "edge_type": "SENT_TO",
    "direction": "outgoing",
    "limit": 20,
    "offset": 0,
})
```

Đầu ra thành công có `ok`, `tool`, `data`. Khi lỗi có `ok=False`, `tool`,
`error.code`, `error.message`. Các mã lỗi là `invalid_arguments`, `unknown_tool`,
`not_found`, `storage_unavailable`, `invalid_data`. Không đưa exception hoặc
đường dẫn database vào kết quả gửi model.

## Phạm vi từng tool

- `cluster_money_flow(cluster_id? hoặc app_ids?, limit?, offset?)`: tổng hợp
  dòng tiền tối đa 100 hồ sơ, có thống kê từng hồ sơ, nơi nhận chung và nguồn.
  Tổng không phụ thuộc trang chi tiết. Xem [đánh giá cụm](cluster_assessments.md).
- `get_application(app_id)`: lấy hồ sơ theo khóa chính, chấp nhận cả `HS00001`
  và `app:HS00001`; giữ tín hiệu kỹ thuật và che CCCD/SĐT.
- `neighbors(node_id, edge_type?, direction?, limit?, offset?)`: lấy cạnh kề
  một bước theo chiều vào, ra hoặc cả hai. Mỗi kết quả giữ ID cạnh và nguồn
  bằng chứng; không gộp mất những giao dịch lặp.
- `money_flow(app_id, limit?, offset?)`: lấy cạnh `SENT_TO` đi ra từ hồ sơ.
  `total_transfers` và `total_amount` tính trên toàn bộ giao dịch của hồ sơ,
  còn `transfers` chỉ là trang hiện tại. Phần trăm khoản vay tính theo từng
  giao dịch. So khớp tên được tính trong code sau khi bỏ dấu, chuẩn hóa chữ
  hoa/thường và khoảng trắng; không phải xác minh chủ sở hữu tài khoản.
- `get_evidence(edge_id)`: tra đúng dòng dữ liệu nguồn của cạnh, trả bản đã
  lọc và che thông tin. Không trả dòng nguồn nguyên văn.

Mặc định 20, tối đa 50 cạnh mỗi trang. `returned_count` là số cạnh trong trang;
`truncated=True` và `next_offset` báo còn dữ liệu. Tiếp tục dùng cùng bộ lọc,
cùng limit và offset được trả về để đọc trang sau. Một node có thể xuất hiện
trên nhiều cạnh. Database cần giữ ổn định trong quá trình phân trang.

## Dữ liệu cá nhân và ID

SĐT, CCCD và số tài khoản hiển thị được che bốn số giữa; định danh ngắn được
che toàn bộ. Họ tên, ngày sinh, địa chỉ, ghi chú giao dịch và raw text tin báo
không được trả ra. Với tin báo, `raw_text_omitted=True` nêu rõ phần chưa cung
cấp. Pipeline AI riêng phân tích tin báo; tool reports_mentioning chỉ cung
cấp đánh giá, thủ đoạn, reporter_app_ids và độ phủ thay vì raw text.

Node gốc có thể chứa SĐT/CCCD trong chính ID. Đầu ra tool dùng ID ngẫu nhiên
`node:<token>` cho các node đó, thiết bị và dải IP; LLM tiếp tục dùng ID này
để gọi `neighbors()`. ID hồ sơ, tin báo, cạnh và nguồn dữ liệu được giữ để
đối chiếu bằng chứng. Không cần và không được đoán ngược token.

Tạo một `GraphTools` cho mỗi phiên điều tra và giữ instance đó cho toàn bộ
chuỗi gọi tool. ID thay thế chỉ có hiệu lực trong instance này; tạo instance
khác sẽ không đọc được token cũ. Đây không phải cơ chế phân quyền: giới hạn
hồ sơ được phép đọc sẽ triển khai ở tầng phiên/API khi tích hợp Agent.

Mỗi lần gọi mở PostgreSQL bằng phiên chỉ đọc (`default_transaction_read_only`), không tạo schema nếu tên sai,
không dựng lại schema, không nạp toàn bộ graph vào NetworkX. Truy vấn dùng
tham số SQL và index có sẵn trên ID, nguồn và đích.

## Kiểm tra

```powershell
uv run python -m unittest discover -s tests -v
```

Các test của tool nằm ở `tests/test_graph_tools.py`, bao gồm việc đi từ hồ sơ
qua thiết bị để tìm hồ sơ khác, phân trang, tổng dòng tiền, truy ngược bằng
chứng, che dữ liệu trong ID lẫn payload, tham số sai và database chỉ đọc.
