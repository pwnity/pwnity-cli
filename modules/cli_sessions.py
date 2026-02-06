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

# modules/cli_sessions.py
import copy
from modules.services import log
from .managers.base_manager import BaseManager

class CLISession:
    DEFAULTS = {
        "target": None,
        "tool": None,
        "wordlist": None,
        "report": None,
        "proxy_settings": {}
    }

    def __init__(self, name):
        self.name = name
        self._data = copy.deepcopy(self.DEFAULTS)

    def __getattr__(self, attr):
        """Allows access to session data as attributes (e.g., session.targets)."""
        # Direct access to __dict__ to avoid recursion if _data is not yet
        # initialized (e.g., during `copy.deepcopy` by cmd2).
        if '_data' in self.__dict__ and attr in self.__dict__['_data']:
            return self.__dict__['_data'][attr]

        # Important for compatibility with cmd2 and to ensure normal attribute behavior
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{attr}'")

    def __setattr__(self, attr, value):
        """Allows setting session data as attributes."""
        # Direct access to __dict__ to prevent recursion during the __init__ phase or with
        # `copy.deepcopy`.
        # Always allow 'name' and '_data' to be set directly on the object.
        if attr in ['name', '_data']:
            super().__setattr__(attr, value)
            return

        if '_data' in self.__dict__:
            _data = self.__dict__['_data']
            if attr in _data:
                _data[attr] = value
                return
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{attr}'. Cannot set new attributes.")

    def reset(self):
        self._data = copy.deepcopy(self.DEFAULTS)

class CLISessionManager(BaseManager):
    def __init__(self):
        self.sessions = {}
        self.active = None

    def _error(self, msg):
        log.error(msg)
        return None

    def new(self, name):
        if name in self.sessions:
            return self._error(f"Session '{name}' already exists.")
        self.sessions[name] = CLISession(name)
        self.active = self.sessions[name]
        log.info(f"Session '{name}' created and set active.")
        return self.active

    def switch(self, name):
        if name not in self.sessions:
            return self._error(f"Session '{name}' not found.")
        self.active = self.sessions[name]
        log.info(f"Switched to session '{name}'.")
        return self.active

    def destroy(self, name):
        if name not in self.sessions:
            return self._error(f"Session '{name}' not found.")
        del self.sessions[name]
        if self.active and self.active.name == name:
            self.active = None
        log.info(f"Session '{name}' destroyed.")
        return True

    def list(self):
        return list(self.sessions.keys())

    def _cmd_new(self, args, cli):
        """Handles 'session new'."""
        cli.session = self.new(args.name)

    def _cmd_switch(self, args, cli):
        """Handles 'session switch'."""
        cli.session = self.switch(args.name)

    def _cmd_list(self, args, cli):
        """Handles 'session list'."""
        all_sessions = self.list()
        active_session_name = self.active.name if self.active else None
        if not all_sessions:
            log.info("No sessions found.")
        else:
            cli.display_mgr.display_session_list(all_sessions, active_session_name)

    def _cmd_destroy(self, args, cli):
        """Handles 'session destroy'."""
        if self.destroy(args.name):
            if not cli.session or cli.session.name == args.name:
                cli.session = self.active

    def _cmd_show(self, args, cli):
        """Handles 'session show'."""
        cli.display_mgr.display_session_status(cli.session)

    def _cmd_export(self, args, cli):
        """Generates the 'load' commands for the current session."""
        session = cli.session
        if not session:
            log.warning("No active session.")
            return

        commands = []
        if session.target:
            commands.append(f"target load {session.target}")
        if session.tool:
            commands.append(f"tool load {session.tool}")
        if session.wordlist:
            commands.append(f"wordlist load {session.wordlist}")
        if session.report:
            commands.append(f"report load {session.report}")

        log.header(f"Export for current session '{session.name}'")
        if commands:
            cli.poutput("\n".join(commands))
        else:
            log.info("Session is empty (nothing is loaded).")
