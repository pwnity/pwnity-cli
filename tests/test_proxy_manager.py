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

# tests/test_proxy_manager.py
import pytest
from modules.managers.proxy_manager import ProxyManager
from modules.services import config, log

@pytest.fixture
def proxy_manager():
    """Stellt eine saubere Instanz des ProxyManager bereit."""
    return ProxyManager()

@pytest.fixture
def mock_session(mocker):
    """Stellt ein gemocktes Session-Objekt mit einem leeren proxy_settings-Dict bereit."""
    session = mocker.MagicMock()
    session.proxy_settings = {}
    return session

@pytest.fixture
def mock_cli_with_session(mocker, mock_session, proxy_manager):
    """Provides a mock CLI instance with a session and the proxy manager."""
    cli = mocker.MagicMock()
    cli.session = mock_session
    cli.proxy_mgr = proxy_manager # Ensure the real manager is used
    cli.display_mgr = mocker.MagicMock() # For _cmd_show
    cli.poutput.side_effect = lambda x: None # Mock poutput if needed
    cli.help_mgr = mocker.MagicMock() # For help calls
    return cli


@pytest.fixture
def mock_global_config(monkeypatch):
    """Mockt die globalen Proxy-Einstellungen aus der config.ini."""
    global_proxy_config = {
        "ENABLED": "false",
        "TYPE": "http",
        "HOST": "127.0.0.1",
        "PORT": "8080",
        "WRAPPER_COMMAND": None,
        "WRAPPER_NEEDS_SUDO": "false",
    }
    # Mocke get_section, um unsere Test-Konfiguration zurückzugeben
    monkeypatch.setattr(config, 'get_section', lambda section_name: global_proxy_config if section_name == "PROXY" else {})
    
    # Logger stummschalten
    import logging
    monkeypatch.setattr(log, 'log_value', logging.CRITICAL + 1)
    
    return global_proxy_config

def test_get_effective_config_disabled_by_default(proxy_manager, mock_session, mock_global_config):
    """Testet, ob der Proxy standardmässig (global deaktiviert) None zurückgibt."""
    assert proxy_manager.get_effective_config(mock_session) is None

def test_get_effective_config_enabled_globally(proxy_manager, mock_session, mock_global_config):
    """Testet, ob die globalen Einstellungen übernommen werden, wenn der Proxy global aktiviert ist."""
    mock_global_config["ENABLED"] = "true"
    effective = proxy_manager.get_effective_config(mock_session)
    assert effective is not None
    assert effective["host"] == "127.0.0.1"
    assert effective["port"] == "8080"
    assert effective["wrapper_needs_sudo"] is False

def test_get_effective_config_session_enables_proxy(proxy_manager, mock_session, mock_global_config):
    """Testet, ob eine Session-Einstellung den global deaktivierten Proxy aktivieren kann."""
    mock_session.proxy_settings["enabled"] = True
    effective = proxy_manager.get_effective_config(mock_session)
    assert effective is not None
    assert effective["host"] == "127.0.0.1"

def test_get_effective_config_session_disables_proxy(proxy_manager, mock_session, mock_global_config):
    """Testet, ob eine Session-Einstellung den global aktivierten Proxy deaktivieren kann."""
    mock_global_config["ENABLED"] = "true"
    mock_session.proxy_settings["enabled"] = False
    assert proxy_manager.get_effective_config(mock_session) is None

def test_get_effective_config_session_overrides_host(proxy_manager, mock_session, mock_global_config):
    """Testet, ob eine Session-Einstellung eine globale Einstellung (z.B. Host) überschreibt."""
    mock_global_config["ENABLED"] = "true"
    mock_session.proxy_settings["host"] = "localhost"
    mock_session.proxy_settings["wrapper_needs_sudo"] = "true"
    
    effective = proxy_manager.get_effective_config(mock_session)
    assert effective is not None
    assert effective["host"] == "localhost" # Session-Wert wird verwendet
    assert effective["port"] == "8080" # Globaler Wert wird als Fallback verwendet
    assert effective["wrapper_needs_sudo"] is True # Korrekte Typumwandlung

def test_set_enabled(proxy_manager, mock_session):
    """Testet das explizite Aktivieren und Deaktivieren des Proxys in der Session."""
    proxy_manager.set_enabled(mock_session, True)
    assert mock_session.proxy_settings["enabled"] is True

    proxy_manager.set_enabled(mock_session, False)
    assert mock_session.proxy_settings["enabled"] is False

def test_set_config(proxy_manager, mock_session, mocker):
    """Testet das Setzen von Konfigurationswerten und die Ablehnung ungültiger Schlüssel."""
    proxy_manager.set_config(mock_session, "host", "testhost")
    assert mock_session.proxy_settings["host"] == "testhost"

    # Teste einen ungültigen Schlüssel
    mock_log_error = mocker.patch("modules.services.log.error")
    proxy_manager.set_config(mock_session, "invalid_key", "some_value")
    mock_log_error.assert_called_with("Invalid key 'invalid_key'.")
    assert "invalid_key" not in mock_session.proxy_settings

