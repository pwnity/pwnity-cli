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

# modules/config_parser.py
import os
import json

class ConfigParser:
    def __init__(self, config_path=None):
        # Prioritize environment variable for testability
        env_config_path = os.environ.get('pwnity_CONFIG_PATH')
        if env_config_path and os.path.exists(env_config_path):
            self.config_path = env_config_path
        elif config_path and os.path.exists(config_path):
            self.config_path = config_path # Fallback to provided path
        else:
            # Fallback to the default path if no custom path is provided or if it doesn't exist
            self.config_path = os.path.join(os.path.dirname(__file__), "..", "etc", "config.json")
        
        self._config = self._load()

    def _load(self):
        """Loads the configuration from the JSON file."""
        if not os.path.exists(self.config_path):
            print(f"[ERROR] Config file not found at {self.config_path}")
            return {}
        try:
            with open(self.config_path, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"[ERROR] Failed to load or parse config.json: {e}")
            return {}

    def save(self):
        """Saves the current in-memory configuration to the file."""
        try:
            with open(self.config_path, 'w') as f:
                json.dump(self._config, f, indent=2)
            return True
        except IOError as e:
            print(f"[ERROR] Failed to save config.json: {e}")
            return False

    def get_parameter(self, section, key, fallback=None):
        """Gets a single parameter from a section."""
        return self._config.get(section, {}).get(key, fallback)

    def get_section(self, section):
        """Gets an entire section as a dictionary."""
        return self._config.get(section, {})

    def get_loot_types(self):
        """Retrieves loot types from the config file as a list."""
        return self.get_parameter("GLOBAL", "LOOT_TYPES", fallback=[])

    def set_parameter(self, section, key, value):
        """
        Sets a parameter in the in-memory config. Does NOT save to file.
        Returns True on success, False on failure.
        """
        if section not in self._config:
            self._config[section] = {}
        
        original_value = self._config[section].get(key)
        
        # Try to auto-convert type based on existing value
        if isinstance(original_value, bool):
            new_value = str(value).lower() in ['true', '1', 'yes', 'on']
        elif isinstance(original_value, int):
            try:
                new_value = int(value)
            except ValueError:
                return False # Let the caller log the error
        else:
            new_value = value

        self._config[section][key] = new_value
        return True

    def get_all_data(self):
        """Returns the entire configuration dictionary."""
        return self._config