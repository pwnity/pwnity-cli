# tests/test_target_manager.py
import pytest
from modules.managers.target_manager import TargetManager
from modules.services import config, log

import urllib.parse # Import here to access uses_netloc
@pytest.fixture
def target_manager(tmp_path, monkeypatch):
    """Stellt einen sauberen TargetManager bereit, der in ein temporäres Verzeichnis schreibt."""
    targets_dir = tmp_path / "targets"
    targets_dir.mkdir()

    # Leite den Manager auf das temporäre Verzeichnis um
    original_get_parameter = config.get_parameter
    def mock_get_parameter(section, key, fallback=None):
        if section == "DIRS" and key == "TARGETS":
            return str(targets_dir)
        return original_get_parameter(section, key, fallback)
    monkeypatch.setattr(config, 'get_parameter', mock_get_parameter)

    # Logger stummschalten
    import logging
    monkeypatch.setattr(log, 'log_value', logging.CRITICAL + 1)

    # Ensure custom schemes are recognized by urlparse for the duration of the test
    monkeypatch.setattr(urllib.parse, 'uses_netloc', 
                        urllib.parse.uses_netloc + ['ssh', 'smb', 'telnet', 'rdp', 'vnc'])

    return TargetManager()

def test_target_create_and_exists(target_manager):
    """Testet, ob ein Target korrekt erstellt wird und existiert."""
    target_name = "test-server"
    assert target_manager.exists(target_name) is False
    
    target_manager.create(target_name)
    
    assert target_manager.exists(target_name) is True
    target_data = target_manager.load(target_name)
    assert target_data is not None
    assert target_data.get("name") == target_name

def test_update_from_url_parsing(target_manager, monkeypatch):
    """
    Testet die Kernlogik: das Parsen einer URL und das automatische
    Befüllen der Target-Felder.
    """
    target_name = "example.com"
    target_manager.create(target_name)

    # Mocke externe Aufrufe, die während des Parsens stattfinden
    # 1. Mock für die DNS-Auflösung
    monkeypatch.setattr("socket.gethostbyname", lambda host: "93.184.216.34")
    
    # 2. Mock für die Domain-Analyse (tldextract)
    # Wir erstellen ein einfaches Objekt, das die erwarteten Attribute hat.
    class MockTldExtractResult:
        registered_domain = "example.com"
        domain = "example"
        suffix = "com"
        subdomain = "www"
    monkeypatch.setattr("modules.managers.target_manager.tldextract.extract", lambda url: MockTldExtractResult())

    # Führe die Update-Funktion aus
    url_to_parse = "https://www.example.com:8443/path/to/page?param1=val1&param2=val2"
    target_manager._parse_and_update_from_url(target_name, url_to_parse, cli=None)

    # Lade die aktualisierten Daten und überprüfe die Felder
    updated_data = target_manager.load(target_name)
    assert updated_data is not None
    assert updated_data.get("url") == url_to_parse
    assert updated_data.get("protocol") == "https"
    assert updated_data.get("hostname") == "www.example.com"
    assert updated_data.get("ip") == "93.184.216.34"
    assert updated_data.get("port") == "8443"
    assert updated_data.get("uri") == "/path/to/page"
    assert updated_data.get("domain") == "example.com"
    assert updated_data.get("subdomains") == ["www"]
    assert "param1=val1" in updated_data.get("query_params", [])

def test_update_from_url_with_auth_and_no_tldextract(target_manager, monkeypatch):
    """
    Testet das URL-Parsing mit Authentifizierungsdaten und simuliert,
    dass `tldextract` nicht verfügbar ist.
    """
    target_name = "localhost-test"
    target_manager.create(target_name)

    # Mocke externe Aufrufe
    monkeypatch.setattr("socket.gethostbyname", lambda host: "127.0.0.1")
    # Simuliere, dass tldextract nicht installiert ist
    monkeypatch.setattr("modules.managers.target_manager.tldextract", None)

    # Führe die Update-Funktion aus
    url_to_parse = "http://admin:secret123@localhost:8080/dashboard"
    target_manager._parse_and_update_from_url(target_name, url_to_parse, cli=None)

    # Lade die aktualisierten Daten und überprüfe die Felder
    updated_data = target_manager.load(target_name)
    assert updated_data is not None
    assert updated_data.get("username") == "admin"
    assert updated_data.get("password") == "secret123"
    assert updated_data.get("hostname") == "localhost"
    assert updated_data.get("ip") == "127.0.0.1"
    assert updated_data.get("port") == "8080"
    # Domain-Felder sollten nicht gesetzt sein
    assert "domain" not in updated_data
    assert "subdomains" not in updated_data

