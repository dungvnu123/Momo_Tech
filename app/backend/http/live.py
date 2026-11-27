import asyncio
import json
from fastapi.responses import StreamingResponse
from fastapi import HTTPException
from .common import alert_row


def register(app, tools, adapter, META):
    @app.get("/api/live")
    async def live(start: str = "2026-11-01", day_seconds: float = 12):
        """Phát lại realtime: đồng hồ mô phỏng chạy nhanh (1 ngày = day_seconds giây), đẩy cảnh báo đúng lúc nó sinh ra.
        Cảnh báo do app/engine.py sinh khi xử lý từng sự kiện theo thời gian; chạy thật thì engine đọc thẳng hàng đợi sự kiện."""
        from datetime import datetime, timedelta
        try:
            datetime.fromisoformat(start)
        except ValueError:
            raise HTTPException(400, "Ngày bắt đầu sai định dạng (YYYY-MM-DD)") from None
        day_seconds = max(1.0, min(day_seconds, 120.0))
        rows = [alert_row(r) for r in tools.q("SELECT * FROM alerts WHERE ts >= ? ORDER BY ts", start)]
        end = datetime.fromisoformat(META["last_day"]) + timedelta(days=1)

        async def stream():
            clock, i, tick = datetime.fromisoformat(start), 0, 0.25
            step = timedelta(days=tick / max(day_seconds, 0.5))
            while clock < end:
                clock += step
                batch = []
                while i < len(rows) and rows[i]["ts"] <= clock.isoformat():
                    batch.append(rows[i])
                    i += 1
                yield "data: " + json.dumps({"clock": clock.isoformat(timespec="minutes"), "alerts": batch}, ensure_ascii=False) + "\n\n"
                await asyncio.sleep(tick)
            yield "data: " + json.dumps({"clock": end.isoformat(timespec="minutes"), "alerts": [], "done": True}) + "\n\n"
        return StreamingResponse(stream(), media_type="text/event-stream")
