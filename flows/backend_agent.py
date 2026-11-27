"""Feature Flow for the backend investigation path that is running today."""
from feature_flow import Flow
from feature_flow.model import Group


def backend_agent_pipeline():
    f = Flow("thienla-backend-agent-pipeline", "Backend → Full Agent → Kết quả")
    f.group, f.look = "Thiên La", "flat"
    f.meta(
        subtitle="Theo code đang chạy: snapshot cảnh báo → Gemini + tool → kiểm chứng → lưu case → SSE về giao diện.",
        duration="5 phút", level="Pipeline thực tế",
        learn=[
            "Backend tạo đầu vào; LLM chọn bước đọc; tool chỉ trả dữ liệu có nguồn",
            "Giới hạn 12 tool call, tính cả submit_case; kết luận sai nguồn phải sửa",
            "Đề xuất xử lý giao dịch tách khỏi kết luận vai trò người vay",
            "Chỉ phiên completed được lưu; lỗi không ghi đè kết quả cũ",
        ],
    )
    start = f.start("Bắt đầu")
    data = f.process("Dữ liệu và cảnh báo có sẵn", step=1, icon="database", badge="backend",
        explain="Demo: gen_data.py sinh CSV; build.py chạy Engine theo thời gian và ghi thienla.db. "
                "Engine + mock_ai.py dựng cảnh báo/kết luận mẫu bằng luật, không gọi LLM. "
                "Đây là dữ liệu mô phỏng; chưa có kết nối thật tới ngân hàng, ví hay SIMO.")
    request = f.process("Bấm Điều tra", step=2, icon="laptop", badge="EventSource",
        explain="web/app.js: runInvestigate(alert_id) gọi GET /api/alerts/{aid}/investigate. "
                "Request chỉ gửi ID cảnh báo, không gửi toàn bộ graph hoặc prompt tự do.")
    middleware = f.process("Kiểm tra request", step=3, icon="lock", badge="ASGI",
        explain="app/middleware/: nhận/tạo X-Request-ID và ghi log trạng thái, thời gian. "
                "Nếu cấu hình APP_API_KEY thì /api/* cần X-API-Key; không hợp lệ trả 401. "
                "Demo giao diện local hiện để khóa service trống. Middleware không suy luận gian lận.")
    snapshot = f.process("Đọc snapshot cảnh báo", step=4, icon="file", badge="alert.ts",
        explain="backend/http/alerts.py → Tools.alert(aid): đọc app_ids, signals, kind, transfer_id và ts. "
                "Không tìm thấy trả 404. BackendAgentTools chỉ cho đọc hồ sơ/giao dịch/tin báo đã xuất hiện tới ts. "
                "Nếu không có hồ sơ hợp lệ, trả case status=failed, reason=snapshot_empty.")
    agent = f.process("Khởi tạo Full Agent", step=5, icon="gear", badge="kế thừa BaseAgent",
        explain="BackendAI.investigate tạo InvestigationAgent và truyền tools_factory=BackendAgentTools. "
                "Dùng backend/investigation_prompt.md; Agent tạo run_id, messages, steps và LangGraph. "
                "request_id theo dõi HTTP; run_id theo dõi phiên điều tra. Không gửi toàn bộ dữ liệu cho model.")
    model = f.process("Gemini chọn bước tiếp theo", step=6, icon="cloud", badge="model node",
        explain="workflow.model_node → GeminiToolClient.complete(messages, definitions). "
                "Model nhận prompt + lịch sử các kết quả tool + schema tool. "
                "SDK tắt tự chạy hàm: LLM chỉ đề nghị tool_call, code kiểm tra và thực thi. "
                "Lượt cuối chỉ cung cấp submit_case. Tổng tối đa 12 call, gồm call sai và submit_case.")
    protocol = f.decision("Tool call hợp lệ?", step=7,
        explain="Code kiểm tra: có gọi tool, ID call không trùng, batch không vượt ngân sách, "
                "submit_case gọi riêng và lượt cuối chỉ được nộp kết luận. Sai giao thức thì dừng phiên.")
    kind = f.decision("Đọc dữ liệu hay nộp case?", step=8,
        explain="Tool đọc đi vào tools_node. submit_case đi vào kiểm chứng kết luận. "
                "Agent không có tool chuyển tiền, liên hệ khách hay phong tỏa tài khoản.")
    tool = f.process("Tool truy vấn dữ liệu có nguồn", step=9, icon="database", badge="SQLite chỉ đọc",
        explain="backend/agent_tools.py + evidence/: get_cluster, get_transfer, get_application, money_flow, "
                "reports_mentioning, account_senders, tech_profile, timeline. "
                "SQL bị giới hạn phạm vi và thời điểm; che thông tin cá nhân, dùng token nơi nhận theo phiên. "
                "Chi tiết giao dịch/tin báo/người gửi có phân trang tối đa 50, next_offset khi còn dữ liệu. "
                "Cờ SIMO và nguồn khớp tin báo được giữ lại; khớp số ngân hàng chưa xác minh phải ghi rõ.")
    observe = f.process("Gắn tool_call_id và đọc tiếp", step=10, icon="file", badge="tool_result → step",
        explain="ToolStep giữ tên tool, tool_call_id và JSON kết quả. JSON được thêm vào messages cho lượt LLM tiếp theo. "
                "Backend đổi event tool_result thành SSE type=step cho giao diện. "
                "Tool trả lỗi có cấu trúc thì model có thể đổi truy vấn; lỗi/timeout thực thi làm phiên dừng.")
    submit = f.process("submit_case: kết quả có cấu trúc", step=11, icon="check", badge="không trả văn bản suông",
        explain="CaseSubmission: verdict fraud_ring/victims/benign/inconclusive, summary, evidence, "
                "benign_explanation, missing_information, actions và transaction_assessments. "
                "Mỗi đề xuất giao dịch có transfer_id, allow/warn/hold/review, lý do và evidence.source. "
                "confidence do model tự đánh giá, chưa hiệu chuẩn thành xác suất gian lận.")
    validation = f.decision("Schema và bằng chứng đúng?", step=12,
        explain="workflow.validate_submission kiểm tra schema, nguồn là call đọc thành công trong phiên, "
                "app_id đã quan sát, members/victims không chồng nhau và bảo vệ người tự báo bị lừa. "
                "evidence/validation.py kiểm tra đúng giao dịch gây cảnh báo và nguồn chứa giao dịch đó. "
                "hold cần SIMO hoặc cảnh báo nơi nhận có phạm vi đã xác minh; mock/khớp số ngân hàng chưa đủ. "
                "inconclusive phải nêu cụ thể thông tin thiếu. Các kiểm tra không gán verdict hay confidence cố định.")
    repair = f.process("Phản hồi lỗi để model sửa", step=13, icon="alert", badge="invalid_case",
        explain="Trả error.fields/message, available_evidence_sources và observed_app_ids về model. "
                "Kết luận không hợp lệ chưa được chấp nhận hoặc lưu. Còn ngân sách thì sửa và nộp lại; hết lượt thì dừng.")
    result = f.process("Tạo InvestigationResult", step=14, icon="file", badge="event done nội bộ",
        explain="Agent trả run_id, app_id, status, reason, case, steps, model_turns. "
                "Kết luận hợp lệ có status=completed, kể cả verdict=inconclusive. "
                "Timeout/provider/giao thức/hết lượt sinh failed hoặc limit_reached với kết luận dự phòng. "
                "Giới hạn mặc định: 180 giây/phiên, 30 giây/thao tác.")
    completed = f.decision("Phiên completed?", step=15,
        explain="Phân biệt kết luận hợp lệ nhưng còn thiếu dữ liệu với lỗi chạy model. "
                "Chỉ completed mới được ghi vào cases và cập nhật cảnh báo.")
    persist = f.process("Lưu case và dấu vết điều tra", step=16, icon="database", badge="commit SQLite",
        explain="backend/integration.py: INSERT OR REPLACE cases, UPDATE alerts.verdict/case_conf rồi commit. "
                "Body lưu source_evidence, tool_steps, model_turns và run_id để đọc lại. "
                "Đề xuất hold chỉ là đề xuất cho người có thẩm quyền; code không thực hiện giữ tiền.")
    failure = f.process("Dừng an toàn, giữ kết quả cũ", step=17, icon="alert", badge="không ghi đè",
        explain="Lỗi trong phiên/timeout/hết lượt: trả failed hoặc limit_reached và không lưu đè case cũ. "
                "Snapshot rỗng cũng trả failed. Lỗi mạng/DB có thể kết thúc stream trước khi nhận case; giao diện mở lại nút thử.")
    rejected = f.process("Dừng request hoặc stream", step=17, icon="lock", badge="401 / 404 / cấu hình",
        explain="401 do khóa service, 404 do ID cảnh báo không tồn tại: chưa chạy Agent. "
                "Thiếu cấu hình Gemini được phát hiện trước vòng lặp: request/stream có thể kết thúc lỗi, không có case mới để lưu.")
    response = f.process("Backend trả kết quả qua SSE", step=18, icon="server", badge="type=case",
        explain="BackendAI đổi done thành {type: case, case: ...}, giữ nguồn có cấu trúc và bản bằng chứng đọc được. "
                "Controller gửi data: JSON qua text/event-stream; các bước trước đó đã gửi type=step. "
                "Middleware chuyển tiếp chunk, không gom hết stream mới trả.")
    ui = f.process("Giao diện và đội rủi ro xem", step=19, icon="user", badge="showCase",
        explain="web/app.js: EventSource nhận step/case, hiển thị đề xuất giao dịch, bằng chứng, giả thuyết vô hại, "
                "thông tin thiếu và việc cần làm. Vai trò inconclusive không trình bày như xác suất 50%. "
                "Phiên lỗi được ghi là chưa hoàn thành. Đội rủi ro xác minh và quyết định ngoài Agent.")
    end = f.end("Hoàn tất / chờ xác minh")
    f.nodes[-1].step = 20

    for source, target in ((start, data), (data, request), (request, middleware), (middleware, snapshot),
                           (snapshot, agent), (agent, model), (model, protocol), (protocol, kind),
                           (tool, observe), (observe, model), (submit, validation), (result, completed),
                           (persist, response), (failure, response), (response, ui), (ui, end), (rejected, end)):
        f.link(source, target)
    for source, target, label in (
        (middleware, rejected, "khóa sai"), (snapshot, rejected, "không có cảnh báo"),
        (snapshot, failure, "snapshot rỗng"), (agent, rejected, "thiếu cấu hình"),
        (model, failure, "provider / timeout"), (protocol, failure, "sai giao thức / vượt lượt"),
        (kind, tool, "tool đọc"), (kind, submit, "submit_case"), (tool, failure, "lỗi / timeout"),
        (validation, result, "hợp lệ"), (validation, repair, "chưa hợp lệ"),
        (repair, model, "còn lượt"), (repair, failure, "hết lượt"),
        (completed, persist, "có"), (completed, failure, "không"),
    ):
        f.link(source, target, label)

    for group_id, label, color, members in (
        ("backend", "1. Backend tạo đầu vào", "#2f80c0", [data, request, middleware, snapshot]),
        ("agent", "2. Agent: model ↔ tool", "#7b5ea7", [agent, model, protocol, kind, tool, observe]),
        ("grounding", "3. Kiểm chứng kết luận", "#c77700", [submit, validation, repair, result]),
        ("output", "4. Lưu và trả kết quả", "#20875e", [completed, persist, response, ui]),
    ):
        f.groups.append(Group(id=group_id, label=label, color=color, members=members))
    for node in f.nodes:
        if node.id in {failure, rejected, repair}:
            node.color = "#f8d8cd"
        elif node.id in {agent, model, tool, observe}:
            node.color = "#e5dcf5"
        elif node.id in {persist, response, ui}:
            node.color = "#d8eddf"

    # Four lanes keep the overview readable instead of a very tall diagram.
    positions = {
        start: (60, -120), data: (60, 40), request: (60, 200),
        middleware: (60, 360), snapshot: (60, 520), rejected: (60, 840),
        agent: (440, 40), model: (440, 200), protocol: (440, 360),
        kind: (440, 520), tool: (440, 680), observe: (440, 840),
        submit: (820, 40), validation: (820, 200), repair: (820, 360),
        result: (820, 520), failure: (820, 840),
        completed: (1200, 40), persist: (1200, 200), response: (1200, 520),
        ui: (1200, 680), end: (1200, 840),
    }
    for node in f.nodes:
        node.x, node.y = positions[node.id]

    stories = [
        ("Dữ liệu xuất phát từ đâu?", "Demo dựng cảnh báo trước bằng build.py/Engine trên dữ liệu mô phỏng. LLM thật bắt đầu khi bạn bấm Điều tra; không có giao dịch ngân hàng thật được đọc tự động."),
        ("Backend nhận yêu cầu", "Người dùng chọn alert_id trên Lưới & Thám tử. Giao diện mở EventSource tới GET /api/alerts/{aid}/investigate."),
        ("Middleware làm phần chung", "Tạo request_id, ghi thời gian và kiểm tra khóa nếu có cấu hình. Middleware không đánh giá gian lận."),
        ("Đóng phạm vi điều tra", "Backend đọc snapshot tại alert.ts. Những giao dịch hoặc tin báo xuất hiện sau thời điểm đó không được đưa vào phiên này."),
        ("Full Agent vẫn kế thừa BaseAgent", "BackendAI truyền bộ tool snapshot vào InvestigationAgent. Agent dựng LangGraph và dùng prompt riêng cho backend, không tạo một Agent nghiệp vụ khác."),
        ("LLM chọn hành động", "Gemini chỉ thấy dữ liệu đã đọc và schema tool. Nó chọn tool cần gọi; không tự chạy SQL, không nhận cả graph và không có quyền giữ tiền."),
        ("Code kiểm tra giao thức", "Call ID phải duy nhất, batch trong ngân sách, submit_case gọi riêng. Lượt cuối chỉ được nộp kết luận; tổng tối đa 12 tool call."),
        ("Hai đường đi trong vòng lặp", "Cần thêm dữ liệu thì gọi tool đọc. Có thể tổng hợp thì gọi submit_case. Chưa đủ chứng cứ vẫn được nộp inconclusive, nhưng phải nêu thiếu gì."),
        ("Tool đọc và che dữ liệu", "get_transfer giữ SIMO và ngữ cảnh người nhận; reports_mentioning nối tin báo với token đúng người nhận. Dữ liệu có as_of, nguồn và giới hạn trang."),
        ("Kết quả quay lại LLM", "ToolStep có tool_call_id. Kết quả được thêm vào messages, đồng thời giao diện nhận type=step. Model dùng bằng chứng đó để chọn bước tiếp theo."),
        ("Tách hai loại kết quả", "Vai trò người vay nằm trong verdict. Đề xuất xử lý từng giao dịch nằm trong transaction_assessments. Giao dịch có thể cần xác minh dù vai trò người vay chưa rõ."),
        ("Kiểm chứng bằng code", "Không chấp nhận nguồn bịa, app_id chưa thấy hoặc đề xuất sai giao dịch. Hold cần căn cứ nơi nhận đã xác minh; khớp số ngân hàng hay nhãn mock không tự thành bằng chứng chắc chắn."),
        ("Sai thì model sửa", "Code trả lỗi và các nguồn hợp lệ để LLM sửa. Không âm thầm nhận một kết luận sai schema. Hết ngân sách thì dừng và giữ kết quả cũ."),
        ("Agent trả kết quả phiên", "done nội bộ chứa case, steps, run_id, model_turns, status và reason. Completed + inconclusive là kết luận hợp lệ về giới hạn dữ liệu; failed là lỗi thực thi."),
        ("Chọn có lưu hay không", "Backend chỉ lưu khi status=completed. Không lấy failed/limit_reached ghi đè case đã có."),
        ("Lưu để mở lại được", "cases giữ kết luận, source_evidence và tool_steps; alerts giữ verdict/case_conf để danh sách cập nhật. Chưa thực hiện phong tỏa hoặc liên hệ khách."),
        ("Nhánh lỗi được hiển thị riêng", "401/404 dừng trước Agent. Lỗi trong phiên trả failed/limit_reached khi có thể; stream đứt hoặc thiếu cấu hình có thể không có case cuối. Không giả thành một kết luận 50%."),
        ("Trả về giao diện", "Backend chuyển event done thành SSE type=case. Các bước đọc trước đó đã được phát dần; không chờ hết phiên mới hiển thị toàn bộ."),
        ("Ví dụ từ ca đã thử", "Dữ liệu mô phỏng AL000326: CK77099 có SIMO=true và 3 tin báo khớp số chưa xác minh ngân hàng. Một phiên đã thử đề xuất hold để xác minh, còn vai trò người vay là inconclusive; lần chạy khác có thể khác. Không tự giữ tiền."),
        ("Đội rủi ro quyết định", "Xem bằng chứng và thông tin thiếu, xác minh trạng thái giao dịch/người nhận và trao đổi với khách theo quy trình. Feature Flow chỉ trình chiếu pipeline; mở Lưới & Thám tử để chạy Agent thật."),
    ]
    for step, (title, body) in enumerate(stories, 1):
        f.narrate(step, title, body)
    return f
