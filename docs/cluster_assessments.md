# Đánh giá cụm và vai trò từng hồ sơ

Agent đọc tổng hợp có nguồn, sau đó đánh giá riêng hai câu hỏi: cụm có tổ
hợp dấu hiệu đáng điều tra không, và dữ liệu nào hỗ trợ vai trò từng hồ sơ.
Cụm đáng điều tra không tự biến mọi người chuyển tiền thành đồng phạm.

## Tool tổng hợp

`app/tools/cluster_summary.py` tính tổng tất định, không dùng LLM cộng tiền.
Hai adapter phục vụ hai nguồn:

| Nguồn | Module | Phạm vi thời gian |
|---|---|---|
| Graph PostgreSQL | `app/tools/handlers/cluster_money.py` | Snapshot graph đang đọc |
| Backend | `app/backend/evidence/cluster_money.py` | Chỉ dữ liệu tới `alert.ts` |

GraphTools nhận `cluster_money_flow(cluster_id=...)` hoặc
`cluster_money_flow(app_ids=[...])`, tối đa 100 hồ sơ khác nhau. Backend gọi
không tham số để lấy toàn bộ snapshot cảnh báo. Không tải toàn bộ graph vào
prompt và không đọc đáp án để tổng hợp.

Tool trả `totals`, `application_summaries`, `recipients`, `transfers`,
`reports`, `coverage` và `limitations`. Tổng tiền/số giao dịch bao phủ mọi
giao dịch trong phạm vi chọn, kể cả khi trang chi tiết chỉ trả 20/50 giao
dịch. `next_offset` đọc tiếp chi tiết. Tối đa 20 nơi nhận và 50 tin báo chi
tiết; cờ truncated cho biết phần bị giới hạn. Hồ sơ không có giao dịch vẫn
xuất hiện. Tên thiếu ghi unknown, không tính là khác tên. Thống kê chuyển
nhanh khác tên dùng 120 phút sau giải ngân, không tự kết luận gian lận.

Mã nguồn ví dụ: `apps:HS...`, `transfers:CK...`, `reports:TB...` ở backend;
`applications:HS...`, `wallet_transfers:CK...`, `ai_report_analysis:TB...`
ở graph. Giao dịch có số tiền, thời điểm, mã hồ sơ và token nơi nhận; tin báo
có người báo thuộc hồ sơ nào, nguồn khớp và chế độ phân tích. Tool mới bỏ
tên, SĐT, CCCD và văn bản tin báo thô. Khớp tên không xác minh chủ tài khoản;
nơi nhận chung không xác định ý định.

## Kết quả và kiểm tra nguồn

`cluster_assessment.level` gồm `suspicious`, `no_pattern_observed`,
`insufficient_data`, kèm lý do, bằng chứng và giới hạn. Mức đầu nghĩa là cần
điều tra tổ hợp dấu hiệu, không xác nhận đường dây phạm tội. Mức thứ hai chỉ
nói về dữ liệu đã xem, không bảo đảm an toàn.

`application_assessments` ghi từng app_id, vai trò, lý do, bằng chứng và
thông tin thiếu:

| Role | Cách hiểu |
|---|---|
| `suspected_participant` | Có dấu hiệu riêng nghi liên quan phối hợp |
| `possible_victim` | Có dấu hiệu riêng về khả năng bị hại |
| `no_adverse_evidence` | Chưa thấy bằng chứng bất lợi trong dữ liệu đã xem |
| `undetermined` | Chưa xác định vai trò; phải nêu dữ liệu thiếu |

Mọi nhận định đều `verification_status=unverified`. Prompt ưu tiên tối đa
8 hồ sơ có bằng chứng rõ trong một phản hồi; server bổ sung hồ sơ còn lại
bằng `assessment_status=not_assessed`, role `undetermined`, không tự tạo
bằng chứng hoặc vai trò. Phân biệt với `assessed/undetermined`: đã xem riêng
nhưng vẫn thiếu thông tin. Giao diện hiển thị số đã đánh giá trên tổng số.

`app/agents/investigation/assessments.py` yêu cầu đọc tổng hợp đủ phạm vi
trước khi nộp. evidence.source phải là tool_call_id đọc thành công trong
chính phiên; record_ids phải có trong kết quả tool được dẫn. Bằng chứng cá
nhân phải thuộc đúng hồ sơ hoặc đến từ tool đọc trực tiếp hồ sơ đó. Không
dùng danh sách thành viên cụm làm bằng chứng riêng, không gán người tự báo
bị lừa thành suspected_participant. Dữ liệu bị cắt/độ phủ tin báo thiếu cần
ghi trong giới hạn.

Đây là kiểm tra nguồn và liên hệ với hồ sơ, **không chứng minh mọi suy luận
trong câu chữ là đúng**. Người kiểm tra cần đối chiếu và xác minh thêm.
Không tự đặt confidence hoặc ép kết luận.

Backend, API điều tra độc lập và pipeline bật require_assessments=True.
Mặc định False của lớp Agent giữ tương thích caller cũ. Case lưu cũ vẫn đọc
được; chạy Điều tra lại mới có định dạng mới. Verdict/members/victims cũ giữ
tương thích, phải khớp vai trò riêng khi được dùng. Đề xuất giao dịch tách
biệt với đánh giá cụm/vai trò, không thực hiện chặn tiền thật.

## Xem và kiểm thử

Lưới & Thám tử hiển thị đánh giá cụm, vai trò và nhóm chưa đánh giá. Bấm
**Xem nguồn** để mở ToolStep đã lưu: mã bản ghi, số tiền, thời điểm và độ
phủ. `web/case_evidence.js` phụ trách phần này. Trace pipeline đọc bằng:

`GET /api/ai/pipeline/runs/{run_id}/traces/{cluster_id}`

Endpoint dùng cùng đăng nhập/khóa service với API pipeline. Chấm sau chạy
đo riêng mức nghi vấn cụm, vai trò đã đánh giá/chưa đánh giá và verdict cũ;
đổi cách trình bày không được coi là tăng độ chính xác phát hiện gian lận.

```powershell
uv run python -m unittest discover -s tests -q
```

Feature Flow: `/flows/#/thienla-backend-agent-pipeline` và
`/flows/#/thienla-ai-batch-pipeline`.

Kết quả đã đo: [cluster_assessment_trial.md](cluster_assessment_trial.md).
