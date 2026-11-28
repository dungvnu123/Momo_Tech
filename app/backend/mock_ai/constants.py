import re

MODE = 'mock'

OFFICIAL = 'FinVay'

INJECTION = re.compile('(?i)(bo qua moi chi dan|\\[system\\]|assistant must|ghi chu cho ai)')

SCAM_HINT = re.compile('(?i)(chuyen|nop|ck|stk|\\btk\\b|momo|thanh toan ngay|truy cap|phi kich hoat|giam 50|tat toan|cong an|khoi kien|xac minh|kich hoat)')

VICTIM_HINT = re.compile('(?i)(toi bi lua|toi vua vay|toi da mat|nho .* ho tro|mat tien|khong goi duoc|chan lien lac)')

OTP_ASK = re.compile('(?i)(nhap|cung cap|gui|doc)( lai)? ma otp|otp vua nhan')

LEGIT_HINT = re.compile('(?i)(khong (bao gio )?yeu cau chuyen (khoan|tien)|ma otp cua ban|cam on quy khach da thanh toan|da duoc giai ngan ve vi)')

URL_RE = re.compile('(?i)\\b(?:https?://)?((?:[a-z0-9-]+\\.)+(?:com|net|top|vn|ly)(?:/[\\w-]+)?)')

ACC_RE = re.compile('(?<![\\w])((?:[0-9oO][ .]?){8,16}[0-9oO])(?![\\w])')

NOTE_TAGS = {'fee': 'phi giai ngan|xac minh|bao lanh|hoan tien|kich hoat', 'debt_collection': 'tra no|tat toan|thanh toan (khoan )?vay|no qua han|thu hoi no|finvay', 'urgent': 'gap|cap cuu|benh vien|tai nan|cong an|khan cap'}
