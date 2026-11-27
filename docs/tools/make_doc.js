const fs = require('fs');
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, ExternalHyperlink,
  WidthType, ShadingType, AlignmentType, LevelFormat, BorderStyle,
} = require('docx');

const FONT = 'Arial';
const ACCENT = 'B4232A';
const W = 9638; // A4, lề trái/phải 2 cm

const t = (s) => new TextRun(s);
const b = (s) => new TextRun({ text: s, bold: true });
const p = (runs, opts = {}) => new Paragraph({ spacing: { after: 120 }, ...opts, children: typeof runs === 'string' ? [t(runs)] : runs });
const h1 = (s) => new Paragraph({ text: s, heading: 'Heading1' });
const h2 = (s) => new Paragraph({ text: s, heading: 'Heading2' });
const li = (ref) => (runs) => new Paragraph({ numbering: { reference: ref, level: 0 }, spacing: { after: 60 }, children: typeof runs === 'string' ? [t(runs)] : runs });
const bullet = li('bul');
const num = li('num');
const gap = () => new Paragraph({ spacing: { after: 120 }, children: [] });
const link = (text, url) => new ExternalHyperlink({ link: url, children: [new TextRun({ text, style: 'Hyperlink' })] });

function table(widths, rows) {
  const border = { style: BorderStyle.SINGLE, size: 4, color: 'BFBFBF' };
  const borders = { top: border, bottom: border, left: border, right: border };
  return new Table({
    width: { size: W, type: WidthType.DXA },
    columnWidths: widths,
    rows: rows.map((r, i) => new TableRow({
      tableHeader: i === 0,
      children: r.map((c, j) => new TableCell({
        width: { size: widths[j], type: WidthType.DXA },
        borders,
        margins: { top: 60, bottom: 60, left: 100, right: 100 },
        shading: i === 0 ? { type: ShadingType.CLEAR, color: 'auto', fill: 'F2DCDB' } : undefined,
        children: [new Paragraph({ children: [new TextRun({ text: c, bold: i === 0, size: 19 })] })],
      })),
    })),
  });
}

const SRC = [
  ['Công an tỉnh An Giang, “Cảnh báo thủ đoạn lừa đảo dụ dỗ vay tiền qua ứng dụng tài chính trực tuyến”, 09/11/2026', 'https://congan.angiang.gov.vn/canh-bao-thu-doan-lua-dao-du-do-vay-tien-qua-ung-dung-tai-chinh-truc-tuyen'],
  ['Vietstock (theo VietNamNet), “Triệt phá đường dây gần 1.000 tài khoản, lộ thủ đoạn qua mặt sinh trắc học”, 26/06/2026', 'https://vietstock.vn/2026/06/triet-pha-duong-day-gan-1000-tai-khoan-lo-thu-doan-qua-mat-sinh-trac-hoc-757-1458887.htm'],
  ['CafeF (theo Người Lao Động), “Ngân hàng Nhà nước cảnh báo thủ đoạn lừa đảo mới nhất liên quan dữ liệu sinh trắc học”, 20/04/2026', 'https://cafef.vn/ngan-hang-nha-nuoc-canh-bao-thu-doan-lua-dao-moi-nhat-lien-quan-du-lieu-sinh-trac-hoc-188260420200728924.chn'],
  ['CafeF (theo Nhịp sống Thị trường), “Đã xác thực sinh trắc học, vì sao lừa đảo vẫn rút được số tiền lớn từ tài khoản nạn nhân?”, 06/05/2026', 'https://cafef.vn/da-xac-thuc-sinh-trac-hoc-vi-sao-lua-dao-van-rut-duoc-so-tien-lon-tu-tai-khoan-nan-nhan-188260506160917319.chn'],
  ['Cổng TTĐT Bộ Công an, “Nâng cao cảnh giác trước 25 kịch bản lừa đảo trên không gian mạng năm 2026”, 08/09/2026', 'https://bocongan.gov.vn/bai-viet/nang-cao-canh-giac-truoc-25-kich-ban-lua-dao-tren-khong-gian-mang-nam-2026-1788865614'],
  ['Vietnam+ (TTXVN), “Cảnh giác chiêu trò mạo danh cán bộ ngân hàng”, 27/11/2026', 'https://www.vietnamplus.vn/canh-giac-chieu-tro-mao-danh-can-bo-ngan-hang-post1150889.vnp'],
];

