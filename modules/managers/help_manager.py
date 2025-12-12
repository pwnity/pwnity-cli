# modules/help_manager.py

import sys
import argparse, cmd2, re
from rich.rule import Rule
from rich.panel import Panel
from rich.table import Table, box
from rich.text import Text
from rich.console import Group, Console
from modules import functions as pwn_functions

class _CustomHelpAction(argparse.Action):
    """Base class for custom help actions that exit cleanly in cmd2."""
    _help_manager_provider = None

    @staticmethod
    def set_help_manager_provider(provider):
        _CustomHelpAction._help_manager_provider = provider

    def __call__(self, parser, namespace, values, option_string=None):
        if _CustomHelpAction._help_manager_provider:
            help_manager = _CustomHelpAction._help_manager_provider()
            if help_manager:
                self.show_help(parser, help_manager)
        # This is the standard way argparse exits, which cmd2 handles gracefully.
        raise cmd2.Cmd2ArgparseError()

    def show_help(self, parser, help_manager):
        raise NotImplementedError

class RichCommandHelpAction(_CustomHelpAction):
    """A custom argparse action to show the rich help for a main command."""
    def __init__(self, option_strings, dest, command_name, **kwargs):
        self.command_name = command_name
        super().__init__(option_strings, dest=dest, nargs=0, **kwargs)

    def show_help(self, parser, help_manager):
        handler = getattr(help_manager, f"show_help_{self.command_name}", None)
        if handler:
            handler()

class RichSubcommandHelpAction(_CustomHelpAction):
    """A custom argparse action to show the rich help for a subcommand."""
    def __init__(self, option_strings, dest, command_name, subcommand_name, **kwargs):
        self.command_name = command_name
        self.subcommand_name = subcommand_name
        super().__init__(option_strings, dest=dest, nargs=0, **kwargs)

    def show_help(self, parser, help_manager):
        help_manager.show_subcommand_help(self.command_name, self.subcommand_name)

