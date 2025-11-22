# tests/test_utility_manager.py
import pytest
from modules.managers.utility_manager import UtilityManager

@pytest.fixture
def utility_manager(mock_cli):
    """Provides a UtilityManager instance. Requires a mock_cli fixture."""
    return UtilityManager(cli_instance=mock_cli)

@pytest.fixture
def mock_cli(mocker):
    """Provides a mock CLI instance with necessary managers."""
    cli = mocker.MagicMock()
    cli.session = mocker.MagicMock()
    cli.display_mgr = mocker.MagicMock()
    cli.help_mgr = mocker.MagicMock()
    cli.poutput = mocker.MagicMock()

    # Mock managers used by do_placeholders
    cli.target_mgr.load.return_value = {"name": "test-target", "ip": "192.168.1.1"}
    cli.tool_mgr.load.return_value = {"name": "test-tool"}
    cli.wordlist_mgr.load.return_value = None # Simulate not loaded
    cli.profile_mgr.load.return_value = {"lhost": "127.0.0.1"}
    cli.proxy_mgr.get_placeholder_config.return_value = {"host": "localhost"}
    cli.report_mgr.load.return_value = {"name": "test-report"}

    # --- NEW: Mock the utility_manager's internal helper for placeholder tests ---
    # This isolates the get_all_placeholders test from the file parsing logic.
    mocker.patch(
        "modules.managers.utility_manager.placeholders.get_parsed_report_file_data",
        return_value={"nmap_scan_xml": {"host": "data"}}
    )

    return cli

def test_do_placeholders(utility_manager, mock_cli):
    """Tests the do_placeholders handler."""
    args = type('Args', (), {'subcommand': 'all'})()
    utility_manager.do_placeholders(args, mock_cli)

    # Check that display_placeholders was called
    mock_cli.display_mgr.display_placeholders.assert_called_once()
    
    # Check the data that was passed to the display manager
    call_args, _ = mock_cli.display_mgr.display_placeholders.call_args
    passed_data = call_args[0]
    assert 'target' in passed_data
    assert 'tool' in passed_data
    assert 'wordlist' not in passed_data # Should not be included as it was not loaded

def test_do_print(utility_manager, mock_cli, mocker):
    """Tests the do_print handler."""
    # Mock the placeholder resolver to return a predictable value
    mocker.patch("modules.placeholders.resolve_placeholders", return_value="resolved_value")

    statement = mocker.MagicMock()
    statement.raw = "print $some.placeholder"

    utility_manager.do_print(statement, mock_cli)
    mock_cli.poutput.assert_called_once_with("resolved_value")

def test_do_identify(utility_manager, mock_cli, mocker):
    """Tests the do_identify handler."""
    # Mock placeholder resolver and hash identifier
    mocker.patch("modules.placeholders.resolve_placeholders", return_value="some_hash")
    mocker.patch("modules.functions.identify_hash", return_value=["MD5"])

    statement = mocker.MagicMock()
    statement.raw = "identify some_hash"

    utility_manager.do_identify(statement, mock_cli)
    mock_cli.display_mgr.display_hash_identification.assert_called_once_with("some_hash", ["MD5"])

def test_get_all_placeholders(mock_cli):
    """
    Tests the get_all_placeholders method to ensure it correctly gathers
    and formats placeholder strings from the current session state.
    """
    # The mock_cli fixture already has managers and data set up.
    # We just need to instantiate the UtilityManager with it.
    utility_mgr = UtilityManager(mock_cli)

    # Call the method to be tested
    placeholders = utility_mgr.get_all_placeholders(mock_cli.session)

    # Assert that the output is a list of strings
    assert isinstance(placeholders, list)
    assert all(isinstance(p, str) for p in placeholders)

    # Check for expected placeholders from different managers
    assert "$target.ip" in placeholders
    assert "$profile.lhost" in placeholders
    assert "$proxy.host" in placeholders
    assert "$report.name" in placeholders
    assert "$tool.name" in placeholders