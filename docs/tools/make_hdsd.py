# path: docs/tools/make_hdsd.py
"""Dựng HDSD 1 trang A4 (PDF) từ docs/hdsd/hdsd_1trang.html, điền link + tài khoản dùng thử từ .env / Postgres.

Chạy:  uv run python docs/tools/make_hdsd.py --link https://thienla.example.vn
Ra:    docs/hdsd/HDSD_Thien_La.pdf  (+ .png xem trước) — CHỨA tài khoản dùng thử nên đã gitignore, không commit.
In bằng Edge/Chrome chế độ không giao diện (có sẵn trên Windows), không cần cài thêm.
"""
import argparse
import html
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from app import db  # noqa: E402 — nạp .env

ap = argparse.ArgumentParser()
ap.add_argument("--link", default="http://localhost:4420")
args = ap.parse_args()

REACT = ["Tạm giữ ① · Tạm giữ ② (FinVay chỉ thu nợ trong app)", "Tạm giữ ① · Lá chắn báo lừa ② (link giả + đòi OTP)",
         "Tạm giữ ① · Cảnh báo ② (gọi điện xác minh người thân)"]
rows = db.connect().execute("SELECT phone, display_name, scenario FROM khach_accounts ORDER BY balance").fetchall()
persona_rows = "\n".join(f"<tr><td><b>{html.escape(r['display_name'])}</b><br><span class='k'>{r['phone']}</span></td>"
                         f"<td>{html.escape(r['scenario'] or '')}</td><td>{REACT[i] if i < len(REACT) else ''}</td></tr>" for i, r in enumerate(rows))
fill = {"{{LINK}}": args.link.rstrip("/"), "{{PASSWORD}}": html.escape(os.environ.get("THIENLA_PASSWORD", "")),
        "{{PIN}}": html.escape(os.environ.get("DEMO_PIN", "")), "{{PERSONA_ROWS}}": persona_rows,
        "{{AUTOFILL_NOTE}}": "(bản demo tự đăng nhập)" if os.environ.get("DEMO_AUTOFILL") == "1" else ""}
src = (ROOT / "docs/hdsd/hdsd_1trang.html").read_text(encoding="utf-8")
for k, v in fill.items():
    src = src.replace(k, v)
out_html = ROOT / "docs/hdsd/_HDSD_filled.html"
out_html.write_text(src, encoding="utf-8")

browser = next((p for p in (r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe", r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                            shutil.which("chromium"), shutil.which("google-chrome")) if p and Path(p).exists()), None)
if not browser:
    raise SystemExit("Không thấy Edge/Chrome để in PDF")
pdf = ROOT / "docs/hdsd/HDSD_Thien_La.pdf"
subprocess.run([browser, "--headless=new", "--disable-gpu", "--no-pdf-header-footer", f"--print-to-pdf={pdf}", out_html.as_uri()],
               check=True, capture_output=True, timeout=120)
try:
    import fitz  # PyMuPDF (nếu có) → ảnh xem trước + đếm trang
    d = fitz.open(pdf)
    d[0].get_pixmap(dpi=80).save(pdf.with_suffix(".png"))
    print(f"{pdf.name}: {len(d)} trang (yêu cầu ≤ 1)")
except ImportError:
    print(pdf.name)
out_html.unlink()