def test_gather_dns_info(target_manager, monkeypatch):
    """
    Testet die 'gather dns' Funktionalität, indem die 'dns.resolver' Bibliothek gemockt wird.
    """
    target_name = "test-dns.com"
    target_manager.create(target_name)
    target_manager.update(target_name, "hostname", "test-dns.com")

    # Mock für den DNS-Resolver
    class MockAnswer:
        def __init__(self, records):
            self._records = records
        def __iter__(self):
            return iter(self._records)

    class MockRecord:
        def __init__(self, text):
            # Store the raw text for the to_text() method
            self.text = text
        def to_text(self):
            return self.text # AAAA records return the IP directly, TXT records include quotes in their data

    def mock_resolve(hostname, record_type):
        if record_type == 'AAAA':
            return MockAnswer([MockRecord("2001:db8::1")])
        if record_type == 'TXT':
            return MockAnswer([MockRecord("v=spf1 include:_spf.google.com ~all")])
        # Simuliere, dass für andere Typen keine Antwort gefunden wird
        import dns.resolver
        raise dns.resolver.NoAnswer

    # --- FIX: Mock the forward DNS lookup as well to prevent a real network call ---
    monkeypatch.setattr("socket.gethostbyname", lambda host: "93.184.216.34")

    monkeypatch.setattr("dns.resolver.resolve", mock_resolve)
    # Mock für den Reverse-Lookup
    monkeypatch.setattr("socket.gethostbyaddr", lambda ip: ("server.test-dns.com", [], [ip]))

    # Führe die gather-Funktion aus
    from modules.recon import ReconService
    recon_service = ReconService(target_manager.load(target_name))
    dns_updates = recon_service.gather_dns()
    for key, value in dns_updates.items():
        target_manager.update(target_name, key, value)

    # Überprüfe die Ergebnisse
    updated_data = target_manager.load(target_name)
    assert "2001:db8::1" in updated_data.get("ipv6_addresses", [])
    assert "v=spf1 include:_spf.google.com ~all" in updated_data.get("txt_records", [])
    assert updated_data.get("ptr_record") == "server.test-dns.com"

def test_gather_command_fails_gracefully_if_deps_missing(target_manager, mocker):
    """
    Testet, ob der 'gather'-Befehl nicht abstürzt, wenn die ReconService-Abhängigkeiten
    (z.B. dnspython) nicht installiert sind.
    """
    target_name = "test-deps.com"
    target_manager.create(target_name)
    target_manager.update(target_name, "hostname", "test-deps.com")
    
    # Simuliere, dass die Instanziierung von ReconService einen ImportError auslöst.
    # Das ist das korrekte Verhalten, wenn die Abhängigkeiten fehlen.
    mocker.patch("modules.managers.target_manager.ReconService", side_effect=ImportError("Simulated dependency failure"))

    # Simuliere den Aufruf von `target gather test-deps.com all`
    args = type('Args', (), {
        'name': target_name,
        'type': 'all'
    })()

    # Der Aufruf sollte keine Exception auslösen und einfach zurückkehren.
    # Wir fangen die Ausgabe nicht ab, aber der Test schlägt fehl, wenn eine Exception auftritt.
    target_manager._cmd_gather(args, cli=None)

def test_gather_whois_info(target_manager, monkeypatch):
    """
    Testet die 'gather whois' Funktionalität, indem die 'whois' Bibliothek gemockt wird.
    """
    target_name = "test-whois.com"
    target_manager.create(target_name)
    target_manager.update(target_name, "domain", "test-whois.com") # whois uses the 'domain' field

    # Mock für die whois-Bibliothek
    class MockWhoisResult(dict):
        def __init__(self):
            from datetime import datetime
            super().__init__({
                "domain_name": "TEST-WHOIS.COM",
                "registrar": "Test Registrar Inc.",
                "creation_date": datetime(2020, 1, 1)
            })
        def __getattr__(self, name):
            return self.get(name)

    monkeypatch.setattr("modules.recon.whois.whois", lambda domain: MockWhoisResult())

    # Führe die gather-Funktion aus
    from modules.recon import ReconService
    recon_service = ReconService(target_manager.load(target_name))
    whois_updates = recon_service.gather_whois()
    for key, value in whois_updates.items():
        target_manager.update(target_name, key, value)

    # Überprüfe die Ergebnisse
    updated_data = target_manager.load(target_name)
    assert "whois_info" in updated_data
    assert updated_data["whois_info"]["registrar"] == "Test Registrar Inc."
    # Prüfe, ob das datetime-Objekt korrekt in einen ISO-String umgewandelt wurde
    assert updated_data["whois_info"]["creation_date"] == "2020-01-01T00:00:00"

