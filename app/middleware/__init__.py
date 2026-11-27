from .api_key import ServiceKeyMiddleware
from .request_context import RequestContextMiddleware
from .web_security import WebSecurityMiddleware


def configure_middleware(application, *, service_api_key: str = "", web_policy=None):
    if service_api_key:
        application.add_middleware(ServiceKeyMiddleware, api_key=service_api_key, web_policy=web_policy)
    if web_policy is not None:
        application.add_middleware(WebSecurityMiddleware, policy=web_policy)
    application.add_middleware(RequestContextMiddleware)