const children = [
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 60 },
    children: [new TextRun({ text: 'THIÊN LA', bold: true, size: 56, color: ACCENT })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 60 },
    children: [new TextRun({ text: 'Trợ lý AI truy vết đường dây gian lận và lừa đảo tín dụng', bold: true, size: 28 })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 240 },
    border: { bottom: { style: BorderStyle.SINGLE, size: 8, color: ACCENT, space: 8 } },
    children: [new TextRun({ text: '“Một người bị lừa báo tin, cả đường dây lộ diện.”', italics: true, size: 24 })] }),

  h1('1. Tóm tắt'),
  p('Thiên La (từ thành ngữ “thiên la địa võng”) là trợ lý AI dùng chung cho đội rủi ro của ngân hàng cho vay và nền tảng ví điện tử phân phối khoản vay. AI tự điều tra đường dây gian lận bằng cách ghép ba nguồn mà xưa nay nằm tách rời: hồ sơ vay, tín hiệu kỹ thuật lúc nộp hồ sơ, dòng tiền sau giải ngân, và tin báo lừa đảo từ chính khách hàng. Kết quả là hồ sơ vụ việc có bằng chứng, phân biệt rõ kẻ gian cần chặn với nạn nhân cần bảo vệ.'),

  h1('2. Chủ đề và người dùng'),
  table([2600, W - 2600], [
    ['Hạng mục', 'Nội dung'],
    ['Chủ đề', 'Chống lừa đảo (chính) · An ninh mạng · Trợ lý AI'],
    ['Người dùng chính', 'Đội rủi ro của ngân hàng cho vay (thấy hồ sơ, giải ngân) và của nền tảng ví (thấy dòng tiền sau giải ngân) — B2B dùng chung'],
    ['Người dùng phụ', 'Khách vay, qua Lá chắn và cảnh báo lúc chuyển tiền ngay trong app ví'],
    ['Hình thức', 'Ứng dụng web dùng trực tuyến, có tài khoản dùng thử'],
  ]),
  gap(),

  h1('3. Vấn đề'),
  p([b('Một ca thật, mới nhất. '), t('Ngày 09/11/2026, Công an An Giang cảnh báo: kẻ gian tiếp cận qua quảng cáo hoặc giả cơ quan chức năng, hướng dẫn nạn nhân cài ví điện tử (bài nêu cả MoMo), để nạn nhân tự vay và tự xác thực khuôn mặt, rồi viện cớ “xác minh, nộp phí, hoàn tiền” để nạn nhân chuyển toàn bộ tiền vay. Một ca ngày 03/11 mất 120 triệu; nạn nhân vẫn phải tự trả nợ [1].')]),
  num([b('Hợp đồng không kiểm soát được tiền sau giải ngân. '), t('Đối chiếu hợp đồng mẫu của một sản phẩm cho vay tiêu dùng qua nền tảng ví đang vận hành: tiền giải ngân vào tài khoản đứng tên khách, mục đích ghi “hoàn ứng vốn tự có phục vụ đời sống”, khách tự chịu mọi tổn thất kể cả khi bị lợi dụng. Vay xong chuyển hết đi là hợp lệ — luật cứng không chặn được.')]),
  num([b('eKYC không đủ. '), t('Chính chủ tự vay thì eKYC luôn đạt. Kẻ gian còn mua bán tài khoản kèm công cụ qua mặt sinh trắc, như đường dây gần 1.000 tài khoản ở Thanh Hoá [2]; Ngân hàng Nhà nước đã yêu cầu ngân hàng ngăn chặn AI/deepfake trong xác thực [3].')]),
  num([b('Luật cố định ngập cảnh báo sai. '), t('Đo trên dữ liệu mô phỏng 200.000 hồ sơ: gộp 5 luật phổ biến bắt được 93% gian lận nhưng phải gắn cờ 61.306 hồ sơ, và coi 21/28 nạn nhân là kẻ gian.')]),
  num([b('Nguồn tin bị tách rời. '), t('Tin báo lừa đảo nằm ở phía khách, dòng tiền và hồ sơ nằm ở phía công ty. Không ai nối chúng lại.')]),

  h1('4. Giải pháp'),
  h2('① Lá chắn: tiện ích cho khách vay'),
  bullet('Dán tin nhắn, đường link, số tài khoản hoặc số ví đáng ngờ → AI phán Lừa đảo / Đáng ngờ / An toàn kèm lý do, cho biết đã có bao nhiêu người báo cùng dấu vết.'),
  bullet('AI nhận ra cả tin người bị hại tự kể (“tôi vừa vay rồi chuyển cho…”), trích tài khoản, ví, hotline, tên miền đẩy về Lưới.'),
  h2('② Lưới: đồ thị tình báo'),
  bullet('Nối hồ sơ vay, thiết bị, SĐT tham chiếu, dải IP VPN/datacenter, lô SIM mới, tài khoản nhận tiền sau giải ngân, và dấu vết trong tin báo.'),
  bullet('AI hợp nhất thực thể: nhận ra cùng một người, một địa chỉ dù viết theo nhiều cách.'),
  h2('③ Sàng lọc AI'),
  bullet('200.000 hồ sơ sinh ra 4.487 cụm có quan hệ (đã đo), đa số là gia đình. Mỗi khi một cụm đổi, AI đọc bản tóm tắt số liệu (không có thông tin cá nhân), gạt cụm vô hại, giữ cụm có tổ hợp tín hiệu bất thường — 123 cụm được giữ.'),
  h2('④ Thám tử: AI agent điều tra'),
  bullet('Agent tự gọi công cụ: xem dòng tiền, lần ngược từ tài khoản gom ra người gửi, xem tín hiệu kỹ thuật, đọc tin báo liên quan; bắt buộc thử giả thuyết vô hại trước.'),
  bullet('Kết quả: hồ sơ vụ việc gồm sơ đồ đường dây, bằng chứng trỏ tới từng bước điều tra, danh sách kẻ gian và danh sách nạn nhân, đề xuất xử lý (dừng giải ngân, phong toả tài khoản, liên hệ hỗ trợ nạn nhân).'),

  h2('⑤ Cảnh báo lúc chuyển tiền (phía nền tảng ví)'),
  bullet('Ca xấu nhất: mỗi kẻ lừa chỉ dụ 1 người, mỗi lần 1 tài khoản mới → đồ thị không có gì để nối. Chỗ còn chặn được là lúc tiền rời ví, trước khi mất tiền.'),
  bullet('Đã đo: chỉ xét “chuyển ≥ 80% tiền vay trong 60 phút cho người khác tên” (gộp trong 2 giờ) còn 627 cờ trên 200.000 hồ sơ; thêm ngữ cảnh người nhận (không có trong danh bạ hoặc mới lưu vài phút, chưa từng chuyển, SIMO của NHNN gắn cờ) còn 320 cờ, vẫn bắt đủ 28/28 nạn nhân. Thêm luật từ khoá “phí/xác minh” thì trượt toàn bộ 20 nạn nhân được dặn ghi chú vô hại, mà vẫn dính “học phí” — AI phải đọc ngữ cảnh: người nhận lần đầu, ví nhận mới mở vài ngày, máy mở ví nhận dùng chung với ví khác.'),

  h2('⑥ Hàng đợi điều tra theo thời gian thật'),
  bullet('Bộ máy realtime xử lý từng sự kiện theo đúng thứ tự thời gian (nộp hồ sơ, chuyển tiền, tin báo, trả nợ, kiểm tra quá hạn kỳ đầu): 741.593 sự kiện trong khoảng 8 giây, sinh 347 cảnh báo. Mọi quyết định chỉ dùng dữ liệu đã xảy ra tới lúc đó.'),
  bullet('Đội rủi ro lọc theo ngày, khung giờ (đêm 0–6h), mức Khẩn/Cao/Trung bình, kết luận, độ tin cậy; sắp theo ưu tiên. Bấm 1 hồ sơ để xem dòng thời gian: nộp → eKYC → duyệt → giải ngân → chuyển tiền → đến hạn/trả → tin báo, kèm số ngày quá hạn tại đúng lúc cảnh báo.'),

  h1('5. AI là bộ não, đồ thị là trí nhớ'),
  p('Luật và đồ thị chỉ lưu quan hệ và khoanh vùng. Mọi bước tạo ra giá trị đều do AI thực hiện:'),
  table([2500, 3600, W - 6100], [
    ['Việc AI làm', 'Ví dụ', 'Vì sao luật không làm được'],
    ['Đọc tin báo phi cấu trúc', 'Rút số tài khoản viết lách (“19o3 4567”), ví MoMo, hotline, tên miền; nhận ra tin người bị hại tự kể', 'Kẻ gian liên tục đổi cách viết; tin có cả câu tiêm lệnh nhắm vào AI'],
    ['Hợp nhất thực thể mờ', '“Ng V. A, 12/5 P. Láng Hạ” = “Nguyễn Văn A, số 12 ngõ 5 Láng Hạ”', 'So khớp chuỗi bỏ sót hoặc nối nhầm'],
    ['Sàng lọc cụm', 'Gia đình chuyển tiền cho nhau ≠ nhiều ví lạ cùng đổ tiền về 1 tài khoản', 'Mỗi tín hiệu đơn lẻ đều có ca vô hại'],
    ['Điều tra tự chủ', 'Tự chọn hướng lần dấu vết, tự bác bỏ giả thuyết sai', 'Mỗi đường dây một hình dạng'],
    ['Phân biệt kẻ gian và nạn nhân', 'Hồ sơ sạch + chuyển hết tiền cho tài khoản bị báo + tin tự kể bị lừa → nạn nhân', 'Luật “chuyển ≥80% trong 1 giờ” coi 8/8 nạn nhân là kẻ gian'],
  ]),
  gap(),

  h1('6. Dữ liệu mô phỏng'),
  p('Dữ liệu giả hoàn toàn (thương hiệu “FinVay” hư cấu), bám ràng buộc thật: mỗi người một ví chính chủ, khoản vay luôn giải ngân về ví đó. Gồm 6 bảng có mốc thời gian (01/06 → 25/11/2026): 200.000 hồ sơ (nộp → eKYC → duyệt → giải ngân, kỳ hạn 3 tháng), 235.975 lần thử eKYC, 519.342 kỳ trả, 328.221 lần trả, 77.783 lượt chuyển tiền sau giải ngân kèm ngữ cảnh người nhận, 105 tin báo (5 tin chứa câu tiêm lệnh). Quá hạn không có cột chốt sẵn mà tính tại từng thời điểm. Cài sẵn:'),
  table([700, 2300, 900, W - 3900], [
    ['', 'Kiểu', 'Hồ sơ', 'Dấu vết'],
    ['A', 'Ví bị thuê/mua', '8', 'Vay xong chia tiền vào 6 tài khoản gom (2 ví + 4 ngân hàng, mỗi cái một tên); 23 tin báo rải trên 6 tài khoản, nối qua chung hotline và tên miền; 2 hồ sơ chờ giải ngân chỉ lộ qua thiết bị chung'],
    ['B', 'Tham chiếu chung, vay dồn dập', '15', 'Chung 2 SĐT tham chiếu, xoay 3 thiết bị, vay trong 3 ngày, quá hạn ngay kỳ đầu'],
    ['C', 'Một người nhiều CCCD', '7', '7 CCCD, 7 ví khác nhau; tên và địa chỉ viết lệch; chung 1 thiết bị'],
    ['D', 'Trại SIM rác + VPN', '12', 'SIM cùng lô mới 0–6 ngày, cùng dải IP datacenter/VPN, đa số giả lập, điền đơn dưới 70 giây lúc 0–5 giờ sáng'],
    ['E', 'Nạn nhân bị dụ vay', '8', 'Đúng kịch bản An Giang [1]: hồ sơ sạch, vay xong chuyển toàn bộ trong 10–60 phút tới 3 tài khoản có trong tin báo'],
    ['F', 'Chiếm ví + vượt eKYC', '6', 'Theo thủ đoạn camera ảo/deepfake [4]: ví cũ sạch, thiết bị mới gắn vài giờ, máy bị hook, liveness sát ngưỡng, vay kịch hạn mức lúc rạng sáng rồi chuyển hết. Chủ ví là nạn nhân'],
    ['G', 'Ngủ đông', '10', 'Ví nuôi sạch 4–7 tháng, tín hiệu sạch, cùng đợt đổ tiền về 3 tài khoản gom; chỉ 1 tin báo vào ngày cuối'],
    ['H', 'Nạn nhân một-một', '20', 'Ca xấu nhất: mỗi người chuyển vào 1 tài khoản mới riêng, ghi chú vô hại; một nửa là ví mới mở từ 2 máy trại, một nửa là ngân hàng ngoài'],
    ['—', 'Kẻ gian lẻ loi', '5', 'Mọi tín hiệu sạch tuyệt đối. Không kỳ vọng bắt được — công bố trung thực'],
  ]),
  gap(),
  p([b('Nhiễu vô hại cho từng tín hiệu: '), t('12.035 hồ sơ thuộc các gia đình (chung địa chỉ, tham chiếu, thiết bị, chuyển tiền cho nhau), 2.565 công nhân ở 100 ký túc xá, ~4% dùng VPN, ~5% vừa đổi SIM, ~15% rút nhanh về ngân hàng chính chủ, ~6% quá hạn không do gian lận.')]),

  h1('7. Đo bằng số'),
  p('Baseline luật đơn lẻ, đã đo trên 200.000 hồ sơ (58 hồ sơ gian lận, 28 nạn nhân, 5 kẻ lẻ loi):'),
  table([3800, 1300, 1300, 1600, W - 8000], [
    ['Luật', 'Gắn cờ', 'Bắt đúng', 'Nhầm nạn nhân', 'Recall'],
    ['SĐT tham chiếu chung ≥ 3 hồ sơ', '9.052', '15/58', '0/28', '26%'],
    ['Chuyển ≥ 80% tiền trong 1 giờ', '26.169', '26/58', '20/28', '45%'],
    ['IP VPN/datacenter hoặc SIM < 30 ngày', '17.722', '18/58', '2/28', '31%'],
    ['Thiết bị dùng chung ≥ 2 hồ sơ', '3.616', '32/58', '0/28', '55%'],
    ['Phiên eKYC bất thường', '15.755', '18/58', '2/28', '31%'],
    ['Gộp cả 5 luật', '61.306', '54/58', '21/28', '93%'],
    ['Lớp ứng viên đã vá (gộp tiền 2h, người nhận chung, SIMO)', '41.073', '58/58', '28/28 (đánh dấu là nạn nhân)', '100%'],
  ]),
  gap(),
  p([b('Toàn bộ đường đi, chế độ chưa cắm AI (mốc để AI phải vượt): '), t('kết luận 356 hồ sơ là kẻ gian, đúng 58/58, không nhầm nạn nhân nào, nhưng nhầm 298 hồ sơ vô hại; nhận ra 22/28 nạn nhân. Lá chắn giả lập phân loại đúng 105/105 tin, kể cả 5/5 tin tiêm lệnh. Lớp ứng viên đạt 58/58 và 28/28 trên cả seed chuẩn lẫn seed chấm chéo.')]),
  p([b('Thời gian phát hiện (hồ sơ đầu tiên của nhóm → cảnh báo đầu tiên): '), t('ví thuê 18 phút · nạn nhân bị dụ vay 42 phút · nạn nhân một-một 48 phút · trại SIM, tham chiếu chung, ngủ đông khoảng 1 ngày · chiếm ví 4 ngày · một người nhiều CCCD 27 ngày (chỗ AI hợp nhất thực thể cần rút ngắn). Kẻ lẻ loi: không cảnh báo, chỉ còn dấu vết hậu kiểm quá hạn kỳ đầu.')]),
  p([b('Mục tiêu của Thiên La: '), t('dưới 150 hồ sơ phải xem tay; precision ≥ 80%, recall ≥ 85%; không nhầm nạn nhân nào thành kẻ gian; công bố cả số bắt được với 5 kẻ lẻ loi (kỳ vọng 0); Lá chắn chặn được cả 5 tin tiêm lệnh. Kết quả được chấm lại trên một bộ dữ liệu sinh bằng seed khác để tránh “tự ra đề tự chấm”.')]),

  h1('8. Đối chiếu thủ đoạn thực tế 2026'),
  p('Một công cụ không thể bao phủ mọi thủ đoạn. Thiên La đứng ở phía bên cho vay, phủ phần dòng tiền và quan hệ giữa các hồ sơ:'),
  table([3000, 3600, W - 6600], [
    ['Thủ đoạn', 'Thiên La làm được', 'Không làm được'],
    ['Dụ vay rồi chuyển tiền giải ngân cho kẻ lừa [1]', 'Bắt ở dòng tiền, xếp là nạn nhân, đề xuất hỗ trợ; Lá chắn cảnh báo khi khách dán tin “phí xác minh”', 'Chặn trước khi tài khoản lừa bị ai báo'],
    ['Mua bán, thuê tài khoản kèm công cụ qua mặt sinh trắc [2][3]', 'Nhiều ví cùng đổ tiền về nhóm tài khoản gom → lộ cả đường dây, kể cả hồ sơ đang chờ giải ngân', 'Nhận ra khuôn mặt giả (việc của nhà cung cấp eKYC)'],
    ['Chiếm tài khoản bằng camera ảo + deepfake [4]', 'Với khoản vay: bắt bối cảnh quanh phiên eKYC (thiết bị mới, máy root/hook, liveness sát ngưỡng, vay kịch hạn mức rồi chuyển hết)', 'Chặn rút tiền sẵn có trong ví; nhận diện deepfake'],
    ['Mạo danh ngân hàng, tin brandname giả, link/QR độc [5]', 'Lá chắn phán tin, trích dấu vết, đếm lượt bị báo', 'Chặn tin trước khi đến máy; quét mã độc'],
    ['Mỗi kẻ lừa 1 nạn nhân, mỗi lần 1 tài khoản mới (ca xấu nhất)', 'Cảnh báo lúc chuyển tiền; nối qua dấu vết lúc mở ví hoặc kịch bản lừa lặp lại', 'Truy kẻ gian khi tài khoản ở ngân hàng ngoài, kịch bản riêng, không ai báo'],
    ['Deepfake người thân gọi video, vay đáo hạn giả [5][6]', 'Chỉ khi khách dán tin nhắn chữ vào Lá chắn', 'Phân tích cuộc gọi/video'],
  ]),
  gap(),
  p([b('Thông điệp: '), t('không hệ thống nào bắt được kẻ gian chưa để lại dấu vết. Thiên La rút thời gian từ nạn nhân đầu tiên đến lúc chặn cả đường dây xuống còn vài phút.')]),

  h1('9. Kiến trúc và công nghệ'),
  table([2600, W - 2600], [
    ['Thành phần', 'Công nghệ'],
    ['Backend / API', 'Python, FastAPI'],
    ['Bộ máy realtime', 'Tự viết bằng thư viện chuẩn Python (union-find, chỉ nối thêm): 741.593 sự kiện trong khoảng 8 giây'],
    ['AI', 'Claude API: model nhỏ cho Lá chắn, hợp nhất, sàng lọc; model lớn cho agent Thám tử (tool use)'],
    ['Giao diện', 'Một trang HTML + JavaScript thuần, Cytoscape.js (đóng gói sẵn, không gọi CDN), tông hồng'],
    ['Lưu trữ', 'SQLite'],
    ['Bảo mật', 'Đăng nhập + phiên ký HMAC, giới hạn lượt gọi, header CSP, tối thiểu hoá dữ liệu cá nhân'],
    ['Triển khai', 'VPS riêng + HTTPS, tài khoản dùng thử cho Ban giám khảo'],
  ]),
  gap(),

  h1('10. Kịch bản demo (video 3 phút)'),
  table([1500, W - 1500], [
    ['Thời điểm', 'Nội dung'],
    ['0:00–0:30', 'Chị Lan được “nhân viên” hướng dẫn vay 10 triệu để “xác minh hồ sơ”, chuyển đi rồi mất liên lạc — đúng kịch bản Công an An Giang vừa cảnh báo.'],
    ['0:30–1:00', 'Chị Lan kể lại vào Lá chắn. AI nhận ra tin người bị hại, trích số tài khoản: tài khoản này đã nhận tiền từ 7 người khác vừa vay.'],
    ['1:00–2:10', 'Màn đội rủi ro: bấm ▶ Phát realtime, cảnh báo hiện ra đúng giờ; lọc mức Khẩn. Bấm “Điều tra”: agent lần ra 8 nạn nhân, 3 tài khoản lừa, và một đường dây ví thuê đang chờ giải ngân thêm 2 hồ sơ.'],
    ['2:10–2:40', 'Hồ sơ vụ việc: dừng giải ngân 2 hồ sơ, đề nghị phong toả tài khoản gom, liên hệ hỗ trợ 8 nạn nhân thay vì đưa vào danh sách đen.'],
    ['2:40–3:00', 'So sánh: luật gắn cờ 61.306 hồ sơ và coi nạn nhân là kẻ gian; Thiên La chỉ ra đúng người. Kết bằng slogan.'],
  ]),
  gap(),

  h1('11. Trạng thái'),
  table([1800, W - 1800], [
    ['', 'Nội dung'],
    ['Đã xong', 'Dữ liệu mô phỏng 6 bảng có mốc thời gian + đáp án, 2 seed; bộ máy realtime + hàng đợi điều tra (lọc ngày/giờ/mức độ/độ tin cậy); Lá chắn; cảnh báo lúc chuyển tiền; đồ thị + dòng thời gian hồ sơ; chỉ số + thời gian phát hiện; bảo mật cơ bản; 6 luồng trình chiếu; tài liệu thiết kế'],
    ['Còn lại', 'Cắm AI thật vào 4 hàm trong app/ai.py và đo lại trên đúng các mốc ở mục 7; triển khai VPS + HTTPS + tài khoản dùng thử; slide 10 trang, hướng dẫn 1 trang, video 3 phút'],
  ]),
  gap(),

  h1('12. Rủi ro và cách xử lý'),
  table([3400, W - 3400], [
    ['Rủi ro', 'Cách xử lý'],
    ['Dữ liệu tự sinh bị xem là dàn dựng', 'Chấm trên seed khác; công khai cơ chế sinh; có nhiễu vô hại cho từng tín hiệu; công bố cả ca không bắt được'],
    ['Sàng lọc AI gạt nhầm cụm thật', 'Đo recall riêng tầng sàng lọc; cụm dính tin báo luôn được giữ'],
    ['Agent chậm khi giám khảo dùng thử', 'Mặc định xem kết quả đã điều tra sẵn; chạy trực tiếp có giới hạn lượt và số bước'],
    ['Tin báo chứa câu tiêm lệnh nhắm vào AI', 'Tin báo chỉ được coi là dữ liệu; đầu ra AI qua schema; agent không có quyền hành động thật'],
    ['Chi phí gọi AI', 'Bộ nhớ đệm, giới hạn lượt, hạn mức chi tiêu'],
  ]),
  gap(),

  h1('13. Bảo mật và dữ liệu cá nhân'),
  p('Đã rà soát và sửa; mỗi biện pháp đều có phép thử đi kèm:'),
  bullet([b('Đăng nhập: '), t('màn đội rủi ro (hàng đợi, đồ thị, hồ sơ, chuyển tiền) cần đăng nhập; phiên là cookie ký HMAC-SHA256, HttpOnly, SameSite=Strict, Secure khi chạy HTTPS, hết hạn 8 giờ. Lá chắn và trang tổng quan (chỉ số đếm) công khai.')]),
  bullet([b('Chống lạm dụng: '), t('giới hạn lượt gọi theo IP — đăng nhập 5 lần/phút (chống dò mật khẩu), Lá chắn 30, điều tra 12, phát realtime 6 lần/phút.')]),
  bullet([b('Header bảo mật: '), t('CSP chỉ cho script cùng nguồn, chặn nhúng khung, nosniff, không gửi referrer; tắt trang tài liệu API tự sinh.')]),
  bullet([b('Đầu vào: '), t('giới hạn độ dài, kiểm định dạng mã giao dịch và ngày giờ; mọi truy vấn SQL dùng tham số; giao diện escape dữ liệu trước khi hiển thị.')]),
  bullet([b('Dữ liệu cá nhân: '), t('dữ liệu mô phỏng 100%, nhưng vẫn làm như thật — SĐT/CCCD che 4 số giữa, dòng thời gian chỉ hiện năm sinh và tỉnh, AI sàng lọc chỉ nhận số liệu tổng hợp, danh bạ so khớp ngay trên máy khách và chỉ gửi cờ có/không.')]),
  bullet([b('Prompt injection: '), t('tin báo là dữ liệu không tin cậy; bộ thử có 5 tin tiêm lệnh; agent chỉ có công cụ đọc, không có quyền hành động thật.')]),
  bullet([b('Còn lại khi lên môi trường thật: '), t('phân vai và nhật ký truy cập theo từng người; giới hạn lượt gọi dùng chung giữa nhiều tiến trình.')]),

  h1('Nguồn tham khảo'),
  p('Đã đọc bài gốc ngày 27/11/2026.'),
  ...SRC.map(([text, url], i) => p([t(`[${i + 1}] ${text}. `), link(url, url)], { spacing: { after: 80 } })),
];

const doc = new Document({
  styles: {
    default: { document: { run: { font: FONT, size: 22 } } },
    paragraphStyles: [
      { id: 'Heading1', name: 'Heading 1', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { font: FONT, size: 28, bold: true, color: ACCENT },
        paragraph: { spacing: { before: 280, after: 120 }, keepNext: true, outlineLevel: 0 } },
      { id: 'Heading2', name: 'Heading 2', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { font: FONT, size: 24, bold: true },
        paragraph: { spacing: { before: 180, after: 80 }, keepNext: true, outlineLevel: 1 } },
    ],
  },
  numbering: { config: [
    { reference: 'bul', levels: [{ level: 0, format: LevelFormat.BULLET, text: '•', alignment: AlignmentType.LEFT,
      style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
    { reference: 'num', levels: [{ level: 0, format: LevelFormat.DECIMAL, text: '%1.', alignment: AlignmentType.LEFT,
      style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
  ] },
  sections: [{ properties: { page: { margin: { top: 1440, bottom: 1440, left: 1134, right: 1134 } } }, children }],
});

Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync(process.argv[2], buf);
  console.log('written', process.argv[2]);
});
