import pytest
import sys
import os
from unittest.mock import MagicMock

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from plugins.web_ui import app_instance

@pytest.fixture
def mock_cli():
    cli = MagicMock()
    # Mock data managers
    cli.target_mgr = MagicMock()
    cli.tool_mgr = MagicMock()
    cli.wordlist_mgr = MagicMock()
    cli.report_mgr = MagicMock()
    cli.workflow_mgr = MagicMock()
    cli.parser_mgr = MagicMock()
    cli.library_mgr = MagicMock()
    cli.preset_mgr = MagicMock()
    
    # Setup some defaults
    cli.target_mgr.list_all.return_value = []
    cli.tool_mgr.list_all.return_value = []
    
    return cli

@pytest.fixture
def client(mock_cli):
    # Import main UI module to register routes
    # This might have side effects, but usually safe if just defining routes
    try:
        from plugins.web_ui import pwnity_ui
    except ImportError:
        # If it fails due to missing dependencies in test env (unlikely if venv used), we might need mocks
        pass

    # Force set our mock CLI
    app_instance.set_cli(mock_cli)
    
    app_instance.app.config['TESTING'] = True
    
    # Disable CSRF if present (unlikely in this API)
    
    with app_instance.app.test_client() as client:
        yield client
