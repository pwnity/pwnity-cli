# modules/managers/config_manager.py
from .base_manager import BaseManager
from ..services import log, config

class ConfigManager(BaseManager):
    def __init__(self):
        # ConfigManager doesn't manage files in a directory, it interacts with the config service.
        # So, no call to super().__init__ with a folder is needed.
        pass

    def _get_entity_type(self):
        return "Configuration"

    def _cmd_list(self, args, cli):
        """Handles 'config list'."""
        all_config = config.get_all_data()
        cli.display_mgr.display_config(all_config)

    def _cmd_get(self, args, cli):
        """Handles 'config get'."""
        if '.' not in args.key:
            log.error("Invalid key format. Expected: SECTION.KEY (e.g., PROXY.HOST)")
            return
        section, key = args.key.split('.', 1)
        value = config.get_parameter(section.upper(), key)
        if value is not None:
            cli.poutput(str(value))
        else:
            log.error(f"Configuration key '{args.key}' not found.")

    def _cmd_set(self, args, cli):
        """Handles 'config set'."""
        if '.' not in args.key:
            log.error("Invalid key format. Expected: SECTION.KEY (e.g., PROXY.PORT)")
            return
        section, key = args.key.split('.', 1)
        value = " ".join(args.value)
        if config.set_parameter(section.upper(), key, value):
            if config.save():
                log.success(f"Configuration updated: [{section.upper()}].{key} = {value}")
            else:
                log.error(f"Failed to save configuration file.")
        else:
            log.error(f"Failed to set configuration key '{args.key}'. Check if the value is of the correct type (e.g., integer for PORT).")

    def get_all_data(self):
        """Returns the entire configuration dictionary."""
        return config.get_all_data()