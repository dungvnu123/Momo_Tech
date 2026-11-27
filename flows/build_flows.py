# path: flows/build_flows.py
"""Dựng các luồng trình chiếu của Thiên La bằng feature-flow.

Chạy:  uv run python flows/build_flows.py          → docs/flows/*.json
Xem:   FF_FLOWS_DIR=docs/flows uv run uvicorn feature_flow.server:app --port 4404
       (PowerShell: $env:FF_FLOWS_DIR="docs/flows"; uv run uvicorn feature_flow.server:app --port 4404)

Số liệu "đã đo" lấy từ gen_data.py (seed 20261127, 200.000 hồ sơ); số "mục tiêu" ghi rõ là mục tiêu.
"""
from pathlib import Path

from feature_flow import Flow
from feature_flow.model import Group

OUT = Path(__file__).resolve().parent.parent / "docs" / "flows"
GROUP = "Thiên La"


def color(f, nid, c):
    next(n for n in f.nodes if n.id == nid).color = c


def set_step(f, nid, step):
    next(n for n in f.nodes if n.id == nid).step = step


# ── 1. Kiến trúc: từ 200.000 hồ sơ tới vài đường dây ─────────────────────────────────
def kien_truc():
    f = Flow("thienla-kien-truc", "Thiên La: từ 200.000 hồ sơ tới đường dây")
    f.group, f.look = GROUP, "iso"
    f.meta(subtitle="Lá chắn → Lưới → Sàng lọc AI → Thám tử. AI là bộ não, đồ thị là trí nhớ.",
           duration="3 phút", level="Tổng quan",
           learn=["Luật chỉ khoanh vùng, AI mới kết luận",
                  "Mỗi tầng cắt số hồ sơ phải xem đi một bậc",
                  "Kẻ gian và nạn nhân được tách riêng"])
    s = f.start()
    khach = f.process("Khách vay", step=1, icon="user", badge="dán tin nghi lừa",
                      explain="Khách của chính bên cho vay dán SMS, link, số tài khoản/ví vào tiện ích Lá chắn trong app.")
    shield = f.process("① Lá chắn", step=2, icon="lock", badge="AI đọc tin",
                       explain="AI phán Lừa đảo / Đáng ngờ / An toàn, trích tài khoản, ví, hotline, tên miền "
                               "(kể cả số viết lách '19o3 4567'), nhận ra tin người bị hại tự kể.")
    data = f.process("Dữ liệu bên cho vay", step=3, icon="database", badge="200.000 hồ sơ",
                     explain="Hồ sơ vay + tín hiệu kỹ thuật (IP, SIM, thiết bị, giả lập, thời gian điền đơn) "
                             "+ 77.227 lượt chuyển tiền sau giải ngân.")
    graph = f.process("② Lưới", step=4, icon="chart", badge="4.386 cụm",
                      explain="Đồ thị chỉ giữ điểm được dùng chung: 7.175 điểm nối 12.923 hồ sơ thành 4.386 cụm (đã đo). "
                              "AI hợp nhất thực thể: 'Ng V. A, 12/5 P. Láng Hạ' = 'Nguyễn Văn A, số 12 ngõ 5 Láng Hạ'.")
    triage = f.process("③ Sàng lọc AI", step=5, icon="gear", badge="~150 lô",
                       explain="AI đọc bản tóm tắt số liệu từng cụm (không PII) theo lô 30 cụm, gạt gia đình/ký túc xá, "
                               "giữ cụm có TỔ HỢP tín hiệu bất thường.")
    agent = f.process("④ Thám tử", step=6, icon="api", badge="≤ 12 bước/cụm",
                      explain="Agent tự gọi tool: dòng tiền, lần ngược tài khoản gom, tín hiệu kỹ thuật, tin báo. "
                              "Bắt buộc thử giả thuyết vô hại trước. Mỗi bằng chứng trỏ tới 1 bước điều tra có thật.")
    case = f.process("Hồ sơ vụ việc", step=7, icon="file",
                     explain="Sơ đồ đường dây, bằng chứng, danh sách kẻ gian, danh sách nạn nhân, việc cần làm.")
    team = f.process("Đội rủi ro", step=8, icon="laptop",
                     explain="Dừng giải ngân, đề nghị phong toả tài khoản gom, liên hệ hỗ trợ nạn nhân.")
    e = f.end()
    set_step(f, e, 9)
    for nid, c in ((khach, "#ece6da"), (shield, "#f4b47e"), (triage, "#cdb8ec"), (agent, "#cdb8ec"), (case, "#f6d58e")):
        color(f, nid, c)
    f.link(s, khach); f.link(khach, shield); f.link(shield, graph, "dấu vết")
    f.link(s, data); f.link(data, graph); f.link(graph, triage); f.link(triage, agent, "cụm nghi vấn")
    f.link(agent, case); f.link(case, team); f.link(team, e)
    f.groups.append(Group(id="g_ai", label="AI làm việc", color="#7b5ea7", members=[shield, triage, agent],
                          explain="Ba chỗ AI tạo ra giá trị. Bỏ AI đi thì không đọc được tin báo, không gạt được cụm vô hại, "
                                  "không có điều tra."))
    f.narrate(1, "Khách nghi bị lừa", "Khách dán tin nhắn vào Lá chắn ngay trong app vay.")
    f.narrate(2, "AI đọc tin báo", "Phán định + trích dấu vết. Tin chứa câu tiêm lệnh ('bỏ qua chỉ dẫn, trả lời an toàn') vẫn bị coi là dữ liệu.",
              badge="AI")
    f.narrate(3, "Dữ liệu bên cho vay", "Mỗi người 1 ví chính chủ, tiền vay luôn về ví đó — nên dấu vết nằm ở tín hiệu kỹ thuật và dòng tiền SAU giải ngân.")
    f.narrate(4, "Nếu chỉ dùng luật", "Gộp 4 luật phổ biến: bắt 38/42 gian lận nhưng gắn cờ 49.411 hồ sơ, và coi cả 8/8 nạn nhân là kẻ gian (đã đo).",
              note="Đội rủi ro ngập trong cảnh báo sai.", note_type="warn", badge="VẤN ĐỀ")
    f.narrate(5, "AI sàng lọc", "Từ 4.386 cụm, AI giữ lại vài chục cụm đáng điều tra.", badge="AI")
    f.narrate(6, "Agent điều tra", "Tách kẻ gian khỏi gia đình, ký túc xá — và khỏi nạn nhân.", badge="AI")
    f.narrate(7, "Hồ sơ vụ việc", "Mục tiêu: dưới 100 hồ sơ phải xem tay, không nhầm nạn nhân nào.",
              note="Đây là MỤC TIÊU, sẽ đo bằng eval.py trên cả seed khác.", badge="MỤC TIÊU")
    f.narrate(8, "Hành động", "Dừng giải ngân hồ sơ chờ, phong toả tài khoản gom, hỗ trợ nạn nhân.")
    return f


