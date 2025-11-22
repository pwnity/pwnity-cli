# modules/functions.py
import base64
import urllib.parse
import hashlib
import html
import codecs
import re

def b64encode_str(s: str) -> str:
    """Base64 encodes a string."""
    return base64.b64encode(s.encode('utf-8')).decode('utf-8')

def b64decode_str(s: str) -> str:
    """Base64 decodes a string."""
    return base64.b64decode(s.encode('utf-8')).decode('utf-8')

def urlencode_str(s: str) -> str:
    """URL-encodes a string."""
    return urllib.parse.quote(s, safe='')

def urldecode_str(s: str) -> str:
    """URL-decodes a string."""
    return urllib.parse.unquote(s)

def hexencode_str(s: str) -> str:
    """Hex-encodes a string."""
    return s.encode('utf-8').hex()

def hexdecode_str(s: str) -> str:
    """Hex-decodes a string."""
    return bytes.fromhex(s).decode('utf-8')

def md5_str(s: str) -> str:
    """Calculates the MD5 hash of a string."""
    return hashlib.md5(s.encode('utf-8')).hexdigest()

def sha1_str(s: str) -> str:
    """Calculates the SHA1 hash of a string."""
    return hashlib.sha1(s.encode('utf-8')).hexdigest()

def sha256_str(s: str) -> str:
    """Calculates the SHA256 hash of a string."""
    return hashlib.sha256(s.encode('utf-8')).hexdigest()

def sha512_str(s: str) -> str:
    """Calculates the SHA512 hash of a string."""
    return hashlib.sha512(s.encode('utf-8')).hexdigest()

def html_encode_str(s: str) -> str:
    """HTML-encodes a string."""
    return html.escape(s)

def html_decode_str(s: str) -> str:
    """HTML-decodes a string."""
    return html.unescape(s)
    
HASH_TYPES = [
    # Hashes identified primarily by length and hex characters
    {'name': 'MD5', 'length': 32, 'regex': re.compile(r'^[a-f0-9]{32}$', re.IGNORECASE)},
    {'name': 'NTLM', 'length': 32, 'regex': re.compile(r'^[a-f0-9]{32}$', re.IGNORECASE)},
    {'name': 'SHA1', 'length': 40, 'regex': re.compile(r'^[a-f0-9]{40}$', re.IGNORECASE)},
    {'name': 'SHA256', 'length': 64, 'regex': re.compile(r'^[a-f0-9]{64}$', re.IGNORECASE)},
    {'name': 'SHA512', 'length': 128, 'regex': re.compile(r'^[a-f0-9]{128}$', re.IGNORECASE)},
    
    # Hashes identified by specific prefixes/formats, length is less important or variable
    {'name': 'MySQL5 / SHA1(SHA1(pass))', 'length': None, 'regex': re.compile(r'^\*[a-f0-9]{40}$', re.IGNORECASE)},
    {'name': 'bcrypt', 'length': None, 'regex': re.compile(r'^\$2[aby]\$\d{2}\$.{53}$', re.IGNORECASE)},
    {'name': 'md5crypt', 'length': None, 'regex': re.compile(r'^\$1\$.+$', re.IGNORECASE)},
    {'name': 'sha256crypt', 'length': None, 'regex': re.compile(r'^\$5\$.+$', re.IGNORECASE)},
    {'name': 'sha512crypt', 'length': None, 'regex': re.compile(r'^\$6\$.+$', re.IGNORECASE)},
]

def identify_hash(s: str) -> list[str]:
    """Identifies the possible hash type(s) of a string based on length and format."""
    s = s.strip()
    s_len = len(s)
    possible_types = []
    for hash_info in HASH_TYPES:
        # If length is specified, it must match. If not, we only check regex.
        # This is efficient for fixed-length hashes.
        if hash_info['length'] is None or hash_info['length'] == s_len:
            if hash_info['regex'].match(s):
                possible_types.append(hash_info['name'])
    return possible_types

def list_hash_types() -> list[str]:
    """Returns a sorted list of all identifiable hash type names."""
    # Use a set to get unique names, as MD5 and NTLM are duplicated by design
    return sorted(list(set(h['name'] for h in HASH_TYPES)))

FUNCTION_REGISTRY = {
    'b64encode': b64encode_str,
    'b64decode': b64decode_str,
    'urlencode': urlencode_str,
    'urldecode': urldecode_str,
    'hexencode': hexencode_str,
    'hexdecode': hexdecode_str,
    'md5': md5_str,
    'sha1': sha1_str,
    'sha256': sha256_str,
    'sha512': sha512_str,
    'html_encode': html_encode_str,
    'html_decode': html_decode_str,
}

def list_all():
    return sorted(list(FUNCTION_REGISTRY.keys()))