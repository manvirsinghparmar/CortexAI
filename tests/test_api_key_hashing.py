from utils.api_key_utils import compute_api_key_hash, generate_api_key


def test_compute_api_key_hash_is_stable_and_hex():
    raw = "dev-key-1"
    h1 = compute_api_key_hash(raw)
    h2 = compute_api_key_hash(raw)

    assert h1 == h2
    assert len(h1) == 64
    assert all(ch in "0123456789abcdef" for ch in h1)


def test_generate_api_key_uses_prefix():
    key = generate_api_key(prefix="cortex")
    assert key.startswith("cortex_")
    assert len(key) > len("cortex_") + 20
