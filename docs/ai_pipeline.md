# Phần AI của Thiên La

Các chức năng AI đã tách trong `app/ai/`, dùng chung client Gemini, output
tool schema, validation và cache SQLite. Không cần tạo thêm agent điều phối
cho từng chức năng; Agent Thám tử vẫn kế thừa BaseAgent.

| Module | Nhiệm vụ |
|---|---|
| `shield/` | Schema, service, prompt và chuẩn hóa dấu vết trong tin báo |
| `entities/` | Schema, service, prompt và blocking cặp thực thể |
| `triage/` | Schema, service, prompt và thống kê cụm không PII |
| `transfer/` | Schema, service và prompt đánh giá giao dịch |
| `common/` | Runner/cache, schema nền và validation dùng chung |
| `service.py` | Ghép các service, giữ giao diện gọi chung |
| `pipeline/` | Đọc dữ liệu và lưu kết quả theo chức năng |
| `evaluation/` | Chấm từng giai đoạn, fixture giả, tổng hợp báo cáo |
| `../graph/ai_store/` | Lưu tin báo, thực thể, cụm và metadata thành module riêng |

Cấu trúc controller, tool và middleware: [project_structure.md](project_structure.md).

## API

Chạy `uv run uvicorn app.main:app --reload`, cấu hình key/model trong `.env`
theo [hướng dẫn Gemini](investigation_agent.md). Swagger tại `/docs`.

| POST | Đầu vào | Đầu ra |
|---|---|---|
| `/api/ai/shield/analyze` | `{text}` | scam/suspicious/safe, dấu vết, người báo có phải nạn nhân, lý do và lời khuyên |
| `/api/ai/entities/resolve` | `{pairs: [...]}` tối đa 20 | same/different/same_household cho từng pair_id |
| `/api/ai/triage` | `{clusters: [...]}` tối đa 30 | skip/investigate, loại nghi vấn và lý do cho từng cluster_id |
| `/api/ai/transfer/check` | Ngữ cảnh trước giao dịch | allow/warn/hold, lý do và lời khuyên; chỉ đề xuất |
| `/api/investigations` | app_id, cluster_id tùy chọn | Kết luận cùng bằng chứng và nhật ký tool, JSON hoặc SSE |

Schema đầy đủ được hiển thị trong Swagger. API AI phân tích đầu vào và trả
kết quả, không tự ghi kết quả bất kỳ từ caller vào graph. Pipeline offline
mới kiểm tra đối chiếu nguồn và lưu các nhận định.

Thiếu cấu hình model trả `503`, timeout `504`, provider/output không hợp lệ
trả `502`. Không trả nhãn safe giả khi phân tích thất bại. Lỗi trong phiên
Agent trả `status=failed` hoặc `limit_reached`, verdict `inconclusive`.

## Tích hợp dữ liệu và graph

```powershell
uv run python -m app.ai reports --limit 20 --output data/report-processing.json
uv run python -m app.ai entities --limit 100 --output data/entity-processing.json
uv run python -m app.ai triage --groups data/groups.json --output data/triage-processing.json
```

Nếu uv chưa có trên PATH, thay bằng `.\.tools\bin\uv.exe` trong workspace.
Các lệnh trên dùng model thật. Cache mặc định `data/ai-cache.db`, khóa cache
gồm provider, model, prompt, input và schema. Kết quả cache cũng được kiểm tra
lại; cache không còn hợp lệ bị bỏ để gọi model lại. Không có key trong cache.

Ví dụ `data/groups.json` do tầng dữ liệu/backend cung cấp:

```json
[
  {"cluster_id": "cluster-001", "app_ids": ["HS00001", "HS00002"]}
]
```

Tính thống kê cụm từ dữ liệu thật trong SQLite, gồm thời gian, SIM/VPN/eKYC,
độ tập trung thiết bị/tham chiếu, tiền đi nhanh, người nhận chung, tin báo và
quá hạn. Phần này không tự tạo cộng đồng/cụm từ toàn bộ graph. Không có eKYC
thì ghi thiếu dữ liệu; chưa phân tích đủ tin báo thì ghi rõ tỷ lệ phủ.

Tin báo được phân tích rồi lưu tại `ai_report_analysis`, tạo cạnh `MENTIONS`
từ Report đến Account/Phone/Domain/Url. Mỗi dấu vết phải là một đoạn có thật
trong văn bản nguồn, ngân hàng cũng phải hiện diện trong nguồn. Chỉ chuẩn hóa
sau khi giữ đoạn gốc. Link rút gọn giữ cả path để không gộp mọi link bit.ly
vào một thực thể. Không dùng raw text làm chỉ dẫn hệ thống.

