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
import cmd2
from cmd2 import ansi
from rich.panel import Panel
import os
import sys

def _apply_test_mode_patches():
    """
    Applies patches to network-related modules for testing purposes.
    This must be called before any other application modules are imported.
    """
    if os.environ.get("pwnity_TEST_MODE") != "1":
        return

    import socket
    socket.gethostbyname = lambda host: "127.0.0.1"

    try:
        import dns.resolver
        dns.resolver.resolve = lambda hostname, record_type: (_ for _ in ()).throw(dns.resolver.NoAnswer(f"Mocked DNS failure for {hostname}"))
    except ImportError:
        pass  # dnspython not installed

    try:
        import requests
        def mock_requests_get(url, **kwargs):
            class MockResponse:
                def __init__(self):
                    self.status_code = 200
                    self.text = "Mocked response"
                def __enter__(self): return self
                def __exit__(self, exc_type, exc_val, exc_tb): pass
            return MockResponse()
        requests.get = mock_requests_get
    except ImportError:
        pass  # requests not installed

    try:
        import webbrowser
        webbrowser.open = lambda url, new=0, autoraise=True: None
    except ImportError:
        pass  # Should not happen

    try:
        sys.modules['questionary'] = None
    except ImportError:
        pass  # questionary not installed

_apply_test_mode_patches()

from rich.console import Console as RichConsole, Group
from rich.align import Align
from rich.text import Text
from modules.managers.help_manager import HelpManager, RichCommandHelpAction, _CustomHelpAction
from modules.managers import TargetManager, WordlistManager, ToolManager, PresetManager, ProfileManager, ManualManager, ParserManager, LogbookManager, ReportManager, RevshellManager, HeartbeatManager, LibraryManager, WorkflowManager
from modules.managers.job_manager import JobManager
from modules.managers.display_manager import DisplayManager
from modules.cli_sessions import CLISessionManager
from modules.managers.command_executor import CommandExecutor
from modules.services import log, config # pwn_functions is not used directly here
from modules.parser_factory import ParserFactory
from modules.managers.proxy_manager import ProxyManager
from modules.managers.config_manager import ConfigManager # This was the old completer import, now it's config_manager
from modules.managers.utility_manager import UtilityManager
from modules.managers.run_manager import RunManager
from modules import functions as pwn_functions
from modules import placeholders
import threading, time
from datetime import datetime
try: # datetime is used in _write_state_to_file
    import psutil
except ImportError:
    psutil = None
import argparse, shlex, os, subprocess, sys, re, json

try:
    import questionary
except ImportError:
    questionary = None

try:
    from rich_argparse import RichHelpFormatter
    # Customize the styles for a more consistent look
    RichHelpFormatter.styles["argparse.args"] = "cyan"
    RichHelpFormatter.styles["argparse.groups"] = "dim"
    RichHelpFormatter.styles["argparse.help"] = "default"
    RichHelpFormatter.styles["argparse.metavar"] = "italic"
    RichHelpFormatter.styles["argparse.prog"] = "yellow"
    RichHelpFormatter.styles["argparse.syntax"] = "bold"
except ImportError:
    # If rich-argparse is not installed, fall back to the default formatter
    # and log an error to guide the user.
    if 'rich_argparse' not in sys.modules:
        log.error("Optional dependency 'rich-argparse' not found. Help messages will not be styled.")
        log.error("For a better experience, please install with: pip install rich-argparse")
    RichHelpFormatter = argparse.HelpFormatter

