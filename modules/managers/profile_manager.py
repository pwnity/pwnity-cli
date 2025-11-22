# modules/managers/profile_manager.py
import json
import os
from modules.services import log, config
from rich.table import Table
from rich.panel import Panel

class ProfileManager:
    def __init__(self):
        # Use get_parameter for consistency and testability.
        self.profile_file = config.get_parameter("DIRS", "PROFILE_FILE", "etc/profile.json")
        
        profile_dir = os.path.dirname(self.profile_file)
        if profile_dir:
            os.makedirs(profile_dir, exist_ok=True)
            
        self.data = self._load_from_file()

    def _load_from_file(self):
        """Loads the profile from the JSON file."""
        if os.path.exists(self.profile_file):
            try:
                with open(self.profile_file, "r") as f:
                    return json.load(f)
            except json.JSONDecodeError:
                log.error(f"Error parsing profile file '{self.profile_file}'. Creating an empty profile.")
                return {}
        return {}

    def _save(self):
        """Saves the current profile to the JSON file."""
        try:
            with open(self.profile_file, "w") as f:
                json.dump(self.data, f, indent=2)
        except Exception as e:
            log.error(f"Error saving profile to '{self.profile_file}': {e}")

    def load(self, name=None):
        """
        Compatibility method for the placeholder system.
        Always returns the entire profile data dict, ignoring the name.
        """
        return self.data

    def update(self, key, value):
        """Updates a key-value pair in the profile."""
        self.data[key] = value
        self._save()
        log.success(f"Profile setting '{key}' updated.")

    def delete(self, key, silent=False):
        """Deletes a key from the profile."""
        if key in self.data:
            del self.data[key]
            self._save()
            if not silent: log.success(f"Profile setting '{key}' deleted.")
        else:
            if not silent: log.warning(f"Profile setting '{key}' not found.")

    def list_all(self):
        """Lists all keys in the profile (for autocompletion)."""
        return list(self.data.keys())

    def dispatch(self, subcommand, args, cli):
        """Dispatches a subcommand to a handler."""
        # If no subcommand is given, show the help for the profile command.
        if not subcommand:
            cli.help_mgr.show_help_profile()
            return True

        handler_method_name = f"_cmd_{subcommand}"
        handler = getattr(self, handler_method_name, None)

        if callable(handler):
            handler(args, cli)
            return True
        return False

    def _cmd_update(self, args, cli):
        """Handles the 'update' subcommand."""
        if len(args.update_args) < 2:
            log.error("Invalid command. Expected: profile update <key> <value>")
            return
        key = args.update_args[0]
        value = " ".join(args.update_args[1:])
        self.update(key, value)

    def _cmd_delete(self, args, cli):
        """Handles the 'delete' subcommand."""
        self.delete(args.key, silent=False)

    def _cmd_show(self, args, cli):
        """Handles the 'show' subcommand."""
        if not self.data:
            log.info("No profile settings configured.")
            return
        table = Table(title="Global Profile Settings", box=None, show_header=False)
        table.add_column(style="bold blue", no_wrap=True)
        table.add_column(style="green")
        for key, value in sorted(self.data.items()):
            table.add_row(key, str(value))
        panel = Panel(table, border_style="dim", expand=False)
        cli.console.print(panel)