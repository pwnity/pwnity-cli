#
# # Project: https://github.com/pwnity/pwnity-cli
# # Copyright 2025 pwnity
# #
# # Licensed under the Apache License, Version 2.0 (the "License");
# # you may not use this file except in compliance with the License.
# # You may obtain a copy of the License at
# #
# #     http://www.apache.org/licenses/LICENSE-2.0
# #
# # Unless required by applicable law or agreed to in writing, software
# # distributed under the License is distributed on an "AS IS" BASIS,
# # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# # See the License for the specific language governing permissions and
# # limitations under the License.#

# tests/test_recon.py
import pytest
import json
import socket
from modules.recon import ReconService
from modules.services import log
from datetime import datetime

@pytest.fixture
def recon_service():
    """
    Provides a ReconService instance initialized with basic target data.
    """
    # Mock the dependencies check in the constructor
    # We assume they are installed for these tests.
    target_data = {
        "hostname": "example.com",
        "ip": "93.184.216.34",
        "domain": "example.com"
    }
    return ReconService(target_data)

def test_gather_dns(recon_service, monkeypatch, mocker):
    """
    Tests the gather_dns method by mocking all external DNS and socket calls.
    """
    # --- Mocks for dns.resolver ---
    class MockAnswer:
        def __init__(self, records):
            self._records = records
        def __iter__(self):
            return iter(self._records)

    class MockRecord:
        def __init__(self, text, target=None):
            self.text = text
            self.target = target
        def to_text(self):
            return self.text

    def mock_resolve(hostname, record_type):
        if record_type == 'AAAA':
            return MockAnswer([MockRecord("2606:2800:220:1:248:1893:25c8:1946")])
        if record_type == 'TXT':
            return MockAnswer([MockRecord('"v=spf1 -all"')])
        if record_type == 'NS':
            return MockAnswer([MockRecord(None, target="a.iana-servers.net.")])
        if record_type == 'MX':
            # MX records have preference and exchange attributes
            mx_rec = mocker.MagicMock()
            mx_rec.preference = 10
            mx_rec.exchange = "mail.example.com."
            return MockAnswer([mx_rec])
        # Simulate no CNAME record found
        import dns.resolver
        raise dns.resolver.NoAnswer

    monkeypatch.setattr("dns.resolver.resolve", mock_resolve)

    # --- Mocks for socket ---
    monkeypatch.setattr("socket.gethostbyname", lambda host: "93.184.216.34")
    monkeypatch.setattr("socket.gethostbyaddr", lambda ip: ("example.com", [], [ip]))

    # --- Execute and Assert ---
    updates = recon_service.gather_dns()

    assert updates['ip'] == "93.184.216.34"
    assert updates['ipv6_addresses'] == ["2606:2800:220:1:248:1893:25c8:1946"]
    assert updates['txt_records'] == ["v=spf1 -all"]
    assert updates['name_servers'] == ["a.iana-servers.net."]
    assert updates['mx_records'] == ["10 mail.example.com."]
    assert updates['ptr_record'] == "example.com"

def test_gather_whois(recon_service, monkeypatch):
    """
    Tests the gather_whois method by mocking the whois library.
    """
    class MockWhoisResult(dict):
        def __init__(self):
            super().__init__({
                "domain_name": "EXAMPLE.COM",
                "registrar": "Test Registrar",
                "creation_date": datetime(2020, 1, 1),
                "emails": ["abuse@example.com"]
            })
        def __getattr__(self, name):
            return self.get(name)

    monkeypatch.setattr("modules.recon.whois.whois", lambda domain: MockWhoisResult())

    updates = recon_service.gather_whois()

    assert "whois_info" in updates
    assert updates["whois_info"]["registrar"] == "Test Registrar"
    # Check that the datetime object was correctly serialized to an ISO string
    assert updates["whois_info"]["creation_date"] == "2020-01-01T00:00:00"

def test_gather_geo(recon_service, mocker):
    """
    Tests the gather_geo method by mocking http.client to simulate an API response.
    """
    mock_response = mocker.MagicMock()
    mock_response.status = 200
    # The API returns a JSON string as bytes
    api_data = {
        "status": "success", "query": "93.184.216.34", "country": "United States",
        "city": "Norwell", "lat": 42.15, "lon": -70.8, "isp": "Zscaler",
        "org": "IANA", "as": "AS396982 RESERVED-AS"
    }
    mock_response.read.return_value = json.dumps(api_data).encode('utf-8')

    mock_conn = mocker.MagicMock()
    mock_conn.getresponse.return_value = mock_response

    mocker.patch("http.client.HTTPConnection", return_value=mock_conn)

    updates = recon_service.gather_geo()

    assert "geo_intel" in updates
    assert updates["geo_intel"]["country"] == "United States"
    assert updates["geo_intel"]["isp"] == "Zscaler"