class MyCLI(cmd2.Cmd):
    def completer_pre_parse_matches(self, matches: list) -> list:
        """
        A cmd2 hook to post-process completion matches before they are displayed or inserted.
        This is used to solve the "index (value)" completion problem for tool parameters.
        We want to display "1 (-s)" but only insert "1".
        """
        new_matches = []
        for match in matches:
            # Check if the match is in the format "123 (some value)"
            if isinstance(match, str) and match.endswith(')') and ' (' in match:
                # Extract just the number, e.g., "1" from "1 (-s)"
                base_match = match.split(' (', 1)[0]

                # --- FINAL FIX: Add a space for 'reorder' for better usability ---
                # This allows tabbing through both indices without manual spacing.
                # We check the raw statement directly, as `self.last_command` might not be updated yet.
                if self.statement.raw.strip().startswith('tool reorder'):
                    match = base_match + ' '
                else:
                    match = base_match
            new_matches.append(match)
        return new_matches

    # --- Define empty parsers at the class level so the decorators have a target.
    # The actual configuration happens in __init__ via the ParserFactory.
    alias_parser = argparse.ArgumentParser(formatter_class=RichHelpFormatter, add_help=False, prog="alias")
    target_parser = argparse.ArgumentParser(description="Manages targets for scans.", formatter_class=RichHelpFormatter, add_help=False, prog="target")
    tool_parser = argparse.ArgumentParser(description="Configures external tools for execution.", formatter_class=RichHelpFormatter, add_help=False, prog="tool")
    wordlist_parser = argparse.ArgumentParser(description="Manages wordlists for fuzzing and brute-force.", formatter_class=RichHelpFormatter, add_help=False, prog="wordlist")
    preset_parser = argparse.ArgumentParser(description="Manages presets (saved sessions).", formatter_class=RichHelpFormatter, add_help=False, prog="preset")
    profile_parser = argparse.ArgumentParser(description="Manages global profile settings.", formatter_class=RichHelpFormatter, add_help=False, prog="profile")
    session_parser = argparse.ArgumentParser(description="Manages the working context (loaded targets, tools, etc.).", formatter_class=RichHelpFormatter, add_help=False, prog="session")
    jobs_parser = argparse.ArgumentParser(description="Manages background jobs.", formatter_class=RichHelpFormatter, add_help=False, prog="jobs")
    proxy_parser = argparse.ArgumentParser(description="Manages proxy settings.", formatter_class=RichHelpFormatter, add_help=False, prog="proxy")
    pwn_parser = argparse.ArgumentParser(description="Builds and executes the command for the tool loaded in the session.", formatter_class=RichHelpFormatter, prog="pwn")
    overview_parser = argparse.ArgumentParser(formatter_class=RichHelpFormatter, add_help=False, prog="overview")
    note_parser = argparse.ArgumentParser(description="Manages notes for the current target.", formatter_class=RichHelpFormatter, add_help=False, prog="note")
    loot_parser = argparse.ArgumentParser(description="Manages loot (passwords, keys, etc.) for the current target.", formatter_class=RichHelpFormatter, add_help=False, prog="loot")
    placeholders_parser = argparse.ArgumentParser(description="Lists available placeholders.", formatter_class=RichHelpFormatter, add_help=False, prog="placeholders")
    manual_parser = argparse.ArgumentParser(description="Displays the pwnity manual.", formatter_class=RichHelpFormatter, add_help=False, prog="manual")
    config_parser = argparse.ArgumentParser(description="Manages application configuration.", formatter_class=RichHelpFormatter, add_help=False, prog="config")
    parser_parser = argparse.ArgumentParser(description="Manages and applies output parsers.", formatter_class=RichHelpFormatter, add_help=False, prog="parser")
    logbook_parser = argparse.ArgumentParser(description="Manages logs of command executions.", formatter_class=RichHelpFormatter, add_help=False, prog="logbook")
    report_parser = argparse.ArgumentParser(description="Manages analysis reports from parsers.", formatter_class=RichHelpFormatter, add_help=False, prog="report")
    revshell_parser = argparse.ArgumentParser(description="Generates reverse shell payloads.", formatter_class=RichHelpFormatter, add_help=False, prog="revshell")
    heartbeat_parser = argparse.ArgumentParser(description="Monitors a target's health and responsiveness.", formatter_class=RichHelpFormatter, add_help=False, prog="heartbeat")
    library_parser = argparse.ArgumentParser(description="Manages a library of useful links.", formatter_class=RichHelpFormatter, add_help=False, prog="library")
    workflow_parser = argparse.ArgumentParser(description="Manages automated workflows.", formatter_class=RichHelpFormatter, add_help=False, prog="workflow")

    def _display_welcome_banner(self):
        """Displays a custom welcome banner using rich."""
        ascii_art = """  ██████╗  ██╗    ██╗███╗   ██╗██╗████████╗██╗   ██╗
  ██╔══██╗ ██║    ██║████╗  ██║██║╚══██╔══╝╚██╗ ██╔╝
 ██████╔╝ ██║ █╗ ██║██╔██╗ ██║██║   ██║    ╚████╔╝ 
██╔═══╝  ██║███╗██║██║╚██╗██║██║   ██║     ╚██╔╝  
██║      ╚███╔███╔╝██║ ╚████║██║   ██║      ██║   
╚═╝       ╚══╝╚══╝ ╚═╝  ╚═══╝╚═╝   ╚═╝      ╚═╝   """
        logo = Text(ascii_art, style="bold cyan", justify="center")

        tagline = Text.from_markup(
            "Your smart companion for pentesting, bug bounty hunting, and CTFs.",
            justify="center"
        )
        
        help_text = Text.from_markup(
            "Start with '[bold]help[/bold]' for a command overview or '[bold]help <command>[/bold]' for details.",
            justify="center"
        )

        disclaimer = Text.from_markup(
            "\n[yellow]WARNING:[/] This tool is intended for legal and ethical purposes only. Any misuse is strictly prohibited.",
            justify="center"
        )

        content = Group(
            logo,
            tagline,
            help_text,
            disclaimer
        )

        banner = Panel(
            Align.center(content, vertical="middle"),
            title="[bold]pwnity[/bold]",
            border_style="blue",
            expand=False,
            padding=(1, 2)
        )
        self.console.print(banner)

    # INIT 
    def __init__(self, shared_job_mgr=None):
        self._shared_job_mgr = shared_job_mgr  # Store for use in _init_managers
        self._setup_paths()
        # Determine if we are running in an internal mode (Web UI PTY or Headless API)
        web_ui_mode = '--web-ui-mode' in sys.argv
        headless_mode = os.environ.get('PWNITY_HEADLESS') == '1'
        
        # Only disable CLI args (commands at startup) if we are in internal modes
        # to prevent cmd2 from complaining about internal flags like --web-ui-mode
        super().__init__(persistent_history_file=self.history_file, allow_cli_args=not (web_ui_mode or headless_mode))

        self.web_ui_mode = web_ui_mode
        self.headless_mode = headless_mode
        self.console = RichConsole()

        # Bind logger to the cmd2 instance
        log.set_cli_instance(self)
        # Enable cmd2's own debugging if the log level is low
        self.debug = log.log_value <= log.LEVEL["DEBUG"]
        self._init_managers()
        self._init_placeholders()
        self._original_stty_settings = None # Initialize attribute
        self._init_parsers()
        self._web_ui_extension_loaded = False

        # If running in UI or headless mode, try to load the web_ui extension
        if self.web_ui_mode or self.headless_mode:
            try:
                from plugins.web_ui.backend.cli_extension import setup_ui_extension
                setup_ui_extension(self)
                self._web_ui_extension_loaded = True
            except ImportError:
                # Plugin not found, continue in standard CLI mode
                pass

        # Handle command line arguments for initial state
        import argparse
        parser = argparse.ArgumentParser(add_help=False)
        parser.add_argument('--session', type=str)
        parser.add_argument('--execute', type=str)
        args, _ = parser.parse_known_args()

        if args.session:
            if args.session in self.session_mgr.sessions:
                self.session = self.session_mgr.switch(args.session)
            else:
                log.warning(f"Session '{args.session}' not found during startup.")

        self._initial_command = args.execute

        # Set self.aliases_file so that 'alias save' writes to the correct file
        self._load_aliases_from_file()
        self._old_aliases = None  # Is initialized in the first precmd hook

        # Only run the full startup logic (banner, threads) if not in the initial
        # Flask reloader process. The reloader sets this env var in the child process.
        is_reloader_process = os.environ.get('WERKZEUG_RUN_MAIN') == 'true'

        # --- Display Welcome Banner ---
        if not self.web_ui_mode or is_reloader_process:
            self._display_welcome_banner()
            self.intro = "" # Disable cmd2's default intro
            # --- Display Mode ---
            if self.web_ui_mode:
                log.info("Running in Web UI Mode.")
            else:
                log.info("Running in CLI Mode.")

        self.last_command = None
        self._start_background_threads()
        
        # --- NEW: IPC attributes ---
        self._ipc_socket_path = None
    
    def _cleanup_state_files(self):
        """Removes the process-specific jobs file and IPC socket upon exit. (Overwritten by UI extension)"""
        pass
    
    def _setup_paths(self):
        """Sets up paths for history and alias files from config."""
        self.history_file = config.get_parameter("GLOBAL", "HISTORY_FILE", "data/.pwnity_history")
        history_dir = os.path.dirname(self.history_file)
        if history_dir:
            os.makedirs(history_dir, exist_ok=True)

        self.aliases_file = config.get_parameter("GLOBAL", "ALIASES_FILE", "etc/aliases.txt")
        aliases_dir = os.path.dirname(self.aliases_file)
        if aliases_dir:
            os.makedirs(aliases_dir, exist_ok=True)

    def _init_managers(self):
        """Initializes all manager instances."""
        self.display_mgr = DisplayManager(self.console)
        self.manual_mgr = ManualManager(self.console)
        self.help_mgr = HelpManager(self.console, self)
        _CustomHelpAction.set_help_manager_provider(lambda: self.help_mgr)

        self.target_mgr = TargetManager()
        self.wordlist_mgr = WordlistManager()
        self.tool_mgr = ToolManager()
        self.logbook_mgr = LogbookManager()
        self.preset_mgr = PresetManager()
        self.profile_mgr = ProfileManager()
        self.report_mgr = ReportManager()
        self.heartbeat_mgr = HeartbeatManager(self.target_mgr)
        self.revshell_mgr = RevshellManager()
        self.library_mgr = LibraryManager()
        self.workflow_mgr = WorkflowManager()
        
        # Use shared job manager if provided, otherwise create new instance
        if self._shared_job_mgr:
            self.job_mgr = self._shared_job_mgr
        else:
            self.job_mgr = JobManager(self, self.logbook_mgr, self.report_mgr)
        
        self.config_mgr = ConfigManager()
        self.utility_mgr = UtilityManager(self)
        self.run_mgr = RunManager()
        self.session_mgr = CLISessionManager()
        self.session = self.session_mgr.new("default")
        self.executor = CommandExecutor(self.job_mgr, self.logbook_mgr, self.report_mgr, self.display_mgr)
        self.proxy_mgr = ProxyManager()
        self.parser_mgr = ParserManager()

        from modules.completer import Completer
        self.completer = Completer(self)

    def _init_placeholders(self):
        """Registers all managers with the placeholder service."""
        placeholders.register_manager("TARGET", self.target_mgr)
        placeholders.register_manager("TOOL", self.tool_mgr)
        placeholders.register_manager("WORDLIST", self.wordlist_mgr)
        placeholders.register_manager("PROFILE", self.profile_mgr)
        placeholders.register_manager("PROXY", self.proxy_mgr)
        placeholders.register_manager("REPORT", self.report_mgr)
        placeholders.register_manager("LOGBOOK", self.logbook_mgr)

    # --- Parser Initialization Flag ---
    # Since parsers are class-level attributes, they should only be populated once.
    _parsers_loaded = False

    def _init_parsers(self):
        """Creates and populates all argparse parsers using the factory."""
        if MyCLI._parsers_loaded:
            return

        parser_factory = ParserFactory(
            self.target_mgr, self.tool_mgr, self.wordlist_mgr, self.preset_mgr, self.session_mgr, self.job_mgr,
            self.profile_mgr, self.help_mgr, self.manual_mgr, self.parser_mgr, self.logbook_mgr, self.report_mgr,
            self.revshell_mgr, self.heartbeat_mgr, self.library_mgr, self.workflow_mgr, self.config_mgr
        )
        all_parsers = {
            "target": MyCLI.target_parser, "alias": MyCLI.alias_parser, "note": MyCLI.note_parser,
            "loot": MyCLI.loot_parser, "placeholders": MyCLI.placeholders_parser, "tool": MyCLI.tool_parser,
            "wordlist": MyCLI.wordlist_parser, "preset": MyCLI.preset_parser, "profile": MyCLI.profile_parser,
            "session": MyCLI.session_parser, "jobs": MyCLI.jobs_parser, "pwn": MyCLI.pwn_parser,
            "proxy": MyCLI.proxy_parser, "manual": MyCLI.manual_parser, "parser": MyCLI.parser_parser,
            "logbook": MyCLI.logbook_parser, "report": MyCLI.report_parser, "revshell": MyCLI.revshell_parser,
            "heartbeat": MyCLI.heartbeat_parser, "library": MyCLI.library_parser, "config": MyCLI.config_parser,
            "overview": MyCLI.overview_parser, "workflow": MyCLI.workflow_parser,
        }
        parser_factory.populate_all_parsers(all_parsers)

        # Add our custom help action to all main parsers
        for name, parser in all_parsers.items():
            # pwn parser is special, it doesn't have a custom help panel.
            if name != 'pwn':
                parser.add_argument('-h', '--help', action=RichCommandHelpAction, command_name=name, help=f'Show help for the {name} command.')

        MyCLI._parsers_loaded = True

    def _start_background_threads(self):
        """Starts background threads for library checks and (if extended) UI syncing."""
        # 1. UI Syncing & IPC (if injected by extension)
        if self._web_ui_extension_loaded:
            self.last_running_job_ids = set()
            self.stop_sync_thread = threading.Event()
            
            if hasattr(self, '_background_state_syncer'):
                self.sync_thread = threading.Thread(target=self._background_state_syncer, daemon=True)
                self.sync_thread.start()

            if hasattr(self, '_ipc_server'):
                self.ipc_thread = threading.Thread(target=self._ipc_server, daemon=True)
                self.ipc_thread.start()

        # 2. Library check (Core CLI)
        is_reloader_process = os.environ.get('WERKZEUG_RUN_MAIN') == 'true'
        if not self.web_ui_mode or is_reloader_process:
            self.library_check_thread = threading.Thread(target=self.library_mgr.check_all_entries_on_startup, daemon=True)
            self.library_check_thread.start()

    @property
    def prompt(self):
        """Generates the dynamic prompt based on the session status."""
        # --- Line 1: Information ---
        line1_parts = []

        # Part 1: Host and Session
        host_part = ansi.style("pwnity", bold=True)

        # Determine separator color based on proxy status
        proxy_config = self.proxy_mgr.get_effective_config(self.session)
        if proxy_config:
            # Proxy is ON -> Green separator
            separator_color = ansi.Fg.GREEN
        else:
            # Proxy is OFF -> Default blue separator
            separator_color = ansi.Fg.BLUE

        separator = ansi.style(" ㉿ ", fg=separator_color)
        session_name = self.session.name if self.session else "no-session"
        session_part = ansi.style(f"({session_name})", fg=ansi.Fg.CYAN)
        part1 = f"{host_part}{separator}{session_part}"
        line1_parts.append(ansi.style("┌──(", fg=ansi.Fg.BLUE) + part1 + ansi.style(")", fg=ansi.Fg.BLUE))

        # Part 2: Context (Target, Tool, Wordlist)
        path_parts = []
        if self.session and self.session.target: path_parts.append(ansi.style(self.session.target, fg=ansi.Fg.GREEN))
        if self.session and self.session.tool: path_parts.append(ansi.style(self.session.tool, fg=ansi.Fg.YELLOW))
        if self.session and self.session.wordlist: path_parts.append(ansi.style(self.session.wordlist, fg=ansi.Fg.MAGENTA))
        if self.session and self.session.report: path_parts.append(ansi.style(self.session.report, fg=ansi.Fg.WHITE))

        if path_parts:
            part2 = " | ".join(path_parts)
            line1_parts.append(ansi.style(" - [ ", fg=ansi.Fg.BLUE) + part2 + ansi.style(" ]", fg=ansi.Fg.BLUE))

        # Part 3: Job status
        running_jobs = [j for j in self.job_mgr.list_jobs() if j.status == 'running']
        if running_jobs:
            # Use blue for the job status to avoid conflict with yellow for tools
            part3 = ansi.style(f"Running Jobs: {len(running_jobs)}", fg=ansi.Fg.BLUE)
            line1_parts.append(ansi.style(" - [ ", fg=ansi.Fg.BLUE) + part3 + ansi.style(" ]", fg=ansi.Fg.BLUE))

        line1 = "".join(line1_parts)

        # --- Line 2: Input ---
        line2 = f"{ansi.style('└─', fg=ansi.Fg.BLUE)}$ "

        return f"\n{line1}\n{line2}"

    def _background_state_syncer(self):
        """Polls for state changes. (Implemented by UI Extension)"""
        pass

    def _write_state_to_file(self):
        """Writes state to filesystem. (Implemented by UI Extension)"""
        pass

    def _sync_session_state_for_ui(self, signal_command_completion=False, hint=None):
        """Sends updates to Web UI. (Implemented by UI Extension)"""
        pass

    def _load_aliases_from_file(self):
        """Manually loads aliases from the alias file to avoid parsing issues."""
        if not os.path.exists(self.aliases_file):
            return
        try:
            with open(self.aliases_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line.startswith('alias create'):
                        continue
                    try:
                        # shlex.split is ideal for safely splitting a command line
                        parts = shlex.split(line)
                        if len(parts) == 4 and parts[0] == 'alias' and parts[1] == 'create':
                            _, _, alias_name, alias_value = parts
                            self.aliases[alias_name] = alias_value
                    except ValueError:
                        log.warning(f"Could not parse alias line in '{self.aliases_file}': {line}")
        except Exception as e:
            log.error(f"Error loading aliases from '{self.aliases_file}': {e}")

    def precmd(self, statement: cmd2.Statement) -> cmd2.Statement:
        """Hook that runs before each command. Saves the state of the aliases and reloads session if changed externally."""
        # Save a copy of the aliases to detect changes after command execution.
        self._old_aliases = self.aliases.copy()
        
        # CRITICAL: Reload session state from file if it was modified externally
        # This allows the PTY CLI to see changes made by the headless API
        if self.web_ui_mode:
            try:
                from modules.services import config
                import json
                
                session_file = config.get_parameter("GLOBAL", "SESSION_STATE_FILE", "data/.session.json")
                
                # Check if file exists and was modified
                if os.path.exists(session_file):
                    # Read the file
                    with open(session_file, 'r') as f:
                        state = json.load(f)
                    
                    # Update our session object with the file's state
                    
                    # 1. Sync session name if changed externally
                    session_name = state.get('session_name')
                    if session_name and hasattr(self, 'session_mgr') and session_name != self.session.name:
                        if session_name in self.session_mgr.sessions:
                            self.session = self.session_mgr.switch(session_name)
                            log.debug(f"[Session Sync] Switched to session: {self.session.name}")

                    # 2. Sync session attributes
                    # Only update if values are different to avoid unnecessary changes
                    if state.get('target') != self.session.target:
                        self.session.target = state.get('target')
                        log.debug(f"[Session Sync] Reloaded target: {self.session.target}")
                    
                    if state.get('tool') != self.session.tool:
                        self.session.tool = state.get('tool')
                        log.debug(f"[Session Sync] Reloaded tool: {self.session.tool}")
                    
                    if state.get('wordlist') != self.session.wordlist:
                        self.session.wordlist = state.get('wordlist')
                        log.debug(f"[Session Sync] Reloaded wordlist: {self.session.wordlist}")
                    
                    if state.get('report') != self.session.report:
                        self.session.report = state.get('report')
                        log.debug(f"[Session Sync] Reloaded report: {self.session.report}")
                    
                    # --- FIX: Sync Proxy Settings ---
                    loaded_proxy_settings = state.get('proxy_settings', {})
                    if loaded_proxy_settings != self.session.proxy_settings:
                        # Update specific keys to preserve reference if needed, or just replace dict content
                        self.session.proxy_settings.clear()
                        self.session.proxy_settings.update(loaded_proxy_settings)
                        log.debug(f"[Session Sync] Reloaded proxy settings: {self.session.proxy_settings}")
                        
            except Exception as e:
                log.debug(f"[Session Sync] Error reloading session: {e}")
        
        return statement

    def postcmd(self, stop: bool, statement: cmd2.Statement) -> bool:
        """Hook that runs after each command. Saves aliases and checks for job notifications."""
        # Compare the current aliases with the state before the command.
        if self.aliases != self._old_aliases:
            log.debug("Alias change detected, saving automatically...")
            # Note: The alias save logic is separate from the session state sync.
            # We use shlex.quote to handle values with spaces correctly.
            # The 'w' mode overwrites the file with the complete, current set of aliases.
            # This is simpler and more robust than trying to patch the file.

            try:
                # Write all current aliases to the file. 'w' overwrites the file.
                with open(self.aliases_file, 'w') as f:
                    for alias_name, alias_value in self.aliases.items():
                        # shlex.quote ensures that values with spaces are saved correctly.
                        f.write(f'alias create {alias_name} {shlex.quote(alias_value)}\n')
                log.info(f"Aliases automatically saved to '{self.aliases_file}'.")
            except Exception as e:
                log.error(f"Error while auto-saving aliases: {e}")

        # --- NEW: Web UI State Synchronization ---
        if self.web_ui_mode:
            # With the new 'morphdom' frontend, we always trigger a refresh signal.
            # The frontend handles this intelligently and silently without a full page reload.
            # This simplifies the backend logic significantly.
            should_refresh = True

            # Determine a hint for targeted UI refresh using the command verb
            hint = None
            cmd_verb = statement.command.lower() if statement.command else None
            
            if cmd_verb == 'target': hint = 'target'
            elif cmd_verb == 'tool': hint = 'tool'
            elif cmd_verb == 'wordlist': hint = 'wordlist'
            elif cmd_verb == 'report': hint = 'report'
            elif cmd_verb == 'preset': hint = 'preset'
            elif cmd_verb == 'library': hint = 'library'
            elif cmd_verb == 'parser': hint = 'parser'
            elif cmd_verb == 'session': hint = 'session'
            elif cmd_verb in ['pwn', 'run', 'logbook', 'scan', 'pwnity']: 
                hint = 'logbook'

            raw_command = statement.raw.strip().lower()

            # The only exception is a 'pwn' or 'run' command without 'now' or 'bg',
            # which is just a preview and should not cause any state change or refresh.
            if (raw_command.startswith('pwn') or raw_command.startswith('run')) and 'bg' not in raw_command and 'now' not in raw_command:
                should_refresh = False

            # The `skipNextViewRefresh` flag in the frontend handles cases where a refresh
            # is explicitly unwanted (e.g., silent updates within a modal).
            self._sync_session_state_for_ui(signal_command_completion=should_refresh, hint=hint)

        # Check for and display notifications from finished background jobs.
        # This ensures messages don't interrupt user input.
        if self.job_mgr.notifications:
            # Add a newline for spacing, but only if there are notifications.
            # poutput is used to ensure it's printed above the next prompt.
            self.poutput("")
            while self.job_mgr.notifications:
                job_id = self.job_mgr.notifications.popleft()
                job = self.job_mgr.get_job(job_id)
                if not job:
                    continue

                status_map = {
                    "finished": ("Finished", "bold green"),
                    "failed": ("Failed", "bold red"),
                    "killed": ("Killed", "bold magenta"),
                }
                status_text, status_style = status_map.get(job.status, (job.status.capitalize(), "bold yellow"))

                self.display_mgr.display_execution_summary(
                    title="[bold]Background Job Completed[/bold]",
                    status_text=status_text,
                    status_style=status_style,
                    return_code=job.return_code,
                    duration=job.duration,
                    command_str=job.command_str,
                    logbook_id=job.logbook_id,
                    session_name=job.session_name,
                    timestamp=time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(job.end_time)) if job.end_time else None
                )
        return stop

    def preloop(self):
        """
        Hook that runs once before the command loop starts.
        Used here to apply terminal compatibility fixes after cmd2 has initialized.
        """
        if self._initial_command:
            log.info(f"Executing initial command: {self._initial_command}")
            # Execute synchronously to avoid dual-access to the TTY during interactive jobs
            for cmd in self._initial_command.split(' ; '):
                if cmd.strip():
                    self.onecmd_plus_hooks(cmd.strip())
            
            # Exit after execution of initial commands to keep the terminal process clean
            # and prevent unwanted CLI prompts in separate Web UI terminal tabs.
            sys.exit(0)

        # --- FIX: Save original terminal settings before modification ---
        # This ensures we can restore them in postloop() to prevent breaking
        # the user's shell after exiting pwnity.
        if not self.web_ui_mode:
            self._save_and_fix_stty()

    def _save_and_fix_stty(self):
        """Saves current stty settings and applies a compatibility fix for the Backspace key."""
        if sys.platform != 'win32':
            try:
                # Save the original settings
                self._original_stty_settings = subprocess.check_output(['stty', '-g'], text=True, stderr=subprocess.DEVNULL).strip()
                log.debug(f"Saved original stty settings: {self._original_stty_settings}")

                # Check if cmd2 set the erase character to ^H, which breaks modern terminals
                current_stty = subprocess.check_output(['stty', '-a'], text=True, stderr=subprocess.DEVNULL)
                if re.search(r"erase\s*=\s*\^H;", current_stty):
                    log.debug("Detected 'stty erase ^H'. Applying compatibility fix.")
                    # Set the erase character to '^?' (DEL), the modern standard
                    subprocess.run(['stty', 'erase', '^?'], check=True, stderr=subprocess.DEVNULL)
                    log.info("Applied terminal compatibility fix for Backspace key.")
            except (FileNotFoundError, subprocess.CalledProcessError) as e:
                log.warning(f"Could not manage terminal settings with 'stty': {e}")
                self._original_stty_settings = None

    def _ipc_server(self):
        """Listens for IPC commands. (Implemented by UI Extension)"""
        pass


    def _is_heartbeat_active(self, target_name: str) -> bool:
        """
        Checks if a heartbeat is active by looking at the manager's internal state.
        This is the single source of truth for the CLI process.
        """
        if not hasattr(self, 'heartbeat_mgr'):
            return False
        
        return target_name in self.heartbeat_mgr.active_heartbeats

    def do_help(self, arg: str) -> None:
        """Provides customized, categorized help output."""
        arg_parts = arg.split()
        main_command = arg_parts[0] if arg_parts else None

        # Handle 'run' as an alias for 'pwn'
        if main_command == 'run':
            main_command = 'pwn'
            # Reconstruct arg if needed for super().do_help
            arg = " ".join([main_command] + arg_parts[1:])

        # Case 1: Help for a specific subcommand (e.g., 'help target add' or 'help tool -h')
        if main_command and len(arg_parts) > 1:
            if self.help_mgr.show_subcommand_help(main_command, arg_parts[1]):
                return
            # Fallback to cmd2's help if our handler doesn't find it
            return super().do_help(arg)

        # Case 2: Help for a top-level command (e.g., 'help target')
        if main_command and len(arg_parts) == 1:
            help_handler_name = f"show_help_{main_command}"
            custom_help_handler = getattr(self.help_mgr, help_handler_name, None)
            if callable(custom_help_handler):
                custom_help_handler()
                return

        # Case 3: General help (e.g., 'help')
        if not arg:
            self.help_mgr.show_command_overview()
        else:
            # Fallback for anything not covered (e.g., help for a command that doesn't exist)
            return super().do_help(arg)

    def complete_help(self, text, line, begidx, endidx):
        return self.completer.complete_help(text, line, begidx, endidx)

    @cmd2.with_argparser(manual_parser)
    def do_manual(self, args):
        """Displays detailed documentation on pwnity concepts and commands."""
        if args.topic:
            self.manual_mgr.show_page(args.topic)
        else:
            # If no topic is given, show the help for the manual command itself
            self.help_mgr.show_help_manual()

    def complete_manual(self, text, line, begidx, endidx):
        return self.completer.complete_manual(text, line, begidx, endidx)

    @cmd2.with_argparser(parser_parser)
    def do_parser(self, args):
        """Manages and applies output parsers to extract information."""
        self._dispatch_command('parser', args, self.parser_mgr)


    def complete_parser(self, text, line, begidx, endidx):
        return self.completer.complete_parser(text, line, begidx, endidx)

    @cmd2.with_argparser(logbook_parser)
    def do_logbook(self, args):
        """Manages and displays logs of command executions."""
        self._dispatch_command('logbook', args, self.logbook_mgr)

    def complete_logbook(self, text, line, begidx, endidx):
        return self.completer.complete_logbook(text, line, begidx, endidx)

    @cmd2.with_argparser(report_parser)
    def do_report(self, args):
        """Manages and displays analysis reports."""
        self._dispatch_command('report', args, self.report_mgr)

    def complete_report(self, text, line, begidx, endidx):
        return self.completer.complete_report(text, line, begidx, endidx)

    @cmd2.with_argparser(revshell_parser)
    def do_revshell(self, args):
        """Generates reverse shell payloads and optional tool configurations."""
        self._dispatch_command('revshell', args, self.revshell_mgr)

    def complete_revshell(self, text, line, begidx, endidx):
        return self.completer.complete_revshell(text, line, begidx, endidx)

    @cmd2.with_argparser(heartbeat_parser)
    def do_heartbeat(self, args):
        """Monitors a target's health and responsiveness."""
        self._dispatch_command('heartbeat', args, self.heartbeat_mgr)

    def complete_heartbeat(self, text, line, begidx, endidx):
        return self.completer.complete_heartbeat(text, line, begidx, endidx)

    @cmd2.with_argparser(library_parser)
    def do_library(self, args):
        """Manages a library of useful links and resources."""
        self._dispatch_command('library', args, self.library_mgr)

    def complete_library(self, text, line, begidx, endidx):
        return self.completer.complete_library(text, line, begidx, endidx)

    @cmd2.with_argparser(workflow_parser)
    def do_workflow(self, args):
        """Manages automated workflows."""
        self._dispatch_command('workflow', args, self.workflow_mgr)

    def complete_workflow(self, text, line, begidx, endidx):
        return self.completer.complete_workflow(text, line, begidx, endidx)

    @cmd2.with_argparser(target_parser)
    def do_target(self, args):
        '''Manages targets for scans. Subcommands: add, list, update, delete, destroy, load, show, gather'''
        self._dispatch_command('target', args, self.target_mgr)

    def complete_target(self, text, line, begidx, endidx):
        """Custom completer for the 'target' command."""
        return self.completer.complete_target(text, line, begidx, endidx)

    # wordlist
    @cmd2.with_argparser(wordlist_parser)
    def do_wordlist(self, args):
        '''Manages wordlists for fuzzing and brute-force. Subcommands: add, list, update, delete, destroy, load, show'''
        self._dispatch_command('wordlist', args, self.wordlist_mgr)

    def complete_wordlist(self, text, line, begidx, endidx):
        """Custom completer for the 'wordlist' command."""
        return self.completer.complete_wordlist(text, line, begidx, endidx)

    # tool
    @cmd2.with_argparser(tool_parser)
    def do_tool(self, args):
        '''Configures external tools for execution. Subcommands: add, list, update, delete, reorder, destroy, load, show, export'''
        self._dispatch_command('tool', args, self.tool_mgr)

    def complete_tool(self, text, line, begidx, endidx):
        """Custom completer for the 'tool' command."""
        return self.completer.complete_tool(text, line, begidx, endidx)

    # profile
    @cmd2.with_argparser(profile_parser)
    def do_profile(self, args):
        '''Manages global settings (e.g., User-Agent). Subcommands: show, update, delete'''
        self._dispatch_command('profile', args, self.profile_mgr)

    # preset
    @cmd2.with_argparser(preset_parser)
    def do_preset(self, args):
        '''Manages presets (saved sessions). Subcommands: save, load, list, show, destroy'''
        self._dispatch_command('preset', args, self.preset_mgr)

    def complete_preset(self, text, line, begidx, endidx):
        """Custom completer for the 'preset' command."""
        return self.completer.complete_preset(text, line, begidx, endidx)

    # proxy
    @cmd2.with_argparser(proxy_parser)
    def do_proxy(self, args):
        """Manages proxy settings for the current session. Subcommands: show, on, off, set, reset"""
        self._dispatch_command('proxy', args, self.proxy_mgr)

    # session
    @cmd2.with_argparser(session_parser)
    def do_session(self, args):
        """Manages the working context (loaded targets, tools, etc.). Subcommands: new, switch, list, destroy, show"""
        self._dispatch_command('session', args, self.session_mgr)

    def complete_session(self, text, line, begidx, endidx):
        """Custom completer for the 'session' command."""
        return self.completer.complete_session(text, line, begidx, endidx)

    # jobs
    @cmd2.with_argparser(jobs_parser)
    def do_jobs(self, args):
        """Manages background jobs. Subcommands: list, show, kill, clear"""
        self._dispatch_command('jobs', args, self.job_mgr)

    def complete_jobs(self, text, line, begidx, endidx):
        """Custom completer for the 'jobs' command."""
        return self.completer.complete_jobs(text, line, begidx, endidx)

    # overview
    @cmd2.with_argparser(overview_parser)
    def do_overview(self, args):
        """Displays a clear summary of the current state."""
        # The DisplayManager is now responsible for gathering and displaying the data.
        self.display_mgr.do_overview(args, self)

    # note
    @cmd2.with_argparser(note_parser)
    def do_note(self, args):
        """Manages notes for the currently loaded target."""
        # This command is handled by the ReportManager
        self._dispatch_command('note', args, self.report_mgr)

    def complete_note(self, text, line, begidx, endidx):
        """Autocompletion for the note command."""
        try:
            tokens = shlex.split(line[:begidx])
        except ValueError:
            tokens = line[:begidx].split()

        num_tokens = len(tokens)

        if num_tokens == 1:
            subparsers_action = next((action for action in self.note_parser._actions if isinstance(action, argparse._SubParsersAction)), None)
            if subparsers_action:
                return [s for s in subparsers_action.choices if s.startswith(text)]

        if num_tokens == 2 and tokens[1] == 'delete':
            if not self.session.report: return []
            report_data = self.report_mgr.load(self.session.report)
            if not report_data: return []
            notes = report_data.get('notes', [])
            indices = [str(i) for i in range(1, len(notes) + 1)]
            return [i for i in indices if i.startswith(text)]

        return []

    # loot
    @cmd2.with_argparser(loot_parser)
    def do_loot(self, args):
        """Manages loot for the currently loaded report."""
        # This command is handled by the ReportManager
        self._dispatch_command('loot', args, self.report_mgr)

    def complete_loot(self, text, line, begidx, endidx):
        """Autocompletion for the loot command."""
        try:
            tokens = shlex.split(line[:begidx])
        except ValueError:
            tokens = line[:begidx].split()

        num_tokens = len(tokens)

        if num_tokens == 1:
            subparsers_action = next((action for action in self.loot_parser._actions if isinstance(action, argparse._SubParsersAction)), None)
            if subparsers_action:
                return [s for s in subparsers_action.choices if s.startswith(text)]

        if num_tokens == 2 and tokens[1] == 'add':
            # Suggest loot types from the configuration
            loot_types = config.get_loot_types()
            return [lt for lt in loot_types if lt.startswith(text)]

        if num_tokens == 2 and tokens[1] == 'delete':
            if not self.session.report: return []
            report_data = self.report_mgr.load(self.session.report)
            if not report_data: return []
            loots = report_data.get('loot', [])
            indices = [str(i) for i in range(1, len(loots) + 1)]
            return [i for i in indices if i.startswith(text)]

        return []

    # placeholders
    @cmd2.with_argparser(placeholders_parser)
    def do_placeholders(self, args):
        """Lists available placeholders for the current session."""
        self.utility_mgr.do_placeholders(args, self)

    @cmd2.with_argparser(config_parser)
    def do_config(self, args):
        """Manages application configuration settings."""
        self._dispatch_command('config', args, self.config_mgr)

    def complete_config(self, text, line, begidx, endidx):
        return self.completer.complete_config(text, line, begidx, endidx)

    def do_print(self, statement: cmd2.Statement):
        """Resolves placeholders and functions in a string and prints the result."""
        self.utility_mgr.do_print(statement, self)

    def do_identify(self, statement: cmd2.Statement):
        """Identifies the possible type of a given hash string."""
        self.utility_mgr.do_identify(statement, self)

    def complete_identify(self, text, line, begidx, endidx):
        return self.completer.complete_identify(text, line, begidx, endidx)

    def complete_print(self, text, line, begidx, endidx):
        return self.completer.complete_print(text, line, begidx, endidx)

    def complete_pwn(self, text, line, begidx, endidx):
        return self.completer.complete_pwn(text, line, begidx, endidx)

    def complete_run(self, text, line, begidx, endidx):
        return self.completer.complete_run(text, line, begidx, endidx)

    # pwn / run
    @cmd2.with_argparser(pwn_parser)
    def do_pwn(self, args):
        """Builds and executes the command for the tool loaded in the session. Alias: run"""
        self.run_mgr.do_pwn(args, self)

    do_run = do_pwn  # 'run' is an alias for 'pwn'

    def postloop(self):
        """Called when the app is exiting. Shuts down all jobs."""
        if hasattr(self, 'stop_sync_thread'):
            self.stop_sync_thread.set()
            self.sync_thread.join(timeout=1) # Wait for the thread to finish
        self.job_mgr.shutdown()
        self.heartbeat_mgr.shutdown()

        # --- FIX: Restore original terminal settings on exit ---
        if self._original_stty_settings and sys.platform != 'win32':
            try:
                log.debug(f"Restoring original stty settings: {self._original_stty_settings}")
                subprocess.run(['stty', self._original_stty_settings], check=True, stderr=subprocess.DEVNULL)
            except (FileNotFoundError, subprocess.CalledProcessError) as e:
                log.warning(f"Failed to restore terminal settings: {e}")

        self.poutput("Goodbye!")

    def export_current_session(self):
        # This method is now handled by the SessionManager
        self._subcommand(self.session_mgr, argparse.Namespace(subcommand='export'), self)

    # subcommands
    def _subcommand(self,manager, args):
        """Dispatches the command to the responsible manager."""
        was_handled = manager.dispatch(args.subcommand, args, self)

    def _dispatch_command(self, command_name: str, args: argparse.Namespace, manager):
        """
        A generic dispatcher for commands that follow the standard manager pattern.
        Handles 'help' subcommands and fallbacks to the main help panel.
        """
        self.last_command = command_name

        # Handle 'command help' or 'command -h' which are parsed by RichCommandHelpAction
        if hasattr(args, 'show_help') and args.show_help:
            # The action has already displayed help, so we do nothing.
            return

        # Handle 'command help' as a subcommand
        if hasattr(args, 'subcommand') and args.subcommand == 'help':
            # Show the main help panel for the command.
            getattr(self.help_mgr, f"show_help_{command_name}")()
            return

        # Special handling for commands that don't use subparsers but have positional arguments
        # (e.g., 'revshell bash-tcp'). For these, 'subcommand' will always be None.
        if command_name == 'revshell':
            if getattr(args, 'language', None): # If a language is provided, dispatch to the manager
                manager.dispatch(None, args, self)

        # Get the subcommand, or None if it doesn't exist (e.g., for 'revshell bash-tcp').
        subcommand = getattr(args, 'subcommand', None)

        if subcommand:
            manager.dispatch(subcommand, args, self)
        else:
            # If no subcommand is given, show the help for the command.
            getattr(self.help_mgr, f"show_help_{command_name}")()

# Main
if __name__ == "__main__":
    # The MyCLI constructor reads flags like '--web-ui-mode' directly from sys.argv.
    # We call cmdloop() without arguments to ensure it always starts in interactive
    # mode and does not try to execute command-line arguments as commands.
    app = MyCLI()
    sys.exit(app.cmdloop())
