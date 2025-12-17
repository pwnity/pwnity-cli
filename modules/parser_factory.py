# modules/parser_factory.py
import argparse
from modules import functions as pwn_functions
import sys
from .services import config, log

try:
    from rich_argparse import RichHelpFormatter
except ImportError:
    RichHelpFormatter = argparse.HelpFormatter # Fallback, pwnity.py will log an error.

class ChoicesProvider:
    """
    Helper class to provide choices for Argparse completers.
    This avoids deepcopy errors by only holding a reference to the manager.
    An instance of this class is a 'callable' that cmd2 can use as a `completer`.
    """
    def __init__(self, manager, method_name='list_all'):
        self.manager = manager
        self.method_name = method_name

    def __call__(self, *args, **kwargs):
        list_method = getattr(self.manager, self.method_name)
        return list_method()

class ParserFactory:
    def __init__(self, target_mgr, tool_mgr, wordlist_mgr, preset_mgr, session_mgr, job_mgr, profile_mgr, help_mgr, manual_mgr, parser_mgr=None, logbook_mgr=None, report_mgr=None, revshell_mgr=None, heartbeat_mgr=None, library_mgr=None, workflow_mgr=None, config_mgr=None):
        self.target_mgr = target_mgr
        self.tool_mgr = tool_mgr
        self.wordlist_mgr = wordlist_mgr
        self.preset_mgr = preset_mgr
        self.session_mgr = session_mgr
        self.job_mgr = job_mgr
        self.profile_mgr = profile_mgr
        self.help_mgr = help_mgr
        self.manual_mgr = manual_mgr
        self.logbook_mgr = logbook_mgr
        self.report_mgr = report_mgr
        self.revshell_mgr = revshell_mgr
        self.heartbeat_mgr = heartbeat_mgr
        self.parser_mgr = parser_mgr
        self.workflow_mgr = workflow_mgr
        self.config_mgr = config_mgr
        self.library_mgr = library_mgr
        self.formatter = RichHelpFormatter

    def populate_all_parsers(self, parsers):
        """Populates the existing parser objects with subcommands and arguments."""
        target_completer = ChoicesProvider(self.target_mgr)
        tool_completer = ChoicesProvider(self.tool_mgr)
        wordlist_completer = ChoicesProvider(self.wordlist_mgr)
        preset_completer = ChoicesProvider(self.preset_mgr)
        session_completer = ChoicesProvider(self.session_mgr, method_name='list')
        jobs_completer = ChoicesProvider(self.job_mgr, method_name='list_jobs') # Assumption: job_mgr has list_jobs
        logbook_completer = ChoicesProvider(self.logbook_mgr, method_name='list_all') if self.logbook_mgr else None
        profile_key_completer = ChoicesProvider(self.profile_mgr)
        library_completer = ChoicesProvider(self.library_mgr) if self.library_mgr else None

        if "target" in parsers:
            self._populate_target_parser(parsers["target"], target_completer)
        if "tool" in parsers:
            self._populate_tool_parser(parsers["tool"], tool_completer)
        if "wordlist" in parsers:
            self._populate_wordlist_parser(parsers["wordlist"], wordlist_completer)
        if "preset" in parsers:
            self._populate_preset_parser(parsers["preset"], preset_completer)
        if "jobs" in parsers:
            self._populate_jobs_parser(parsers["jobs"])
        if "session" in parsers:
            self._populate_session_parser(parsers["session"], session_completer)
        if "profile" in parsers:
            self._populate_profile_parser(parsers["profile"], profile_key_completer)
        if "proxy" in parsers:
            self._populate_proxy_parser(parsers["proxy"])
        if "overview" in parsers:
            self._populate_overview_parser(parsers["overview"])
        if "note" in parsers:
            self._populate_note_parser(parsers["note"])
        if "loot" in parsers:
            self._populate_loot_parser(parsers["loot"])
        if "placeholders" in parsers:
            self._populate_placeholders_parser(parsers["placeholders"])
        if "config" in parsers:
            self._populate_config_parser(parsers["config"])
        if "manual" in parsers:
            self._populate_manual_parser(parsers["manual"])
        if "parser" in parsers and self.parser_mgr:
            self._populate_parser_parser(parsers["parser"], logbook_completer)
        if "logbook" in parsers and self.logbook_mgr:
            self._populate_logbook_parser(parsers["logbook"], logbook_completer)
        if "report" in parsers and self.report_mgr:
            self._populate_report_parser(parsers["report"])
        if "revshell" in parsers and self.revshell_mgr:
            self._populate_revshell_parser(parsers["revshell"])
        if "heartbeat" in parsers and self.heartbeat_mgr:
            self._populate_heartbeat_parser(parsers["heartbeat"])
        if "library" in parsers and self.library_mgr:
            self._populate_library_parser(parsers["library"], library_completer)
        if "workflow" in parsers and self.workflow_mgr:
            self._populate_workflow_parser(parsers["workflow"])
        if "pwn" in parsers:
            self._populate_pwn_parser(parsers["pwn"])

    def _populate_alias_parser(self, parser):
        """Populates the parser for the built-in 'alias' command."""
        # This is a special case. cmd2 has its own subcommands for alias
        # (create, list, delete). We just define the top-level parser
        # here to attach our custom help, but we do NOT add our own subparsers
        # to avoid conflicts.
        pass # Intentionally left blank

    def _add_custom_help(self, parser, subcommand_name):
        """Attaches the help manager and the custom help action to a parser."""
        from modules.managers.help_manager import RichSubcommandHelpAction
        # The main command name is stored in the parser's 'prog' attribute
        command_name = parser.prog.split()[0]
        parser.add_argument('-h', '--help', action=RichSubcommandHelpAction,
                            command_name=command_name, subcommand_name=subcommand_name,
                            help='Show this help message and exit.')

    def _build_common_subparsers(self, subparsers, choices_provider, entity_name_singular, entity_name_plural, exclude=None):
        if exclude is None:
            exclude = []

        if "add" not in exclude:
            add_parser = subparsers.add_parser("add",
                                               help=f"Create a new {entity_name_singular}.",
                                               description=f"Creates a new, empty {entity_name_singular} identified by a unique name.",
                                               formatter_class=self.formatter, add_help=False)
            self._add_custom_help(add_parser, "add")
            add_parser.add_argument("name", help=f"A unique name for the new {entity_name_singular}.")

        # Add a 'help' subcommand to all common parsers for consistency (e.g., 'tool help')
        help_parser = subparsers.add_parser("help",
                                            help=f"Show help for the {entity_name_singular} command.",
                                            description=f"Displays detailed help for the main {entity_name_singular} command.",
                                            formatter_class=self.formatter, add_help=False)
        self._add_custom_help(help_parser, "help")

        if "rename" not in exclude:
            rename_parser = subparsers.add_parser("rename",
                                                  help=f"Rename a {entity_name_singular}.",
                                                  description=f"Renames a {entity_name_singular} from <old_name> to <new_name>. This updates the configuration file and the internal 'name' field.",
                                                  formatter_class=self.formatter, add_help=False)
            self._add_custom_help(rename_parser, "rename")
            rename_parser.add_argument("old_name", help=f"The current name of the {entity_name_singular}.", choices_provider=choices_provider)
            rename_parser.add_argument("new_name", help=f"The new name for the {entity_name_singular}.")

        if "copy" not in exclude:
            copy_parser = subparsers.add_parser("copy",
                                                help=f"Copy a {entity_name_singular}.",
                                                description=f"Copies a {entity_name_singular} from <source_name> to <dest_name>.",
                                                formatter_class=self.formatter, add_help=False)
            self._add_custom_help(copy_parser, "copy")
            copy_parser.add_argument("source_name", help=f"The name of the {entity_name_singular} to copy.", choices_provider=choices_provider)
            copy_parser.add_argument("dest_name", help=f"The new name for the copied {entity_name_singular}.")

        if "update" not in exclude:
            update_parser = subparsers.add_parser("update",
                                                  help=f"Update an existing {entity_name_singular} (e.g., URL, path, parameters).",
                                                  description=f"Updates a field of an existing {entity_name_singular}. For example: 'update <name> url http://new.url' or 'update <name> sudo true'.",
                                                  formatter_class=self.formatter, add_help=False)
            self._add_custom_help(update_parser, "update")
            update_parser.add_argument("name", help=f"The name of the {entity_name_singular} to update.", choices_provider=choices_provider)
            update_parser.add_argument("update_args", nargs=argparse.REMAINDER, help="The field and value to update (e.g., 'url https://example.com').")
        if "delete" not in exclude:
            delete_parser = subparsers.add_parser("delete",
                                                  help=f"Delete a {entity_name_singular} or a field from it.",
                                                  description=f"Deletes a field from a {entity_name_singular}, or the entire object if no field is specified. Use 'destroy' to remove the file completely.",
                                                  formatter_class=self.formatter, add_help=False)
            self._add_custom_help(delete_parser, "delete")
            delete_parser.add_argument("name", help=f"The name of the {entity_name_singular} to modify.", choices_provider=choices_provider)
            delete_parser.add_argument("field", nargs="?", default=None, help="Optional: Name of the field to delete. If omitted, the entire object is deleted.")
        if "destroy" not in exclude:
            destroy_parser = subparsers.add_parser("destroy",
                                                   help=f"Completely delete a {entity_name_singular} and its configuration file.",
                                                   description=f"Completely deletes a {entity_name_singular} and its configuration file. This action cannot be undone.",
                                                   formatter_class=self.formatter, add_help=False)
            self._add_custom_help(destroy_parser, "destroy")
            destroy_parser.add_argument("name", help=f"The name of the {entity_name_singular} to destroy.", choices_provider=choices_provider)
        if "list" not in exclude:
            list_parser = subparsers.add_parser("list",
                                                help=f"List all available {entity_name_plural}.",
                                                description=f"Lists the names of all available {entity_name_plural} found in the configuration directory.",
                                                formatter_class=self.formatter, add_help=False)
            self._add_custom_help(list_parser, "list")
        if "load" not in exclude:
            load_parser = subparsers.add_parser("load",
                                                help=f"Load a {entity_name_singular} into the active session.",
                                                description=f"Loads a {entity_name_singular} into the current session, making it available for other commands like 'pwn'.",
                                                formatter_class=self.formatter, add_help=False)
            self._add_custom_help(load_parser, "load")
            load_parser.add_argument("name", help=f"The name of the {entity_name_singular} to load.", choices_provider=choices_provider)
        if "show" not in exclude:
            show_parser = subparsers.add_parser("show",
                                                help=f"Show details for a {entity_name_singular}.",
                                                description=f"Displays all stored information for a specific {entity_name_singular} in a formatted table.",
                                                formatter_class=self.formatter, add_help=False)
            self._add_custom_help(show_parser, "show")
            # Make 'name' optional. If omitted, the loaded entity will be shown.
            show_parser.add_argument("name", nargs='?', default=None,
                                     help=f"Name of the {entity_name_singular} to show. If omitted, shows the loaded {entity_name_singular}.",
                                     choices_provider=choices_provider)
            show_parser.add_argument("field", nargs="?", default=None, help="Optional: Display only the value of this specific field.")
        if "unload" not in exclude:
            unload_parser = subparsers.add_parser("unload",
                                                  help=f"Unload the current {entity_name_singular} from the session.",
                                                  description=f"Unloads the currently active {entity_name_singular} from the session, clearing it from the prompt.",
                                                  formatter_class=self.formatter, add_help=False)
            self._add_custom_help(unload_parser, "unload")

    def _populate_target_parser(self, parser, completer):
        subparsers = parser.add_subparsers(dest="subcommand", title="Available Actions", help="Target subcommands")
        self._build_common_subparsers(subparsers, completer, "Target", "Targets", exclude=['update', 'delete'])

        # Custom 'update' parser for targets to provide better examples
        update_parser = subparsers.add_parser("update",
                                              help="Update a target's field, especially its URL.",
                                              description="Updates a field of an existing Target. The 'url' field is special: it automatically parses the URL to extract IP, hostname, port, domain, etc.",
                                              formatter_class=self.formatter, add_help=False)
        self._add_custom_help(update_parser, "update")
        update_parser.add_argument("name", help="The name of the Target to update.", choices_provider=completer)
        update_parser.add_argument("update_args", nargs=argparse.REMAINDER, help="The field and value to update (e.g., 'url https://example.com').")
        update_parser.examples = [
            ("target update my-server url https://example.com:8443/path", "Sets the URL and extracts all related info."),
            ("target update my-server notes 'Initial reconnaissance target.'", "Adds or overwrites a custom field."),
            ("target update my-server ip 192.168.1.1", "Manually overrides the IP address.")
        ]

        # Custom 'delete' parser for targets to clarify its behavior
        delete_parser = subparsers.add_parser("delete",
                                              help="Delete a target's field or the entire target object.",
                                              description="Deletes a specific field from a target. If no field is specified, the entire target object and its file are deleted (this is the same as the 'destroy' command).",
                                              formatter_class=self.formatter, add_help=False)
        self._add_custom_help(delete_parser, "delete")
        delete_parser.add_argument("name", help="The name of the Target to modify.", choices_provider=completer)
        delete_parser.add_argument("field", nargs="?", default=None, help="Optional: The field to delete. If omitted, the entire target is deleted.")
        delete_parser.examples = [
            ("target delete my-server notes", "Deletes only the 'notes' field from the target."),
            ("target delete my-server", "Deletes the entire 'my-server' target and its file.")
        ]

        gather_parser = subparsers.add_parser("gather",
                                              help="Gather additional information about a target (DNS, WHOIS, etc.).",
                                              description="Actively gathers information about a target, such as DNS records, WHOIS data, or HTTP headers, and saves it to the target object.",
                                              formatter_class=self.formatter, add_help=False)
        self._add_custom_help(gather_parser, "gather")
        gather_parser.add_argument("name", help="Name of the target.", choices_provider=completer)
        gather_parser.add_argument("type", choices=['dns', 'mx', 'whois', 'http', 'geo', 'all'], help="The type of information to gather.")
        gather_parser.examples = [
            ("target gather my-server dns", "Gathers DNS records (A, AAAA, CNAME, etc.)."),
            ("target gather my-server geo", "Gathers Geo-IP information for the target's IP address."),
            ("target gather my-server all", "Gathers all available information.")
        ]

        fork_parser = subparsers.add_parser("fork-domain",
                                            help="Create a new target from the main domain of an existing target.",
                                            description="If the current target is a subdomain (e.g., 'sub.example.com'), this command creates a new, separate target for the main domain ('example.com').",
                                            formatter_class=self.formatter, add_help=False)
        self._add_custom_help(fork_parser, "fork-domain")
        fork_parser.add_argument("name", help="Name of the source target (with subdomain).", choices_provider=completer)
        fork_parser.examples = [("target fork-domain sub.example.com", "Creates a new target named 'example.com'.")]

        export_parser = subparsers.add_parser("export", aliases=['reverse'],
                                              help="Generate the commands to reconstruct a target.",
                                              description="Outputs a series of pwnity commands that can be used to recreate the specified target object, including its gathered data, notes, and loot.",
                                              formatter_class=self.formatter, add_help=False)
        self._add_custom_help(export_parser, "export")
        export_parser.add_argument("name", help="Name of the target to export.", choices_provider=completer)
        export_parser.examples = [("target export my-server", "Prints the commands to recreate 'my-server'.")]

    def _add_help_subcommand_to_parser(self, subparsers, entity_name_singular):
        """Helper to add a 'help' subcommand to a given subparsers object."""
        help_parser = subparsers.add_parser("help",
                                            # --- CORRECT FIX ---
                                            # Using `help=argparse.SUPPRESS` causes the ugly '==SUPPRESS==' output in cmd2's completion hints.
                                            # By omitting the `help` argument and setting `add_help=False`, we create a functional subcommand
                                            # that is completely hidden from the top-level help and completion lists, which is the desired behavior.
                                            add_help=False,
                                            description=f"Displays detailed help for the main {entity_name_singular} command.",
                                            formatter_class=self.formatter)
        self._add_custom_help(help_parser, "help")


    def _populate_tool_parser(self, parser, completer):
        subparsers = parser.add_subparsers(dest="subcommand", title="Available Actions", help="Tool subcommands")
        # Most subcommands are generic, but 'delete' and 'update' need special handling for tools.
        self._build_common_subparsers(subparsers, completer, "Tool", "Tools", exclude=['delete', 'update'])
        
        # Custom 'update' parser for tools
        update_parser = subparsers.add_parser("update",
                                              help="Update a tool's field, command, or parameter.",
                                              description="Updates a specific part of a tool's configuration. This can be a top-level field (like 'path' or 'sudo'), a new command, or a parameter for a command.",
                                              formatter_class=self.formatter, add_help=False)
        self._add_custom_help(update_parser, "update")
        update_parser.add_argument("name", help="The name of the tool to update.", choices_provider=completer)
        update_parser.add_argument("update_args", nargs=argparse.REMAINDER, help="The update instruction (e.g., 'sudo true', 'command <cmd_name>', or '<cmd_name> param <param_value>').")
        update_parser.examples = [
            ("tool update nmap sudo true", "Marks the tool to always run with sudo."),
            ("tool update nmap command stealth-scan", "Adds a new command named 'stealth-scan'."),
            ("tool update nmap stealth-scan param '-p-'", "Adds a parameter to the 'stealth-scan' command."),
            ("tool update nmap stealth-scan param 2 '-p 1-100'", "Updates the 2nd parameter of the command.")
        ]
        
        # Custom 'delete' parser for tools, offering more flexibility.
        delete_parser = subparsers.add_parser("delete",
                                              help="Delete a field, command, or parameter from a tool.",
                                              description="Deletes a specific part of a tool's configuration. Can delete a top-level field, a whole command, or a specific parameter from a command.",
                                              formatter_class=self.formatter, add_help=False)
        self._add_custom_help(delete_parser, "delete")
        delete_parser.add_argument("name", help="Name of the tool to modify.", choices_provider=completer)
        delete_parser.add_argument("delete_args", nargs=argparse.REMAINDER, help="What to delete (e.g., 'path' or '<cmd> param <param_value>').")
        delete_parser.examples = [
            ("tool delete nmap path", "Deletes the custom path, falling back to system PATH."),
            ("tool delete nmap stealth-scan", "Deletes the 'stealth-scan' command (shortcut)."),
            ("tool delete nmap command stealth-scan", "Deletes the 'stealth-scan' command (explicit)."),
            ("tool delete nmap stealth-scan param 2", "Deletes the 2nd parameter of the 'stealth-scan' command."),
        ]

        reorder_parser = subparsers.add_parser("reorder",
                                               help="Change the order of a parameter within a tool command.",
                                               description="Changes the position of a parameter within a tool's command. Useful for adjusting command-line argument order.",
                                               formatter_class=self.formatter, add_help=False)
        self._add_custom_help(reorder_parser, "reorder")
        reorder_parser.add_argument("name", help="Name of the tool.", choices_provider=completer)
        reorder_parser.add_argument("command_name", help="Name of the command.")
        reorder_parser.add_argument("old_index", type=int, help="The current position of the parameter (1-based).")
        reorder_parser.add_argument("new_index", type=int, help="The new position of the parameter (1-based).")
        reorder_parser.examples = [
            ("tool reorder nmap stealth-scan 3 1", "Moves the 3rd parameter to the 1st position.")
        ]

        export_parser = subparsers.add_parser("export", aliases=['reverse'],
                                              help="Generate the commands to reconstruct a tool.",
                                              description="Outputs a series of pwnity commands that can be used to recreate the specified tool, including its commands and parameters.",
                                              formatter_class=self.formatter, add_help=False)
        self._add_custom_help(export_parser, "export")
        export_parser.add_argument("name", help="Name of the tool to export.", choices_provider=completer)
        export_parser.examples = [("tool export nmap", "Prints the commands to recreate the 'nmap' tool.")]

    def _populate_wordlist_parser(self, parser, completer):
        subparsers = parser.add_subparsers(dest="subcommand", title="Available Actions", help="Wordlist subcommands")
        self._build_common_subparsers(subparsers, completer, "Wordlist", "Wordlists")
        export_parser = subparsers.add_parser("export", aliases=['reverse'],
                                              help="Generate the commands to reconstruct a wordlist.",
                                              description="Outputs the pwnity commands needed to recreate the specified wordlist reference.",
                                              formatter_class=self.formatter, add_help=False)
        self._add_custom_help(export_parser, "export")
        export_parser.add_argument("name", help="Name of the wordlist to export.", choices_provider=completer)
        export_parser.examples = [("wordlist export rockyou", "Prints the command to recreate the 'rockyou' wordlist.")]

    def _populate_preset_parser(self, parser, completer):
        subparsers = parser.add_subparsers(dest="subcommand", title="Available Actions", help="Preset subcommands")
        self._build_common_subparsers(subparsers, completer, "Preset", "Presets")
        save_parser = subparsers.add_parser("save",
                                            help="Save the current session as a new preset.",
                                            description="Saves the currently loaded target, tool, wordlist, and proxy settings as a named preset for quick loading in the future.",
                                            formatter_class=self.formatter, add_help=False)
        self._add_custom_help(save_parser, "save")
        save_parser.add_argument("name", help="Name for the new preset.")
        save_parser.examples = [
            ("preset save my-scan", "Saves the currently loaded items as a preset.")
        ]

        export_parser = subparsers.add_parser("export", aliases=['reverse'],
                                              help="Generate the commands stored in the preset.",
                                              description="Outputs the 'load' commands that are stored within the specified preset.",
                                              formatter_class=self.formatter, add_help=False)
        self._add_custom_help(export_parser, "export")
        export_parser.add_argument("name", help="Name of the preset to export.", choices_provider=completer)
        export_parser.examples = [("preset export my-scan", "Prints the load commands stored in the preset.")]

    def _populate_profile_parser(self, parser, completer):
        """Populates the parser for the global profile."""
        subparsers = parser.add_subparsers(dest="subcommand", title="Available Actions", help="Profile subcommands")
        self._add_help_subcommand_to_parser(subparsers, "profile")

        show_parser = subparsers.add_parser("show",
                                            help="Show all global profile settings.",
                                            description="Displays all key-value pairs currently stored in the global profile.",
                                            formatter_class=self.formatter, add_help=False)
        self._add_custom_help(show_parser, "show")
        show_parser.examples = [("profile show", "Shows all configured global settings.")]
        
        update_parser = subparsers.add_parser("update",
                                              help="Add or change a global setting.",
                                              description="Adds a new key-value pair to the global profile or updates an existing one. These values can be used in placeholders (e.g., $profile.user_agent).",
                                              formatter_class=self.formatter, add_help=False)
        self._add_custom_help(update_parser, "update")
        update_parser.add_argument("update_args", nargs=argparse.REMAINDER, help="Key and value (e.g., 'user_agent MyBot/1.0').")
        update_parser.examples = [
            ("profile update user_agent 'My Custom UA/1.0'", "Sets a global User-Agent string.")
        ]

        delete_parser = subparsers.add_parser("delete",
                                              help="Delete a global setting.",
                                              description="Removes a key-value pair from the global profile.",
                                              formatter_class=self.formatter, add_help=False)
        self._add_custom_help(delete_parser, "delete")
        delete_parser.add_argument("key", help="The key to delete.", choices_provider=completer)
        delete_parser.examples = [("profile delete user_agent", "Removes the User-Agent from the profile.")]

    def _populate_proxy_parser(self, parser):
        """Populates the parser for proxy settings."""
        subparsers = parser.add_subparsers(dest="subcommand", title="Available Actions", help="Proxy subcommands")
        self._add_help_subcommand_to_parser(subparsers, "proxy")

        p_show = subparsers.add_parser("show", help="Show current proxy status and configuration.", aliases=['status'], formatter_class=self.formatter, add_help=False)
        self._add_custom_help(p_show, "show")
        p_show.examples = [("proxy show", "Displays the current proxy status and configuration.")]
        p_on = subparsers.add_parser("on", help="Enable proxy usage for the current session.", formatter_class=self.formatter, add_help=False)
        self._add_custom_help(p_on, "on")
        p_on.examples = [("proxy on", "Enables the proxy for the current session.")]
        p_off = subparsers.add_parser("off", help="Disable proxy usage for the current session.", formatter_class=self.formatter, add_help=False)
        self._add_custom_help(p_off, "off")
        p_off.examples = [("proxy off", "Disables the proxy for the current session.")]
        
        set_parser = subparsers.add_parser("set", help="Set a proxy configuration value for the current session.", formatter_class=self.formatter, add_help=False)
        self._add_custom_help(set_parser, "set")
        # --- FIX: Define key and value as separate arguments for better autocompletion ---
        valid_set_keys = ['wrapper_command', 'wrapper_options', 'wrapper_needs_sudo', 'type', 'host', 'port', 'username', 'password', 'wrapper_template']
        set_parser.add_argument("key", help="The configuration key to set.", choices=valid_set_keys)
        set_parser.add_argument("value", nargs=argparse.REMAINDER, help="The value to assign to the key.")
        set_parser.examples = [
            ("proxy set host 127.0.0.1", "Sets the proxy host for the current session."),
            ("proxy set port 8080", "Sets the proxy port.")
        ]

        reset_parser = subparsers.add_parser("reset", help="Reset a proxy setting to its global default by removing it from the session.", formatter_class=self.formatter, add_help=False)
        self._add_custom_help(reset_parser, "reset")
        # --- FIX: Use choices for better autocompletion ---
        valid_reset_keys = ['all', 'enabled', 'wrapper_command', 'wrapper_options', 'wrapper_needs_sudo', 'type', 'host', 'port', 'username', 'password', 'wrapper_template']
        reset_parser.add_argument("key", nargs='?', default='all',
                                  help="The key to reset (e.g., 'host'). If 'all' or omitted, all session-specific proxy settings are reset.",
                                  choices=valid_reset_keys)
        reset_parser.examples = [
            ("proxy reset host", "Resets the session's host setting to the global default."),
            ("proxy reset all", "Resets all session-specific proxy settings.")
        ]

    def _populate_session_parser(self, parser, completer):
        subparsers = parser.add_subparsers(dest="subcommand", title="Available Actions", help="Session subcommands")
        self._add_help_subcommand_to_parser(subparsers, "session")
        new_parser = subparsers.add_parser("new",
                                           help="Create and activate a new session.",
                                           description="Creates a new, empty session and immediately switches to it, making it the active workspace.",
                                           formatter_class=self.formatter, add_help=False)
        self._add_custom_help(new_parser, "new")
        new_parser.add_argument("name", help="A unique name for the new session.")
        new_parser.examples = [("session new project-x", "Creates a new session and switches to it.")]

        switch_parser = subparsers.add_parser("switch",
                                              help="Switch to an existing session.",
                                              description="Activates a previously created session, restoring its context (loaded target, tool, etc.).",
                                              formatter_class=self.formatter, add_help=False)
        self._add_custom_help(switch_parser, "switch")
        switch_parser.add_argument("name", help="The name of the session to switch to.", choices_provider=completer)
        switch_parser.examples = [("session switch default", "Switches back to the default session.")]

        list_parser = subparsers.add_parser("list",
                                            help="List all sessions.",
                                            description="Displays a list of all existing sessions.",
                                            formatter_class=self.formatter, add_help=False)
        self._add_custom_help(list_parser, "list")
        list_parser.examples = [("session list", "Shows all available sessions.")]

        destroy_parser = subparsers.add_parser("destroy",
                                               help="Delete a session.",
                                               description="Deletes a session. This does not delete any targets or tools, only the session context itself.",
                                               formatter_class=self.formatter, add_help=False)
        self._add_custom_help(destroy_parser, "destroy")
        destroy_parser.add_argument("name", help="The name of the session to delete.", choices_provider=completer)
        destroy_parser.examples = [("session destroy project-y", "Deletes the 'project-y' session.")]

        export_parser = subparsers.add_parser("export", aliases=['reverse'],
                                              help="Generate the 'load' commands for the current session.",
                                              description="Outputs the 'load' commands required to restore the current session's context.",
                                              formatter_class=self.formatter, add_help=False)
        self._add_custom_help(export_parser, "export")
        export_parser.examples = [("session export", "Prints the load commands for the current session.")]

        show_parser = subparsers.add_parser("show",
                                            help="Show the status of the current session.",
                                            description="Displays the currently loaded target, tool, and wordlist for the active session.",
                                            formatter_class=self.formatter, add_help=False)
        self._add_custom_help(show_parser, "show")
        show_parser.examples = [("session show", "Shows what is loaded in the current session.")]

    def _populate_jobs_parser(self, parser):
        subparsers = parser.add_subparsers(dest="subcommand", title="Available Actions", help="Job management commands")
        self._add_help_subcommand_to_parser(subparsers, "jobs")
        list_parser = subparsers.add_parser("list",
                                            help="List all background jobs.",
                                            description="Shows a table of all currently running and finished background jobs, including their ID, status, and duration.",
                                            formatter_class=self.formatter, add_help=False)
        self._add_custom_help(list_parser, "list")
        list_parser.examples = [("jobs list", "Shows all running and finished jobs.")]
        
        show_parser = subparsers.add_parser("show",
                                            help="Show the output of a specific job.",
                                            description="Displays the captured standard output and error for a specific background job.",
                                            formatter_class=self.formatter, add_help=False)
        self._add_custom_help(show_parser, "show")
        show_parser.add_argument("id", type=str, help="The ID of the job.")
        show_parser.examples = [("jobs show 3", "Displays the full output of job with ID 3.")]

        kill_parser = subparsers.add_parser("kill",
                                            help="Kill a running job.",
                                            description="Terminates a background job that is currently running.",
                                            formatter_class=self.formatter, add_help=False)
        self._add_custom_help(kill_parser, "kill")
        kill_parser.add_argument("id", type=str, help="The ID of the job to kill.")
        kill_parser.examples = [("jobs kill 3", "Terminates the running job with ID 3.")]

        clear_parser = subparsers.add_parser("clear",
                                             help="Remove all finished jobs from the list.",
                                             description="Clears all jobs from the list that have a status of 'finished', 'failed', or 'killed'.",
                                             formatter_class=self.formatter, add_help=False)
        self._add_custom_help(clear_parser, "clear")
        clear_parser.examples = [("jobs clear", "Removes non-running jobs from the list.")]

        input_parser = subparsers.add_parser("input",
                                             help="Send text input to a running job.",
                                             description="Sends a line of text to the standard input of a running job. Useful for interacting with prompts.",
                                             formatter_class=self.formatter, add_help=False)
        self._add_custom_help(input_parser, "input")
        input_parser.add_argument("id", type=str, help="The ID of the job to send input to.")
        input_parser.add_argument("text", nargs=argparse.REMAINDER, help="The text to send to the job.")
        input_parser.examples = [("jobs input 1 \"some text\"", "Sends 'some text' to job #1.")]


    def _populate_pwn_parser(self, parser):
        parser.description = "Builds and executes the command for the tool loaded in the session. Use 'pwn <command> [now|bg]'."
        parser.add_argument("pwn_args", nargs=argparse.REMAINDER, help="The tool command to run, extra parameters, and an optional execution keyword ('now' or 'bg').")

    def _populate_overview_parser(self, parser):
        parser.description = "Display a clear summary of the current state."
        parser.add_argument(
            '--short',
            action='store_true',
            help="Display a compact, summarized overview."
        )

    def _populate_note_parser(self, parser):
        subparsers = parser.add_subparsers(dest="subcommand", title="Available Actions", help="Note commands")
        self._add_help_subcommand_to_parser(subparsers, "note")
        add_parser = subparsers.add_parser("add",
                                           help="Add a new note.",
                                           description="Adds a timestamped note to the currently loaded report.",
                                           formatter_class=self.formatter, add_help=False)
        self._add_custom_help(add_parser, "add")
        add_parser.add_argument("text", nargs=argparse.REMAINDER, help="The content of the note.")
        add_parser.examples = [("note add Found admin panel at /secret-admin", "Adds a new note to the current report.")]

        list_parser = subparsers.add_parser("list",
                                            help="List all notes.",
                                            description="Displays all notes associated with the currently loaded target.",
                                            formatter_class=self.formatter, add_help=False)
        self._add_custom_help(list_parser, "list")
        list_parser.examples = [("note list", "Shows all notes for the current target.")]

        delete_parser = subparsers.add_parser("delete",
                                              help="Delete a note.",
                                              description="Deletes a specific note from the currently loaded report, identified by its index.",
                                              formatter_class=self.formatter, add_help=False)
        self._add_custom_help(delete_parser, "delete")
        delete_parser.add_argument("index", type=int, help="The index of the note to delete (1-based).")
        delete_parser.examples = [("note delete 1", "Deletes the first note from the list.")]

    def _populate_loot_parser(self, parser):
        subparsers = parser.add_subparsers(dest="subcommand", title="Available Actions", help="Loot commands")
        self._add_help_subcommand_to_parser(subparsers, "loot")
        add_parser = subparsers.add_parser("add",
                                           help="Add new loot.",
                                           description="Adds a new loot item (e.g., a password, key, or flag) to the currently loaded report.",
                                           formatter_class=self.formatter, add_help=False)
        self._add_custom_help(add_parser, "add")

        # NEW: Use a choices_provider for dynamic autocompletion from config
        loot_types = config.get_loot_types()
        if not loot_types:
            # Fallback if config key is missing or empty
            log.warning("No LOOT_TYPES defined in config.ini. 'loot add' will accept any type.")
            add_parser.add_argument("type", help="Type of loot (e.g., password, key, flag).")
        else:
            # Using choices_provider enables autocompletion and validation
            loot_completer = ChoicesProvider(config, method_name='get_loot_types')
            add_parser.add_argument("type", choices_provider=loot_completer, help="Type of loot (defined in config.ini).")

        add_parser.add_argument("value", nargs=argparse.REMAINDER, help="The found value.")
        add_parser.examples = [
            ("loot add credential admin:password123", "Adds a credential as loot."),
            ("loot add flag THM{...}", "Adds a flag as loot.")
        ]

        list_parser = subparsers.add_parser("list",
                                            help="List all loot.",
                                            description="Displays all loot associated with the currently loaded report.",
                                            formatter_class=self.formatter, add_help=False)
        self._add_custom_help(list_parser, "list")
        list_parser.examples = [("loot list", "Shows all loot for the current target.")]

        delete_parser = subparsers.add_parser("delete",
                                              help="Delete a loot entry.",
                                              description="Deletes a specific loot item from the currently loaded report, identified by its index.",
                                              formatter_class=self.formatter, add_help=False)
        self._add_custom_help(delete_parser, "delete")
        delete_parser.add_argument("index", type=int, help="The index of the loot entry to delete (1-based).")
        delete_parser.examples = [("loot delete 1", "Deletes the first loot item from the list.")]

    def _populate_placeholders_parser(self, parser):
        parser.description = "List all available placeholders for a specific entity or all entities."
        # Create the subparsers action ONCE.
        subparsers = parser.add_subparsers(dest="subcommand", title="Available Actions", help="Placeholder subcommands")
        # Add the 'help' subcommand to this action.
        self._add_help_subcommand_to_parser(subparsers, "placeholders")
        
        def add_placeholder_subcommand(name, help_text):
            p = subparsers.add_parser(name, help=help_text, formatter_class=self.formatter, add_help=False)
            self._add_custom_help(p, name)

        add_placeholder_subcommand("all", "Show placeholders for all loaded entities.")
        add_placeholder_subcommand("target", "Show placeholders for the loaded target.")
        add_placeholder_subcommand("tool", "Show placeholders for the loaded tool.")
        add_placeholder_subcommand("wordlist", "Show placeholders for the loaded wordlist.")
        add_placeholder_subcommand("profile", "Show placeholders for the global profile.")
        add_placeholder_subcommand("proxy", "Show placeholders for the effective proxy configuration.")
        add_placeholder_subcommand("report", "Show placeholders for the loaded report.")
        add_placeholder_subcommand("functions", "Show available placeholder functions (e.g., b64encode).")

    def _populate_manual_parser(self, parser):
        """Populates the parser for the manual command."""
        parser.description = "Displays detailed documentation on pwnity concepts and commands."
        # Instead of using subparsers (which are static after startup), we accept
        # any string as a topic. The validation happens at runtime inside the
        # do_manual command. This makes the command truly dynamic, picking up
        # new .md files without a restart. The completer is already dynamic.
        parser.add_argument('topic', nargs='?', default=None,
                            help="The manual topic to display. (e.g., 'concepts', 'workflow')")

    def _populate_parser_parser(self, parser, logbook_completer=None):
        """Populates the parser for the 'parser' command with full CRUD operations."""
        subparsers = parser.add_subparsers(dest="subcommand", title="Available Actions", help="Parser commands")
        parser_completer = ChoicesProvider(self.parser_mgr, method_name='list_all')

        # Use the common builder for standard commands
        self._build_common_subparsers(subparsers, parser_completer, "Parser", "Parsers", exclude=['load', 'update', 'delete'])

        # Custom 'update' parser for parsers
        update_parser = subparsers.add_parser("update",
                                              help="Update a parser's field, rule, or exclusion pattern.",
                                              description="Updates a specific part of a parser's configuration. This can be a top-level field (like 'description'), a new rule, or a field within a rule.",
                                              formatter_class=self.formatter, add_help=False)
        self._add_custom_help(update_parser, "update")
        update_parser.add_argument("name", help="The name of the parser to update.", choices_provider=parser_completer)
        update_parser.add_argument("update_args", nargs=argparse.REMAINDER, help="The update instruction (e.g., 'description ...', 'add-rule <rule_name>', or '<rule_name> regex ...').")
        update_parser.examples = [
            ("parser update common description \"New description.\"", "Updates the parser's description."),
            ("parser update common add-rule new_rule", "Adds a new, empty rule named 'new_rule'."),
            ("parser update common new_rule regex \"^\\d+$\"", "Sets the regex for the 'new_rule'."),
            ("parser update common new_rule exclude \"^123$\"", "Adds an exclusion pattern to the 'new_rule'.")
        ]

        # Custom 'delete' parser for parsers
        delete_parser = subparsers.add_parser("delete",
                                              help="Delete a field, rule, or exclusion pattern from a parser.",
                                              description="Deletes a specific part of a parser's configuration. Can delete a top-level field, a whole rule, or a specific exclusion pattern from a rule.",
                                              formatter_class=self.formatter, add_help=False)
        self._add_custom_help(delete_parser, "delete")
        delete_parser.add_argument("name", help="Name of the parser to modify.", choices_provider=parser_completer)
        delete_parser.add_argument("delete_args", nargs=argparse.REMAINDER, help="What to delete (e.g., 'description', '<rule_name>', or '<rule_name> exclude <index>').")
        delete_parser.examples = [
            ("parser delete common description", "Deletes the description field."),
            ("parser delete common ipv4", "Deletes the entire 'ipv4' rule."),
            ("parser delete common ipv4 exclude 1", "Deletes the 1st exclusion pattern from the 'ipv4' rule.")
        ]

        apply_parser = subparsers.add_parser("apply",
                                             help="Apply a parser to a source to extract findings.",
                                             description="Applies a parser's rules to a logbook entry's output and adds the findings to the currently loaded report.",
                                             formatter_class=self.formatter, add_help=False)
        self._add_custom_help(apply_parser, "apply")
        apply_parser.add_argument("name", help="The name of the parser to use.", choices_provider=parser_completer)
        apply_parser.add_argument("logbook_id", type=str, help="The ID of the logbook entry to parse.", choices_provider=logbook_completer)
        apply_parser.examples = [
            ("parser apply common 1", "Parses the output of logbook entry #1 using the 'common' parser."),
        ]

        export_parser = subparsers.add_parser("export", aliases=['reverse'],
                                              help="Generate the commands to reconstruct a parser.",
                                              description="Outputs a series of pwnity commands that can be used to recreate the specified parser, including all its rules and patterns.",
                                              formatter_class=self.formatter, add_help=False)
        self._add_custom_help(export_parser, "export")
        export_parser.add_argument("name", help="Name of the parser to export.", choices_provider=parser_completer)
        export_parser.examples = [("parser export common", "Prints the commands to recreate the 'common' parser.")]

        # Add a custom help panel entry for 'parser'
        if self.help_mgr:
            self.help_mgr.add_command_to_category('parser', 'Data Management', 'Extract info from output using regex parsers.')

    def _populate_logbook_parser(self, parser, logbook_completer=None):
        """Populates the parser for the 'logbook' command."""
        subparsers = parser.add_subparsers(dest="subcommand", title="Available Actions", help="Logbook commands")
        self._add_help_subcommand_to_parser(subparsers, "logbook")

        list_parser = subparsers.add_parser("list",
                                            help="List the most recent command executions.",
                                            description="Shows a history of the most recent command executions.",
                                            formatter_class=self.formatter, add_help=False)
        self._add_custom_help(list_parser, "list")
        list_parser.add_argument("-n", "--limit", type=int, default=20, help="Number of entries to show (default: 20).")

        show_parser = subparsers.add_parser("show",
                                            help="Show the full output of a specific logbook entry.",
                                            description="Displays the complete, captured output for a specific logbook entry.",
                                            formatter_class=self.formatter, add_help=False)
        self._add_custom_help(show_parser, "show")
        show_parser.add_argument("id", type=str, help="The ID of the logbook entry to show.", choices_provider=logbook_completer)

        filter_parser = subparsers.add_parser("filter",
                                              help="Filter the logbook by a specific criterion.",
                                              description="Filters the logbook history based on context like target, tool, session, or status.",
                                              formatter_class=self.formatter, add_help=False)
        self._add_custom_help(filter_parser, "filter")
        filter_parser.add_argument("type", choices=['target', 'tool', 'session', 'status'], help="The field to filter by.")
        filter_parser.add_argument("value", help="The value to filter for (e.g., a target name, 'nmap', 'success').")
        filter_parser.add_argument("-n", "--limit", type=int, default=20, help="Number of entries to show (default: 20).")
        filter_parser.examples = [
            ("logbook filter target my-server", "Show logs for a specific target."),
            ("logbook filter status failed -n 5", "Show the last 5 failed commands."),
        ]

        # Add a custom help panel entry for 'logbook'
        if self.help_mgr:
            self.help_mgr.add_command_to_category('logbook', 'Session & State', 'View execution logs.')

    def _populate_report_parser(self, parser):
        """Populates the parser for the 'report' command."""
        subparsers = parser.add_subparsers(dest="subcommand", title="Available Actions", help="Report commands")
        report_completer = ChoicesProvider(self.report_mgr)

        # Use the common builder for most commands, but customize show and delete
        self._build_common_subparsers(subparsers, report_completer, "Report", "Reports", exclude=['update', 'show', 'delete'])

        # Custom 'show' command that can show the loaded report without a name
        show_parser = subparsers.add_parser("show", help="Show the contents of a report.", formatter_class=self.formatter, add_help=False)
        self._add_custom_help(show_parser, "show")
        show_parser.add_argument("name", nargs='?', default=None, help="Name of the report to show. If omitted, shows the loaded report.", choices_provider=report_completer)
        show_parser.add_argument("field", nargs="?", default=None, help="Optional: Display only the value of this specific field.")
        show_parser.examples = [
            ("report show my-report", "Shows the contents of 'my-report'."),
            ("report show", "Shows the contents of the currently loaded report.")
        ]

        # Custom 'delete' as an alias for 'destroy'
        delete_parser = subparsers.add_parser("delete", help="Delete a report (alias for 'destroy').", formatter_class=self.formatter, add_help=False)
        self._add_custom_help(delete_parser, "delete")
        delete_parser.add_argument("name", help="The name of the report to delete.", choices_provider=report_completer)
        delete_parser.examples = [("report delete my-report", "Deletes the 'my-report' file.")]

        # Custom 'view' command to see a file inside a report
        view_parser = subparsers.add_parser("view", help="View the content of a file within a report.", formatter_class=self.formatter, add_help=False)
        self._add_custom_help(view_parser, "view")
        # This allows for 'view <file>' (if report is loaded) or 'view <report> <file>'
        view_parser.add_argument("arg1", help="File to view, or report name if a second argument is given.")
        view_parser.add_argument("arg2", nargs='?', default=None, help="Optional: File to view if the first argument is a report name.")
        view_parser.examples = [
            ("report view nmap_scan.txt", "Displays 'nmap_scan.txt' from the loaded report."),
            ("report view my-report nmap_scan.txt", "Displays 'nmap_scan.txt' from the specified 'my-report'.")
        ]

        # Add export parser
        export_parser = subparsers.add_parser("export", aliases=['reverse'],
                                              help="Generate the commands to reconstruct a report.",
                                              description="Outputs a series of pwnity commands that can be used to recreate the specified report, including its notes and loot.",
                                              formatter_class=self.formatter, add_help=False)
        self._add_custom_help(export_parser, "export")
        export_parser.add_argument("name", help="Name of the report to export.", choices_provider=report_completer)
        export_parser.examples = [("report export my-report", "Prints the commands to recreate 'my-report'.")]

        # Add render parser
        render_parser = subparsers.add_parser("render",
                                              help="Render a human-readable summary of a report to a file.",
                                              description="Generates a clean, human-readable summary of the report (in Markdown format) and saves it to a file for easy sharing or documentation.",
                                              formatter_class=self.formatter, add_help=False)
        self._add_custom_help(render_parser, "render")
        render_parser.add_argument("name", help="Name of the report to render.", choices_provider=report_completer)
        render_parser.add_argument("output_file", nargs='?', default=None, help="Optional: Filename for the output. Defaults to 'exports/reports/<name>.md'.")
        render_parser.examples = [
            ("report render my-report", "Saves a summary to 'exports/reports/my-report.md'."),
            ("report render my-report summary.txt", "Saves a summary to 'exports/reports/summary.txt'."),
        ]

        if self.help_mgr:
            self.help_mgr.add_command_to_category('report', 'Data Management', 'Manage analysis reports.')

    def _populate_config_parser(self, parser):
        """Populates the parser for the 'config' command."""
        subparsers = parser.add_subparsers(dest="subcommand", title="Available Actions", help="Config commands")
        self._add_help_subcommand_to_parser(subparsers, "config")

        list_parser = subparsers.add_parser("list", help="List all configuration settings.", formatter_class=self.formatter, add_help=False)
        self._add_custom_help(list_parser, "list")

        get_parser = subparsers.add_parser("get", help="Get the value of a specific configuration key.", formatter_class=self.formatter, add_help=False)
        self._add_custom_help(get_parser, "get")
        get_parser.add_argument("key", help="The key to retrieve, in SECTION.KEY format (e.g., PROXY.HOST).")

        set_parser = subparsers.add_parser("set", help="Set the value of a configuration key.", formatter_class=self.formatter, add_help=False)
        self._add_custom_help(set_parser, "set")
        set_parser.add_argument("key", help="The key to set, in SECTION.KEY format (e.g., PROXY.PORT).")
        set_parser.add_argument("value", nargs=argparse.REMAINDER, help="The new value to set.")

        set_parser.examples = [
            ("config set PROXY.HOST 127.0.0.1", "Sets the proxy host."),
            ("config set PROXY.ENABLED true", "Enables the proxy by default."),
        ]

    def _populate_revshell_parser(self, parser):
        """Populates the parser for the 'revshell' command."""
        parser.description = "Generates reverse shell one-liner payloads for various languages. Defaults to using '$profile.lhost' and '$profile.lport'."
        
        language_completer = ChoicesProvider(self.revshell_mgr, method_name='list_languages')
        parser.add_argument("language", nargs='?', default=None, help="The language for the payload.", choices_provider=language_completer)
        parser.add_argument("ip", nargs='?', default=None, help="Optional: The listener IP address. Defaults to '$profile.lhost'.")
        parser.add_argument("port", nargs='?', default=None, help="Optional: The listener port. Defaults to '$profile.lport'.")

        parser.examples = [
            ("revshell php", "Generates a PHP revshell payload using profile settings."),
            ("revshell python3 10.10.14.5 9001", "Generates a Python 3 revshell payload with a specific IP and port."),
        ]
        if self.help_mgr:
            self.help_mgr.add_command_to_category('revshell', 'Data Management', 'Generate reverse shell payloads.')

    def _populate_heartbeat_parser(self, parser):
        """Populates the parser for the 'heartbeat' command."""
        subparsers = parser.add_subparsers(dest="subcommand", title="Available Actions", help="Heartbeat commands")
        self._add_help_subcommand_to_parser(subparsers, "heartbeat")

        heartbeat_completer = ChoicesProvider(self.heartbeat_mgr, method_name='list_all')

        start_parser = subparsers.add_parser("start", help="Start monitoring the loaded target.", formatter_class=self.formatter, add_help=False)
        self._add_custom_help(start_parser, "start")
        start_parser.add_argument("options", nargs=argparse.REMAINDER, help="Optional overrides: delaymin <sec>, delaymax <sec>, timelimit <sec>.")
        start_parser.examples = [
            ("heartbeat start", "Starts monitoring the loaded target with default random delays."),
            ("heartbeat start delaymin 1 delaymax 3 timelimit 600", "Starts monitoring with custom delays and a 10-minute time limit.")
        ]

        stop_parser = subparsers.add_parser("stop", help="Stop monitoring a target.", formatter_class=self.formatter, add_help=False)
        self._add_custom_help(stop_parser, "stop")
        stop_parser.add_argument("name", nargs='?', default=None, help="The target to stop monitoring. Defaults to the loaded target.", choices_provider=heartbeat_completer)

        show_parser = subparsers.add_parser("show", help="Show live or historical data for a heartbeat.", formatter_class=self.formatter, add_help=False)
        self._add_custom_help(show_parser, "show")
        show_parser.add_argument("name", help="The name of the target whose heartbeat data to show.", choices_provider=heartbeat_completer)

        list_parser = subparsers.add_parser("list", help="List all active and saved heartbeats.", formatter_class=self.formatter, add_help=False)
        self._add_custom_help(list_parser, "list")

        if self.help_mgr:
            self.help_mgr.add_command_to_category('heartbeat', 'Session & State', "Monitor a target's health.")

    def _populate_library_parser(self, parser, completer):
        """Populates the parser for the 'library' command."""
        subparsers = parser.add_subparsers(dest="subcommand", title="Available Actions", help="Library subcommands")
        # Most commands are common, but we customize 'add' and 'update'
        self._build_common_subparsers(subparsers, completer, "Library entry", "Library entries", exclude=['load', 'add', 'update'])

        # Custom 'update' parser to provide better examples
        update_parser = subparsers.add_parser("update",
                                              help="Update a library entry's field (e.g., URL, comment).",
                                              description="Updates a field of an existing library entry. If the 'url' field is updated, its status is automatically checked.",
                                              formatter_class=self.formatter, add_help=False)
        self._add_custom_help(update_parser, "update")
        update_parser.add_argument("name", help="The name of the library entry to update.", choices_provider=completer)
        update_parser.add_argument("update_args", nargs=argparse.REMAINDER, help="The field and value to update (e.g., 'url https://example.com').")
        update_parser.examples = [("library update gtfobins comment \"A great resource for LOLBAS\"", "Updates the comment for the 'gtfobins' entry.")]

        # Custom 'add' parser to include the category option
        add_parser = subparsers.add_parser("add",
                                           help="Create a new library entry.",
                                           description="Creates a new, empty library entry. A category can be set afterwards using 'library update'.",
                                           formatter_class=self.formatter, add_help=False)
        self._add_custom_help(add_parser, "add")
        add_parser.add_argument("name", help="A unique name for the new library entry.")
        add_parser.examples = [("library add 'My Cheatsheet'", "Creates a new entry.")]

        check_parser = subparsers.add_parser("check",
                                             help="Check the status of a library entry's URL.",
                                             description="Performs a HEAD request to the URL of a library entry to check its reachability and status code.",
                                             formatter_class=self.formatter, add_help=False)
        self._add_custom_help(check_parser, "check")
        check_parser.add_argument("name", help="The name of the library entry to check, or 'all' to check every entry.")
        check_parser.examples = [
            ("library check gtfobins", "Checks the URL for the 'gtfobins' entry."),
            ("library check all", "Checks the URL for all library entries.")
        ]

        open_parser = subparsers.add_parser("open",
                                            help="Open a library entry's URL in a web browser.",
                                            description="Opens the URL associated with a specific library entry in the default web browser.",
                                            formatter_class=self.formatter, add_help=False)
        self._add_custom_help(open_parser, "open")
        open_parser.add_argument("name", help="The name of the library entry to open.", choices_provider=completer)
        open_parser.examples = [("library open gtfobins", "Opens the URL for the 'gtfobins' entry.")]

        export_parser = subparsers.add_parser("export", aliases=['reverse'],
                                              help="Generate the commands to reconstruct a library entry.",
                                              description="Outputs the pwnity commands needed to recreate the specified library entry.",
                                              formatter_class=self.formatter, add_help=False)
        self._add_custom_help(export_parser, "export")
        export_parser.add_argument("name", help="Name of the library entry to export.", choices_provider=completer)
        export_parser.examples = [("library export gtfobins", "Prints the commands to recreate the 'gtfobins' entry.")]

        if self.help_mgr:
            self.help_mgr.add_command_to_category('library', 'Data Management', 'Manage a library of useful links.')

    def _populate_workflow_parser(self, parser):
        """Populates the parser for the 'workflow' command."""
        subparsers = parser.add_subparsers(dest="subcommand", title="Available Actions", help="Workflow commands")
        workflow_completer = ChoicesProvider(self.workflow_mgr)

        # Use the common builder for most commands
        self._build_common_subparsers(subparsers, workflow_completer, "Workflow", "Workflows", exclude=['update'])

        run_parser = subparsers.add_parser("run", help="Run a workflow.", formatter_class=self.formatter, add_help=False)
        self._add_custom_help(run_parser, "run")
        run_parser.add_argument("name", help="Name of the workflow to run.", choices_provider=workflow_completer)