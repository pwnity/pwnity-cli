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

# tests/test_cli_sessions.py
import pytest
from modules.cli_sessions import CLISession, CLISessionManager
from modules.services import log

# --- Tests for CLISession ---

def test_session_initialization():
    """Tests that a new session is created with default values."""
    session = CLISession("test")
    assert session.name == "test"
    assert session.target is None
    assert session.tool is None
    assert session.proxy_settings == {}

def test_session_attribute_access():
    """Tests getting and setting session data via attributes."""
    session = CLISession("test")
    
    # Set attributes
    session.target = "test-server"
    session.proxy_settings = {"enabled": True}
    
    # Get attributes
    assert session.target == "test-server"
    assert session.proxy_settings["enabled"] is True

    # Test setting a non-existent attribute (should fail)
    with pytest.raises(AttributeError):
        session.non_existent_attr = "value"

def test_session_reset():
    """Tests that a session can be reset to its default state."""
    session = CLISession("test")
    session.target = "test-server"
    session.reset()
    assert session.target is None

def test_session_isolation():
    """Tests that two sessions are independent of each other."""
    session1 = CLISession("s1")
    session2 = CLISession("s2")

    session1.target = "server1"
    session2.target = "server2"

    assert session1.target == "server1"
    assert session2.target == "server2"

    # Also test proxy_settings, as it's a mutable dictionary
    session1.proxy_settings["host"] = "127.0.0.1"
    assert "host" not in session2.proxy_settings

# --- Tests for CLISessionManager ---

@pytest.fixture
def session_manager(monkeypatch):
    """Provides a clean CLISessionManager instance for each test."""
    # Suppress logger output for clean test runs
    import logging
    monkeypatch.setattr(log, 'log_value', logging.CRITICAL + 1)
    return CLISessionManager()

@pytest.fixture
def mock_cli(mocker, session_manager):
    """Provides a mock CLI instance with a session manager."""
    cli = mocker.MagicMock()
    cli.session_mgr = session_manager
    cli.session = None # Start with no active session
    cli.display_mgr = mocker.MagicMock()
    cli.poutput = mocker.MagicMock()
    return cli

def test_manager_new_session(session_manager):
    """Tests creating a new session."""
    session = session_manager.new("project-x")
    assert session is not None
    assert session.name == "project-x"
    assert session_manager.active == session
    assert "project-x" in session_manager.sessions

def test_manager_new_session_duplicate_fails(session_manager):
    """Tests that creating a session with a duplicate name fails."""
    session_manager.new("project-x")
    duplicate_session = session_manager.new("project-x")
    assert duplicate_session is None

def test_manager_switch_session(session_manager):
    """Tests switching between sessions."""
    s1 = session_manager.new("s1")
    s2 = session_manager.new("s2") # 'new' automatically switches
    assert session_manager.active == s2

    # Switch back to s1
    switched = session_manager.switch("s1")
    assert switched == s1
    assert session_manager.active == s1

def test_manager_switch_to_nonexistent_fails(session_manager):
    """Tests that switching to a non-existent session fails."""
    assert session_manager.switch("nonexistent") is None

def test_manager_destroy_session(session_manager):
    """Tests destroying a session."""
    session_manager.new("s1")
    session_manager.new("s2")
    
    assert "s1" in session_manager.sessions
    result = session_manager.destroy("s1")
    assert result is True
    assert "s1" not in session_manager.sessions
    # Active session should not be affected
    assert session_manager.active.name == "s2"

def test_manager_destroy_active_session(session_manager):
    """Tests that destroying the active session correctly updates the active pointer."""
    session_manager.new("s1")
    assert session_manager.active.name == "s1"

    session_manager.destroy("s1")
    assert session_manager.active is None

def test_manager_list_sessions(session_manager):
    """Tests listing all session names."""
    session_manager.new("s1")
    session_manager.new("s2")
    session_manager.new("s3")
    
    session_list = session_manager.list()
    assert sorted(session_list) == ["s1", "s2", "s3"]

# --- New tests for _cmd_* methods ---

def test_cmd_new(session_manager, mock_cli):
    """Tests the _cmd_new handler."""
    args = type('Args', (), {'name': 'new-project'})()
    session_manager._cmd_new(args, mock_cli)
    assert mock_cli.session is not None
    assert mock_cli.session.name == 'new-project'

def test_cmd_switch(session_manager, mock_cli):
    """Tests the _cmd_switch handler."""
    session_manager.new("s1")
    session_manager.new("s2")
    args = type('Args', (), {'name': 's1'})()
    session_manager._cmd_switch(args, mock_cli)
    assert mock_cli.session.name == 's1'

def test_cmd_list(session_manager, mock_cli):
    """Tests the _cmd_list handler."""
    session_manager.new("s1")
    session_manager.new("s2")
    session_manager._cmd_list(args=None, cli=mock_cli)
    mock_cli.display_mgr.display_session_list.assert_called_once_with(['s1', 's2'], 's2')

def test_cmd_destroy(session_manager, mock_cli):
    """Tests the _cmd_destroy handler."""
    s1 = session_manager.new("s1")
    mock_cli.session = s1 # Set s1 as active
    args = type('Args', (), {'name': 's1'})()
    session_manager._cmd_destroy(args, mock_cli)
    assert "s1" not in session_manager.sessions
    assert mock_cli.session is None # Active session should be cleared

def test_cmd_show(session_manager, mock_cli):
    """Tests the _cmd_show handler."""
    mock_cli.session = session_manager.new("s1")
    session_manager._cmd_show(args=None, cli=mock_cli)
    mock_cli.display_mgr.display_session_status.assert_called_once_with(mock_cli.session)