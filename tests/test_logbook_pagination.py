# tests/test_logbook_pagination.py
import pytest
import argparse
from modules.managers.logbook_manager import LogbookManager
from modules.services import config, log

@pytest.fixture
def logbook_manager(tmp_path, monkeypatch):
    """Provides a clean LogbookManager for pagination tests."""
    logbook_dir = tmp_path / "logbook"
    logbook_dir.mkdir()
    
    original_get_parameter = config.get_parameter
    def mock_get_parameter(section, key, fallback=None):
        if section == "DIRS" and key == "LOGBOOK":
            return str(logbook_dir)
        return original_get_parameter(section, key, fallback)
    monkeypatch.setattr(config, 'get_parameter', mock_get_parameter)
    
    # Mute logger
    import logging
    monkeypatch.setattr(log, 'log_value', logging.CRITICAL + 1)
    
    return LogbookManager()

def test_pagination_chunking_trigger(logbook_manager, mocker):
    """Tests if the chunking is triggered correctly when more than 20 entries exist."""
    # Create 25 entries
    for i in range(25):
        logbook_manager.create_entry(f"cmd{i}", f"out{i}", 0, 1.0, None)

    mock_cli = mocker.MagicMock()
    mock_cli.web_ui_mode = False
    mock_cli.headless_mode = False
    mock_cli.console = mocker.MagicMock()

    # Mock single key press: ' ' (Space) for more
    mock_get_key = mocker.patch.object(LogbookManager, '_get_single_key')
    mock_get_key.return_value = ' '

    # Run list with a limit 0 for all
    logbook_manager._cmd_list(argparse.Namespace(limit=0), mock_cli)

    # Check if get_key was called once (at the 20-entry mark)
    assert mock_get_key.call_count == 1
    # Check if console.print was called correctly
    # 2 chunky tables + 1 prompt + 1 clear prompt
    assert mock_cli.console.print.call_count == 4

def test_pagination_stop_early(logbook_manager, mocker):
    """Tests if the user can stop the pagination early."""
    # Create 45 entries (3 chunks of 20, 20, 5)
    for i in range(45):
        logbook_manager.create_entry(f"cmd{i}", f"out{i}", 0, 1.0, None)

    mock_cli = mocker.MagicMock()
    mock_cli.web_ui_mode = False
    mock_cli.headless_mode = False
    mock_cli.console = mocker.MagicMock()

    # Mock single key press: 'q' to quit
    mock_get_key = mocker.patch.object(LogbookManager, '_get_single_key')
    mock_get_key.return_value = 'q'

    logbook_manager._cmd_list(argparse.Namespace(limit=0), mock_cli)

    # Should have called get_key once and stopped
    assert mock_get_key.call_count == 1
    # 1 table + 1 prompt + 1 clear prompt
    assert mock_cli.console.print.call_count == 3

def test_pagination_disabled_in_ui_mode(logbook_manager, mocker):
    """Tests if pagination is disabled in Web UI mode."""
    for i in range(25):
        logbook_manager.create_entry(f"cmd{i}", f"out{i}", 0, 1.0, None)

    mock_cli = mocker.MagicMock()
    mock_cli.web_ui_mode = True # UI mode
    mock_cli.console = mocker.MagicMock()

    mock_get_key = mocker.patch.object(LogbookManager, '_get_single_key')

    logbook_manager._cmd_list(argparse.Namespace(limit=0), mock_cli)

    # Confirm should NOT be called in UI mode
    assert mock_get_key.call_count == 0
    # Should show all in one table/panel
    assert mock_cli.console.print.call_count == 1
