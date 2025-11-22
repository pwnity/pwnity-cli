# tests/test_logger.py
import pytest
from modules.logger import Logger
from modules.config_parser import ConfigParser
import re

@pytest.fixture
def mock_config(mocker):
    """Provides a mocked ConfigParser instance."""
    mock = mocker.MagicMock(spec=ConfigParser)
    # Provide a minimal color map for the tests
    mock.get_section.return_value = {
        "GREEN": "\u001b[92m",
        "RED": "\u001b[91m",
        "BLUE": "\u001b[94m",
        "RESET": "\u001b[0m"
    }
    # Default log level is INFO for most tests
    mock.get_parameter.return_value = "INFO"
    return mock

@pytest.fixture
def mock_cli(mocker):
    """Provides a mocked CLI instance to capture output."""
    cli = mocker.MagicMock()
    # Use a list to capture all calls to poutput
    cli.poutput_calls = []
    cli.poutput.side_effect = lambda msg: cli.poutput_calls.append(msg)
    return cli

@pytest.fixture
def logger(mock_config, mock_cli):
    """Provides a Logger instance with mocked dependencies."""
    log_instance = Logger(config=mock_config, cli_instance=mock_cli)
    return log_instance

def test_log_level_filtering(mock_config, mock_cli):
    """
    Tests that messages below the minimum log level are filtered out.
    """
    # Set log level to WARNING
    mock_config.get_parameter.return_value = "WARNING"
    # Re-initialize logger to apply the new log level
    log_instance = Logger(config=mock_config, cli_instance=mock_cli)

    log_instance.debug("This should be filtered.")
    log_instance.info("This should also be filtered.")
    log_instance.warning("This should be visible.")
    log_instance.error("This should be visible too.")

    assert len(mock_cli.poutput_calls) == 2
    assert "This should be visible." in mock_cli.poutput_calls[0]
    assert "This should be visible too." in mock_cli.poutput_calls[1]

def test_log_output_format(logger, mock_cli):
    """
    Tests that a log message is formatted correctly with symbol and color.
    """
    logger.success("Test success message")
    
    assert len(mock_cli.poutput_calls) == 1
    output = mock_cli.poutput_calls[0]
    
    # Check for color code, symbol, reset code, and message
    assert output.startswith("\u001b[92m[+]\u001b[0m")
    assert "Test success message" in output

def test_log_history(logger):
    """
    Tests that the logger correctly maintains a history of recent messages.
    """
    logger.info("Message 1")
    logger.warning("Message 2")
    logger.error("Message 3")

    history = logger.get_history()
    assert len(history) == 3
    # History should contain the uncolored message with its symbol
    assert history[0] == "[*] Message 1"
    assert history[2] == "[-] Message 3"

def test_timestamp_enabled(mock_config, mock_cli):
    """
    Tests that enabling timestamps adds a timestamp to the output.
    """
    # Initialize logger with timestamp=True
    log_instance = Logger(config=mock_config, cli_instance=mock_cli, timestamp=True)

    log_instance.info("Timestamped message")

    assert len(mock_cli.poutput_calls) == 1
    output = mock_cli.poutput_calls[0]
    # Check for a timestamp pattern like [YYYY-MM-DD HH:MM:SS.ffffff]
    assert re.match(r'^\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{6}\]', output)

def test_invalid_log_level_in_config(mock_config, mock_cli):
    """
    Tests that the logger falls back to a default level if the config is invalid.
    """
    mock_config.get_parameter.return_value = "INVALID_LEVEL"
    log_instance = Logger(config=mock_config, cli_instance=mock_cli)

    # The logger should have logged an error about the invalid config
    assert len(mock_cli.poutput_calls) == 1
    assert "INVALID_LEVEL not defined" in mock_cli.poutput_calls[0]
    # The log level should have fallen back to the default (DEBUG)
    assert log_instance.min_log_level == "DEBUG"

def test_log_header_format(logger, mock_cli):
    """Tests that the header method uses its special formatting."""
    logger.header("My Test Header")
    assert len(mock_cli.poutput_calls) == 1
    output = mock_cli.poutput_calls[0]
    # Headers should not have the symbol prefix, but the surrounding '---'
    assert "--- My Test Header ---" in output
    assert "[+]" not in output
    assert "[*]" not in output

def test_log_custom_method(logger, mock_cli):
    """Tests the custom log method, including timestamp override."""
    # Logger is initialized with timestamp=False
    assert logger.timestamp is False
    
    # Call custom with timestamp=True
    logger.custom("My custom message", timestamp=True)
    
    assert len(mock_cli.poutput_calls) == 1
    output = mock_cli.poutput_calls[0]
    assert re.match(r'^\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{6}\]', output)
    # Check for the symbol and message separately to be resilient to color codes
    assert "[#]" in output
    assert "My custom message" in output

def test_fallback_to_print_when_cli_is_none(logger, mock_cli, mocker):
    """Tests that the logger falls back to print() if the cli_instance is removed."""
    mock_print = mocker.patch("builtins.print")

    logger.info("This goes to poutput.")
    logger.set_cli_instance(None) # Remove the cli instance
    logger.error("This should go to print.")

    assert len(mock_cli.poutput_calls) == 1 # Only the first message
    mock_print.assert_called_once()
    assert "This should go to print." in mock_print.call_args[0][0]