def test_gather_http_info(target_manager, mocker):
    """
    Testet die 'gather http' Funktionalität, indem http.client und ssl gemockt werden.
    """
    target_name = "test-http.com"
    target_manager.create(target_name)
    target_manager.update(target_name, "hostname", "test-http.com")
    target_manager.update(target_name, "protocol", "https")
    target_manager.update(target_name, "port", 443)

    # Mock für die HTTP-Verbindung und SSL-Zertifikat
    mock_response = mocker.MagicMock()
    mock_response.status = 200
    mock_response.getheaders.return_value = [("Content-Type", "text/html"), ("Server", "TestServer/1.0")]

    mock_conn = mocker.MagicMock()
    mock_conn.getresponse.return_value = mock_response

    mocker.patch("http.client.HTTPSConnection", return_value=mock_conn)
    mocker.patch("ssl.create_default_context") # Verhindert den echten SSL-Kontext-Aufbau

    # Führe die gather-Funktion aus
    from modules.recon import ReconService
    recon_service = ReconService(target_manager.load(target_name))
    http_updates = recon_service.gather_http()
    for key, value in http_updates.items():
        target_manager.update(target_name, key, value)

    # Überprüfe die Ergebnisse
    updated_data = target_manager.load(target_name)
    assert "http_headers" in updated_data
    assert updated_data["http_headers"]["Server"] == "TestServer/1.0"
    # SSL-Info wird in diesem vereinfachten Test nicht gemockt, wir prüfen nur die Header

@pytest.mark.parametrize("target_data, expected_result", [
    ({"hostname": "localhost"}, True),
    ({"ip": "127.0.0.1"}, True),
    ({"ip": "192.168.1.1"}, True),
    ({"ip": "10.0.0.5"}, True),
    ({"ip": "172.16.31.254"}, True),
    ({"ip": "8.8.8.8"}, False),
    ({"hostname": "google.com", "ip": "142.250.185.142"}, False),
    ({"ip": "invalid-ip"}, False),
    ({}, False),
])
def test_is_local_target(target_manager, target_data, expected_result):
    """Testet die `_is_local_target` Logik mit verschiedenen IPs und Hostnames."""
    assert target_manager._is_local_target(target_data) == expected_result

def test_update_non_url_field(target_manager):
    """Testet, ob das Aktualisieren eines normalen Feldes (nicht 'url') funktioniert."""
    target_name = "simple-update"
    target_manager.create(target_name)

    # Simuliere den Aufruf von `target update simple-update custom_field some value`
    args = type('Args', (), {
        'name': target_name,
        'update_args': ['custom_field', 'some', 'value']
    })()
    target_manager._cmd_update(args, cli=None)

    data = target_manager.load(target_name)
    assert data.get("custom_field") == "some value"

def test_fork_domain_workflow(target_manager, monkeypatch, mocker):
    """Testet den `fork-domain` Befehl."""
    source_name = "sub.example.com"
    forked_name = "example.com"

    # Mocke die Netzwerkfunktionen, die von _parse_and_update_from_url aufgerufen werden
    monkeypatch.setattr("socket.gethostbyname", lambda host: "93.184.216.34")
    mock_tldextract = mocker.MagicMock()
    # Konfiguriere das Mock-Objekt so, dass es sich wie das Ergebnis von tldextract.extract verhält
    mock_tldextract.extract.return_value = type('DummyExtract', (), {
        'registered_domain': 'example.com', 'domain': 'example', 'suffix': 'com', 'subdomain': 'sub'
    })()
    monkeypatch.setattr("modules.managers.target_manager.tldextract", mock_tldextract)

    # 1. Erstelle das Quell-Target und fülle es mit URL-Daten
    target_manager.create(source_name)
    target_manager._parse_and_update_from_url(source_name, f"https://{source_name}", cli=None)

    # 2. Führe den Fork-Befehl aus
    args = type('Args', (), {'name': source_name})()
    target_manager._cmd_fork_domain(args, cli=None)

    # 3. Überprüfe, ob das neue Target erstellt wurde
    assert target_manager.exists(forked_name) is True
    forked_data = target_manager.load(forked_name)
    assert forked_data.get("hostname") == forked_name

