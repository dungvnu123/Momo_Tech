"""Ground action recommendations without assigning a fraud verdict by rule."""


def validate_case(context, case, steps):
    transactions = {}
    by_source = {}
    for step in steps:
        if not step.result.get("ok"):
            continue
        data = step.result.get("data", {})
        records = data.get("transfers", []) + ([data["transfer"]] if data.get("transfer") else [])
        by_source[step.tool_call_id] = {t["transfer_id"]: t for t in records}
        transactions.update(by_source[step.tool_call_id])
    focused = context.alert.get("transfer_id")
    if context.alert.get("kind") == "transfer" and focused:
        if focused not in transactions:
            raise ValueError("Read triggering_transfer_id with get_transfer or money_flow before concluding a transfer alert")
        if not any(item.transfer_id == focused for item in case.transaction_assessments):
            raise ValueError("Supply a transaction_assessments entry for triggering_transfer_id; borrower role can remain inconclusive")
    if case.verdict == "inconclusive" and not case.missing_information:
        raise ValueError("State the specific missing_information and actionable checks; do not use a generic uncertain conclusion")
    seen = set()
    for item in case.transaction_assessments:
        if item.transfer_id in seen:
            raise ValueError("Assess each transfer once")
        seen.add(item.transfer_id)
        transaction = transactions.get(item.transfer_id)
        if transaction is None:
            raise ValueError("Assess only transfers observed in successful tool results")
        if not any(item.transfer_id in by_source.get(e.source, {}) for e in item.evidence):
            raise ValueError("Transaction evidence must cite a tool result containing that exact transfer")
        if item.recommendation == "hold" and not (transaction.get("simo_flag") is True or transaction.get("verified_reported_recipient_count", 0) > 0):
            raise ValueError("Hold needs a recorded recipient warning with verified scope; mock assessments or number-only bank matches require warn or review")
        if item.recommendation == "allow" and transaction.get("simo_flag") is True:
            raise ValueError("A recorded SIMO warning is unresolved; recommend review, warn or hold instead of allow")
