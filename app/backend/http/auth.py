from fastapi import HTTPException, Request, Response
from pydantic import BaseModel, Field

from app.security import COOKIE, TTL, check_password, make_token


class LoginIn(BaseModel):
    password: str = Field(min_length=1, max_length=200)


def register(app):
    policy = app.state.web_security

    @app.post("/api/login", tags=["auth"])
    def login(body: LoginIn, request: Request, response: Response):
        if not check_password(body.password, password=policy.password):
            raise HTTPException(401, "Sai mật khẩu")
        response.set_cookie(COOKIE, make_token(secret=policy.secret), max_age=TTL, httponly=True, samesite="strict",
                            secure=request.url.scheme == "https" or policy.behind_proxy)
        return {"ok": True}

    @app.post("/api/logout", tags=["auth"])
    def logout(response: Response):
        response.delete_cookie(COOKIE)
        return {"ok": True}

    @app.get("/api/me", tags=["auth"])
    def me(request: Request):
        return {"auth_required": bool(policy.password), "logged_in": policy.valid_session(request)}
