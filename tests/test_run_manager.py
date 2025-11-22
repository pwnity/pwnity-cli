# tests/test_run_manager.py
import pytest
from modules.managers.run_manager import RunManager

@pytest.fixture
def run_manager():
    """Provides a RunManager instance."""
    return RunManager()

@pytest.fixture
def mock_cli(mocker):
    """Provides a mock CLI instance with all necessary managers."""
    cli = mocker.MagicMock()
    cli.session = mocker.MagicMock()
    cli.tool_mgr = mocker.MagicMock()
    cli.proxy_mgr = mocker.MagicMock()
    cli.executor = mocker.MagicMock()
    cli.display_mgr = mocker.MagicMock()
    cli.help_mgr = mocker.MagicMock()
    cli.console = mocker.MagicMock()

    # Default mock behaviors
    cli.session.tool = "nmap"
    cli.tool_mgr.load.return_value = {
        "name": "nmap",
        "commands": [{"name": "scan", "params": ["-p-", "$target.ip"]}]
    }
    cli.tool_mgr.build_command.return_value = [["nmap", "-p-", "$target.ip"]]
    cli.proxy_mgr.get_effective_config.return_value = None # Proxy off by default

    return cli

def test_do_pwn_preview(run_manager, mock_cli, mocker):
    """Tests that 'pwn' without 'now' or 'bg' shows a preview."""
    mock_log_prompt = mocker.patch("modules.managers.run_manager.log.prompt")
    mocker.patch("modules.placeholders.resolve_placeholders", side_effect=lambda p, s: p.replace("$target.ip", "127.0.0.1"))
    
    args = type('Args', (), {'pwn_args': ['scan']})()
    run_manager.do_pwn(args, mock_cli)

    # Executor should not be called
    mock_cli.executor.execute.assert_not_called()
    # A panel should be printed to the console
    mock_cli.console.print.assert_called_once()
    # Check that a prompt for execution is logged
    mock_log_prompt.assert_any_call("This is a preview. The command has not been executed yet.")

def test_do_pwn_run_now(run_manager, mock_cli, mocker):
    """Tests that 'pwn ... now' calls the executor."""
    mocker.patch("modules.placeholders.resolve_placeholders", side_effect=lambda p, s: p.replace("$target.ip", "127.0.0.1"))

    args = type('Args', (), {'pwn_args': ['scan', 'now']})()
    run_manager.do_pwn(args, mock_cli)

    mock_cli.executor.execute.assert_called_once()
    call_args, call_kwargs = mock_cli.executor.execute.call_args
    assert call_kwargs['run_now'] is True
    assert call_kwargs['run_bg'] is False

def test_do_pwn_run_bg(run_manager, mock_cli, mocker):
    """Tests that 'pwn ... bg' calls the executor."""
    mocker.patch("modules.placeholders.resolve_placeholders", side_effect=lambda p, s: p.replace("$target.ip", "127.0.0.1"))

    args = type('Args', (), {'pwn_args': ['scan', 'bg']})()
    run_manager.do_pwn(args, mock_cli)

    mock_cli.executor.execute.assert_called_once()
    call_args, call_kwargs = mock_cli.executor.execute.call_args
    assert call_kwargs['run_now'] is False
    assert call_kwargs['run_bg'] is True

def test_do_pwn_no_tool_loaded(run_manager, mock_cli, mocker):
    """Tests that an error is shown if no tool is loaded."""
    mock_log_error = mocker.patch("modules.managers.run_manager.log.error")
    mock_cli.session.tool = None # Simulate no tool loaded
    args = type('Args', (), {'pwn_args': ['scan', 'now']})()
    run_manager.do_pwn(args, mock_cli)

    mock_log_error.assert_called_with("No tool loaded in the current session. (e.g., 'tool load gobuster')")
    mock_cli.executor.execute.assert_not_called()