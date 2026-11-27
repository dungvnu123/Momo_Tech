import json
import logging


class RequestLogFormatter(logging.Formatter):
    def format(self, record):
        fields = ("request_id", "method", "route", "operation", "status_code", "duration_ms", "completed")
        return json.dumps({"event": "http_request", **{field: getattr(record, field, None) for field in fields}})


def configure_request_logging():
    logger = logging.getLogger("app.requests")
    if not any(getattr(handler, "thienla_request_log", False) for handler in logger.handlers):
        handler = logging.StreamHandler()
        handler.thienla_request_log = True
        handler.setFormatter(RequestLogFormatter())
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
