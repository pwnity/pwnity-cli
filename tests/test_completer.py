# tests/test_completer.py
import pytest
from modules.completer import Completer

@pytest.fixture
def mock_cli(mocker):
    """Provides a mocked CLI instance with mocked managers."""
    cli = mocker.MagicMock()
    
    # Mock managers and their list methods
    cli.target_mgr.list_all.return_value = ["target-a", "target-b"]
    cli.tool_mgr.list_all.return_value = ["nmap", "gobuster"]
    cli.wordlist_mgr.list_all.return_value = ["rockyou", "common"]
    
    # Mock tool data for pwn completer
    cli.tool_mgr.load.return_value = {
        "name": "nmap",
        "commands": [{"name": "scan"}, {"name": "ping"}]
    }
    
    # Mock session
    cli.session = mocker.MagicMock()
    cli.session.tool = "nmap" # Simulate a tool being loaded

    return cli

@pytest.fixture
def completer(mock_cli):
    """Provides a Completer instance with a mocked CLI."""
    return Completer(cli_instance=mock_cli)

def test_basic_manager_completion(completer):
    """
    Tests the generic completion helper for a simple manager command.
    We test this by calling a command that uses it, e.g., `target`.
    """
    # Test completing the subcommand
    subcommands = ['add', 'list', 'show', 'rename', 'destroy', 'delete', 'load']
    result1 = completer._basic_manager_completion("l", "target l", 7, 8, completer.cli.target_mgr, subcommands)
    assert "list" in result1
    assert "load" in result1

    # Test completing the entity name
    result2 = completer._basic_manager_completion("target-", "target load target-", 12, 19, completer.cli.target_mgr, subcommands)
    assert "target-a" in result2
    assert "target-b" in result2

def test_pwn_completer(completer):
    """
    Tests the specific completer for the 'pwn' command.
    """
    # Case 1: Completing the command name
    line = "pwn sc"
    result1 = completer.complete_pwn("sc", line, 4, 6)
    assert "scan" in result1
    assert "ping" not in result1 # 'ping' does not start with 'sc'

    # Case 2: Completing the execution keyword
    line = "pwn scan n"
    result2 = completer.complete_pwn("n", line, 9, 10)
    assert "now" in result2
    assert "bg" not in result2