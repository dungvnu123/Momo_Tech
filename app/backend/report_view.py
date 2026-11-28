from app.ai.shield.indicators import canonical_indicator


def report_view(result):
    indicators = {"accounts": [], "phones": [], "urls": []}
    canonical = []
    for item in result.indicators:
        key = canonical_indicator(item)
        canonical.append(key)
        group = (
            "accounts"
            if item.kind == "bank_account"
            else "urls"
            if item.kind == "url"
            else "phones"
        )
        indicators[group].append(
            key.rsplit(":", 1)[-1] if group != "urls" else key.split(":", 1)[-1]
        )
    return {
        **result.model_dump(),
        "indicators": indicators,
        "canonical_indicators": canonical,
        "analysis": result.model_dump(),
        "mode": "gemini",
        "verification_status": "unverified",
    }
