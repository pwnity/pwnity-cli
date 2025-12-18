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

# tests/test_config_parser.py
import pytest
import json
from modules.config_parser import ConfigParser

@pytest.fixture
def temp_config_file(tmp_path):
    """Creates a temporary config.json file with some default data."""
    config_content = {
        "GLOBAL": {
            "DEBUG_LEVEL": "INFO",
            "HISTORY_FILE": "data/.pwnity_history"
        },
        "PROXY": {
            "ENABLED": False,
            "HOST": "127.0.0.1",
            "PORT": 8080
        }
    }
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps(config_content, indent=2))
    return str(config_file)

@pytest.fixture
def config_parser(temp_config_file, monkeypatch):
    """Provides a ConfigParser instance that uses the temporary config file."""
    # Patch the __init__ method to use our temporary file path
    monkeypatch.setattr(ConfigParser, "__init__", lambda self: setattr(self, 'config_path', temp_config_file) or setattr(self, '_config', self._load()))
    return ConfigParser()

def test_load_config(config_parser):
    """Tests that the configuration is loaded correctly from the file."""
    assert config_parser._config is not None
    assert "GLOBAL" in config_parser._config
    assert config_parser._config["PROXY"]["HOST"] == "127.0.0.1"

def test_get_parameter_and_section(config_parser):
    """Tests the getter methods for sections and individual parameters."""
    # Test get_parameter
    assert config_parser.get_parameter("PROXY", "HOST") == "127.0.0.1"
    assert config_parser.get_parameter("PROXY", "PORT") == 8080
    # Test fallback value
    assert config_parser.get_parameter("PROXY", "NON_EXISTENT", "fallback") == "fallback"
    assert config_parser.get_parameter("NON_EXISTENT_SECTION", "KEY", "fallback") == "fallback"

    # Test get_section
    proxy_section = config_parser.get_section("PROXY")
    assert isinstance(proxy_section, dict)
    assert proxy_section["HOST"] == "127.0.0.1"

def test_set_parameter_and_save(config_parser, temp_config_file):
    """
    Tests setting parameters with type conversion and saving them to the file.
    """
    # 1. Update an existing string value
    assert config_parser.set_parameter("PROXY", "HOST", "localhost") is True
    assert config_parser.get_parameter("PROXY", "HOST") == "localhost"

    # 2. Update an existing boolean value (with string input)
    assert config_parser.set_parameter("PROXY", "ENABLED", "true") is True
    assert config_parser.get_parameter("PROXY", "ENABLED") is True

    # 3. Update an existing integer value (with string input)
    assert config_parser.set_parameter("PROXY", "PORT", "9090") is True
    assert config_parser.get_parameter("PROXY", "PORT") == 9090

    # 4. Add a new key to an existing section
    assert config_parser.set_parameter("PROXY", "TYPE", "socks5") is True
    assert config_parser.get_parameter("PROXY", "TYPE") == "socks5"

    # 5. Add a new section and key
    assert config_parser.set_parameter("NEW_SECTION", "NEW_KEY", "new_value") is True
    assert config_parser.get_parameter("NEW_SECTION", "NEW_KEY") == "new_value"

    # 6. Save all changes to the file
    assert config_parser.save() is True

    # 7. Read the file directly and verify the changes
    with open(temp_config_file, 'r') as f:
        saved_data = json.load(f)
    
    assert saved_data["PROXY"]["HOST"] == "localhost"
    assert saved_data["PROXY"]["ENABLED"] is True
    assert saved_data["PROXY"]["PORT"] == 9090
    assert saved_data["PROXY"]["TYPE"] == "socks5"
    assert saved_data["NEW_SECTION"]["NEW_KEY"] == "new_value"

def test_set_parameter_invalid_type(config_parser):
    """Tests that setting a parameter with a wrong type fails correctly."""
    # Try to set a string value for an integer parameter
    assert config_parser.set_parameter("PROXY", "PORT", "not-a-number") is False
    # The original value should remain unchanged
    assert config_parser.get_parameter("PROXY", "PORT") == 8080

def test_parser_handles_missing_file(tmp_path, monkeypatch):
    """
    Tests that the parser initializes with an empty config if the file is missing,
    without crashing.
    """
    missing_file_path = tmp_path / "nonexistent.json"
    monkeypatch.setattr(ConfigParser, "__init__", lambda self: setattr(self, 'config_path', str(missing_file_path)) or setattr(self, '_config', self._load()))
    
    parser = ConfigParser()
    assert parser._config == {}
    # Getters should return fallback values
    assert parser.get_parameter("ANY", "KEY", "default") == "default"

def test_parser_handles_corrupt_file(tmp_path, monkeypatch):
    """
    Tests that the parser initializes with an empty config if the JSON file
    is corrupted.
    """
    corrupt_file = tmp_path / "corrupt.json"
    corrupt_file.write_text("{'invalid-json':,}") # Write malformed JSON
    monkeypatch.setattr(ConfigParser, "__init__", lambda self: setattr(self, 'config_path', str(corrupt_file)) or setattr(self, '_config', self._load()))

    parser = ConfigParser()
    assert parser._config == {}