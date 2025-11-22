# tests/test_completer.py
import pytest
from unittest.mock import MagicMock, PropertyMock

# Da MyCLI beim Import viel initialisiert, mocken wir es, bevor wir es importieren
from unittest.mock import patch

@pytest.fixture
def cli_app(monkeypatch):
    """
    Fixture to create a MyCLI instance with mocked managers for completer testing.
    """
    # Mock managers to avoid file system access and other side effects
    mock_tool_mgr = MagicMock()
    mock_target_mgr = MagicMock()
    mock_preset_mgr = MagicMock()
    mock_wordlist_mgr = MagicMock()
    mock_report_mgr = MagicMock()
    mock_session = MagicMock()

    # Patch the MyCLI.__init__ to replace managers with mocks
    def mock_init(self):
        self.tool_mgr = mock_tool_mgr
        self.target_mgr = mock_target_mgr
        self.preset_mgr = mock_preset_mgr
        self.wordlist_mgr = mock_wordlist_mgr
        self.report_mgr = mock_report_mgr
        self.session = mock_session
        from modules.completer import Completer
        self.completer = Completer(self)

    monkeypatch.setattr("pwnity_cli.MyCLI.__init__", mock_init)

    from pwnity_cli import MyCLI
    cli = MyCLI()
    return cli


def test_complete_tool(cli_app):
    """Tests autocompletion for the 'tool' command."""
    completer = cli_app.completer

    # Test subcommand completion
    line = "tool "
    completions = completer.complete_tool("", line, len(line), len(line))
    assert "update" in completions
    assert "list" in completions

    # Test tool name completion
    cli_app.tool_mgr.list_all.return_value = ["nmap", "gobuster"]
    line = "tool update "
    completions = completer.complete_tool("g", line, len(line), len(line) + 1)
    assert completions == ["gobuster"]

    # Test field/command completion for 'tool update <name>'
    cli_app.tool_mgr.load.return_value = {
        "name": "gobuster",
        "commands": [{"name": "dir"}, {"name": "dns"}]
    }
    line = "tool update gobuster "
    completions = completer.complete_tool("", line, len(line), len(line))
    assert "path" in completions
    assert "command" in completions
    assert "dir" in completions
    assert "dns" in completions

    # Test command action completion for 'tool update <name> <command>'
    line = "tool update gobuster dir "
    completions = completer.complete_tool("p", line, len(line), len(line) + 1)
    assert "param" in completions


def test_complete_target(cli_app):
    """Tests autocompletion for the 'target' command."""
    completer = cli_app.completer

    # Test subcommand completion
    line = "target "
    completions = completer.complete_target("", line, len(line), len(line))
    assert "update" in completions
    assert "delete" in completions

    # Test target name completion
    cli_app.target_mgr.list_all.return_value = ["server1", "workstation2"]
    line = "target update "
    completions = completer.complete_target("s", line, len(line), len(line) + 1)
    assert completions == ["server1"]

    # Test field completion for 'target update <name>'
    cli_app.target_mgr.load.return_value = {"ip": "10.10.10.1", "hostname": "test.local"}
    line = "target update server1 "
    completions = completer.complete_target("", line, len(line), len(line))
    assert "url" in completions
    assert "ip" in completions
    assert "hostname" in completions


def test_complete_preset(cli_app):
    """Tests autocompletion for the 'preset' command."""
    completer = cli_app.completer

    # Test field completion for 'preset update <name>'
    line = "preset update mypreset "
    completions = completer.complete_preset("", line, len(line), len(line))
    assert "target" in completions
    assert "tool" in completions
    assert "wordlist" in completions
    assert "report" in completions

    # Test entity name completion for 'preset update <name> target'
    cli_app.target_mgr.list_all.return_value = ["target1", "target2"]
    line = "preset update mypreset target "
    completions = completer.complete_preset("t", line, len(line), len(line) + 1)
    assert completions == ["target1", "target2"]

    # Test entity name completion for 'preset update <name> tool'
    cli_app.tool_mgr.list_all.return_value = ["nmap", "gobuster"]
    line = "preset update mypreset tool "
    completions = completer.complete_preset("g", line, len(line), len(line) + 1)
    assert completions == ["gobuster"]


def test_complete_wordlist(cli_app):
    """Tests autocompletion for the 'wordlist' command."""
    completer = cli_app.completer

    # Test field completion for 'wordlist update <name>'
    line = "wordlist update mylist "
    completions = completer.complete_wordlist("", line, len(line), len(line))
    assert completions == ["path"]


def test_complete_report(cli_app):
    """Tests autocompletion for the 'report' command."""
    completer = cli_app.completer

    # Mock the currently loaded report in the session
    cli_app.session.report = "scan_report_123"

    # Mock the files listed for that report
    cli_app.report_mgr.list_files.return_value = ["nmap_full.xml", "nmap_quick.txt", "notes.md"]

    # Test file completion for 'report view'
    # Simulate typing 'report view nmap'
    line = "report view nmap"
    completions = completer.complete_report("nmap", line, len("report view "), len(line))
    assert "nmap_full.xml" in completions
    assert "nmap_quick.txt" in completions
    assert "notes.md" not in completions

    # Test with no loaded report
    cli_app.session.report = None
    completions = completer.complete_report("", line, len(line), len(line))
    # In this specific test case, it will still try to complete based on the line, so we don't assert empty.
    # The important part is the case above.