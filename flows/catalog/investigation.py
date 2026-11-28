from flows.common import Flow, Group, GROUP, set_step


def agent_loop():
    f = Flow("thienla-agent-dieu-tra", "Agent Thám tử điều tra 1 cụm")
    f.group = GROUP
    f.meta(
        subtitle="Vòng lặp tool use có giới hạn: thử vô hại trước, bằng chứng phải trỏ tới bước thật.",
        duration="kỹ thuật",
        level="Chi tiết",
        learn=[
            "Tối đa 12 lượt tool rồi buộc kết luận",
            "Giả thuyết vô hại được thử TRƯỚC",
            "Bằng chứng không trỏ tới tool_call thật thì bị loại",
        ],
    )
    s = f.start()
    get = f.process("Nhận cụm + tóm tắt sàng lọc", step=1, icon="file")
    hyp = f.process(
        "Đặt giả thuyết vô hại trước",
        step=2,
        explain="Gia đình? Ký túc xá? VPN công ty? Vừa đổi SIM? Rút về ngân hàng chính chủ?",
    )
    tool = f.process(
        "Gọi tool đọc",
        step=3,
        icon="api",
        explain="money_flow · account_senders · tech_profile · reports_mentioning · timeline · neighbors · entity_info",
    )
    check = f.decision(
        "Giả thuyết còn đứng?",
        step=4,
        explain="So bằng chứng mới với giả thuyết hiện tại; bác bỏ thì đổi hướng điều tra.",
    )
    enough = f.decision("Đủ bằng chứng hoặc hết 12 lượt?", step=5)
    submit = f.process(
        "submit_case",
        step=6,
        icon="check",
        explain="verdict: fraud_ring | victims | benign | inconclusive. Hết lượt mà chưa kết luận → inconclusive.",
    )
    verify = f.decision(
        "Bằng chứng trỏ tới tool_call thật?",
        step=7,
        explain="Code kiểm tra từng bằng chứng; cái nào bịa nguồn thì bị loại khỏi hồ sơ.",
    )
    out = f.process("Hồ sơ vụ việc", step=8, icon="file")
    e = f.end()
    set_step(f, e, 9)
    f.link(s, get)
    f.link(get, hyp)
    f.link(hyp, tool)
    f.link(tool, check)
    f.link(check, enough, "còn / đã đổi hướng")
    f.link(enough, tool, "chưa ↺")
    f.link(enough, submit, "đủ")
    f.link(submit, verify)
    f.link(verify, out, "đạt")
    f.link(out, e)
    f.groups.append(
        Group(
            id="g_loop",
            label="Vòng điều tra",
            color="#4e9a5f",
            members=[tool, check, enough],
            explain="Mỗi vòng: gọi 1 tool, đối chiếu giả thuyết, quyết định dừng hay đi tiếp. Tối đa 12 lượt.",
        )
    )
    f.narrate(1, "Nhận cụm", "Agent nhận cụm đã qua sàng lọc AI, kèm bản tóm tắt số liệu.")
    f.narrate(
        2,
        "Vô hại trước",
        "Chặn thói 'trùng là nghi': phải bác bỏ được giả thuyết vô hại mới được kết luận gian lận.",
        badge="NGUYÊN TẮC",
    )
    f.narrate(3, "Gọi tool", "Chỉ có tool ĐỌC. Agent không có quyền hành động thật (chặn, khoá).")
    f.narrate(4, "Đối chiếu", "Bằng chứng mới củng cố hay bác bỏ giả thuyết?")
    f.narrate(
        5,
        "Dừng hay đi tiếp",
        "Đủ bằng chứng → kết luận. Chưa → vòng tiếp. Quá 12 lượt → buộc dừng.",
        note="Giới hạn bước giữ chi phí và thời gian chờ của giám khảo.",
        note_type="info",
    )
    f.narrate(6, "Kết luận", "Ra 1 trong 4: đường dây, nạn nhân, vô hại, chưa đủ căn cứ.")
    f.narrate(
        7,
        "Kiểm chứng nguồn",
        "Mỗi bằng chứng phải trỏ tới 1 lần gọi tool có thật.",
        badge="CHỐNG BỊA",
    )
    f.narrate(8, "Hồ sơ vụ việc", "Đội rủi ro đọc, quyết định cuối cùng vẫn là con người.")
    return f
