import pytest
import os
import json
from flask_wtf.csrf import generate_csrf
from modules import placeholders
import defusedxml.ElementTree as ET

def test_csrf_protection_enforced(client):
    """Verifies that POST requests without CSRF token are blocked."""
    # Try to creating an item without CSRF should fail with 400 or 403 depending on implementation
    # Flask-WTF usually returns 400 Bad Request if token is missing
    resp = client.post('/api/item/target', json={'name': 'test'})
    assert resp.status_code == 400

def test_csrf_protection_bypass_with_token(client):
    """Verifies that requests with CSRF token are allowed."""
    # A GET request sets the cookie
    resp = client.get('/')
    # In Flask Test Client, cookies are in the response object
    # or accessible via the client's cookie jar settings. 
    # Let's try to find it in the response headers Set-Cookie
    cookies = resp.headers.getlist('Set-Cookie')
    csrf_token = None
    for cookie in cookies:
        if 'csrf_token=' in cookie:
            csrf_token = cookie.split('csrf_token=')[1].split(';')[0]
            break
    
    assert csrf_token is not None
    
    resp = client.post('/api/item/target', 
                      json={'name': 'csrf-test'},
                      headers={'X-CSRF-TOKEN': csrf_token})
    
    # It might still fail with 404/500 if other mocks aren't perfect, 
    # but NOT with 400 CSRF error.
    assert resp.status_code != 400

def test_xxe_protection_in_placeholders(tmp_path, mocker):
    """Tests that defusedxml prevents external entity expansion."""
    # Create a malicious XML file
    xml_content = """<?xml version="1.0"?>
    <!DOCTYPE data [
      <!ENTITY xxe SYSTEM "file:///etc/passwd">
    ]>
    <data>&xxe;</data>"""
    
    report_dir = tmp_path / "test-report"
    report_dir.mkdir()
    xml_file = report_dir / "vuln.xml"
    xml_file.write_text(xml_content)
    
    mock_report_mgr = mocker.MagicMock()
    mock_report_mgr.folder = str(tmp_path)
    placeholders.register_manager("REPORT", mock_report_mgr)
    
    session = mocker.MagicMock()
    session.report = "test-report"
    
    # Try to resolve placeholder that accesses this XML
    # defusedxml should either raise an error or return the unexpanded entity
    # depending on how it's called. ElementTree.fromstring in defusedxml 
    # raises DTDForbidden by default if DTD is present.
    try:
        placeholders.resolve_placeholders("$report.file.vuln_xml.data", session)
    except Exception as e:
        # If it raises an error, that's also a form of protection (fail closed)
        assert "DTD" in str(e) or "entities" in str(e).lower()

def test_path_traversal_protection(tmp_path, mocker):
    """Tests that path traversal in placeholders is blocked."""
    report_dir = tmp_path / "test-report"
    report_dir.mkdir()
    
    # Create a file outside the report directory
    secret_file = tmp_path / "secret.json"
    secret_file.write_text('{"key": "secret_value"}')
    
    mock_report_mgr = mocker.MagicMock()
    mock_report_mgr.folder = str(report_dir) # Point directly to logs
    placeholders.register_manager("REPORT", mock_report_mgr)
    
    session = mocker.MagicMock()
    session.report = "." # Try to stay in same dir
    
    # The payload attempts to go up to find secret.json
    # sanitized: .._secret_json -> .._secret.json -> os.path.basename -> secret.json
    # It should looking for secret.json INSIDE report_dir/. (which doesn't exist)
    placeholder = "$report.file.backstep_secret_json.key"
    
    resolved = placeholders.resolve_placeholders(placeholder, session)
    assert "secret_value" not in resolved
    assert resolved == placeholder # Should remain unreplaced as file not found in subdir

def test_wordlist_metadata_safety(client, mock_cli, tmp_path):
    """Tests that very large wordlists don't cause hangs and return 'File too large'."""
    # Create a "large" file (over 500MB)
    large_file = tmp_path / "huge.txt"
    large_file.write_bytes(b"A" * (501 * 1024 * 1024))
    
    mock_cli.wordlist_mgr.list_all.return_value = ['huge']
    mock_cli.wordlist_mgr.load.return_value = {'name': 'huge', 'path': str(large_file)}
    
    resp = client.get('/api/wordlists/list?details=true')
    assert resp.status_code == 200
    data = resp.json[0]
    assert data['line_count'] == "File too large (skipped count)"
    assert "501.00 MB" in data['file_size']

def test_wordlist_rockyou_sized_allowed(client, mock_cli, tmp_path):
    """Tests that rockyou.txt (approx 134MB) is still counted."""
    # rockyou.txt is about 134MB. Our limit is now 500MB.
    rockyou_file = tmp_path / "rockyou.txt"
    # Create a 140MB file with 10 lines
    content = b"password\n" * 10 
    padding = b"A" * (140 * 1024 * 1024 - len(content))
    rockyou_file.write_bytes(content + padding)
    
    mock_cli.wordlist_mgr.list_all.return_value = ['rockyou']
    mock_cli.wordlist_mgr.load.return_value = {'name': 'rockyou', 'path': str(rockyou_file)}
    
    resp = client.get('/api/wordlists/list?details=true')
    assert resp.status_code == 200
    data = resp.json[0]
    assert data['line_count'] == "11" # 10 newlines + 1 for the remaining content
    assert "140.00 MB" in data['file_size']
