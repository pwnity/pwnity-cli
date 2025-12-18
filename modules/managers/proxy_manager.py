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

# modules/managers/proxy_manager.py
from ..services import log, config
from .base_manager import BaseManager
import tempfile
import os
class ProxyManager(BaseManager):
    def set_enabled(self, session, status: bool):
        """Enables or disables the proxy for a given session."""
        if not session:
            log.error("Cannot manage proxy settings without an active session.")
            return False
        session.proxy_settings['enabled'] = status
        log.success(f"Proxy {'enabled' if status else 'disabled'} for the current session.")
        return True

    def _cmd_on(self, args, cli):
        """Handles the 'proxy on' subcommand."""
        return self.set_enabled(cli.session, True)

    def _cmd_off(self, args, cli):
        """Handles the 'proxy off' subcommand."""
        return self.set_enabled(cli.session, False)

    def set_config(self, session, key: str, value: str):
        if not session:
            log.error("Cannot manage proxy settings without an active session.")
            return
        
        valid_keys = ['wrapper_command', 'wrapper_options', 'wrapper_needs_sudo', 'type', 'host', 'port', 'username', 'password', 'wrapper_template']
        if key not in valid_keys:
            log.error(f"Invalid key '{key}'.")
            log.prompt(f"Valid keys for 'set' are: {', '.join(valid_keys)}")
            return
        
        session.proxy_settings[key] = value
        log.success(f"Proxy setting '{key}' set for the current session.")

    def _cmd_set(self, args, cli):
        """Handles the 'proxy set' subcommand."""
        if not cli.session:
            log.error("Cannot manage proxy settings without an active session.")
            return
        if not args.key or not args.value:
            log.error("Invalid command. Expected: proxy set <key> <value>")
            log.prompt("Example: proxy set host 127.0.0.1")
            return
        
        # The key is now a dedicated argument, and value is the remainder.
        self.set_config(cli.session, args.key, " ".join(args.value))

    def reset_config(self, session, key: str):
        """Resets a proxy setting for a given session."""
        if not session:
            log.error("Cannot manage proxy settings without an active session.")
            return
        
        all_proxy_keys = ['enabled', 'wrapper_command', 'wrapper_options', 'wrapper_needs_sudo', 'type', 'host', 'port', 'username', 'password', 'wrapper_template']
        if key == 'all':
            session.proxy_settings.clear()
            log.success("All session-specific proxy settings have been reset to global defaults.")
        elif key in all_proxy_keys:
            if key in session.proxy_settings:
                del session.proxy_settings[key]
                log.success(f"Session setting '{key}' has been reset to the global default.")
            else:
                log.info(f"Setting '{key}' was not set in the session. It already uses the global default.")
        else:
            log.error(f"Invalid key '{key}' to reset.")
            log.prompt(f"Valid keys are: {', '.join(all_proxy_keys)}, or 'all'.")

    def _cmd_reset(self, args, cli):
        """Handles the 'proxy reset' subcommand."""
        self.reset_config(cli.session, args.key)

    def get_status_data(self, session):
        """
        Collects all data required to display the proxy status.
        Returns a dictionary containing global, session, and effective settings.
        """
        if not session:
            return None
        
        global_settings = config.get_section("PROXY")
        session_settings = session.proxy_settings
        effective_config = self.get_effective_config(session)
        return {
            "global_settings": global_settings,
            "session_settings": session_settings,
            "effective_config": effective_config,
        }

    def _cmd_show(self, args, cli):
        """Handles the 'proxy show' subcommand."""
        if not cli.session:
            log.error("Cannot show proxy status without an active session.")
            return
        status_data = self.get_status_data(cli.session)
        if status_data:
            cli.display_mgr.display_proxy_status(**status_data)
        else:
            log.error("Cannot show proxy status without an active session.") # Should not happen if session exists

    def get_placeholder_config(self, session):
        """
        Returns the proxy configuration that *would* be effective if the proxy were enabled.
        This is used to display placeholders even when the proxy is off.
        """
        # This logic must mirror get_effective_config to ensure consistency,
        # but without the final check for the 'enabled' flag at the end.
        global_proxy_settings = config.get_section("PROXY") or {}
        session_proxy_settings = session.proxy_settings if session else {}

        placeholder_config = {}
        keys_to_check = ['wrapper_command', 'wrapper_options', 'wrapper_needs_sudo', 'type', 'host', 'port', 'username', 'password', 'wrapper_template']

        for key in keys_to_check:
            session_val = session_proxy_settings.get(key)
            if session_val is not None:
                placeholder_config[key] = session_val
            else:
                placeholder_config[key] = global_proxy_settings.get(key.upper())

        # Also determine the 'enabled' status for the placeholder.
        session_enabled_val = session_proxy_settings.get('enabled')
        if session_enabled_val is not None:
            placeholder_config['enabled'] = session_enabled_val
        else:
            placeholder_config['enabled'] = str(global_proxy_settings.get("ENABLED", "false")).lower() in ('true', '1', 'yes')

        # Ensure boolean conversion for wrapper_needs_sudo
        sudo_val = placeholder_config.get('wrapper_needs_sudo')
        if not isinstance(sudo_val, bool):
            placeholder_config['wrapper_needs_sudo'] = str(sudo_val).lower() in ('true', '1', 'yes')

        return placeholder_config

    def get_effective_config(self, session):
        global_proxy_settings = config.get_section("PROXY")
        session_proxy_settings = session.proxy_settings if session else {}

        # Determine the final 'enabled' status, with session settings taking precedence
        session_enabled_val = session_proxy_settings.get('enabled')
        if session_enabled_val is not None:
            is_enabled = session_enabled_val
        else:
            is_enabled = str(global_proxy_settings.get("ENABLED", "false")).lower() in ('true', '1', 'yes')

        if not is_enabled:
            return None

        effective_config = {}
        keys_to_check = ['wrapper_command', 'wrapper_options', 'wrapper_needs_sudo', 'type', 'host', 'port', 'username', 'password', 'wrapper_template']

        for key in keys_to_check:
            # Session settings (e.g., from 'proxy set host ...') take precedence.
            session_val = session_proxy_settings.get(key)
            if session_val is not None:
                effective_config[key] = session_val
            else: # Fallback to global settings from config.json
                effective_config[key] = global_proxy_settings.get(key.upper())

        sudo_val = effective_config.get('wrapper_needs_sudo')
        if not isinstance(sudo_val, bool):
            effective_config['wrapper_needs_sudo'] = str(sudo_val).lower() in ('true', '1', 'yes')

        return effective_config