Hợp nhất người dùng DOB cùng thiết bị, tên hoặc địa chỉ để sinh cặp ứng viên
có giới hạn. Chỉ gửi tên, DOB, địa chỉ và token thiết bị, không gửi CCCD/SĐT
trong module này. Chỉ `same` mới tạo `ResolvedPerson` và cạnh `RESOLVED_AS`;
`same_household` giữ khác người, chỉ tạo `HOUSEHOLD_CANDIDATE`. Không xóa node
Person gốc. Các quyết định không tương thích trong cùng nhóm hoặc DOB khác
nhau không được hợp nhất. Lỗi lưu rollback toàn bộ batch.

Kết quả AI là nhận định có thể sai, cạnh có `ai_generated=true`, nguồn và
quyết định gốc để kiểm tra. Dựng lại graph bằng `--replace` sẽ xóa các nhận
định/cụm AI cũ trong cùng transaction, tránh gắn nhầm sang dữ liệu mới.

## Agent và bộ tool

Agent có 11 tool đọc: cluster_money_flow, get_application, neighbors, money_flow, get_evidence,
get_cluster, account_senders, reports_mentioning, timeline, tech_profile,
entity_info; tool kết thúc là submit_case. Nếu có cluster_id, Agent được
cung cấp phạm vi cụm để dùng truy vấn theo lô, không phải dò từng hồ sơ từ đầu.
Tóm tắt sàng lọc vẫn chỉ là gợi ý, cần đối chiếu dữ liệu trước khi kết luận.

Các truy vấn của Agent chỉ đọc database, có giới hạn, che định danh và dùng
ID thay thế theo phiên. Không trả nguyên văn tin báo có PII cho Agent;
reports_mentioning trả đánh giá, thủ đoạn, dấu hiệu nạn nhân và độ phủ phân
tích. Coverage chưa đủ thì kết quả không có tin báo không chứng minh an toàn.

## Kiểm tra và phạm vi đo

```powershell
uv run python -m unittest discover -s tests -v
uv run python -m app.ai evaluate --report-limit 12 --investigation-limit 4 --output data/ai-evaluation.json
```

Đánh giá dùng `ground_truth.json` **chỉ trong module chấm điểm** để chọn mẫu
và so kết quả. Không truyền nhãn, mô tả đường dây hoặc đáp án vào prompt.
Kết quả gồm số ca đúng/tổng, lỗi, trích xuất tài khoản, nhận diện người bị hại,
nguồn bằng chứng và số lượt tool. Một số cặp và tình huống chuyển tiền là bộ
kiểm tra giả được tạo riêng; ghi rõ trong báo cáo.

Các nhóm trong kiểm tra sàng lọc/điều tra là nhóm đã biết để kiểm tra năng lực
phân biệt, không đo khả năng tự phát hiện nhóm từ 200.000 hồ sơ. Mẫu hiện tại
đã dùng để chỉnh prompt và bổ sung đặc trưng; đây là tập phát triển, không
phải tập kiểm định độc lập. Không suy rộng accuracy trên mẫu thành precision/
recall toàn bộ hệ thống. Chưa chạy chấm chéo seed khác trong phiên này.

Lượt kiểm tra cuối trên dữ liệu seed `20261127` (Gemini thật, dùng lại cache
hợp lệ của các bước đã chạy):

| Phần | Số ca khớp đáp án |
|---|---:|
| Tin báo, gồm 5 tin chứa prompt injection | 12/12 |
| Cặp thực thể (4 cặp giả và 6 cặp từ dữ liệu) | 10/10 |
| Sàng lọc nhóm đã biết | 6/6 |
| Tình huống chuyển tiền giả | 4/4 |
| Verdict điều tra (2 nhóm gian lận, 1 nhóm nạn nhân, 1 nhóm vô hại) | 4/4 |

Chi tiết kết quả thực tế ở
`data/ai-evaluation.json`, nhật ký từng phiên ở `data/ai-investigations/`.

Accuracy của Agent trong báo cáo là độ khớp verdict ở từng tình huống, chưa
phải recall đầy đủ thành viên đường dây. Những verdict `inconclusive`, lỗi
provider và ca bị chặn validation được tính là chưa đạt khi so với đáp án.
Agent dành lượt cuối cho submit_case; hồ sơ đã có bằng chứng tự báo là nạn
nhân không được tự động đưa vào members, phải để xác minh nếu còn mâu thuẫn.

Muốn đánh giá bộ dữ liệu khác, dựng graph tương ứng rồi truyền đồng thời
`--database` và `--data-dir` phù hợp. File đánh giá, cache, raw input và key
đều nằm trong các vị trí được Git bỏ qua; chỉ `.env.example` được commit.

Backend vẫn phụ trách nguồn dữ liệu, tạo cụm ứng viên, phân quyền, lưu phiên
vụ việc, rate limit người dùng và giao diện. Module AI hiện là nền tảng chạy
local, chưa thực thi quyết định tài chính hay hành động bên ngoài.
