def select_reports(truth, limit):
    groups = {}
    for identifier, record in truth["reports"].items():
        groups.setdefault(record["label"], []).append(identifier)
    selected = sorted(groups.pop("scam_injection", []))[:min(5, limit)]
    while len(selected) < limit and any(groups.values()):
        for label in sorted(groups):
            if groups[label] and len(selected) < limit:
                selected.append(groups[label].pop(0))
    return selected


def accuracy(cases):
    scored = [item for item in cases if item.get("expected") is not None]
    return {"evaluated": len(scored), "correct": sum(item.get("correct", False) for item in scored),
            "accuracy": sum(item.get("correct", False) for item in scored) / len(scored) if scored else None}
