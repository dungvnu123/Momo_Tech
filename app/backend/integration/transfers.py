from app.backend import mock_ai
from app.ai.transfer.schemas import TransferCheck

RULES = "luật (chưa cấu hình AI)"


async def check_transfer(self, ctx):
    if not self.ready():
        return {**mock_ai.check_transfer(ctx), "mode": RULES}
    request = TransferCheck(
        loan_amount=ctx["loan_amount"],
        transfer_amount=ctx["amount"],
        minutes_after_disbursal=max(0, ctx["minutes_after_disbursal"]),
        recipient_name_matches=ctx["to_name_matches_borrower"],
        recipient_in_contacts=ctx["recipient_in_contacts"],
        contact_saved_minutes_ago=ctx["contact_saved_minutes_ago"],
        prior_transfers_to_recipient=ctx["prior_transfers_to_recipient"],
        simo_flag=ctx["simo_flag"],
        reported_recipient_count=ctx["times_reported"],
        recipient_ring_senders=(ctx.get("ring_case") or {}).get("n_senders", 0),
        share_of_balance=min(1, ctx["amount"] / ctx["balance"]) if ctx.get("balance") else None,
        note_tags=mock_ai.note_tags(ctx.get("note")),
        unverified_case_count=ctx.get("unverified_case_count", 0),
        unscoped_report_count=ctx.get("unscoped_report_count", 0),
        customer_says_coached=bool(ctx.get("coached")),
    )
    result = await self.service.check_transfer(request)
    return {**result.model_dump(), "message_for_customer": result.advice, "mode": "gemini"}
