# tests/test_profile_manager.py
import pytest
import json
from modules.managers.profile_manager import ProfileManager
from modules.services import config, log

@pytest.fixture
def profile_manager(tmp_path, monkeypatch):
    """
    Provides a ProfileManager instance that reads/writes to a temporary file.
    """
    profile_file = tmp_path / "profile.json"
    
    # Mock config to point to our temporary file
    monkeypatch.setattr(config, 'get_parameter', lambda section, key, fallback=None: str(profile_file) if key == "PROFILE_FILE" else fallback)

    # Suppress logger output
    import logging
    monkeypatch.setattr(log, 'log_value', logging.CRITICAL + 1)

    # The manager will be re-initialized for each test, ensuring a clean state.
    return ProfileManager()

@pytest.fixture
def mock_cli_for_profile(mocker):
    """Provides a mock CLI instance for profile tests."""
    cli = mocker.MagicMock()
    cli.session = mocker.MagicMock()
    cli.help_mgr = mocker.MagicMock()
    cli.console = mocker.MagicMock()
    return cli

def test_profile_update_and_save(profile_manager, tmp_path):
    """
    Tests that updating a profile setting correctly modifies the in-memory
    data and saves it to the JSON file.
    """
    profile_file = tmp_path / "profile.json"

    # 1. Update a setting
    profile_manager.update("lhost", "10.10.14.5")
    profile_manager.update("user_agent", "MyTestAgent/1.0")

    # 2. Check in-memory data
    assert profile_manager.data["lhost"] == "10.10.14.5"

    # 3. Check that the data was saved to the file
    assert profile_file.is_file()
    with open(profile_file, 'r') as f:
        saved_data = json.load(f)
    assert saved_data["lhost"] == "10.10.14.5"
    assert saved_data["user_agent"] == "MyTestAgent/1.0"

def test_profile_delete(profile_manager):
    """
    Tests that deleting a profile setting removes it from the data
    and saves the change.
    """
    # 1. Add some initial data
    profile_manager.update("lhost", "10.10.14.5")
    profile_manager.update("lport", "9001")
    assert "lport" in profile_manager.data

    # 2. Delete a setting
    profile_manager.delete("lport")

    # 3. Check that it's gone from memory and the file
    assert "lport" not in profile_manager.data
    # Reload from file to confirm it was saved
    reloaded_data = profile_manager._load_from_file()
    assert "lport" not in reloaded_data
    assert "lhost" in reloaded_data # Ensure other keys were not affected

def test_profile_load_for_placeholders(profile_manager):
    """
    Tests that the `load` method correctly returns the entire profile
    for the placeholder system.
    """
    profile_manager.update("lhost", "10.10.14.5")
    
    # The `load` method in ProfileManager ignores the name argument
    loaded_data = profile_manager.load(name="any_name")
    
    assert isinstance(loaded_data, dict)
    assert loaded_data["lhost"] == "10.10.14.5"

def test_profile_handles_corrupt_file(tmp_path, monkeypatch):
    """
    Tests that the manager initializes with an empty profile if the
    JSON file is corrupted, preventing a crash on startup.
    """
    profile_file = tmp_path / "profile.json"
    profile_file.write_text("{'invalid-json':,}") # Write malformed JSON

    # Mock config to point to our corrupt file
    monkeypatch.setattr(config, 'get_parameter', lambda section, key, fallback=None: str(profile_file))

    # Initialization should not raise an exception
    manager = ProfileManager()
    
    # The manager's data should be an empty dictionary
    assert manager.data == {}

def test_dispatch_shows_help_if_no_subcommand(profile_manager, mock_cli_for_profile):
    """
    Tests that the dispatch method calls the help manager if no subcommand is provided.
    """
    # Simulate calling 'profile' with no subcommand
    profile_manager.dispatch(subcommand=None, args=None, cli=mock_cli_for_profile)
    mock_cli_for_profile.help_mgr.show_help_profile.assert_called_once()