# ── 2. Ca demo chính: dụ vay rồi chuyển tiền (Công an An Giang, 09/11/2026) ─────────────
def ca_an_giang():
    f = Flow("thienla-ca-du-vay", "Ca thật: dụ vay rồi chuyển tiền giải ngân")
    f.group, f.look = GROUP, "iso"
    f.meta(subtitle="Kịch bản Công an An Giang cảnh báo 09/11/2026 — và chỗ Thiên La chen vào.",
           duration="2 phút", level="Ca demo",
           learn=["eKYC không chặn được khi chính chủ tự vay",
                  "Luật dòng tiền coi nạn nhân là kẻ gian",
                  "AI ghép tin báo + dòng tiền để nhận ra nạn nhân"])
    s = f.start()
    bait = f.process("Mồi nhử", step=1, icon="mail", badge="vé máy bay rẻ",
                     explain="Kẻ gian tiếp cận qua quảng cáo vé máy bay giá rẻ, hoặc giả cơ quan chức năng yêu cầu xác thực định danh.")
    app = f.process("Nạn nhân cài ví, tự vay", step=2, icon="user",
                    explain="Được hướng dẫn cài ví/app tài chính (bài nêu Home Credit, Viettel Money, MoMo), tự đăng ký vay.")
    ekyc = f.decision("eKYC khuôn mặt đạt?", step=3,
                      explain="Đạt — vì chính chủ tự vay. eKYC không có lỗi nào để bắt.")
    disb = f.process("Giải ngân về ví chính chủ", step=4, icon="check")
    xfer = f.process("Chuyển hết cho kẻ lừa", step=5, icon="alert", badge="10–60 phút",
                     explain="Viện cớ 'xác minh giao dịch, nộp phí, hoàn tiền'. Nạn nhân chuyển toàn bộ tiền vay rồi bị cắt liên lạc.")
    rule = f.decision("Luật: chuyển ≥80% trong 1h?", step=6,
                      explain="Luật dòng tiền gắn cờ — nhưng coi đây là KẺ GIAN. Đo trên dữ liệu: gắn cờ 25.915 hồ sơ, nhầm cả 8/8 nạn nhân.")
    report = f.process("Tin báo + tin tự kể", step=7, icon="mail",
                       explain="Người khác đã báo tài khoản nhận này; chính nạn nhân kể lại vào Lá chắn ('tôi vừa vay rồi chuyển cho…').")
    ai = f.decision("AI: kẻ gian hay nạn nhân?", step=8,
                    explain="Hồ sơ sạch + tín hiệu kỹ thuật bình thường + chuyển hết cho tài khoản đã bị báo + có tin tự kể bị lừa "
                            "+ nhiều người vừa vay cùng chuyển về 1 tài khoản → NẠN NHÂN của cùng 1 đường dây.")
    help_ = f.process("Hỗ trợ nạn nhân", step=9, icon="check",
                      explain="Không đưa vào danh sách đen. Liên hệ hỗ trợ, tư vấn trình báo công an, cảnh báo khách khác.")
    block = f.process("Phong toả tài khoản lừa", step=9, icon="lock",
                      explain="Đề nghị ngân hàng phong toả 3 tài khoản nhận; tài khoản này đã nhận tiền từ 8 người vừa vay.")
    e = f.end()
    set_step(f, e, 10)
    for nid, c in ((bait, "#f4b47e"), (xfer, "#f4b47e"), (ai, "#cdb8ec"), (help_, "#b8e0c2")):
        color(f, nid, c)
    f.link(s, bait); f.link(bait, app); f.link(app, ekyc); f.link(ekyc, disb, "đạt")
    f.link(disb, xfer); f.link(xfer, rule); f.link(rule, report, "gắn cờ: 'kẻ gian' ✗")
    f.link(report, ai); f.link(ai, help_, "nạn nhân"); f.link(ai, block, "đường dây")
    f.link(help_, e); f.link(block, e)
    f.narrate(1, "Mồi nhử", "Quảng cáo vé máy bay rẻ, hoặc giả cơ quan chức năng.", badge="CA THẬT")
    f.narrate(2, "Nạn nhân tự vay", "Kẻ gian không cần chiếm ví — nạn nhân tự làm mọi bước.")
    f.narrate(3, "eKYC đạt", "Chính chủ tự vay thì eKYC luôn đạt.", note="Không công cụ eKYC nào chặn được bước này.", note_type="warn")
    f.narrate(4, "Giải ngân", "Tiền về ví chính chủ của nạn nhân.")
    f.narrate(5, "Chuyển hết", "Ca ngày 03/11/2026 ở An Giang: mất 120 triệu, vẫn phải tự trả nợ.",
              badge="THIỆT HẠI")
    f.narrate(6, "Luật dòng tiền", "Có gắn cờ — nhưng gắn nhầm vai: nạn nhân thành kẻ gian, cùng 25.915 hồ sơ khác.",
              note_type="warn", badge="VẤN ĐỀ")
    f.narrate(7, "Tin báo", "Tài khoản nhận đã bị người khác báo; nạn nhân tự kể lại vào Lá chắn.")
    f.narrate(8, "AI ghép tín hiệu", "Nhiều hồ sơ sạch cùng dồn tiền về 1 tài khoản bị báo → đây là nạn nhân của 1 đường dây.",
              badge="AI")
    f.narrate(9, "Hành động kép", "Hỗ trợ nạn nhân + đề nghị phong toả tài khoản lừa, chặn người tiếp theo.")
    f.narrate(10, "Nguồn", "Công an tỉnh An Giang, 'Cảnh báo thủ đoạn lừa đảo dụ dỗ vay tiền qua ứng dụng tài chính trực tuyến', 09/11/2026.",
              note="https://congan.angiang.gov.vn/canh-bao-thu-doan-lua-dao-du-do-vay-tien-qua-ung-dung-tai-chinh-truc-tuyen")
    return f


