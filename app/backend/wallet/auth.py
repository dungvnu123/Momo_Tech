import os
from fastapi import HTTPException, Request, Response
from app import security
from .schemas import LoginIn


def register(router, wallet):
    @router.post("/login")
    def login(body: LoginIn, request: Request, response: Response):
        rows = wallet.tools.q(
            "SELECT pin_salt, pin_hash FROM khach_accounts WHERE phone=?", body.phone
        )
        if not rows or not security.check_pin(body.pin, rows[0]["pin_salt"], rows[0]["pin_hash"]):
            raise HTTPException(401, "SĐT hoặc PIN không đúng")
        response.set_cookie(
            security.KHACH_COOKIE,
            security.make_khach_token(body.phone),
            max_age=security.KHACH_TTL,
            httponly=True,
            samesite="strict",
            secure=request.url.scheme == "https",
        )
        return {"ok": True}

    @router.get("/demo")
    def demo_accounts():
        """SĐT các tài khoản demo để bấm chọn. PIN chỉ trả ra khi bật DEMO_AUTOFILL (chế độ trình diễn)."""
        rows = wallet.tools.q(
            "SELECT phone, display_name, scenario FROM khach_accounts ORDER BY balance"
        )
        pin = os.environ.get("DEMO_PIN", "") if security.DEMO_AUTOFILL else ""
        return [
            {
                "phone": r["phone"],
                "name": r["display_name"],
                "scenario": r["scenario"],
                **({"pin": pin} if pin else {}),
            }
            for r in rows
        ]

    @router.post("/logout")
    def logout(response: Response):
        response.delete_cookie(security.KHACH_COOKIE)
        return {"ok": True}
