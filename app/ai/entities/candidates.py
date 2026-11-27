import hashlib
import re
import unicodedata
from collections import defaultdict

from .schemas import EntityPair, EntityRecord


def entity_record(row):
    token = hashlib.sha256(row["device_id"].encode()).hexdigest()[:20] if row.get("device_id") else None
    return EntityRecord(app_id=row["app_id"], full_name=row["full_name"], dob=row["dob"],
                        address=row["address"], device_token=token)


def entity_candidates(records, *, limit=100):
    if not 1 <= limit <= 1000:
        raise ValueError("Candidate limit must be 1..1000")
    blocks, seen, result = defaultdict(list), set(), []

    def tokens(text):
        text = text.casefold().replace("đ", "d")
        text = "".join(char for char in unicodedata.normalize("NFD", text) if not unicodedata.combining(char))
        return re.findall(r"[a-z0-9]+", text)

    for row in records:
        record = entity_record(row)
        words = tokens(record.full_name)
        keys = [(record.dob, "device", record.device_token)] if record.device_token else []
        if words:
            keys.append((record.dob, "name", words[0], words[-1]))
        numbers = re.findall(r"\d+", record.address)
        if numbers:
            keys.append((record.dob, "address", numbers[0]))
        for key in keys:
            for previous in blocks[key][:20]:
                if key[1] == "address":
                    left, right = set(tokens(previous.address)), set(tokens(record.address))
                    if len(left & right) / max(len(left), len(right), 1) < 0.6:
                        continue
                pair_key = tuple(sorted((previous.app_id, record.app_id)))
                if pair_key in seen:
                    continue
                seen.add(pair_key)
                result.append(EntityPair(pair_id="pair-" + hashlib.sha256("|".join(pair_key).encode()).hexdigest()[:16],
                                         left=previous, right=record))
                if len(result) >= limit:
                    return result
            blocks[key].append(record)
    return result
