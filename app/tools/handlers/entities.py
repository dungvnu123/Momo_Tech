import re

from app.ai.shield.indicators import redact_text


def decision_view(store, record):
    result = {key: record[key] for key in ("pair_id", "app_ids", "decision", "confidence") if key in record}
    reason = record.get("reason", "")
    for app_id in record.get("app_ids", []):
        original = store.application(app_id)
        for field in ("full_name", "address", "dob"):
            if original.get(field):
                reason = re.sub(re.escape(original[field]), "[redacted]", reason, flags=re.IGNORECASE)
    result["reason"] = redact_text(reason)
    return result


def entity_info(store, request, views):
    identifier = views.resolve(request.node_id)
    result = store.entity_details(identifier)
    result["node_id"] = views.public_id(identifier)
    result["decisions"] = [decision_view(store, record) for record in result["decisions"]]
    return result