def test_fork_domain_on_root_domain(target_manager, monkeypatch, mocker):
    """
    Testet, dass `fork-domain` nichts tut, wenn das Quell-Target bereits eine Hauptdomain ist.
    """
    source_name = "example.com"

    # Mocke die Netzwerkfunktionen
    monkeypatch.setattr("socket.gethostbyname", lambda host: "93.184.216.34")
    mock_tldextract = mocker.MagicMock()
    mock_tldextract.extract.return_value = type('DummyExtract', (), {'registered_domain': 'example.com', 'domain': 'example', 'suffix': 'com', 'subdomain': ''})()
    monkeypatch.setattr("modules.managers.target_manager.tldextract", mock_tldextract)

    target_manager.create(source_name)
    target_manager._parse_and_update_from_url(source_name, f"https://{source_name}", cli=None)

    args = type('Args', (), {'name': source_name})()
    target_manager._cmd_fork_domain(args, cli=None)

    assert len(target_manager.list_all()) == 1 # Es sollte kein neues Target erstellt worden sein

def test_add_findings_and_notes(target_manager):
    """Testet das Hinzufügen von Parser-Findings zum Target."""
    target_name = "target-with-findings"
    target_manager.create(target_name)

    findings = {
        "ip_addresses": ["192.168.1.1", "192.168.1.2"],
        "hostnames": ["server1.local"]
    }

    # Füge die Findings hinzu
    target_manager.add_findings(target_name, findings)
    data = target_manager.load(target_name)
    assert "192.168.1.2" in data["findings"]["ip_addresses"]
    assert "server1.local" in data["findings"]["hostnames"]

    # Füge die gleichen Findings erneut hinzu
    target_manager.add_findings(target_name, findings)
    data_after_second_add = target_manager.load(target_name)
    # Die Anzahl der Einträge sollte sich nicht geändert haben
    assert len(data_after_second_add["findings"]["ip_addresses"]) == 2
    assert len(data_after_second_add["findings"]["hostnames"]) == 1

    # Teste das Hinzufügen als Notizen
    target_manager.add_findings_as_notes(target_name, {"ports": ["80", "443"]})
    notes_data = target_manager.load(target_name)
    assert any("[Parser Finding][ports] 80" in note["text"] for note in notes_data["notes"])

    # Füge die gleichen Notizen erneut hinzu, es sollten keine Duplikate entstehen
    original_note_count = len(notes_data["notes"])
    target_manager.add_findings_as_notes(target_name, {"ports": ["80", "443"]})
    notes_data_after_second_add = target_manager.load(target_name)
    assert len(notes_data_after_second_add["notes"]) == original_note_count

