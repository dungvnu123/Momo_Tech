def entity_cases():
    def record(identifier, name, dob, address, device):
        return {"app_id": identifier, "full_name": name, "dob": dob, "address": address, "device_token": device}

    cases = [
        ("same", record("E01", "Nguyễn Văn An", "1990-01-02", "Số 12 ngõ 5 Lê Lợi, phường Bến Thành, TP Hồ Chí Minh", "d1"),
         record("E02", "Ng. Văn An", "1990-01-02", "12/5 Le Loi, P. Ben Thanh, TP Ho Chi Minh", "d1")),
        ("same_household", record("E03", "Trần Minh Bình", "1988-05-03", "15 Lê Duẩn, phường Hải Châu, Đà Nẵng", "d2"),
         record("E04", "Nguyễn Thu Hà", "1990-09-12", "15 Lê Duẩn, phường Hải Châu, Đà Nẵng", "d2")),
        ("different", record("E05", "Lê Quốc Nam", "1995-08-15", "20 Láng Hạ, Hà Nội", "d3"),
         record("E06", "Phạm Thị Hoa", "1995-08-15", "81 Lê Lợi, Đà Nẵng", "d4")),
        ("same", record("E07", "Đặng Thị Mai", "1992-07-04", "12/5 Nguyễn Trãi, Hà Nội", "d5"),
         record("E08", "DANG THI MAI", "1992-07-04", "Số 12 ngõ 5 Nguyễn Trãi, Hà Nội", "d5")),
    ]
    return [{"pair": {"pair_id": f"pair-{index}", "left": left, "right": right}, "expected": expected}
            for index, (expected, left, right) in enumerate(cases)]


def transfer_cases():
    base = {"loan_amount": 10000000, "transfer_amount": 9000000, "minutes_after_disbursal": 20,
            "recipient_name_matches": False, "recipient_in_contacts": False,
            "prior_transfers_to_recipient": 0}
    return [
        {"input": {**base, "recipient_name_matches": True, "recipient_in_contacts": True,
                   "prior_transfers_to_recipient": 10}, "expected": "allow"},
        {"input": base, "expected": "warn"},
        {"input": {**base, "recipient_in_contacts": True, "contact_saved_minutes_ago": 5}, "expected": "warn"},
        {"input": {**base, "simo_flag": True}, "expected": "hold"},
    ]
