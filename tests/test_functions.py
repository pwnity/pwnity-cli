# tests/test_functions.py
import pytest
from modules import functions as pwn_functions

# --- Testdaten ---
PLAIN_TEXT = "hello world! 123"
B64_ENCODED = "aGVsbG8gd29ybGQhIDEyMw=="
URL_ENCODED = "hello%20world%21%20123"
HEX_ENCODED = "68656c6c6f20776f726c642120313233"
HTML_ENCODED = "hello world! 123" # html.escape only escapes <, >, &
HTML_SPECIAL_ENCODED = "&lt;script&gt;alert(1)&lt;/script&gt;"
HTML_SPECIAL_PLAIN = "<script>alert(1)</script>"

MD5_HASH = "f78e68164a1dff699609560171ecf6fb"
SHA1_HASH = "03b08b94b550e520bdb7d86315b921208d4380c5"
SHA256_HASH = "97a4801932c60bf791b0b71111e485ab1334e12ba73429faad399aafaa93f3c5"
SHA512_HASH = "ecffe43cf00cfa13685e85862bede0a217bb7e7cf625df78a5076ff6e3e97814017f25e15b6f9d5296eda8c4271688453fdc1f217885a79bae016a65dd8962f5"

# --- Tests für Kodierungs- und Dekodierungsfunktionen ---

def test_base64_encoding_decoding():
    assert pwn_functions.b64encode_str(PLAIN_TEXT) == B64_ENCODED
    assert pwn_functions.b64decode_str(B64_ENCODED) == PLAIN_TEXT

def test_url_encoding_decoding():
    assert pwn_functions.urlencode_str(PLAIN_TEXT) == URL_ENCODED
    assert pwn_functions.urldecode_str(URL_ENCODED) == PLAIN_TEXT

def test_hex_encoding_decoding():
    assert pwn_functions.hexencode_str(PLAIN_TEXT) == HEX_ENCODED
    assert pwn_functions.hexdecode_str(HEX_ENCODED) == PLAIN_TEXT

def test_html_encoding_decoding():
    assert pwn_functions.html_encode_str(HTML_SPECIAL_PLAIN) == HTML_SPECIAL_ENCODED
    assert pwn_functions.html_decode_str(HTML_SPECIAL_ENCODED) == HTML_SPECIAL_PLAIN

# --- Tests für Hashing-Funktionen ---

def test_hashing_functions():
    assert pwn_functions.md5_str(PLAIN_TEXT) == MD5_HASH
    assert pwn_functions.sha1_str(PLAIN_TEXT) == SHA1_HASH
    assert pwn_functions.sha256_str(PLAIN_TEXT) == SHA256_HASH
    assert pwn_functions.sha512_str(PLAIN_TEXT) == SHA512_HASH

# --- Tests für die Hash-Identifikation ---

@pytest.mark.parametrize("hash_input, expected_types", [
    ("d3486ae9136e7856bc42212385ea797094475802", ["SHA1"]),
    ("4d9391263335328249febf36ae13a0c0", ["MD5", "NTLM"]),
    ("7509e5bda0c762d2bac7f90d758b5b2263fa01ccbc542ab5e3df163be08e6ca9", ["SHA256"]),
    ("861844d6704e8573fec34d967e20bcfef3d424cf48be04e6dc57aa79cc5982d46c345370eb3476d4deda621de1f4ca981029e7b1728c5b190424b73574880d25", ["SHA512"]),
    ("$2a$12$Y3.xY.a.pD.xY.a.pD.xY.a.pD.xY.a.pD.xY.a.pD.xY.a.pD.xY", ["bcrypt"]),
    ("$1$saltsalt$r1hB8FzKj.Pj.B8FzKj.P0", ["md5crypt"]),
    ("$5$saltsalt$r1hB8FzKj.Pj.B8FzKj.P0", ["sha256crypt"]),
    ("$6$saltsalt$r1hB8FzKj.Pj.B8FzKj.P0", ["sha512crypt"]),
    ("*2470C0C06DEE42FD1618BB99005ADCA2EC9D1E19", ["MySQL5 / SHA1(SHA1(pass))"]),
    ("not a hash", []),
])
def test_identify_hash(hash_input, expected_types):
    """
    Testet die `identify_hash`-Funktion mit verschiedenen Hash-Formaten.
    """
    result = pwn_functions.identify_hash(hash_input)
    # Wir sortieren beide Listen, um die Reihenfolge zu ignorieren
    assert sorted(result) == sorted(expected_types)

def test_list_hash_types():
    """
    Testet, ob `list_hash_types` eine sortierte Liste einzigartiger Namen zurückgibt.
    """
    types = pwn_functions.list_hash_types()
    assert isinstance(types, list)
    assert "MD5" in types
    assert "NTLM" in types
    # MD5 und NTLM haben denselben Regex, aber beide Namen sollten in der Liste sein.
    # Die Funktion verwendet ein Set, um Duplikate im Code zu entfernen, aber die Namen sind einzigartig.
    assert len(types) == len(set(h['name'] for h in pwn_functions.HASH_TYPES))
    # Überprüfe, ob die Liste sortiert ist
    assert types == sorted(types)

# --- Tests für die Funktions-Registry ---

def test_list_all_registered_functions():
    """
    Testet, ob list_all() alle Schlüssel aus dem FUNCTION_REGISTRY zurückgibt und sie sortiert sind.
    """
    all_funcs = pwn_functions.list_all()
    registry_keys = sorted(list(pwn_functions.FUNCTION_REGISTRY.keys()))
    assert all_funcs == registry_keys

def test_function_registry_integrity():
    """
    Stellt sicher, dass jeder Eintrag im FUNCTION_REGISTRY auf eine
    existierende, aufrufbare Funktion im Modul verweist.
    """
    for name, func in pwn_functions.FUNCTION_REGISTRY.items():
        assert callable(func), f"Registry entry '{name}' points to a non-callable object."
        assert hasattr(pwn_functions, func.__name__), f"Function '{func.__name__}' for key '{name}' not found in module."

# --- Tests für Edge Cases ---

def test_encoding_with_empty_string():
    """Tests that encoding an empty string results in an empty string."""
    assert pwn_functions.b64encode_str("") == ""
    assert pwn_functions.urlencode_str("") == ""
    assert pwn_functions.hexencode_str("") == ""
    assert pwn_functions.html_encode_str("") == ""

def test_decoding_with_empty_string():
    """Tests that decoding an empty string results in an empty string."""
    assert pwn_functions.b64decode_str("") == ""
    assert pwn_functions.urldecode_str("") == ""
    assert pwn_functions.hexdecode_str("") == ""
    assert pwn_functions.html_decode_str("") == ""

def test_decoding_invalid_input():
    """Tests that decoding functions handle invalid input by raising errors."""
    import binascii
    # Invalid Base64 should raise binascii.Error
    with pytest.raises(binascii.Error):
        pwn_functions.b64decode_str("this is not base64")
    # Invalid Hex (odd length or non-hex chars) should raise ValueError
    with pytest.raises(ValueError):
        pwn_functions.hexdecode_str("abc") # odd length
    with pytest.raises(ValueError):
        pwn_functions.hexdecode_str("gg") # non-hex chars