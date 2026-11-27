def _same_ids(actual, expected):
    if len(actual) != len(set(actual)) or set(actual) != set(expected):
        raise ValueError("Output must contain each input ID exactly once")
