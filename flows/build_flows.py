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

if __package__:
    from .backend_agent import backend_agent_pipeline
    from .batch_ai import batch_ai_pipeline
    from .realtime_ai import realtime_ai_pipeline
else:
    from backend_agent import backend_agent_pipeline
    from batch_ai import batch_ai_pipeline
    from realtime_ai import realtime_ai_pipeline

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
                             "+ phiên eKYC lúc vay + 77.783 lượt chuyển tiền sau giải ngân (kèm ngữ cảnh người nhận: danh bạ, lịch sử, SIMO).")
    graph = f.process("② Lưới", step=4, icon="chart", badge="4.487 cụm",
                      explain="Đồ thị chỉ giữ điểm được dùng chung: các hồ sơ có điểm chung gom thành 4.487 cụm (đã đo). "
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
    f.narrate(4, "Nếu chỉ dùng luật", "Gộp 5 luật phổ biến: bắt 54/58 gian lận nhưng gắn cờ 61.306 hồ sơ, và coi 21/28 nạn nhân là kẻ gian (đã đo).",
              note="Đội rủi ro ngập trong cảnh báo sai.", note_type="warn", badge="VẤN ĐỀ")
    f.narrate(5, "AI sàng lọc", "Từ 4.487 cụm, AI giữ lại vài chục cụm đáng điều tra.", badge="AI")
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
                      explain="Luật dòng tiền gắn cờ — nhưng coi đây là KẺ GIAN. Đo trên dữ liệu: gắn cờ 26.169 hồ sơ, coi 20/28 nạn nhân là kẻ gian.")
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
    f.narrate(6, "Luật dòng tiền", "Có gắn cờ — nhưng gắn nhầm vai: nạn nhân thành kẻ gian, cùng hơn 26 nghìn hồ sơ khác.",
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


# ── 4. Vòng đời 1 hồ sơ: dữ liệu nhiều bảng, mọi thứ có mốc thời gian ──────────────────
def vong_doi():
    f = Flow("thienla-vong-doi-ho-so", "Vòng đời 1 hồ sơ vay — mỗi bước là 1 bảng có mốc thời gian")
    f.group = GROUP
    f.meta(subtitle="Nộp → eKYC → duyệt → giải ngân → chuyển tiền → đến hạn → trả hoặc quá hạn. Quá hạn tính TẠI từng thời điểm.",
           duration="dữ liệu", level="Nền tảng",
           learn=["Không có cột 'quá hạn' chốt sẵn — tính từ lịch trả + các lần trả",
                  "Mỗi bước để lại dấu vết riêng: eKYC, dòng tiền, tin báo",
                  "Bộ máy chỉ được thấy bước đã xảy ra tới thời điểm đang xét"])
    s = f.start()
    sub = f.process("Nộp hồ sơ", step=1, icon="user", badge="applications",
                    explain="applied_at + thông tin khai báo + tín hiệu kỹ thuật lúc nộp: thiết bị, IP (di động/nhà/VPN/datacenter), tuổi SIM, giả lập, thời gian điền đơn.")
    ekyc = f.process("eKYC khuôn mặt", step=2, icon="lock", badge="ekyc_sessions",
                     explain="Mỗi lần thử là 1 dòng: thời điểm, thiết bị, liveness, máy bị hook/root, đạt/trượt. Liveness sát ngưỡng + thử nhiều lần + máy mới gắn ví = dấu hiệu vượt eKYC.")
    ok = f.decision("Duyệt?", step=3, explain="decided_at + decision (APPROVED/REJECTED). Hồ sơ chưa có quyết định = đang chờ.")
    rej = f.process("Từ chối", step=4, explain="Dừng ở đây.")
    disb = f.process("Giải ngân về ví chính chủ", step=4, icon="check", badge="disbursed_at",
                     explain="Tiền luôn về tài khoản/ví đứng tên khách (đối chiếu hợp đồng mẫu). Kỳ hạn 3 tháng, lãi 36%/năm.")
    xfer = f.process("Chuyển tiền đi", step=5, icon="api", badge="wallet_transfers",
                     explain="Mỗi lần chuyển: thời điểm, người nhận, số tiền, ghi chú + ngữ cảnh người nhận (danh bạ & lúc lưu số, đã từng chuyển chưa, SIMO, ví nhận bao nhiêu ngày tuổi).")
    due = f.process("Đến hạn kỳ 1, 2, 3", step=6, icon="clock", badge="repayment_schedule",
                    explain="Mỗi kỳ 1 dòng: ngày đến hạn, gốc, lãi.")
    paid = f.decision("Đã trả?", step=7, explain="repayments: mỗi lần trả 1 dòng (thời điểm, số tiền, kênh).")
    good = f.process("Trả đúng / trễ ít", step=8, icon="check")
    fpd = f.process("Quá hạn ngay kỳ đầu", step=8, icon="alert", badge="hậu kiểm",
                    explain="Đến hạn kỳ 1 + 10 ngày chưa trả → tín hiệu 'fpd'. Đứng riêng = rủi ro tín dụng; nằm trong cụm có quan hệ thì làm cụm nặng thêm.")
    rep = f.process("Tin báo lừa đảo", step=5, icon="mail", badge="scam_reports",
                    explain="Bất kỳ lúc nào: khách gửi tin nghi lừa hoặc kể bị lừa. Chỉ có chữ thô — AI trích tài khoản/ví/hotline.")
    e = f.end()
    set_step(f, e, 9)
    for nid, c in ((ekyc, "#cdb8ec"), (xfer, "#f4b47e"), (fpd, "#f4b47e"), (rep, "#f4b47e")):
        color(f, nid, c)
    f.link(s, sub); f.link(sub, ekyc); f.link(ekyc, ok); f.link(ok, rej, "không"); f.link(ok, disb, "có")
    f.link(disb, xfer); f.link(disb, due); f.link(due, paid); f.link(paid, good, "có"); f.link(paid, fpd, "không")
    f.link(s, rep); f.link(good, e); f.link(fpd, e); f.link(rej, e); f.link(xfer, e); f.link(rep, e)
    f.narrate(1, "Nộp hồ sơ", "Bảng applications: 200.000 hồ sơ từ 01/06 tới 25/11/2026.")
    f.narrate(2, "eKYC", "Bảng ekyc_sessions: mỗi lần thử 1 dòng.", note="Nhận ra khuôn mặt giả là việc của nhà cung cấp eKYC; Thiên La bắt BỐI CẢNH quanh phiên eKYC.")
    f.narrate(3, "Quyết định", "Có mốc decided_at → đếm được 'hồ sơ đang chờ' tại đúng thời điểm, không dùng trạng thái cuối.")
    f.narrate(4, "Giải ngân", "Mục đích 'hoàn ứng vốn tự có' → tiền là của khách, không kiểm soát được sau giải ngân.")
    f.narrate(5, "Dòng tiền + tin báo", "Hai nguồn dấu vết chính: tiền đi đâu, và ai báo gì.")
    f.narrate(6, "Lịch trả", "3 kỳ, mỗi kỳ 1 dòng.")
    f.narrate(7, "Trả hay không", "Quá hạn = ngày đang xét − ngày đến hạn của kỳ đầu tiên chưa trả.")
    f.narrate(8, "Hậu kiểm", "Quá hạn ngay kỳ đầu là dấu vết DUY NHẤT của kẻ gian lẻ loi — bắt sau, không bắt trước được.", badge="TRUNG THỰC")
    return f


# ── 5. Bộ máy realtime: mỗi sự kiện → cập nhật đồ thị → có thể sinh cảnh báo ───────────────
def realtime():
    f = Flow("thienla-realtime", "Bộ máy realtime: từ 1 sự kiện tới 1 cảnh báo")
    f.group, f.look = GROUP, "iso"
    f.meta(subtitle="app/engine.py — 741.593 sự kiện xử lý theo đúng thứ tự thời gian trong ~8 giây, sinh 347 cảnh báo.",
           duration="kỹ thuật", level="Chi tiết",
           learn=["Chỉ cập nhật cụm bị chạm tới — không tính lại từ đầu",
                  "Không nhìn trước tương lai: mọi quyết định chỉ dùng dữ liệu đã xảy ra",
                  "AI chỉ được gọi khi cụm vượt ngưỡng — giữ chi phí và tốc độ"])
    s = f.start()
    ev = f.process("Sự kiện tới", step=1, icon="queue", badge="5 loại",
                   explain="Nộp hồ sơ · chuyển tiền · tin báo · trả nợ · kiểm tra quá hạn kỳ 1 (lịch hẹn giờ của chính hệ thống). Bản thi: phát lại theo thời gian; chạy thật: đọc hàng đợi sự kiện.")
    kind = f.decision("Là chuyển tiền?", step=2)
    chk = f.process("Cảnh báo lúc chuyển tiền", step=3, icon="lock", badge="< 1 giây",
                    explain="Ngữ cảnh khoản vay vừa giải ngân + người nhận (danh bạ, lịch sử, SIMO, số tin báo ĐÃ có tới giờ) → cho phép / cảnh báo / tạm giữ.")
    hold = f.decision("Tạm giữ?", step=4)
    al1 = f.process("Cảnh báo giao dịch", step=5, icon="alert", badge="60 lần", explain="Vào hàng đợi với mức Khẩn.")
    upd = f.process("Cập nhật đồ thị", step=3, icon="chart", badge="union-find",
                    explain="Nối hồ sơ qua điểm dùng chung: thiết bị, SĐT tham chiếu, dải IP VPN, lô SIM mới, nơi nhận tiền (đã siết: ≤2h, ≥30% khoản vay, chưa từng chuyển), máy mở ví nhận, tài khoản/hotline trong tin báo. Dữ liệu chỉ thêm, không xoá → nối thêm rất rẻ.")
    ev2 = f.process("Đánh giá cụm vừa đổi", step=4, icon="gear",
                    explain="Đếm tín hiệu của cụm: tham chiếu chung ≥5, thiết bị chung ≥5, nơi nhận chung, cùng quá hạn kỳ đầu, IP/SIM/giả lập, eKYC bất thường, SIMO, tin báo; số hồ sơ đang chờ TẠI thời điểm này.")
    tri = f.decision("AI sàng lọc: đáng điều tra?", step=5,
                     explain="ai.triage_clusters — nhận bản tóm tắt số liệu (không PII), trả quyết định + độ tin cậy + lý do.")
    chg = f.decision("Có bằng chứng mới?", step=6, explain="So với lần cảnh báo trước của cùng cụm: thêm tín hiệu, thêm tin báo, lớn thêm, đổi số hồ sơ chờ. Không đổi → im lặng, tránh spam.")
    al2 = f.process("Cảnh báo cụm", step=7, icon="alert", badge="mức + ưu tiên",
                    explain="Mức Khẩn/Cao/Trung bình; ưu tiên = mức × 10 + tin cậy × 10 + quy mô + 2 × hồ sơ đang chờ. Giữ mã cụm cũ khi 2 cụm nhập lại → diễn biến liền mạch.")
    q = f.process("Hàng đợi điều tra", step=8, icon="laptop")
    e = f.end()
    set_step(f, e, 9)
    for nid, c in ((chk, "#f4b47e"), (tri, "#cdb8ec"), (al1, "#f4b47e"), (al2, "#f4b47e")):
        color(f, nid, c)
    f.link(s, ev); f.link(ev, kind); f.link(kind, chk, "có"); f.link(chk, hold); f.link(hold, al1, "có"); f.link(hold, upd, "không")
    f.link(kind, upd, "không"); f.link(upd, ev2); f.link(ev2, tri); f.link(tri, chg, "có"); f.link(tri, e, "không")
    f.link(chg, al2, "có"); f.link(chg, e, "không"); f.link(al1, q); f.link(al2, q); f.link(q, e)
    f.narrate(1, "Sự kiện", "Mọi thứ thành 1 dòng sự kiện có thời gian.", note="Bản thi phát lại dữ liệu theo đồng hồ tua nhanh; code xử lý giống hệt khi chạy thật.")
    f.narrate(2, "Phân luồng", "Chuyển tiền đi cả 2 đường: kiểm tra ngay + cập nhật đồ thị.")
    f.narrate(3, "Chặn tại chỗ / nối đồ thị", "Kiểm tra chuyển tiền chỉ dùng tin báo đã có TỚI GIỜ — nạn nhân đầu tiên chưa có ai báo.")
    f.narrate(4, "Đánh giá", "Chỉ tính lại cụm vừa bị chạm.")
    f.narrate(5, "AI sàng lọc", "Gọi AI theo nhu cầu, không theo từng sự kiện.", badge="AI")
    f.narrate(6, "Chống spam", "Cụm không có gì mới thì không báo lại.")
    f.narrate(7, "Cảnh báo", "Đo được (seed chuẩn): A 18 phút, E/H ~45 phút, D 1 ngày, G 1 ngày, B 1 ngày, F 4 ngày, C 27 ngày.")
    f.narrate(8, "Hàng đợi", "Lọc theo ngày, khung giờ, mức độ, kết luận, độ tin cậy.")
    return f


# ── 6. Đội rủi ro dùng hàng đợi ────────────────────────────────────────────────────────
def hang_doi():
    f = Flow("thienla-hang-doi", "Đội rủi ro dùng hàng đợi điều tra")
    f.group = GROUP
    f.meta(subtitle="Từ 347 cảnh báo tới quyết định: lọc → chọn → xem đồ thị → xem dòng thời gian hồ sơ → điều tra → hành động.",
           duration="2 phút", level="Hướng dẫn",
           learn=["Bắt đầu từ mức Khẩn + có hồ sơ đang chờ giải ngân",
                  "Dòng thời gian hồ sơ cho thấy đúng thứ tự sự việc",
                  "Quyết định cuối luôn là của con người"])
    s = f.start()
    flt = f.process("Lọc", step=1, icon="gear", explain="Biểu đồ theo ngày + khung giờ (đêm 0–6h đáng xem), mức Khẩn/Cao/Trung bình, loại (cụm / giao dịch giữ), kết luận, độ tin cậy ≥, tìm mã. Sắp xếp: ưu tiên, mới nhất, tin cậy, quy mô.")
    pick = f.process("Chọn cảnh báo", step=2, icon="alert", explain="Mỗi dòng: giờ, mức, tiêu đề, thanh độ tin cậy, số hồ sơ đang chờ, số tin báo, kết luận đã điều tra sẵn.")
    g = f.process("Đồ thị cụm", step=3, icon="chart", explain="Hồ sơ + điểm dùng chung (thiết bị, tham chiếu, nơi nhận tiền, dải IP/lô SIM). Viền vàng = đang chờ giải ngân. Diễn biến cụm theo thời gian ở trên.")
    tl = f.process("Dòng thời gian hồ sơ", step=4, icon="file", explain="Bấm 1 hồ sơ: nộp → eKYC từng lần → duyệt → giải ngân → từng lần chuyển (cờ SIMO, ngoài danh bạ) → đến hạn/trả → tin báo → cảnh báo, kèm 'quá hạn N ngày' TẠI lúc cảnh báo.")
    inv = f.process("Điều tra", step=5, icon="api", explain="Agent chạy từng bước, chỉ thấy dữ liệu tới lúc cảnh báo; ra kết luận: đường dây / nạn nhân / vô hại / chưa đủ căn cứ.")
    dec = f.decision("Con người quyết định", step=6)
    a1 = f.process("Chặn + phong toả", step=7, icon="lock", explain="Dừng giải ngân hồ sơ đang chờ, đề nghị phong toả tài khoản gom, theo dõi thiết bị/SĐT.")
    a2 = f.process("Hỗ trợ nạn nhân", step=7, icon="user", explain="Liên hệ, tư vấn trình báo, KHÔNG đưa vào danh sách đen.")
    a3 = f.process("Đóng, ghi nhãn", step=7, icon="check", explain="Vô hại → ghi nhãn để đo lại độ chính xác hằng tuần.")
    e = f.end()
    set_step(f, e, 8)
    f.link(s, flt); f.link(flt, pick); f.link(pick, g); f.link(g, tl); f.link(tl, inv); f.link(inv, dec)
    f.link(dec, a1, "đường dây"); f.link(dec, a2, "nạn nhân"); f.link(dec, a3, "vô hại"); f.link(a1, e); f.link(a2, e); f.link(a3, e)
    f.narrate(1, "Lọc", "Mặc định: mỗi cụm 1 dòng, sắp theo ưu tiên.")
    f.narrate(2, "Chọn", "Ưu tiên cảnh báo Khẩn có hồ sơ đang chờ — còn chặn kịp tiền.")
    f.narrate(3, "Đồ thị", "Bấm đúp nền hoặc ⤢ Vừa khung để căn lại.")
    f.narrate(4, "Dòng thời gian", "Xem đúng thứ tự: vay xong mấy phút thì tiền đi đâu.")
    f.narrate(5, "Điều tra", "Cảnh báo dựng sẵn dùng luật mô phỏng. Khi bấm Điều tra, backend/integration.py gọi Agent và Gemini thật.",
              note="Mốc bản giả lập: 58/58 kẻ gian, 0 nạn nhân bị nhầm, nhưng nhầm 298 hồ sơ vô hại — AI phải cắt phần này.", note_type="warn")
    f.narrate(6, "Quyết định", "Agent chỉ đề xuất, không có quyền hành động thật.", badge="NGUYÊN TẮC")
    f.narrate(7, "Hành động + nhãn", "Mỗi quyết định thành nhãn để đo lại precision/recall.")
    return f


# ── 7. App ví khách: từ tin lừa tới tạm giữ + cảnh báo đội rủi ro ──────────────────────────
def app_khach():
    f = Flow("thienla-app-khach", "App ví khách: tin lừa → vay → chuyển → tạm giữ → đội rủi ro")
    f.group, f.look = GROUP, "iso"
    f.meta(subtitle="Kịch bản đầu-cuối trên /vi/ — mọi lần chuyển đi qua đúng 1 bộ kiểm tra với ngữ cảnh thật tại lúc chuyển.",
           duration="3 phút", level="Ca demo",
           learn=["Chặn ở lúc tiền rời ví — trước khi mất tiền",
                  "Tin chính thức (kênh đã xác thực) không bị báo nhầm",
                  "Tạm giữ / báo lừa đều thành cảnh báo cho đội rủi ro ngay"])
    s = f.start()
    msg = f.process("Tin nhắn lạ trong hộp tin", step=1, icon="mail", badge="6 tình huống",
                    explain="Dụ vay rồi chuyển (tài khoản bị báo / SIMO / mới tinh) · giả thu hồi nợ · link giả đòi OTP · người thân nhờ chuyển gấp.")
    loan = f.process("Vay nhanh", step=2, icon="check", explain="Khoản vay giải ngân về ví chính chủ — mốc thời gian để đo 'vay xong mấy phút thì chuyển'.")
    follow = f.process("Làm theo hướng dẫn", step=3, icon="user", badge="đóng vai nạn nhân",
                       explain="Form chuyển tiền tự điền theo tin: số tài khoản, tên, số tiền, nội dung; có thể bị dặn 'lưu số vào danh bạ'.")
    ctx = f.process("Dựng ngữ cảnh lúc chuyển", step=4, icon="gear",
                    explain="Phút từ lúc giải ngân · tỉ lệ khoản vay/số dư · người nhận khác tên · có trong danh bạ + lưu bao lâu · đã từng chuyển chưa · SIMO · số tin báo đã có · nội dung.")
    chk = f.decision("check_transfer", step=5,
                     explain="ai.check_transfer — cùng 1 hàm cho app khách, bộ mô phỏng và dữ liệu lịch sử.")
    ok = f.process("Cho phép", step=6, icon="check", explain="Người nhận quen / giao dịch bình thường — không làm phiền.")
    warn = f.process("Khoan đã!", step=6, icon="alert", explain="Có dấu hiệu nhưng có thể là thật (vd người thân nhờ gấp) → khách đọc lý do, Huỷ hoặc Vẫn chuyển.")
    hold = f.process("Tạm giữ", step=6, icon="lock", badge="tiền chưa rời ví",
                     explain="Tài khoản bị báo/SIMO, trả 'nợ' vào TK cá nhân, hoặc vay xong chuyển hết cho người lạ chưa quen + dấu hiệu khác.")
    rep = f.process("Báo lừa đảo", step=7, icon="mail", explain="Lá chắn phân tích tin; tin từ kênh chính thức đã xác thực → An toàn, không cảnh báo.")
    q = f.process("Hàng đợi đội rủi ro", step=8, icon="laptop", badge="LV…",
                  explain="Cảnh báo trực tiếp hiện đầu hàng đợi (tự làm mới) → đồ thị, dòng thời gian, điều tra.")
    e = f.end()
    set_step(f, e, 9)
    for nid, c in ((msg, "#f4b47e"), (chk, "#cdb8ec"), (hold, "#f4b47e"), (warn, "#f6d58e"), (ok, "#b8e0c2")):
        color(f, nid, c)
    f.link(s, msg); f.link(msg, loan); f.link(loan, follow); f.link(follow, ctx); f.link(ctx, chk)
    f.link(chk, ok, "an toàn"); f.link(chk, warn, "đáng ngờ"); f.link(chk, hold, "lừa rõ")
    f.link(msg, rep, "khách tự báo"); f.link(hold, q); f.link(rep, q, "nếu là lừa"); f.link(ok, e); f.link(warn, e); f.link(q, e)
    f.narrate(1, "Tin lừa", "3 khách demo, mỗi người 2 tình huống lừa có thật + tin chính thức của FinVay.", badge="CA THẬT")
    f.narrate(2, "Vay", "Kẻ lừa dụ vay — eKYC vẫn đạt vì chính chủ tự vay.")
    f.narrate(3, "Làm theo", "Nút 'Làm theo hướng dẫn' để giám khảo tự đóng vai nạn nhân.")
    f.narrate(4, "Ngữ cảnh", "Tất cả là dữ liệu tại ĐÚNG lúc chuyển — không biết tương lai.")
    f.narrate(5, "Bộ kiểm tra", "Gemini quyết định chính; luật (app/backend/mock_ai.py) chỉ được nâng mức, và thay thế khi chưa cấu hình AI.", badge="AI")
    f.narrate(6, "3 kết quả", "Đã chạy thử: 5 ca lừa → tạm giữ, ca người thân nhờ gấp → cảnh báo, chuyển cho người thân quen → cho phép.")
    f.narrate(7, "Báo lừa", "Báo nhầm tin chính thức vẫn ra An toàn — không làm phiền đội rủi ro.")
    f.narrate(8, "Đội rủi ro", "Cảnh báo có mã LV…, mức Khẩn với giao dịch tạm giữ.")
    return f


# ── 8. Bộ mô phỏng hoạt động ─────────────────────────────────────────────────────────
def mo_phong():
    f = Flow("thienla-mo-phong", "Bộ mô phỏng hoạt động trực tiếp")
    f.group = GROUP
    f.meta(subtitle="app/sim.py — tự sinh khoản vay + chuyển tiền ngẫu nhiên để hệ thống 'đang sống' khi demo.",
           duration="kỹ thuật", level="Chi tiết",
           learn=["Đi qua ĐÚNG luồng của app khách — không có đường tắt",
                  "Nhãn kịch bản chỉ để đo, bộ kiểm tra không nhìn thấy",
                  "Đo 2 con số: lừa bị chặn / bình thường bị làm phiền"])
    s = f.start()
    tick = f.process("Mỗi nhịp (0,5–30 giây)", step=1, icon="clock", explain="Đội rủi ro bật/tắt và chọn nhịp; SIM_AUTOSTART=1 để bật sẵn. Tự dừng sau 2.000 sự kiện.")
    which = f.decision("Vay hay chuyển?", step=2, explain="40% khoản vay mới (khách ngẫu nhiên trong 200.000 hồ sơ); còn lại: 1 người vừa vay chuyển tiền.")
    loan = f.process("Khoản vay mới", step=3, icon="check", explain="2–20 triệu, giải ngân về ví chính chủ, ghi mốc thời gian.")
    kind = f.decision("Chọn kịch bản", step=3,
                      explain="Bình thường 72% (rút về TK chính chủ, người nhà, trả tiền phòng/mua hàng) · bị dụ vay 13% · giả thu nợ 8% · người thân nhờ gấp 7%.")
    exe = f.process("khach.execute_transfer", step=4, icon="api", explain="Cùng hàm với app khách: dựng ngữ cảnh → ai.check_transfer → ghi giao dịch; tạm giữ → cảnh báo LV….")
    conf = f.decision("Cảnh báo?", step=5, explain="Khách mô phỏng đọc cảnh báo: một nửa huỷ, một nửa vẫn chuyển.")
    cnt = f.process("Bộ đếm + dòng hoạt động", step=6, icon="chart",
                    explain="Khoản vay · giao dịch · cho phép / cảnh báo / tạm giữ · lừa bị chặn / tổng · bình thường bị làm phiền · 15 sự kiện gần nhất.")
    e = f.end()
    set_step(f, e, 7)
    f.link(s, tick); f.link(tick, which); f.link(which, loan, "vay"); f.link(which, kind, "chuyển"); f.link(kind, exe)
    f.link(exe, conf); f.link(conf, cnt, "không / đã xử lý"); f.link(loan, cnt); f.link(cnt, tick, "nhịp tiếp ↺"); f.link(cnt, e, "tắt")
    f.narrate(1, "Nhịp", "Truy vấn DB chạy ở luồng riêng — web không bị đứng.")
    f.narrate(2, "Vay hay chuyển", "Chỉ người vừa vay mới chuyển — đúng hình dạng 'vay xong chuyển đi'.")
    f.narrate(3, "Kịch bản", "Nhãn kịch bản không được đưa vào bộ kiểm tra.", badge="CÔNG BẰNG")
    f.narrate(4, "Kiểm tra", "Giao dịch tạm giữ hiện trên hàng đợi với chữ '(mô phỏng)'.")
    f.narrate(5, "Khách quyết", "Cảnh báo không chặn cứng — khách vẫn được quyền chuyển.")
    f.narrate(6, "Đo", "Một lần chạy ~20 giây: lừa bị chặn 8/8, bình thường bị làm phiền 0.")
    return f


# ── 9. Hạ tầng + bảo mật ─────────────────────────────────────────────────────────────
def ha_tang():
    f = Flow("thienla-ha-tang", "Hạ tầng và bảo mật: một yêu cầu đi qua những lớp nào")
    f.group, f.look = GROUP, "iso"
    f.meta(subtitle="Docker Compose: PostgreSQL 16 + web app FastAPI (user không phải root). Bí mật chỉ nằm trong .env.",
           duration="kỹ thuật", level="Chi tiết",
           learn=["2 loại phiên tách biệt: đội rủi ro và khách",
                  "Giới hạn lượt gọi + header bảo mật ở 1 chỗ (middleware)",
                  "Chế độ demo bật/tắt bằng cờ, không sửa code"])
    s = f.start()
    br = f.process("Trình duyệt", step=1, icon="laptop", explain="Màn đội rủi ro (/), app ví khách (/vi/), luồng trình chiếu (/flows/).")
    px = f.process("Caddy (HTTPS)", step=2, icon="balancer", explain="Reverse proxy + chứng chỉ tự động khi lên VPS; THIENLA_BEHIND_PROXY=1 để lấy IP thật + cookie Secure.")
    mw = f.process("Middleware bảo mật", step=3, icon="lock", badge="security.guard",
                   explain="Giới hạn lượt theo IP (đăng nhập 5/phút…) · chặn API cần đăng nhập · CSP, X-Frame-Options, nosniff, no-referrer · no-store cho API.")
    who = f.decision("Loại phiên?", step=4, explain="Cookie ký HMAC-SHA256, HttpOnly, SameSite=Strict. Đội rủi ro: mật khẩu (8 giờ). Khách: SĐT + PIN băm scrypt (2 giờ).")
    risk = f.process("API đội rủi ro", step=5, icon="api", explain="Hàng đợi, đồ thị, hồ sơ (đã tối thiểu hoá PII), điều tra, phát realtime, mô phỏng.")
    kh = f.process("API khách", step=5, icon="user", explain="Chỉ dữ liệu của chính SĐT đang đăng nhập; cùng 1 thông báo cho sai SĐT và sai PIN.")
    pub = f.process("Công khai", step=5, icon="file", explain="Lá chắn, tổng quan, chỉ số tổng hợp — không có dữ liệu cá nhân.")
    dbn = f.process("PostgreSQL 16", step=6, icon="database", badge="127.0.0.1:5433",
                    explain="Trong Docker, chỉ mở cho máy mình. build.py nạp ~1,3 triệu dòng bằng COPY; dữ liệu mô phỏng 100%.")
    e = f.end()
    set_step(f, e, 7)
    for nid, c in ((mw, "#f4b47e"), (dbn, "#cdb8ec")):
        color(f, nid, c)
    f.link(s, br); f.link(br, px); f.link(px, mw); f.link(mw, who); f.link(who, risk, "đội rủi ro"); f.link(who, kh, "khách"); f.link(who, pub, "không cần")
    f.link(risk, dbn); f.link(kh, dbn); f.link(pub, dbn); f.link(dbn, e)
    f.narrate(1, "Trình duyệt", "3 cửa vào cho 3 đối tượng.")
    f.narrate(2, "HTTPS", "Bản thi chạy sau Caddy; chạy trên máy thì bỏ qua lớp này.")
    f.narrate(3, "Middleware", "Mọi yêu cầu đều qua đây trước — 1 chỗ để rà soát.", badge="BẢO MẬT")
    f.narrate(4, "Phiên", "Phiên khách không mở được API đội rủi ro và ngược lại.",
              note="DEMO_AUTOFILL=1 trả mật khẩu/PIN cho trình duyệt để tự đăng nhập — chỉ bật khi trình diễn.", note_type="warn")
    f.narrate(5, "Phân quyền", "Đã thử: khách gọi API đội rủi ro → 401; cookie giả → 401; PIN sai → 401.")
    f.narrate(6, "Dữ liệu", "Đặt lại demo = chạy lại build.py (xoá sạch rồi dựng lại ~15 giây).")
    return f


if __name__ == "__main__":
    for build in (kien_truc, ca_an_giang, agent_loop, vong_doi, realtime, hang_doi, backend_agent_pipeline, batch_ai_pipeline,
                  app_khach, mo_phong, ha_tang,realtime_ai_pipeline):
        print("saved:", build().save(OUT))
