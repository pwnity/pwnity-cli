# tests/test_heartbeat_manager.py
import pytest
import os
import json
import time
from modules.managers.heartbeat_manager import HeartbeatManager
import http.client # Import for monkeypatching
from modules.managers.target_manager import TargetManager
from modules.managers.proxy_manager import ProxyManager
from modules.cli_sessions import CLISession
from modules.services import config, log

@pytest.fixture
def managers(tmp_path, monkeypatch):
    """
    Stellt eine Sammlung von Managern bereit, die alle auf ein temporäres Verzeichnis
    konfiguriert sind, um eine saubere Testumgebung zu gewährleisten.
    """
    # Konfiguration mocken, um alle Manager auf das tmp_path umzuleiten
    def mock_get_parameter(section, key, fallback=None):
        if section == "DIRS":
            # Make key matching case-insensitive for robustness
            key = key.upper()
            if key == "TARGETS": return str(tmp_path / "targets")
            if key == "HEARTBEATS": return str(tmp_path / "heartbeats")
        # --- FIX: Mocke die globalen Proxy-Einstellungen als Sektion ---
        # Der ProxyManager ruft get_section auf, nicht get_parameter.
        # Wir müssen also die übergeordnete Funktion mocken.
        if section == "PROXY": # This part is for get_parameter, which might be used elsewhere.
            return {"ENABLED": "false", "HOST": "global.proxy", "PORT": "8080", "WRAPPER_COMMAND": None, "WRAPPER_NEEDS_SUDO": "false"}.get(key.upper())
        # --- FIX: Force INFO log level for tests by patching the config service ---
        if key == "DEBUG_LEVEL":
            return "INFO"
        return fallback

    def mock_get_section(section_name):
        if section_name == "PROXY":
            return {"ENABLED": "false", "HOST": "global.proxy", "PORT": "8080", "WRAPPER_COMMAND": None, "WRAPPER_NEEDS_SUDO": "false"}
        # --- FINAL FIX: Ensure DIRS section is also mocked for get_section ---
        # Some managers might use get_section("DIRS") instead of get_parameter.
        # This makes the mock more robust.
        if section_name == "DIRS":
            return {"TARGETS": str(tmp_path / "targets"), "HEARTBEATS": str(tmp_path / "heartbeats")}
        return {}

    monkeypatch.setattr(config, 'get_parameter', mock_get_parameter)
    monkeypatch.setattr(config, 'get_section', mock_get_section)

    # Manager instanziieren
    target_mgr = TargetManager()
    heartbeat_mgr = HeartbeatManager(target_mgr=target_mgr)
    proxy_mgr = ProxyManager()

    # Sicherstellen, dass die Verzeichnisse existieren
    os.makedirs(tmp_path / "targets", exist_ok=True)
    os.makedirs(tmp_path / "heartbeats", exist_ok=True)

    return {
        "target": target_mgr,
        "heartbeat": heartbeat_mgr,
        "proxy": proxy_mgr
    }

@pytest.fixture
def mock_cli(mocker, managers):
    """Stellt ein gemocktes CLI-Objekt mit einer Session und den Managern bereit."""
    cli = mocker.MagicMock()
    cli.session = CLISession("test-session")
    cli.target_mgr = managers["target"]
    # --- FINAL FIX: Use a REAL ProxyManager instance ---
    # Using a mock with spec=True was too restrictive and hid the fact that
    # the get_effective_config method wasn't being called correctly.
    # By using the real manager, we ensure the test accurately reflects the real application's behavior.
    cli.proxy_mgr = managers["proxy"]
    cli.console = mocker.MagicMock()
    cli.display_mgr = mocker.MagicMock()
    cli.help_mgr = mocker.MagicMock() # Added for dispatch test
    # Die Heartbeat-Manager-Methoden benötigen das CLI-Objekt
    return cli

def test_heartbeat_start_stop_and_data_creation(managers, mock_cli, mocker, monkeypatch):
    """
    Ein funktionaler Test, der den gesamten Lebenszyklus eines Heartbeats simuliert:
    Starten, Datenerfassung im Hintergrund und Stoppen.
    Netzwerkaufrufe werden gemockt, um den Test deterministisch zu machen.
    """
    target_mgr = managers["target"]
    heartbeat_mgr = managers["heartbeat"]
    target_name = "test-server.com"

    # --- 1. Arrange: Testumgebung vorbereiten ---

    # Mocke die Netzwerkverbindung, um keinen echten Request zu senden
    mock_response = mocker.MagicMock()
    mock_content = b"<html>OK</html>"
    mock_response.status = 200
    mock_response.read.return_value = mock_content
    mock_conn = mocker.MagicMock()
    mock_conn.getresponse.return_value = mock_response
    mocker.patch("http.client.HTTPConnection", return_value=mock_conn)
    mocker.patch("http.client.HTTPSConnection", return_value=mock_conn)
    monkeypatch.setattr("socket.gethostbyname", lambda host: "127.0.0.1")

    # Erstelle ein Target und lade es in die Session
    target_mgr.create(target_name)
    target_mgr.update(target_name, "url", "http://test-server.com/health")
    mock_cli.session.target = target_name

    # --- 2. Act: Heartbeat starten ---
    start_args = type('Args', (), {'options': ['delaymin', '0.1', 'delaymax', '0.2']})()
    heartbeat_mgr._cmd_start(start_args, mock_cli)

    # Überprüfe, ob der Heartbeat als aktiv registriert ist
    assert target_name in heartbeat_mgr.active_heartbeats

    # Warte kurz, damit der Thread mindestens einen Datenpunkt schreiben kann
    time.sleep(0.5)

    # --- 3. Act: Heartbeat stoppen ---
    stop_args = type('Args', (), {'name': target_name})()
    # Wir übergeben `None` für cli, da die Methode damit umgehen können muss
    # (z.B. beim globalen Shutdown). Dies verhindert auch, dass die Aufräumlogik
    # für den Web-UI-Modus fälschlicherweise ausgelöst wird.
    heartbeat_mgr._cmd_stop(stop_args, cli=None)

    # --- 4. Assert: Ergebnisse überprüfen ---
    assert target_name not in heartbeat_mgr.active_heartbeats

    # Lade die erstellte Datendatei und überprüfe ihren Inhalt
    data = heartbeat_mgr._read_heartbeat_data(target_name)
    assert data is not None
    assert data["status"] == "stopped"
    assert data["url"] == "http://test-server.com/health"
    assert len(data["data_points"]) >= 1
    first_point = data["data_points"][0]
    assert first_point["status_code"] == 200
    assert first_point["content_length"] == len(mock_content)
    assert "latency_ms" in first_point

def test_dispatch_shows_help_if_no_subcommand(managers, mock_cli):
    """
    Tests that the dispatch method calls the help manager if no subcommand is provided.
    """
    heartbeat_mgr = managers["heartbeat"]
    heartbeat_mgr.dispatch(subcommand=None, args=None, cli=mock_cli)
    mock_cli.help_mgr.show_help_heartbeat.assert_called_once()
