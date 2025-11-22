# tests/test_config_manager.py
import pytest
from modules.managers.config_manager import ConfigManager

@pytest.fixture
def config_manager():
    """Provides a ConfigManager instance."""
    return ConfigManager()

@pytest.fixture
def mock_cli(mocker):
    """Provides a mock CLI instance."""
    cli = mocker.MagicMock()
    cli.display_mgr = mocker.MagicMock()
    cli.poutput = mocker.MagicMock()
    return cli

@pytest.fixture
def mock_config_service(mocker):
    """Mocks the global config service."""
    # We must patch the 'config' object where it's used (in the config_manager module),
    # not where it's defined (in the services module).
    mock = mocker.patch("modules.managers.config_manager.config")
    mock.get_all_data.return_value = {"GLOBAL": {"DEBUG_LEVEL": "INFO"}}
    mock.get_parameter.return_value = "INFO"
    mock.set_parameter.return_value = True
    mock.save.return_value = True
    return mock

def test_cmd_list(config_manager, mock_cli, mock_config_service):
    """Tests the _cmd_list handler."""
    config_manager._cmd_list(args=None, cli=mock_cli)
    mock_cli.display_mgr.display_config.assert_called_once_with({"GLOBAL": {"DEBUG_LEVEL": "INFO"}})

def test_cmd_get(config_manager, mock_cli, mock_config_service):
    """Tests the _cmd_get handler."""
    args = type('Args', (), {'key': 'GLOBAL.DEBUG_LEVEL'})()
    config_manager._cmd_get(args, mock_cli)
    mock_config_service.get_parameter.assert_called_once_with("GLOBAL", "DEBUG_LEVEL")
    mock_cli.poutput.assert_called_once_with("INFO")

def test_cmd_get_invalid_key(config_manager, mock_cli, mock_config_service):
    """Tests _cmd_get with an invalid key format."""
    args = type('Args', (), {'key': 'GLOBAL_DEBUG_LEVEL'})()
    config_manager._cmd_get(args, mock_cli)
    mock_config_service.get_parameter.assert_not_called()

def test_cmd_set(config_manager, mock_cli, mock_config_service):
    """Tests the _cmd_set handler."""
    args = type('Args', (), {'key': 'PROXY.HOST', 'value': ['localhost']})()
    config_manager._cmd_set(args, mock_cli)
    mock_config_service.set_parameter.assert_called_once_with("PROXY", "HOST", "localhost")
    mock_config_service.save.assert_called_once()