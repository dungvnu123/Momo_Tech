# Graph dữ liệu

Module độc lập tại `app/graph/`; phần dựng graph cơ sở không gọi LLM.
Agent truy cập qua tool, pipeline AI bổ sung nhận định trong `AIStore`.
PostgreSQL lưu toàn bộ dữ liệu nguồn và quan hệ. NetworkX chỉ tải graph con khi
tra cứu, tránh nạp toàn bộ graph của 200.000 hồ sơ vào RAM.

```text
app/graph/
├── normalize.py   # định danh ví, tài khoản ngân hàng, SĐT, dải IP
├── builder.py     # nạp CSV và dựng node/cạnh trong một transaction
├── store.py       # PostgreSQL, thống kê, truy xuất nguồn và graph con
└── __main__.py    # lệnh build và inspect
```

## Chạy

```powershell
uv sync --locked
uv run python -X utf8 gen_data.py
uv run python -m app.graph build
uv run python -m app.graph inspect app:HS00001 --depth 2
```

Nếu workspace chưa có uv trên PATH, thay `uv` bằng `.\.tools\bin\uv.exe`.

Mặc định đọc ba file trong `data/`, tạo `data/graph.db`; lệnh inspect xuất
`data/subgraph.json` gồm node, cạnh, nguồn bằng chứng và cờ `truncated`.
Các file này không commit. Lệnh build từ chối database đã có dữ liệu; dùng
`--replace` để dựng lại. Nếu nhập hoặc dựng lỗi, transaction rollback, giữ
nguyên dữ liệu trước đó. Chỉ dùng `--replace` trên database đầu ra của module.

Đọc bộ dữ liệu khác bằng:

```powershell
uv run python -m app.graph build --data-dir <thu-muc-csv> --database data/graph-other.db
```

Module hỗ trợ CSV của nhánh hiện tại và những cột bổ sung trên `dev_nghi` khi
được cung cấp. Không tự chuyển nhánh hoặc thay phiên bản `gen_data.py`.

## Quan hệ đã dựng

| Nguồn | Cạnh | Đích |
|---|---|---|
| Application | `HAS_WALLET` | Account ví chính chủ |
| Application | `APPLIED_BY` | Person, chỉ khớp CCCD chính xác |
| Application | `USES_DEVICE` | Device |
| Application | `REFERENCE` | Phone, giữ riêng vị trí ref1/ref2 |
| Application | `FROM_IP` | IpBlock /24, chỉ VPN/datacenter |
| Application | `SIM_IN` | SimBlock 8 số đầu, chỉ SIM dưới 30 ngày |
| Application | `SENT_TO` | Account nhận tiền, mỗi giao dịch là một cạnh riêng |
| Account ví nhận | `OPENED_ON` | Device mở ví, khi CSV có trường tương ứng |
| Report | `REPORTED_BY` | Account ví người báo |

Khóa ví: `account:momo:<sđt>`. Khóa tài khoản ngân hàng:
`account:bank:<mã-ngân-hàng>:<số-tài-khoản>`, giữ số 0 đầu và tách namespace
ngân hàng. Ví người vay và ví người nhận dùng cùng định danh, nên có thể tra
ra hồ sơ của người nhận qua cạnh `HAS_WALLET`.

Địa chỉ, eKYC và các trường hồ sơ khác được giữ trong dữ liệu nguồn. Không tạo
cạnh chung địa chỉ hoặc chung giá trị eKYC. Không hợp nhất người theo tên giống
nhau ở bước dựng graph cơ sở. Pipeline AI riêng trích tài khoản/hotline/tên
miền từ raw text, kiểm tra nguồn và tạo `MENTIONS`; xem [pipeline AI](ai_pipeline.md).
Không đọc `ground_truth.json` hay nhãn gian lận.

Bộ sinh dữ liệu cũ có giao dịch ghi loại ví nhưng số đích không phải SĐT, hoặc
loại đích mâu thuẫn với nhà cung cấp. Module không đoán lại loại tài khoản:
ghi nhận trong `quality_issues`, giữ giao dịch và tạo `UnresolvedAccount`
riêng cho từng giao dịch, với `recipient_resolved=False`. Những node này
không được coi là tài khoản chung để nối các hồ sơ. Có thể xem dòng gốc qua
`source_record()` và sửa dữ liệu nguồn trước khi dựng lại.

Mỗi cạnh có `source_table`, `source_id`, `observed_at`. `observed_at` là thời
điểm hồ sơ/giao dịch/tin báo ghi nhận, không phải thời điểm mở ví. Cạnh `SENT_TO`
có số tiền, phút sau giải ngân, phần trăm khoản vay và ngữ cảnh người nhận nếu
CSV có cung cấp. Trường không có được biểu diễn bằng `None`, không suy ra là
`False`. Toàn bộ dòng nguồn vẫn được giữ trong PostgreSQL.

## Truy vấn bằng Python

```python
from app.graph import GraphStore

with GraphStore("data/graph.db") as store:
    graph = store.neighborhood("app:HS00001", depth=2, max_nodes=200, max_edges=500)
    print(store.stats())
    for source, target, edge_id in graph.edges(keys=True):
        evidence = store.source_record(edge_id)
```

Graph trả về là `networkx.MultiDiGraph`, giữ chiều cạnh và các giao dịch lặp.
Tìm lân cận đi được cả hai hướng để từ thiết bị tìm hồ sơ dùng chung. Depth
giới hạn 0–5; số node/cạnh cũng bị giới hạn. Kết quả bị cắt đặt
`graph.graph['truncated'] = True`, caller cần kiểm tra trước khi sử dụng.

Đây là graph bằng chứng, chưa phải graph gom cụm: cùng người nhận hay cùng
thiết bị không đồng nghĩa gian lận. Bước sau mới xây chính sách chọn liên kết
để tạo cụm, giữ ứng viên đơn lẻ, trích dấu vết bằng AI và tool cho Agent.
Lệnh inspect xuất dữ liệu nguồn có thể chứa thông tin cá nhân; hiện chỉ phục
vụ phát triển local, chưa có che dữ liệu hay phân quyền để đưa ra API.

## Kiểm tra

```powershell
uv run python -m unittest discover -s tests -v
```

Đã kiểm tra toàn bộ dữ liệu seed `20261127`:

| Bộ dữ liệu | Hồ sơ | Giao dịch | Tin báo | Định danh người nhận mâu thuẫn |
|---|---:|---:|---:|---:|
| Bộ sinh hiện tại | 200.000 | 77.227 | 96 | 25.973 |
| Bộ sinh mới trên `dev_nghi` | 200.000 | 76.953 | 105 | 0 |

Cả hai dựng graph thành công. Đây là kiểm tra tính toàn vẹn dữ liệu và quan
hệ, chưa phải kết quả phát hiện gian lận. Bộ kiểm thử của Agent và
graph gồm truy ngược nguồn, nhiều giao dịch cùng cặp node, rollback khi dựng
lỗi, dữ liệu người nhận mâu thuẫn và giới hạn kích thước graph con.
