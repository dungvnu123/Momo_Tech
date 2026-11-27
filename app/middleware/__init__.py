from .api_key import ServiceKeyMiddleware
from .request_context import RequestContextMiddleware


def configure_middleware(application, *, service_api_key: str = ""):
    if service_api_key:
        application.add_middleware(ServiceKeyMiddleware, api_key=service_api_key)
    application.add_middleware(RequestContextMiddleware)
