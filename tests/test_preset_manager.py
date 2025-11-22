# tests/test_preset_manager.py
import pytest
from modules.managers.preset_manager import PresetManager
from modules.cli_sessions import CLISession
from modules.services import config, log

@pytest.fixture
def preset_manager(tmp_path, monkeypatch):
    """
    Stellt einen sauberen PresetManager bereit, der in ein temporäres Verzeichnis schreibt.
    """
    presets_dir = tmp_path / "presets"
    presets_dir.mkdir()

    # Leite den Manager auf das temporäre Verzeichnis um
    original_get_parameter = config.get_parameter
    def mock_get_parameter_for_preset(section, key, fallback=None):
        if section == "DIRS" and key == "PRESETS":
            return str(presets_dir)
        # --- FIX: Force INFO log level for tests by patching the config service ---
        # This ensures that any module using the logger during this test will get
        # an instance configured with the INFO level.
        if key == "DEBUG_LEVEL":
            return "INFO"
        return original_get_parameter(section, key, fallback)
    
    monkeypatch.setattr(config, 'get_parameter', mock_get_parameter_for_preset)

    return PresetManager()

@pytest.fixture
def mock_cli(mocker):
    """
    Stellt ein gemocktes CLI-Objekt mit einer Session und einem SessionManager bereit.
    """
    cli = mocker.MagicMock()
    cli.session = CLISession("test-session")
    cli.session_mgr = mocker.MagicMock()
    cli.session_mgr.sessions = {"test-session": cli.session}
    cli.session_mgr.new.return_value = cli.session
    cli.help_mgr = mocker.MagicMock()
    cli.session_mgr.switch.return_value = cli.session
    return cli

def test_preset_save_and_load(preset_manager, mock_cli):
    """
    Testet den kompletten Zyklus: Speichern einer Session als Preset und Laden dieses Presets.
    """
    preset_name = "my-scan"
    
    # 1. Konfiguriere die Session, die wir speichern wollen
    mock_cli.session.target = "test-server"
    mock_cli.session.tool = "nmap"
    mock_cli.session.wordlist = "common"
    mock_cli.session.report = "project-x-report"
    mock_cli.session.proxy_settings = {"enabled": True, "host": "127.0.0.1"}

    # 2. Speichere die Session als Preset
    save_args = type('Args', (), {'name': preset_name})()
    preset_manager._cmd_save(save_args, mock_cli)

    # Überprüfe, ob das Preset physisch existiert
    assert preset_manager.exists(preset_name) is True
    saved_data = preset_manager.load(preset_name)
    assert saved_data["target"] == "test-server"
    assert "proxy_settings" in saved_data
    assert saved_data["proxy_settings"]["host"] == "127.0.0.1"

    # 3. Setze die Session zurück, um das Laden zu simulieren
    mock_cli.session.target = None
    mock_cli.session.tool = None
    mock_cli.session.wordlist = None
    mock_cli.session.report = None
    mock_cli.session.proxy_settings = {}

    # 4. Lade das Preset
    load_args = type('Args', (), {'name': preset_name})()
    preset_manager._cmd_load(load_args, mock_cli)

    # Überprüfe, ob die Session korrekt wiederhergestellt wurde
    assert mock_cli.session.target == "test-server"
    assert mock_cli.session.tool == "nmap"
    assert mock_cli.session.wordlist == "common"
    assert mock_cli.session.report == "project-x-report"
    assert mock_cli.session.proxy_settings["enabled"] is True
    assert mock_cli.session.proxy_settings["host"] == "127.0.0.1"

def test_preset_load_creates_new_session(preset_manager, mock_cli):
    """
    Testet, ob `preset load` eine neue Session erstellt, wenn keine mit dem Preset-Namen existiert.
    """
    preset_name = "new-session-preset"
    preset_manager.create(preset_name) # Erstelle ein leeres Preset

    # Simuliere, dass die Session noch nicht existiert
    mock_cli.session_mgr.sessions = {}

    load_args = type('Args', (), {'name': preset_name})()
    preset_manager._cmd_load(load_args, mock_cli)

    # Überprüfe, ob der SessionManager angewiesen wurde, eine neue Session zu erstellen
    mock_cli.session_mgr.new.assert_called_once_with(preset_name)

def test_preset_export(preset_manager, mocker):
    """
    Testet, ob die Export-Funktion die korrekten Rekonstruktions-Befehle generiert,
    insbesondere für Proxy-Einstellungen.
    """
    preset_name = "export-test"
    preset_data = {
        "name": preset_name,
        "target": "test-server",
        "tool": "nmap",
        "proxy_settings": {
            "enabled": True,
            "type": "socks5",
            "host": "localhost",
            "port": "9050"
        }
    }
    preset_manager._save_data(preset_name, preset_data)

    # Mocke das cli-Objekt und seine poutput-Methode
    mock_cli = mocker.MagicMock()
    captured_output = []
    mock_cli.poutput.side_effect = lambda x: captured_output.append(x)

    # Führe die Export-Methode aus
    export_args = type('Args', (), {'name': preset_name})()
    preset_manager._cmd_export(export_args, mock_cli)

    full_output = "\n".join(captured_output)
    assert "target load test-server" in full_output
    assert "tool load nmap" in full_output
    assert "proxy reset all" in full_output
    assert "proxy on" in full_output
    assert "proxy set type socks5" in full_output
    assert "proxy set port 9050" in full_output
    assert "proxy set host localhost" in full_output

def test_save_empty_session(preset_manager, mock_cli):
    """Testet, ob das Speichern einer leeren Session korrekt funktioniert."""
    preset_name = "empty-preset"
    
    # Stelle sicher, dass die Session leer ist
    mock_cli.session.target = None
    mock_cli.session.tool = None
    mock_cli.session.wordlist = None
    mock_cli.session.report = None
    mock_cli.session.proxy_settings = {}

    # Speichere die leere Session
    save_args = type('Args', (), {'name': preset_name})()
    preset_manager._cmd_save(save_args, mock_cli)

    # Überprüfe die gespeicherten Daten
    assert preset_manager.exists(preset_name) is True
    saved_data = preset_manager.load(preset_name)
    assert saved_data["target"] is None
    assert saved_data["tool"] is None
    assert "proxy_settings" not in saved_data # Leere Proxy-Settings werden nicht gespeichert

def test_export_with_disabled_proxy(preset_manager, mocker):
    """
    Testet, ob der Export-Befehl 'proxy off' generiert, wenn der Proxy im Preset deaktiviert ist.
    """
    preset_name = "proxy-off-test"
    preset_data = {
        "name": preset_name,
        "target": "test-server",
        "proxy_settings": { "enabled": False }
    }
    preset_manager._save_data(preset_name, preset_data)

    mock_cli = mocker.MagicMock()
    captured_output = []
    mock_cli.poutput.side_effect = lambda x: captured_output.append(x)

    export_args = type('Args', (), {'name': preset_name})()
    preset_manager._cmd_export(export_args, mock_cli)

    full_output = "\n".join(captured_output)
    assert "target load test-server" in full_output
    assert "proxy reset all" in full_output
    assert "proxy off" in full_output
    assert "proxy on" not in full_output # Wichtig: 'proxy on' darf nicht erscheinen

def test_dispatch_shows_help_if_no_subcommand(preset_manager, mock_cli):
    """
    Tests that the dispatch method calls the help manager if no subcommand is provided.
    """
    preset_manager.dispatch(subcommand=None, args=None, cli_instance=mock_cli)
    mock_cli.help_mgr.show_help_preset.assert_called_once()