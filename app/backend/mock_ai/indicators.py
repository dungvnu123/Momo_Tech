import re
import unicodedata
from .constants import ACC_RE,URL_RE,OFFICIAL
def plain(s: str) -> str:
    s = s.replace('đ', 'd').replace('Đ', 'D')
    return ''.join((c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn'))

def norm_number(raw: str) -> str:
    """Chuẩn hoá số viết lách: bỏ khoảng trắng/chấm, o/O → 0. Phần TẤT ĐỊNH — giữ lại kể cả khi dùng AI."""
    return re.sub('[ .]', '', raw).replace('o', '0').replace('O', '0')

def extract_indicators(text: str) -> dict:
    nums = [norm_number(m) for m in ACC_RE.findall(text)]
    nums = [n for n in nums if n.isdigit() and 8 <= len(n) <= 16]
    phones = [n for n in nums if len(n) == 10 and n[0] == '0']
    return {'accounts': [n for n in nums if n not in phones], 'phones': phones, 'urls': [u for u in URL_RE.findall(text) if not u.lower().startswith(OFFICIAL.lower() + '.')]}
