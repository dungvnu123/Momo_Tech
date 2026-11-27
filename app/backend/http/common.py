import json


def times_reported(tools, ids, as_of="9999"):
    ids = set(ids)
    n = 0
    for r in tools.q("SELECT analysis FROM reports WHERE reported_at <= ?", as_of):
        ind = json.loads(r["analysis"])["indicators"]
        n += bool(ids & set(ind["accounts"] + ind["phones"]))
    return n


def alert_row(r):
    r = dict(r)
    r["signals"], r["app_ids"] = json.loads(r["signals"]), json.loads(r["app_ids"])
    r["conf"] = r["case_conf"] if r["case_conf"] is not None else r["confidence"]
    return r
