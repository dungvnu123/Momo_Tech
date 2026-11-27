from ..pipeline import triage_groups


def evaluation_groups(truth):
    groups, expected_cases = [], []
    for ring in truth["fraud_rings"]:
        expected_cases.append({"app_ids": ring["app_ids"], "verdict": "victims" if ring["type"] == "account_takeover_ekyc_bypass" else "fraud_ring"})
    expected_cases += [{"app_ids": item["app_ids"], "verdict": "victims"} for item in truth["victims"]]
    expected_cases += [{"app_ids": truth["benign_groups"][0]["app_ids"], "verdict": "benign"}]
    for index, item in enumerate(expected_cases):
        groups.append({"cluster_id": f"evaluation-{index}", "app_ids": item["app_ids"]})
        item["cluster_id"] = f"evaluation-{index}"
    return groups, expected_cases


async def evaluate_triage(service, database, truth):
    groups, expected_cases = evaluation_groups(truth)
    triage_cases = []
    try:
        _, decisions = await triage_groups(service, database, groups)
        actual = {item.cluster_id: item.decision for item in decisions}
        for group, expected in zip(groups, expected_cases):
            wanted = "skip" if expected["verdict"] == "benign" else "investigate"
            triage_cases.append({"cluster_id": group["cluster_id"], "expected": wanted,
                                 "actual": actual[group["cluster_id"]], "correct": actual[group["cluster_id"]] == wanted})
    except Exception as error:
        triage_cases = [{"expected": "skip" if item["verdict"] == "benign" else "investigate",
                         "correct": False, "error": type(error).__name__} for item in expected_cases]
    return triage_cases, expected_cases