class HelpManager:
    def __init__(self, console: Console, cli_instance=None):
        self.console = console
        self.cli_instance = cli_instance
        # This must be initialized here so that `add_command_to_category` can be
        # called during the application's startup phase.
        self._command_categories = {
            "Core Workflow": ["report", "target", "tool", "wordlist", "pwn"],
            "Session & State": ["session", "preset", "overview", "jobs", "heartbeat", "logbook"],
            "Data Management": ["identify", "note", "loot", "parser", "revshell", "placeholders", "profile", "library"],
            "Configuration & Shell": ["config", "print", "proxy", "alias", "history", "edit", "run_script", "shell", "quit"],
            "Help & Information": ["manual", "help", "workflow"]
        }

    def show_command_overview(self):
        """Displays a categorized overview of all available commands."""
        cli = self.cli_instance
        if not cli:
            return

        self.console.print() # Add a little space

        all_commands = cli.get_all_commands()
        
        # Use a single table for consistent column widths across all categories
        table = Table(show_header=False, box=None, expand=True, padding=(0, 2), show_edge=False)
        table.add_column("Command", style="cyan", no_wrap=True, width=25)
        table.add_column("Description", style="default")

        first_category = True
        for category, commands in self._command_categories.items():
            existing_commands = [c for c in commands if c in all_commands]
            if not existing_commands: continue

            # Add a spacer row before all categories except the first one
            if not first_category:
                table.add_row()
            first_category = False

            # Use a Rule for a clean, full-width separator that spans all columns.
            # This provides clear visual grouping while maintaining perfect alignment.
            table.add_row(Rule(f"[bold blue]{category}[/bold blue]", align="left", style="dim"))

            for cmd_name in existing_commands:
                func = getattr(cli, 'do_' + cmd_name, None)
                if func:
                    help_text = (func.__doc__ or '').strip().split('\n')[0]
                    table.add_row(f"  {cmd_name}", help_text)

        main_panel = Panel(table, title="[bold]Available Commands[/bold]",
                           subtitle="Type '[cyan]help <command>[/cyan]' for more details.", border_style="blue")
        self.console.print(main_panel)
        self.console.print()

    def add_command_to_category(self, command, category, description):
        """Dynamically adds a command to a help category."""
        if category not in self._command_categories:
            self._command_categories[category] = []
        if command not in self._command_categories[category]:
            self._command_categories[category].append(command)

    def show_subcommand_help(self, command_name, subcommand_name):
        """Displays a rich help panel for a specific subcommand."""
        cli = self.cli_instance
        if not cli:
            return False

        # 1. Get the main parser
        main_parser = getattr(cli, f"{command_name}_parser", None)
        if not main_parser: return False

        # 2. Find the subparsers action
        subparsers_action = next((action for action in main_parser._actions if isinstance(action, argparse._SubParsersAction)), None)
        if not subparsers_action: return False

        # 3. Get the specific subcommand parser, checking for aliases
        sub_parser = subparsers_action.choices.get(subcommand_name)
        if not sub_parser:
            for name, parser in subparsers_action.choices.items():
                if subcommand_name in getattr(parser, 'aliases', []):
                    sub_parser = parser
                    subcommand_name = name # Use the real name for the title
                    break
            if not sub_parser: return False

        # 4. We have the parser, now build the panel
        panel_title = f"[bold]Help: `{command_name} {subcommand_name}`[/bold]"
        
        # --- Manually build the usage string for full control ---
        # This avoids the layout bugs caused by argparse's format_usage().
        usage_text = Text("Usage: ", style="yellow")
        usage_text.append(f"{command_name} {subcommand_name}")

        pos_args_usage = []
        opt_args_usage = []

        for action in sub_parser._actions:
            if action.option_strings: # Optional argument like -h
                if action.option_strings != ['-h', '--help']:
                    opt_args_usage.append(f"[{action.option_strings[0]}]")
            else: # Positional argument
                pos_args_usage.append(f"<{action.metavar or action.dest}>")
        
        if opt_args_usage:
            usage_text.append(" " + " ".join(opt_args_usage), style="cyan")
        if pos_args_usage:
            usage_text.append(" " + " ".join(pos_args_usage), style="cyan")

        # Description
        description_text = Text.from_markup(f"{sub_parser.description or ''}")

        # Arguments
        pos_args = [action for action in sub_parser._actions if not action.option_strings]
        opt_args = [action for action in sub_parser._actions if action.option_strings and action.option_strings != ['-h', '--help']]

        # Build layout using a Table.grid for robust vertical stacking and width calculation.
        # This is the most reliable way to prevent layout issues with nested panels.
        layout_grid = Table.grid(padding=0, expand=True)
        layout_grid.add_column()

        layout_grid.add_row(usage_text)
        layout_grid.add_row("") # Spacer
        layout_grid.add_row(description_text)
        
        if pos_args:
            # Use expand=False on inner tables to prevent them from breaking the parent panel's layout
            pos_table = Table(box=None, show_header=False, padding=(0, 2), expand=False)
            pos_table.add_column(style="cyan", no_wrap=True)
            pos_table.add_column(style="default")
            for arg in pos_args:
                pos_table.add_row(arg.metavar or arg.dest, arg.help or "")
            layout_grid.add_row("") # Spacer
            layout_grid.add_row(Panel(pos_table, title="[dim]Positional Arguments[/dim]", border_style="dim", expand=True))

        if opt_args:
            opt_table = Table(box=None, show_header=False, padding=(0, 2), expand=False)
            opt_table.add_column(style="cyan", no_wrap=True)
            opt_table.add_column(style="default")
            for arg in opt_args:
                opt_table.add_row(", ".join(arg.option_strings), arg.help or "")
            layout_grid.add_row("") # Spacer
            layout_grid.add_row(Panel(opt_table, title="[dim]Options[/dim]", border_style="dim", expand=True))

        # --- Examples Panel ---
        if hasattr(sub_parser, 'examples') and sub_parser.examples:
            examples_table = Table(box=None, show_header=False, padding=(0, 2), expand=False)
            examples_table.add_column(style="cyan", no_wrap=True)
            examples_table.add_column(style="default")
            for cmd, desc in sub_parser.examples:
                examples_table.add_row(cmd, desc)
            
            layout_grid.add_row("") # Spacer
            layout_grid.add_row(Panel(examples_table, title="[dim]Common Examples[/dim]", border_style="dim", expand=True))

        panel = Panel(layout_grid, title=panel_title, border_style="blue", expand=False, padding=(1, 2))
        self.console.print(panel)
        return True

    def _show_custom_command_help(self, command_name: str, description: str, examples: list[tuple[str, str]], border_color: str = "blue"):
        """Generic helper to display custom help for a command."""
        panel_title = f"[bold]Help: `{command_name}`[/bold]"
        
        description_text = Text.from_markup(description)

        # --- Subcommands Panel ---
        subcommands_panel = None
        cli = self.cli_instance
        parser = getattr(cli, f"{command_name}_parser", None) if cli else None

        if parser:
            # Find the subparsers action which holds all subcommands
            subparsers_action = next((action for action in parser._actions if isinstance(action, argparse._SubParsersAction)), None)
            
            if subparsers_action and subparsers_action.choices:
                subcommands_table = Table(show_header=False, box=None, padding=(0, 2), expand=True)
                subcommands_table.add_column(style="cyan", no_wrap=True, width=25)
                subcommands_table.add_column(style="default")

                # Create a mapping from subcommand name to its help text and aliases.
                # This avoids displaying aliases as separate commands.
                subcommand_info = {}
                for sub_name, sub_parser in subparsers_action.choices.items():
                    # The help text is stored in the action that created the subparser.
                    # We find it by matching the destination variable.
                    action = next((a for a in subparsers_action._choices_actions if a.dest == sub_name), None)
                    help_text = ""
                    if action and action.help and action.help != argparse.SUPPRESS:
                        help_text = action.help
                    elif sub_parser.description and sub_parser.description != argparse.SUPPRESS:
                        help_text = sub_parser.description
                    else:
                        help_text = "" # Don't show "==SUPPRESS=="
                    subcommand_info[sub_name] = {'help': help_text, 'aliases': getattr(sub_parser, 'aliases', [])}

                for sub_name in sorted(subcommand_info.keys()):
                    info = subcommand_info[sub_name]
                    help_text = info['help']
                    aliases = info['aliases']
                    
                    display_name_str = sub_name
                    if aliases:
                        alias_str = ', '.join(aliases)
                        display_name_str = f"{sub_name} [dim]({alias_str})[/dim]"
                    subcommands_table.add_row(Text.from_markup(display_name_str), help_text)
                
                subcommands_panel = Panel(subcommands_table, title="[dim]Available Actions[/dim]", border_style="dim", expand=True)

        # --- Examples Panel ---
        examples_table = Table(box=None, show_header=False, padding=(0, 2), expand=True)
        examples_table.add_column(style="cyan", no_wrap=True)
        examples_table.add_column(style="default")
        for cmd, desc in examples:
            examples_table.add_row(cmd, desc)

        examples_panel = Panel(examples_table, title="[dim]Common Examples[/dim]", border_style="dim", expand=True)

        # --- Footer ---
        footer = Text.from_markup(
            f"Use '[cyan]help {command_name} <action>[/cyan]' for details on a specific action."
        )

        # --- Assemble Content ---
        content_parts = [description_text]
        if subcommands_panel:
            content_parts.extend([Text(""), subcommands_panel])
        
        content_parts.extend([Text(""), examples_panel, Text(""), footer])

        content = Group(*content_parts)

        panel = Panel(content, title=panel_title, border_style=border_color, expand=False, padding=(1, 2))
        self.console.print(panel)

    def show_help_target(self):
        self._show_custom_command_help(
            command_name="target",
            description="Manages targets, which store all relevant information like URLs, IPs, and gathered data. Notes and loot are stored in the loaded report.",
            examples=[
                ("target add <name>", "Create a new, empty target."),
                ("target update <name> url <url>", "Set the URL, which automatically parses IP, domain, etc."),
                ("target gather <name> all", "Actively gather DNS, WHOIS, and HTTP info."),
                ("target load <name>", "Load the target into the current session."),
                ("target show <name>", "Display all information for the target."),
                ("target export <name>", "Generate commands to recreate the target."),
            ], border_color="green")

    def show_help_tool(self):
        self._show_custom_command_help(
            command_name="tool",
            description="Configures external command-line tools. You define how a tool is called, and `pwnity` assembles the command with dynamic placeholders.",
            examples=[
                ("tool add <name>", "Create a new tool, e.g., 'nmap'."),
                ("tool update <name> command <cmd>", "Add a subcommand, e.g., 'stealth-scan'."),
                ("tool update <name> <cmd> param <p>", "Add a parameter with placeholders, e.g., '-p- $target.ip'."),
                ("tool load <name>", "Load the tool into the current session."),
                ("tool show <name>", "Display the tool's configuration."),
                ("tool update <name> sudo true", "Mark the tool to always run with sudo."),
            ], border_color="yellow")

    def show_help_wordlist(self):
        self._show_custom_command_help(
            command_name="wordlist",
            description="Manages references to wordlist files used for fuzzing, brute-forcing, etc.",
            examples=[
                ("wordlist add <name>", "Create a new wordlist reference."),
                ("wordlist update <name> path <path>", "Set the path to the wordlist file."),
                ("wordlist load <name>", "Load the wordlist into the current session."),
                ("wordlist list", "List all available wordlists."),
            ], border_color="magenta")

    def show_help_pwn(self):
        self._show_custom_command_help(
            command_name="pwn",
            description="Builds and executes the command for the currently loaded tool, resolving all placeholders. (Alias: `run`)",
            examples=[
                ("pwn <command>", "Show a preview of the command to be executed."),
                ("pwn <command> now", "Execute the command in the foreground."),
                ("pwn <command> bg", "Execute the command in the background."),
                ("pwn <command> -- -v", "Add extra temporary parameters to the command."),
            ], border_color="red")

    def show_help_session(self):
        self._show_custom_command_help(
            command_name="session",
            description="Manages sessions, which are workspaces that remember your loaded target, tool, wordlist, and report.",
            examples=[
                ("session new <name>", "Create a new session and switch to it."),
                ("session switch <name>", "Switch to an existing session."),
                ("session list", "List all available sessions."),
                ("session show", "Show what is loaded in the current session."),
            ])

    def show_help_note(self):
        self._show_custom_command_help(
            command_name="note",
            description="Manages timestamped notes, which are saved to the currently loaded report.",
            examples=[
                ("note add <text...>", "Add a new note."),
                ("note list", "List all notes in the current report."),
                ("note delete 1", "Delete the first note from the list."),
            ])

    def show_help_loot(self):
        self._show_custom_command_help(
            command_name="loot",
            description="Manages found treasures. The available loot types (e.g., credential, key) are defined in `etc/config.json` and support autocompletion.",
            examples=[
                ("loot add credential admin:password123", "Add a new loot item using a predefined type."),
                ("loot list", "List all loot in the current report."),
                ("loot delete 1", "Delete the first loot item from the list."),
            ])

    def show_help_profile(self):
        self._show_custom_command_help(
            command_name="profile",
            description="Manages global key-value settings that can be used as placeholders across all sessions (e.g., `$profile.user_agent`).",
            examples=[
                ("profile update user_agent 'My UA/1.0'", "Set a global User-Agent string."),
                ("profile update cookie 'session=...'", "Set a global cookie string."),
                ("profile show", "Display all configured profile settings."),
                ("profile delete user_agent", "Remove the User-Agent setting."),
            ], border_color="cyan")

    def show_help_preset(self):
        self._show_custom_command_help(
            command_name="preset",
            description="Manages presets, which are saved sessions (target, tool, wordlist, report, proxy) for quick and repeatable scans.",
            examples=[
                ("preset save <name>", "Save the current session as a new preset."),
                ("preset load <name>", "Load a preset into a new session."),
                ("preset list", "List all available presets."),
                ("preset show <name>", "Display the configuration of a preset."),
            ], border_color="magenta")

    def show_help_proxy(self):
        self._show_custom_command_help(
            command_name="proxy",
            description="Manages proxy settings for the current session, allowing tool traffic to be routed through a proxy like Burp Suite or Tor.",
            examples=[
                ("proxy on", "Enable the proxy for the current session."),
                ("proxy set host 127.0.0.1", "Set the proxy host for this session."),
                ("proxy reset host", "Reset the host to the global default from etc/config.json."),
                ("proxy show", "Show the current status and effective configuration."),
            ])

    def show_help_jobs(self):
        self._show_custom_command_help(
            command_name="jobs",
            description="Manages background jobs, allowing you to run long-lasting commands without blocking the shell.",
            examples=[
                ("jobs list", "List all running and finished jobs."),
                ("jobs show <id>", "Display the output of a specific job."),
                ("jobs kill <id>", "Terminate a running job."),
                ("jobs clear", "Remove all finished jobs from the list."),
            ])

    def show_help_parser(self):
        self._show_custom_command_help(
            command_name="parser",
            description="Manages and applies regex-based parsers to extract structured information (findings) from unstructured text. Findings are added to the currently loaded report.",
            examples=[
                ("parser list", "List all available parsers."),
                ("parser show common", "Show the rules in the 'common' parser."),
                ("parser apply common 1", "Parse logbook entry #1 and add all findings to the currently loaded report."),
                ("parser destroy my-parser", "Deletes the 'my-parser.yaml' file."),
            ], border_color="magenta")

    def show_help_logbook(self):
        self._show_custom_command_help(
            command_name="logbook",
            description="Manages and displays the immutable logs of previous command executions. Each execution creates a logbook entry with a unique ID.",
            examples=[
                ("logbook list", "Show a list of the most recent execution logs."),
                ("logbook show 1", "Display the full, raw output for log entry #1."),
            ], border_color="cyan")

    def show_help_report(self):
        self._show_custom_command_help(
            command_name="report",
            description="Manages reports, which are the central containers for all collected data (findings, notes, loot).",
            examples=[
                ("report add my-project", "Create a new, empty report."),
                ("report load my-project", "Load the report into the session to start collecting data."),
                ("report show", "Show the contents of the loaded report."),
                ("report list", "List all available reports."),
                ("report export my-project", "Prints the commands to recreate the report."),
                ("report render my-project", "Saves a human-readable summary to a file."),
                ("report unload", "Unload the report from the session."),
            ], border_color="yellow")

    def show_help_placeholders(self):
        self._show_custom_command_help(
            command_name="placeholders",
            description="Inspects and displays all available placeholders and their current values for the loaded entities.",
            examples=[
                ("placeholders all", "Show all available placeholders."),
                ("placeholders target", "Show only placeholders for the loaded target."),
                ("placeholders tool", "Show only placeholders for the loaded tool."),
                ("placeholders report", "Show only placeholders for the loaded report."),
                ("placeholders report", "Includes placeholders for parsed files (e.g., $report.file.nmap_xml.host)."),
                ("placeholders profile", "Show only placeholders for the global profile."),
            ])

    def show_help_revshell(self):
        self._show_custom_command_help(
            command_name="revshell",
            description="Generates reverse shell one-liner payloads for various languages. Defaults to using `$profile.lhost` and `$profile.lport`.",
            examples=[
                ("revshell php", "Generates a PHP revshell payload using profile settings."),
                ("revshell python3 10.10.14.5 9001", "Generates a Python 3 revshell payload with a specific IP and port."),
            ], border_color="red")

    def show_help_heartbeat(self):
        self._show_custom_command_help(
            command_name="heartbeat",
            description="Monitors a target's 'vital signs' (latency, status, etc.) over time. This is useful for establishing a baseline or observing the impact of your scans.",
            examples=[
                ("heartbeat start", "Start monitoring the loaded target with default random delays."),
                ("heartbeat start delaymin 1 delaymax 5 timelimit 300", "Start monitoring with custom delays and a 5-minute limit."),
                ("heartbeat show <name>", "Show a live dashboard of the monitoring data."),
                ("heartbeat stop [name]", "Stop the monitoring process for the specified or loaded target."),
                ("heartbeat list", "List all running and saved heartbeats."),
            ], border_color="blue")

    def show_help_library(self):
        self._show_custom_command_help(
            command_name="library",
            description="Manages a library of useful links and resources, allowing you to quickly open or check them.",
            examples=[
                ("library add <name>", "Create a new, empty library entry."),
                ("library update <name> url <url>", "Add or change the URL for an entry."),
                ("library open <name>", "Open the entry's URL in your browser."),
                ("library check <name|all>", "Check if the URL is reachable."),
                ("library list", "List all entries, grouped by category."),
                ("library destroy <name>", "Delete an entry from the library."),
            ], border_color="blue")

    def show_help_overview(self):
        self._show_custom_command_help(
            command_name="overview",
            description="Displays a comprehensive dashboard of the current session, including loaded entities, resolved placeholders, and recent activity.",
            examples=[
                ("overview", "Show the detailed, multi-panel overview."),
                ("overview --short", "Show a compact, summarized version."),
            ])

    def show_help_print(self):
        self._show_custom_command_help(
            command_name="print",
            description="A utility to resolve placeholders and apply functions, bypassing shell parsing for special characters like '<' and '>'.",
            examples=[
                ('print $target.ip', "Display the IP of the loaded target."),
                ('print b64encode "some text"', "Base64-encode a string."),
                ('print html_decode "&lt;script&gt;"', "HTML-decode a string without shell interference."),
                ('print b64encode($target.name)', "Use bracket syntax for nested functions or complex strings."),
            ])

    def show_help_identify(self):
        self._show_custom_command_help(
            command_name="identify",
            description=(
                "Analyzes a string to determine its possible hash type based on length and format. It can also resolve placeholders.\n\n"
                f"Supported types include: [dim]{', '.join(pwn_functions.list_hash_types())}[/dim]"
            ),
            examples=[
                ('identify 5f4dcc3b5aa765d61d8327deb882cf99', "Identify a raw hash string."),
                ('identify "$loot.0.value"', "Identify a hash stored as loot."),
            ],
            border_color="magenta")

    def show_help_config(self):
        self._show_custom_command_help(
            command_name="config",
            description="Manages the application's configuration settings from `etc/config.json`.",
            examples=[
                ('config list', "Display the entire configuration."),
                ('config get PROXY.HOST', "Show the value of a specific key."),
                ('config set PROXY.PORT 9050', "Set a new value for a key."),
            ],
            border_color="white")

    def show_help_manual(self):
        """Displays the overview help for the 'manual' command."""
        cli = self.cli_instance
        examples = []
        if cli and hasattr(cli, 'manual_mgr'):
            # Dynamically generate examples from available topics
            topics = cli.manual_mgr.list_topics()
            for topic in topics:
                summary = cli.manual_mgr.get_topic_summary(topic)
                examples.append((f"manual {topic}", summary))

        self._show_custom_command_help(
            command_name="manual",
            description="Provides detailed documentation on core concepts and workflows within pwnity, similar to a man page.",
            examples=examples,
            border_color="white"
        )
