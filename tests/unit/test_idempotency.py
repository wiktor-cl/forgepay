from forgepay_security.fingerprints import canonical_fingerprint


def test_fingerprint_is_order_independent() -> None:
    left = canonical_fingerprint({"amount_minor": 1000, "currency": "PLN"})
    right = canonical_fingerprint({"currency": "PLN", "amount_minor": 1000})
    assert left == right


def test_fingerprint_changes_with_payload() -> None:
    assert canonical_fingerprint({"amount_minor": 1000}) != canonical_fingerprint(
        {"amount_minor": 2000}
    )