@pytest.mark.parametrize("url, expected_ip, expected_port, expected_protocol, expected_hostname", [
    ("ftp://ftp.example.com", "10.0.0.1", "21", "ftp", "ftp.example.com"),
    ("ssh://user@ssh.example.com", "10.0.0.2", "22", "ssh", "ssh.example.com"),
    ("smb://fileserver/share", "10.0.0.3", "445", "smb", "fileserver"),
    ("telnet://192.168.1.50:2323", "192.168.1.50", "2323", "telnet", "192.168.1.50"),
])
def test_update_from_url_other_protocols(target_manager, monkeypatch, mocker, url, expected_ip, expected_port, expected_protocol, expected_hostname):
    """
    Testet, ob das URL-Parsing auch mit anderen Protokollen (FTP, SSH, SMB) korrekt funktioniert,
    inklusive der Ermittlung von Standard-Ports.
    """
    target_name = "protocol-test"
    target_manager.create(target_name)

    # Mocke die Netzwerkfunktionen, um den Test deterministisch zu machen
    def mock_gethostbyname(hostname):
        # Gib eine feste IP basierend auf dem Hostnamen zurück
        if hostname == "ftp.example.com": return "10.0.0.1"
        if hostname == "ssh.example.com": return "10.0.0.2"
        if hostname == "fileserver": return "10.0.0.3"
        return hostname # Fallback für IPs, die als Hostname übergeben werden

    def mock_getservbyname(service):
        # Gib Standard-Ports für unsere Testprotokolle zurück
        if service == 'ftp': return 21
        if service == 'ssh': return 22
        if service == 'smb': return 445 # Annahme, dass 'smb' zu Port 445 aufgelöst wird
        # Raise an error for any other service to make tests fail explicitly
        # if unexpected lookups occur.
        raise OSError(f"Service '{service}' not found")

    monkeypatch.setattr("socket.gethostbyname", mock_gethostbyname)
    monkeypatch.setattr("socket.getservbyname", mock_getservbyname)

    # --- FINAL FIX: Mock tldextract properly to avoid AttributeErrors ---
    # Instead of setting it to None, we mock the 'extract' function to return a dummy object.
    mock_tldextract = mocker.MagicMock()
    mock_tldextract.extract.return_value = type('DummyExtract', (), {'registered_domain': '', 'domain': '', 'suffix': '', 'subdomain': ''})()
    monkeypatch.setattr("modules.managers.target_manager.tldextract", mock_tldextract)

    # Führe die Update-Funktion aus
    target_manager._parse_and_update_from_url(target_name, url, cli=None)

    # Überprüfe die Ergebnisse
    data = target_manager.load(target_name)
    assert data.get("protocol") == expected_protocol
    assert data.get("hostname") == expected_hostname
    assert data.get("ip") == expected_ip
    assert data.get("port") == expected_port

def test_update_from_url_removes_old_fields(target_manager, monkeypatch):
    """
    Testet, ob beim Aktualisieren einer URL alte, nicht mehr zutreffende Felder
    (wie query_params) korrekt entfernt werden.
    """
    target_name = "field-removal-test"
    target_manager.create(target_name)

    # Mocke die Netzwerkfunktionen
    monkeypatch.setattr("socket.gethostbyname", lambda host: "1.1.1.1")
    monkeypatch.setattr("modules.managers.target_manager.tldextract", None)

    # 1. Setze eine URL mit Query-Parametern
    url_with_params = "http://example.com/page?a=1&b=2"
    target_manager._parse_and_update_from_url(target_name, url_with_params, cli=None)

    # Überprüfe, ob die Parameter vorhanden sind
    data_with_params = target_manager.load(target_name)
    assert "query_params" in data_with_params
    assert "query_values" in data_with_params

    # 2. Aktualisiere mit einer URL ohne Query-Parameter
    url_without_params = "http://example.com/otherpage"
    target_manager._parse_and_update_from_url(target_name, url_without_params, cli=None)

    # Überprüfe, ob die Parameter entfernt wurden
    data_without_params = target_manager.load(target_name)
    assert "query_params" not in data_without_params
    assert "query_values" not in data_without_params
    assert data_without_params.get("uri") == "/otherpage"
    assert data_without_params.get("url") == url_without_params

def test_target_copy(target_manager):
    """Tests copying a target entity."""
    source_name = "source"
    dest_name = "destination"
    target_manager.create(source_name)
    target_manager.update(source_name, "custom_field", "value123")

    # Perform the copy
    assert target_manager.copy(source_name, dest_name) is True

    # Verify source still exists and destination is created
    assert target_manager.exists(source_name) is True
    assert target_manager.exists(dest_name) is True

    # Verify content of the copied target
    dest_data = target_manager.load(dest_name)
    assert dest_data.get("name") == dest_name
    assert dest_data.get("custom_field") == "value123"

def test_target_export_logic(target_manager, mocker):
    """Tests the logic of the _cmd_export method for targets."""
    target_name = "export-test"
    target_manager.create(target_name)
    target_manager.update(target_name, "url", "http://test.com")
    target_manager.update(target_name, "custom", "my_value")
    target_manager.update(target_name, "whois_info", {"some": "data"}) # This should become a gather command

    mock_cli = mocker.MagicMock()
    captured_output = []
    mock_cli.poutput.side_effect = captured_output.append

    target_manager._cmd_export(type('Args', (), {'name': target_name})(), mock_cli)
    output = "\n".join(captured_output)

    assert "target add export-test" in output
    assert "target update export-test url http://test.com" in output
    assert "target gather export-test whois" in output
    assert "target update export-test custom 'my_value'" in output
    assert "target update export-test custom my_value" in output
    assert data_without_params.get("uri") == "/otherpage"
    assert data_without_params.get("url") == url_without_params
