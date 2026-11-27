from .cases import transfer_cases


async def evaluate_transfers(service):
    transfer_results = []
    for item in transfer_cases():
        try:
            actual = await service.check_transfer(item["input"])
            transfer_results.append({"expected": item["expected"], "actual": actual.decision,
                                     "correct": actual.decision == item["expected"]})
        except Exception as error:
            transfer_results.append({"expected": item["expected"], "correct": False, "error": type(error).__name__})
    return transfer_results