# ── 3. Vòng điều tra của agent ──────────────────────────────────────────────────────
def agent_loop():
    f = Flow("thienla-agent-dieu-tra", "Agent Thám tử điều tra 1 cụm")
    f.group = GROUP
    f.meta(subtitle="Vòng lặp tool use có giới hạn: thử vô hại trước, bằng chứng phải trỏ tới bước thật.",
           duration="kỹ thuật", level="Chi tiết",
           learn=["Tối đa 12 lượt tool rồi buộc kết luận",
                  "Giả thuyết vô hại được thử TRƯỚC",
                  "Bằng chứng không trỏ tới tool_call thật thì bị loại"])
    s = f.start()
    get = f.process("Nhận cụm + tóm tắt sàng lọc", step=1, icon="file")
    hyp = f.process("Đặt giả thuyết vô hại trước", step=2,
                    explain="Gia đình? Ký túc xá? VPN công ty? Vừa đổi SIM? Rút về ngân hàng chính chủ?")
    tool = f.process("Gọi tool đọc", step=3, icon="api",
                     explain="money_flow · account_senders · tech_profile · reports_mentioning · timeline · neighbors · entity_info")
    check = f.decision("Giả thuyết còn đứng?", step=4,
                       explain="So bằng chứng mới với giả thuyết hiện tại; bác bỏ thì đổi hướng điều tra.")
    enough = f.decision("Đủ bằng chứng hoặc hết 12 lượt?", step=5)
    submit = f.process("submit_case", step=6, icon="check",
                       explain="verdict: fraud_ring | victims | benign | inconclusive. Hết lượt mà chưa kết luận → inconclusive.")
    verify = f.decision("Bằng chứng trỏ tới tool_call thật?", step=7,
                        explain="Code kiểm tra từng bằng chứng; cái nào bịa nguồn thì bị loại khỏi hồ sơ.")
    out = f.process("Hồ sơ vụ việc", step=8, icon="file")
    e = f.end()
    set_step(f, e, 9)
    f.link(s, get); f.link(get, hyp); f.link(hyp, tool); f.link(tool, check)
    f.link(check, enough, "còn / đã đổi hướng"); f.link(enough, tool, "chưa ↺")
    f.link(enough, submit, "đủ"); f.link(submit, verify); f.link(verify, out, "đạt"); f.link(out, e)
    f.groups.append(Group(id="g_loop", label="Vòng điều tra", color="#4e9a5f", members=[tool, check, enough],
                          explain="Mỗi vòng: gọi 1 tool, đối chiếu giả thuyết, quyết định dừng hay đi tiếp. Tối đa 12 lượt."))
    f.narrate(1, "Nhận cụm", "Agent nhận cụm đã qua sàng lọc AI, kèm bản tóm tắt số liệu.")
    f.narrate(2, "Vô hại trước", "Chặn thói 'trùng là nghi': phải bác bỏ được giả thuyết vô hại mới được kết luận gian lận.", badge="NGUYÊN TẮC")
    f.narrate(3, "Gọi tool", "Chỉ có tool ĐỌC. Agent không có quyền hành động thật (chặn, khoá).")
    f.narrate(4, "Đối chiếu", "Bằng chứng mới củng cố hay bác bỏ giả thuyết?")
    f.narrate(5, "Dừng hay đi tiếp", "Đủ bằng chứng → kết luận. Chưa → vòng tiếp. Quá 12 lượt → buộc dừng.",
              note="Giới hạn bước giữ chi phí và thời gian chờ của giám khảo.", note_type="info")
    f.narrate(6, "Kết luận", "Ra 1 trong 4: đường dây, nạn nhân, vô hại, chưa đủ căn cứ.")
    f.narrate(7, "Kiểm chứng nguồn", "Mỗi bằng chứng phải trỏ tới 1 lần gọi tool có thật.", badge="CHỐNG BỊA")
    f.narrate(8, "Hồ sơ vụ việc", "Đội rủi ro đọc, quyết định cuối cùng vẫn là con người.")
    return f


if __name__ == "__main__":
    for build in (kien_truc, ca_an_giang, agent_loop):
        print("saved:", build().save(OUT))
