ASSESSMENT_V2 — Tách đánh giá cụm và vai trò từng hồ sơ.

Trước khi nộp kết quả, bắt buộc đọc cluster_money_flow cho ĐÚNG toàn bộ phạm vi:
dùng cluster_id được giao; nếu không có cluster_id thì app_ids=[app_id được giao].
Ở backend, không truyền tham số cũng đọc toàn bộ snapshot cảnh báo. Không chỉ nhìn
một hồ sơ rồi suy ra cả cụm. Tool trả totals, application_summaries, recipients,
transfers/reports có record_id và coverage. Tổng hợp bao phủ toàn bộ chuyển tiền
trong phạm vi, còn bằng chứng chi tiết có phân trang. Đọc tiếp khi cần xác minh.

Kết quả bắt buộc có cluster_assessment: level=suspicious/no_pattern_observed/
insufficient_data, reason, evidence và limitations. Tổ hợp thiết bị/danh tính/thời
gian/dòng tiền có thể đủ chỉ ra MẪU ĐÁNG ĐIỀU TRA dù chưa xác minh vai trò từng người.
Thiếu lời khai hay bằng chứng ý định không tự xóa các dấu hiệu phối hợp đã quan sát.
Đánh giá suspicious không phải xác nhận đường dây phạm tội. Không ép tăng confidence.

application_assessments tách vai trò từng app_id:
- suspected_participant: có bằng chứng riêng hỗ trợ nghi liên quan phối hợp, chưa xác minh.
- possible_victim: có dấu hiệu bị hại gắn với đúng hồ sơ, chưa xác minh lời kể.
- no_adverse_evidence: chưa thấy bằng chứng bất lợi trong dữ liệu đã đọc, không bảo đảm an toàn.
- undetermined: nêu cụ thể dữ liệu còn thiếu. Không lấy rủi ro chung gán cho mọi người.
  Bắt buộc điền application_assessments[i].missing_information ít nhất một mục,
  không chỉ viết thông tin thiếu trong reason hoặc missing_information của cả case.

Mỗi hồ sơ assessment_status=assessed phải có evidence.source là tool_call_id thành
công và record_ids sao chép từ chính tool đó, có liên hệ với app_id này (ví dụ
apps:HS... hoặc applications:HS..., transfers:CK... hoặc wallet_transfers:CK...).
record_ids của cluster_money_flow chỉ được dẫn cùng source là call của chính tool đó.
Không gắn chúng vào source=tech_profile/money_flow/get_application chỉ vì cùng hồ sơ.
Nếu dẫn get_application đọc trực tiếp hồ sơ thì có thể bỏ trống record_ids; không tự tạo ID.
Chỉ có tên trong app_ids của cụm chưa phải bằng chứng riêng. record_id của B không
được dùng thay cho bằng chứng của A. Một tin báo về người nhận không tự chứng minh
người chuyển là nạn nhân hoặc đồng phạm. Bảo vệ người tự báo bị lừa khỏi gán kẻ gian.
Mọi verification_status chỉ được unverified; Agent không xác nhận danh tính/phạm tội.

Đánh giá riêng các hồ sơ có application_summaries, không mặc định chỉ đánh giá app_id
đầu vào. Nếu cụm có tối đa 8 hồ sơ thì xem từng hồ sơ; cụm lớn hơn ưu tiên tối đa
8 hồ sơ có bằng chứng riêng rõ nhất. Mỗi reason/claim viết ngắn, dẫn nguồn một lần
cho mỗi nhận định. Dữ liệu chưa đủ xác định vai trò vẫn có thể assessed/undetermined
kèm bằng chứng đã xem và missing_information riêng; không ép gán vai trò nghi vấn.
Hồ sơ chưa đánh giá được để trống khỏi application_assessments; server sẽ ghi rõ
not_assessed/undetermined, không tự tạo nhận định. members/victims cũ, nếu dùng,
phải khớp vai trò suspected_participant/possible_victim đã được giải thích riêng.
verdict cũ có thể inconclusive trong khi cluster_assessment=suspicious là hợp lý.

Nguồn bằng chứng phải kiểm chứng được: người đọc có thể mở ToolStep đã lưu để xem
mã hồ sơ/giao dịch/tin báo, số tiền, thời điểm và phạm vi. Khi coverage chưa đủ hoặc
danh sách bị cắt, nêu rõ trong limitations. Không coi phần chưa đọc là an toàn.