def test_reset_config(proxy_manager, mock_session):
    """Testet das Zurücksetzen von einzelnen und allen Session-Einstellungen."""
    # Setze einige Werte in der Session
    mock_session.proxy_settings["host"] = "localhost"
    mock_session.proxy_settings["port"] = "9090"
    assert "port" in mock_session.proxy_settings

    # Setze einen einzelnen Schlüssel zurück
    proxy_manager.reset_config(mock_session, "port")
    assert "port" not in mock_session.proxy_settings
    assert "host" in mock_session.proxy_settings # Der andere Schlüssel sollte unberührt bleiben

    # Setze alle Schlüssel zurück
    proxy_manager.reset_config(mock_session, "all")
    assert not mock_session.proxy_settings # Das Dict sollte jetzt leer sein

def test_reset_config_invalid_key(proxy_manager, mock_session, mocker):
    """Testet, ob das Zurücksetzen mit einem ungültigen Schlüssel fehlschlägt und einen Fehler loggt."""
    mock_session.proxy_settings["host"] = "localhost"
    mock_log_error = mocker.patch("modules.services.log.error")

    proxy_manager.reset_config(mock_session, "invalid_key")

    # Der Fehler sollte geloggt werden und die Session-Einstellungen sollten unberührt bleiben
    mock_log_error.assert_called_with("Invalid key 'invalid_key' to reset.")
    assert "host" in mock_session.proxy_settings

def test_get_placeholder_config(proxy_manager, mock_session, mock_global_config):
    """
    Testet, ob `get_placeholder_config` die effektive Konfiguration zurückgibt,
    selbst wenn der Proxy deaktiviert ist.
    """
    # Proxy ist global und in der Session deaktiviert
    assert proxy_manager.get_effective_config(mock_session) is None

    # Setze einen Session-spezifischen Wert
    mock_session.proxy_settings["host"] = "placeholder_host"

    # Die Platzhalter-Konfiguration sollte trotzdem die korrekten Werte enthalten
    placeholder_config = proxy_manager.get_placeholder_config(mock_session)
    assert placeholder_config is not None
    assert placeholder_config["host"] == "placeholder_host" # Session-Wert
    assert placeholder_config["port"] == "8080" # Globaler Fallback-Wert
    assert placeholder_config["enabled"] is False # Korrekter Status

def test_get_status_data(proxy_manager, mock_session, mock_global_config):
    """Testet, ob `get_status_data` die korrekte Datenstruktur zurückgibt."""
    mock_session.proxy_settings["host"] = "session_host"
    status_data = proxy_manager.get_status_data(mock_session)

    assert "global_settings" in status_data
    assert "session_settings" in status_data
    assert "effective_config" in status_data
    assert status_data["session_settings"]["host"] == "session_host"

def test_get_effective_config_with_missing_globals(proxy_manager, mock_session, mock_global_config):
    """Testet, ob fehlende globale Einstellungen korrekt als None behandelt werden."""
    mock_global_config["ENABLED"] = "true"
    # Entferne einige Schlüssel aus der globalen Konfiguration
    del mock_global_config["HOST"]
    mock_global_config["WRAPPER_COMMAND"] = None

    effective = proxy_manager.get_effective_config(mock_session)
    assert effective is not None
    assert effective["host"] is None # Sollte None sein, da nicht definiert
    assert effective["port"] == "8080" # Sollte noch vorhanden sein
    assert effective["wrapper_command"] is None

@pytest.mark.parametrize("global_enabled, session_enabled, expected_status", [
    ("true", None, True),
    ("1", None, True),
    ("yes", None, True),
    ("false", None, False),
    ("0", None, False),
    ("no", None, False),
    ("false", True, True), # Session überschreibt global
    ("true", False, False), # Session überschreibt global
])
def test_boolean_conversion_for_enabled_flags(proxy_manager, mock_session, mock_global_config, global_enabled, session_enabled, expected_status):
    """Testet die korrekte Umwandlung verschiedener Boolean-Strings."""
    mock_global_config["ENABLED"] = global_enabled
    if session_enabled is not None:
        mock_session.proxy_settings["enabled"] = session_enabled

    effective = proxy_manager.get_effective_config(mock_session)
    assert (effective is not None) == expected_status

def test_get_effective_config_with_no_session(proxy_manager, mock_global_config):
    """Testet, ob die Methode mit `session=None` umgehen kann und auf globale Werte zurückfällt."""
    mock_global_config["ENABLED"] = "true"
    effective = proxy_manager.get_effective_config(session=None)
    assert effective is not None
    assert effective["host"] == "127.0.0.1"

# --- New tests for _cmd_* methods ---

def test_cmd_on(proxy_manager, mock_cli_with_session, mocker):
    """Testet den _cmd_on Befehl."""
    mock_log_success = mocker.patch("modules.services.log.success")
    mock_cli_with_session.session.proxy_settings['enabled'] = False # Start disabled
    proxy_manager._cmd_on(args=None, cli=mock_cli_with_session)
    assert mock_cli_with_session.session.proxy_settings['enabled'] is True
    mock_log_success.assert_called_with("Proxy enabled for the current session.")

