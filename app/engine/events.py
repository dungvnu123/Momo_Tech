def events(apps, transfers, reports, repayments=(), schedule=(), data_end="9999"):
    """Gộp mọi sự kiện, sắp theo thời gian. (thời điểm, thứ tự, loại, dữ liệu).
    due_check = lịch hẹn giờ của chính hệ thống (đến hạn kỳ 1 + 10 ngày) — không phải dữ liệu tương lai."""
    from datetime import date, timedelta

    ev = [(a["applied_at"], 0, "apply", a) for a in apps]
    ev += [(t["created_at"], 1, "transfer", t) for t in transfers]
    ev += [(r["reported_at"], 2, "report", r) for r in reports]
    ev += [(r["paid_at"], 3, "repayment", r) for r in repayments]
    for s in schedule:
        if s["term_no"] == "1":
            ck = (date.fromisoformat(s["due_date"]) + timedelta(days=10)).isoformat() + "T00:00:00"
            if ck <= data_end:
                ev.append((ck, 4, "due_check", s["app_id"]))
    ev.sort(key=lambda e: (e[0], e[1]))
    return ev
