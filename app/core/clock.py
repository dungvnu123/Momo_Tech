def vntime_now():
    """Giờ Việt Nam (GMT+7), naive — server/pod chạy UTC."""
    from datetime import datetime
    from zoneinfo import ZoneInfo

    return datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).replace(tzinfo=None)