def test_cmd_off(proxy_manager, mock_cli_with_session, mocker):
    """Testet den _cmd_off Befehl."""
    mock_log_success = mocker.patch("modules.services.log.success")
    mock_cli_with_session.session.proxy_settings['enabled'] = True # Start enabled
    proxy_manager._cmd_off(args=None, cli=mock_cli_with_session)
    assert mock_cli_with_session.session.proxy_settings['enabled'] is False
    mock_log_success.assert_called_with("Proxy disabled for the current session.")

def test_cmd_set_valid_key(proxy_manager, mock_cli_with_session, mocker):
    """Testet den _cmd_set Befehl mit gültigen Argumenten."""
    mock_log_success = mocker.patch("modules.services.log.success")
    # Simuliert das Ergebnis des Parsers: args.key und args.value
    args = type('Args', (), {
        'key': 'host',
        'value': ['192.168.1.1']
    })()
    proxy_manager._cmd_set(args, mock_cli_with_session)
    assert mock_cli_with_session.session.proxy_settings['host'] == '192.168.1.1'
    mock_log_success.assert_called_with("Proxy setting 'host' set for the current session.")

def test_cmd_set_invalid_key(proxy_manager, mock_cli_with_session, mocker):
    """Testet den _cmd_set Befehl mit einem ungültigen Schlüssel."""
    mock_log_error = mocker.patch("modules.services.log.error")
    # Der Parser würde hier dank 'choices' bereits einen Fehler werfen,
    # aber wir testen die Logik in _cmd_set, falls der Parser umgangen wird.
    args = type('Args', (), {
        'key': 'invalid_key',
        'value': ['value']
    })()
    proxy_manager._cmd_set(args, mock_cli_with_session)
    mock_log_error.assert_called_with("Invalid key 'invalid_key'.")
    assert 'invalid_key' not in mock_cli_with_session.session.proxy_settings

def test_cmd_set_missing_value(proxy_manager, mock_cli_with_session, mocker):
    """Testet den _cmd_set Befehl, wenn der Wert fehlt."""
    mock_log_error = mocker.patch("modules.services.log.error")
    # Der Parser setzt 'value' auf eine leere Liste, wenn nichts angegeben wird.
    args = type('Args', (), {
        'key': 'host',
        'value': []
    })()
    proxy_manager._cmd_set(args, mock_cli_with_session)
    mock_log_error.assert_called_with("Invalid command. Expected: proxy set <key> <value>")

def test_cmd_reset_single_key(proxy_manager, mock_cli_with_session, mocker):
    """Testet den _cmd_reset Befehl für einen einzelnen Schlüssel."""
    mock_log_success = mocker.patch("modules.services.log.success")
    mock_cli_with_session.session.proxy_settings['host'] = '1.2.3.4'
    args = type('Args', (), {'key': 'host'})()
    proxy_manager._cmd_reset(args, mock_cli_with_session)
    assert 'host' not in mock_cli_with_session.session.proxy_settings
    mock_log_success.assert_called_with("Session setting 'host' has been reset to the global default.")

def test_cmd_reset_all(proxy_manager, mock_cli_with_session, mocker):
    """Testet den _cmd_reset Befehl für 'all'."""
    mock_log_success = mocker.patch("modules.services.log.success")
    mock_cli_with_session.session.proxy_settings['host'] = '1.2.3.4'
    mock_cli_with_session.session.proxy_settings['port'] = '8080'
    args = type('Args', (), {'key': 'all'})()
    proxy_manager._cmd_reset(args, mock_cli_with_session)
    assert not mock_cli_with_session.session.proxy_settings
    mock_log_success.assert_called_with("All session-specific proxy settings have been reset to global defaults.")

def test_cmd_show(proxy_manager, mock_cli_with_session, mocker):
    """Testet den _cmd_show Befehl."""
    mock_cli_with_session.session.proxy_settings['enabled'] = True
    mock_cli_with_session.session.proxy_settings['host'] = '1.2.3.4'
    
    # Mock get_status_data to return a predictable value
    mocker.patch.object(proxy_manager, 'get_status_data', return_value={'global_settings': {}, 'session_settings': {}, 'effective_config': {'host': '1.2.3.4'}})

    args = type('Args', (), {})()
    proxy_manager._cmd_show(args, mock_cli_with_session)
    mock_cli_with_session.display_mgr.display_proxy_status.assert_called_once()

def test_cmd_show_no_session(proxy_manager, mock_cli_with_session, mocker):
    """Testet den _cmd_show Befehl, wenn keine Session geladen ist."""
    mock_log_error = mocker.patch("modules.services.log.error")
    mock_cli_with_session.session = None
    args = type('Args', (), {})()
    proxy_manager._cmd_show(args, mock_cli_with_session)
    mock_log_error.assert_called_with("Cannot show proxy status without an active session.")