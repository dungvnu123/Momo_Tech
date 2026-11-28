import json

from fastapi import HTTPException
from pydantic import BaseModel, Field
from app.core.http import run_ai
from .. import mock_ai as ai
from .common import times_reported


def register(app, tools, adapter, META):
    class ReportIn(BaseModel):
        text: str = Field(max_length=4000)


    @app.post("/api/shield/analyze")
    async def shield(body: ReportIn):
        if not body.text.strip():
            raise HTTPException(400, "Thiếu nội dung tin nhắn")
        res = await run_ai(adapter.analyze_report(body.text[:2000]))
        ind = res["indicators"]
        res["times_reported"] = times_reported(tools, ind["accounts"] + ind["phones"]) if res["verdict"] != "safe" else 0
        return res


    @app.get("/api/shield/samples")
    def shield_samples():
        rows = tools.q("SELECT report_id, raw_text, analysis FROM reports ORDER BY report_id")
        pick, seen = [], set()
        for r in rows:   # chọn mẫu đa dạng theo KẾT QUẢ phân tích (không dùng đáp án)
            an = json.loads(r["analysis"])
            key = ("injection" if ai.INJECTION.search(ai.plain(r["raw_text"])) else
                   "victim" if an["reporter_is_victim"] else an["verdict"])
            if key not in seen:
                seen.add(key); pick.append({"label": {"scam": "Tin đòi chuyển tiền", "safe": "Tin chính thức", "victim": "Người bị hại kể lại",
                                                      "injection": "Tin có câu lừa AI", "suspicious": "Tin đáng ngờ"}[key], "text": r["raw_text"]})
        return pick