def test_gather_http(recon_service, mocker):
    """
    Tests the gather_http method by mocking http.client and ssl.
    """
    # --- Mock for HTTP Headers ---
    mock_http_response = mocker.MagicMock()
    mock_http_response.status = 200
    mock_http_response.getheaders.return_value = [("Server", "Test-Server/1.0"), ("Content-Type", "text/html")]

    mock_http_conn = mocker.MagicMock()
    mock_http_conn.getresponse.return_value = mock_http_response
    mocker.patch("http.client.HTTPConnection", return_value=mock_http_conn)
    mocker.patch("http.client.HTTPSConnection", return_value=mock_http_conn)

    # --- Mock for SSL Certificate ---
    mock_ssl_socket = mocker.MagicMock()
    mock_ssl_socket.getpeercert.return_value = {
        "subject": ((('commonName', 'example.com'),),),
        "issuer": ((('commonName', "Let's Encrypt"),),),
        "notBefore": "Jan  1 00:00:00 2023 GMT",
        "notAfter": "Apr  1 00:00:00 2023 GMT",
        "subjectAltName": (('DNS', 'example.com'), ('DNS', 'www.example.com'))
    }
    # Mock the context manager for `with context.wrap_socket(...)`
    mock_ssl_context = mocker.patch("ssl.create_default_context").return_value
    mock_ssl_context.wrap_socket.return_value.__enter__.return_value = mock_ssl_socket

    # Mock the socket connection itself
    mocker.patch("socket.create_connection")

    # --- Execute and Assert ---
    # We need to set the protocol to https to trigger the SSL check
    recon_service.target['protocol'] = 'https'
    updates = recon_service.gather_http()

    assert "http_headers" in updates
    assert updates["http_headers"]["Server"] == "Test-Server/1.0"

    assert "ssl_info" in updates
    assert updates["ssl_info"]["subject"]["commonName"] == "example.com"
    assert "www.example.com" in updates["ssl_info"]["sans"]

def test_gather_dns_with_exceptions(recon_service, monkeypatch):
    """
    Tests that gather_dns handles exceptions from network calls gracefully
    and returns an empty dictionary without crashing.
    """
    # Mock all resolver calls to raise an exception
    import dns.resolver
    def raise_error(*args, **kwargs):
        raise dns.resolver.LifetimeTimeout("DNS query timed out")

    # This is a trick to make a lambda raise an exception
    def raise_gaierror(host):
        raise socket.gaierror

    monkeypatch.setattr("dns.resolver.resolve", raise_error)
    monkeypatch.setattr("socket.gethostbyname", raise_gaierror)
    monkeypatch.setattr("socket.gethostbyaddr", lambda ip: (_ for _ in ()).throw(socket.herror))

    # Execute and Assert
    updates = recon_service.gather_dns()

    # The method should catch all exceptions and return an empty dict
    assert updates == {}

def test_gather_whois_failure(recon_service, monkeypatch):
    """
    Tests that gather_whois handles exceptions from the whois library gracefully.
    """
    def raise_whois_error(domain):
        raise Exception("Simulated WHOIS failure")

    monkeypatch.setattr("modules.recon.whois.whois", raise_whois_error)

    updates = recon_service.gather_whois()
    assert updates == {}

def test_gather_geo_api_error(recon_service, mocker):
    """
    Tests that gather_geo handles non-200 responses from the API gracefully.
    """
    mock_response = mocker.MagicMock()
    mock_response.status = 500 # Simulate a server error
    mock_conn = mocker.MagicMock()
    mock_conn.getresponse.return_value = mock_response
    mocker.patch("http.client.HTTPConnection", return_value=mock_conn)

    updates = recon_service.gather_geo()
    assert updates == {}

def test_recon_service_init_fails_without_deps(monkeypatch):
    """
    Tests that the ReconService constructor raises an ImportError if
    dependencies are missing.
    """
    # Simulate that the 'dns' library was not imported
    monkeypatch.setattr("modules.recon.dns", None)

    with pytest.raises(ImportError):
        ReconService(target_data={"hostname": "example.com"})