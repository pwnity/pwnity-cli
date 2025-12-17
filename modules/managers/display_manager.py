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

# modules/display_manager.py

from rich.panel import Panel
from rich.columns import Columns
from rich.console import Console, Group
from rich.table import Table, box
from rich.text import Text
from modules.placeholders import resolve_placeholders
from modules.services import log

class DisplayManager:
    def __init__(self, console: Console):
        self.console = console

    def do_overview(self, args, cli):
        """Gathers data from all managers and displays the overview dashboard."""
        if not cli.session:
            log.warning("No active session.")
            return

        # Gather all necessary data from the respective managers
        target_data = cli.target_mgr.load(cli.session.target)
        tool_data = cli.tool_mgr.load(cli.session.tool)
        wordlist_data = cli.wordlist_mgr.load(cli.session.wordlist)
        profile_data = cli.profile_mgr.load()
        proxy_data = cli.proxy_mgr.get_effective_config(cli.session)
        report_data = cli.report_mgr.load(cli.session.report)
        log_history = log.get_history()

        # Call the internal display method
        self.display_overview(
            cli.session, target_data, tool_data, wordlist_data,
            profile_data, proxy_data, report_data, log_history, args.short
        )

    # --- Overview Display ---
    def display_overview(self, session, target_data, tool_data, wordlist_data, profile_data, proxy_data, report_data, log_history, is_short):
        notes_panel = None
        loot_panel = None
        findings_panel = None
        history_panel = None

        if is_short:
            target_panel = self._build_short_panel("Target", target_data, "green")
            tool_panel = self._build_short_panel("Tool", tool_data, "yellow")
            wordlist_panel = self._build_short_panel("Wordlist", wordlist_data, "magenta")
            profile_panel = self._build_short_panel("Profile", profile_data, "cyan")
            proxy_panel = self._build_proxy_panel(proxy_data, "blue", is_short=True)
            report_panel = self._build_short_report_panel(report_data, "white")
        else:
            target_panel = self._build_verbose_panel("Target", target_data, "green", session)
            tool_panel = self._build_verbose_panel("Tool", tool_data, "yellow", session)
            wordlist_panel = self._build_verbose_panel("Wordlist", wordlist_data, "magenta", session)
            profile_panel = self._build_verbose_panel("Profile", profile_data, "cyan", session)
            proxy_panel = self._build_proxy_panel(proxy_data, "blue", is_short=False)

            if report_data:
                report_name = report_data.get('name')
                history_panel = self._build_history_panel(report_data.get('history', []), report_name)
                findings_panel = self._build_findings_panel(report_data.get('findings', []), report_name)
                notes_panel = self._build_notes_panel(report_data.get('notes', []), report_name)
                loot_panel = self._build_loot_panel(report_data.get('loot', []), report_name)

        log_content = Text("\n".join(log_history), no_wrap=True)
        log_panel = Panel(log_content, title="[b]Recent Activity[/b]", border_style="bright_black", expand=True)

        if is_short:
            # Report panel is now handled separately for better layout
            sub_columns = Columns([tool_panel, wordlist_panel, profile_panel, proxy_panel], expand=True)
        else:
            sub_columns = Columns([tool_panel, wordlist_panel, profile_panel, proxy_panel], expand=True)

        self.console.print(f"\n--- Session Overview: [cyan]{session.name}[/cyan] ---")
        if is_short:
            self.console.print(Columns([target_panel, sub_columns]))
            if report_panel:
                self.console.print(report_panel)
        else:
            self.console.print(target_panel)
            self.console.print(sub_columns)
            # --- NEW: Group all report data into a single container ---
            if report_data:
                report_content_panels = []
                if history_panel: report_content_panels.append(history_panel)
                if findings_panel: report_content_panels.append(findings_panel)
                if notes_panel: report_content_panels.append(notes_panel)
                if loot_panel: report_content_panels.append(loot_panel)

                if report_content_panels:
                    report_group = Group(*report_content_panels)
                else:
                    # If the report is loaded but empty, show a message.
                    report_group = Text("Report is empty. Use 'note add' or 'loot add' to add data.", style="dim")

                main_report_panel = Panel(
                        report_group,
                        title=f":notebook_with_decorative_cover: [bold]Report Data: {report_data.get('name')}[/bold]",
                        border_style="white"
                    )
                self.console.print(main_report_panel)

        self.console.print(log_panel)

    def _add_nodes_recursively(self, markup_list: list, data, indent=0, session=None):
        indent_str = "  " * indent
        if isinstance(data, dict):
            for key, value in data.items():
                if key == 'commands' and isinstance(value, list):
                    markup_list.append(f"{indent_str}[bold blue]commands[/bold blue]:")
                    for cmd in value:
                        cmd_name = cmd.get('name', 'N/A')
                        markup_list.append(f"{indent_str}  :arrow_forward: [cyan]{cmd_name}[/cyan]")
                        params = cmd.get('params', [])
                        for j, param in enumerate(params, 1):
                            # Display the raw placeholder, not the resolved value
                            markup_list.append(f"{indent_str}    [dim]{j}:[/dim] [green]{param}[/green]")
                    continue

                if isinstance(value, (dict, list)):
                    markup_list.append(f"{indent_str}[bold blue]{key}[/bold blue]:")
                    self._add_nodes_recursively(markup_list, value, indent + 1, session)
                else:
                    # Display the raw placeholder, not the resolved value
                    markup_list.append(f"{indent_str}[bold blue]{key}[/bold blue]: [green]{value}[/green]")
        elif isinstance(data, list):
            for item in data:
                if isinstance(item, (dict, list)):
                    markup_list.append(f"{indent_str}[dim]•[/dim]")
                    self._add_nodes_recursively(markup_list, item, indent + 1, session)
                else:
                    markup_list.append(f"{indent_str}[green]- {item}[/green]")

    def _build_verbose_panel(self, title, data, color, session):
        if not data:
            content = Text(f"No {title} loaded.", style="dim")
        else:
            data_to_show = data.copy()
            data_to_show.pop('name', None)
            markup_lines = []
            self._add_nodes_recursively(markup_lines, data_to_show, indent=1, session=session)
            content = Text.from_markup("\n".join(markup_lines))
        return Panel(content, title=f"[b]{title}: {data.get('name', 'N/A') if data else 'N/A'}[/b]", border_style=color, expand=True)

    def _build_short_panel(self, title, data, color):
        content = Text()
        if not data:
            content.append(f"No {title} loaded.", style="dim")
            return Panel(content, title=f"[b]{title}[/b]", border_style=color, expand=True)

        preferred_keys = ['name', 'url', 'ip', 'path']
        for key in preferred_keys:
            if key in data:
                value = data[key]
                if isinstance(value, str) and len(value) > 30:
                    value = "..." + value[-27:]
                content.append(f"{key.capitalize():<12}: {value}\n")

        if title == "Tool" and 'commands' in data:
            commands = data.get('commands', [])
            if commands:
                content.append(f"{'Commands':<12}:\n")
                for cmd in commands:
                    cmd_name = cmd.get('name', 'N/A')
                    params_count = len(cmd.get('params', []))
                    content.append(f"  - {cmd_name} ({params_count} params)\n")

        other_keys_content = Text()
        handled_keys = set(preferred_keys) | {'notes', 'loot', 'commands'}
        for key, value in data.items():
            if key not in handled_keys:
                if isinstance(value, list):
                    display_val = f"[{len(value)} Items]"
                elif isinstance(value, dict):
                    keys_str = ", ".join(value.keys())
                    if len(keys_str) > 25:
                        keys_str = keys_str[:22] + "..."
                    display_val = f"{{{keys_str}}}"
                else:
                    display_val = str(value)
                if len(display_val) > 28:
                    display_val = display_val[:25] + "..."
                other_keys_content.append(f"{key.capitalize():<12}: {display_val}\n")
        
        if other_keys_content:
            content.append("----------\n", style="dim")
            content.append(other_keys_content)
        return Panel(content, title=f"[b]{title}[/b]", border_style=color, expand=True)

    def _build_short_report_panel(self, report_data, color):
        title = "Report"
        if not report_data:
            content = Text(f"No {title} loaded.", style="dim")
            return Panel(content, title=f"[b]{title}[/b]", border_style=color, expand=True)
        
        content = Text()
        content.append(f"{'Name':<12}: {report_data.get('name')}\n")
        
        findings_count = len(report_data.get('findings', []))
        notes_count = len(report_data.get('notes', []))
        loot_count = len(report_data.get('loot', []))
        
        content.append(f"{'Findings':<12}: {findings_count}\n")
        content.append(f"{'Notes':<12}: {notes_count}\n")
        content.append(f"{'Loot':<12}: {loot_count}\n")
        
        return Panel(content, title=f"[b]{title}[/b]", border_style=color, expand=True)

    def display_placeholders(self, placeholder_data: dict):
        """Displays a tree of all available placeholders."""

        table = Table(show_header=False, box=None, expand=True)
        table.add_column("Placeholder", style="green", no_wrap=True)
        table.add_column("Example Value", style="dim")

        for prefix, data in placeholder_data.items():
            if data:
                table.add_row(f"[bold blue]${prefix}[/bold blue]", "")
                # --- NEW: Manually add $report.path if it's a report ---
                # This placeholder is dynamically generated and not part of the
                # standard data dictionary, so we need to add it explicitly.
                if prefix == 'report':
                    table.add_row(f"  $report.path", "[dim]Absolute path to the report's data directory[/dim]")

                self._generate_placeholder_rows(table, data, f"${prefix}")

        panel = Panel(table, title="[bold]Available Placeholders[/bold]", border_style="blue", expand=True)
        self.console.print(panel)

    def _generate_placeholder_rows(self, table: Table, data, current_path: str, indent_level=1):
        """Recursively generates rows for the placeholder table."""
        indent = "  " * indent_level
        
        if isinstance(data, dict):
            for key, value in data.items():
                new_path = f"{current_path}.{key}"
                # --- FIX: Correctly handle nested dictionaries and lists ---
                # The previous check `isinstance(value, (dict, list)) and value` was too simple.
                # It failed to recurse correctly for the 'file' object, which is a dictionary
                # containing other dictionaries. We need to check the type and recurse,
                # even if the value is an empty dict/list, to show the path.
                if isinstance(value, dict):
                    table.add_row(f"{indent}{new_path}", "")
                    self._generate_placeholder_rows(table, value, new_path, indent_level + 1)
                elif isinstance(value, list):
                    table.add_row(f"{indent}{new_path}", f"[{len(value)} items]")
                    self._generate_placeholder_rows(table, value, new_path, indent_level + 1)
                else: # It's a simple value (string, int, etc.)
                    display_value = str(value)
                    if len(display_value) > 80: display_value = display_value[:77] + "..."
                    table.add_row(f"{indent}{new_path}", display_value)
        elif isinstance(data, list):
            for i, item in enumerate(data):
                new_path = f"{current_path}.{i}"
                if isinstance(item, (dict, list)):
                    table.add_row(f"{indent}{new_path}", "")
                    self._generate_placeholder_rows(table, item, new_path, indent_level + 1)
                else:
                    display_value = str(item)
                    if len(display_value) > 80: display_value = display_value[:77] + "..."
                    table.add_row(f"{indent}{new_path}", display_value)

    def _build_history_panel(self, history_data, report_name):
        if not history_data: return None
        table = Table(show_header=True, header_style="bold magenta", expand=True, box=None)
        table.add_column("Log ID", style="dim")
        table.add_column("Timestamp", style="dim")
        table.add_column("Tool", style="yellow")
        table.add_column("Command", style="green")
        for entry in history_data:
            tool_name = entry.get('tool')
            tool_cmd = entry.get('tool_command')
            tool_display = f"{tool_name or ''}"
            if tool_cmd:
                tool_display += f"([cyan]{tool_cmd}[/cyan])"

            table.add_row(
                str(entry.get('logbook_id', '')),
                entry.get('timestamp', '').split('T')[0],
                Text.from_markup(tool_display),
                entry.get('command', '')
            )
        return Panel(table, title="[b]Command History[/b]", border_style="dim", expand=True)

    def _build_findings_panel(self, findings_data, report_name):
        if not findings_data: return None
        table = Table(show_header=True, header_style="bold magenta", expand=True, box=None)
        table.add_column("Source", style="dim")
        table.add_column("Target", style="green")
        table.add_column("Category", style="yellow")
        table.add_column("Match", style="default")
        for finding in findings_data:
            table.add_row(
                f"Log #{finding.get('source_log_id')}",
                finding.get('target', 'N/A'),
                finding.get('category', 'N/A'),
                finding.get('match', '')
            )
        return Panel(table, title="[b]Parser Findings[/b]", border_style="dim", expand=True)

    def _build_notes_panel(self, notes_data, report_name):
        if not notes_data: return None
        table = Table(show_header=True, header_style="bold magenta", expand=True, box=None)
        table.add_column("#", style="dim", width=3)
        table.add_column("Timestamp", style="dim")
        table.add_column("Target Context", style="yellow")
        table.add_column("Note", style="white")
        for i, note in enumerate(notes_data, 1):
            table.add_row(str(i), note.get('timestamp', '').split('T')[0], note.get('target', 'N/A'), note.get('text', ''))
        return Panel(table, title="[b]Notes[/b]", border_style="dim", expand=True)

    def _build_loot_panel(self, loot_data, report_name):
        if not loot_data: return None
        table = Table(show_header=True, header_style="bold magenta", expand=True, box=None)
        table.add_column("#", style="dim", width=3)
        table.add_column("Timestamp", style="dim")
        table.add_column("Target Context", style="yellow")
        table.add_column("Type", style="yellow", width=15)
        table.add_column("Value", style="white")
        for i, loot in enumerate(loot_data, 1):
            table.add_row(str(i), loot.get('timestamp', '').split('T')[0], loot.get('target', 'N/A'), loot.get('type', 'N/A'), loot.get('value', ''))
        return Panel(table, title="[b]Loot[/b]", border_style="dim", expand=True)

    def _build_proxy_panel(self, proxy_data, color, is_short):
        title = "Proxy"
        if not proxy_data:
            content = Text("DISABLED", style="bold red")
            return Panel(content, title=f"[b]{title}[/b]", border_style=color, expand=True)
        content = Text()
        if is_short:
            content.append("Status: ENABLED\n", style="bold green")
            keys_to_show = ['wrapper_command', 'type', 'host', 'port']
            for key in keys_to_show:
                value = proxy_data.get(key)
                if value:
                    display_key = key.replace('_', ' ').capitalize()
                    content.append(f"{display_key:<18}: {value}\n")
        else:
            content.append(Text.from_markup("[bold blue]Status[/bold blue]: [bold green]ENABLED[/bold green]\n"))
            data_to_show = proxy_data.copy()
            if 'password' in data_to_show and data_to_show['password']:
                data_to_show['password'] = "********"
            for key, value in data_to_show.items():
                if value and key != 'status':
                    display_key = key.replace('_', ' ')
                    content.append(Text.from_markup(f"  [bold blue]{display_key}[/bold blue]: [green]{value}[/green]\n"))
        return Panel(content, title=f"[b]{title}[/b]", border_style=color, expand=True)

    # --- Proxy Status Display ---
    def display_proxy_status(self, global_settings, session_settings, effective_config):
        log.header("Proxy Status")
        
        effective_table = Table(show_header=False, box=None)
        effective_table.add_column(style="bold blue", no_wrap=True)
        effective_table.add_column(style="green")

        if effective_config:
            effective_table.add_row("Status", "[bold green]ENABLED[/bold green]")
            effective_table.add_row("Wrapper", effective_config.get('wrapper_command', '[dim]N/A[/dim]'))
            effective_table.add_row("Wrapper Options", effective_config.get('wrapper_options', '[dim]N/A[/dim]'))
            effective_table.add_row("Wrapper needs sudo", str(effective_config.get('wrapper_needs_sudo', 'N/A')))
            effective_table.add_row("Type", effective_config.get('type', '[dim]N/A[/dim]'))
            effective_table.add_row("Wrapper Template", effective_config.get('wrapper_template', '[dim]N/A[/dim]'))
            effective_table.add_row("Host", effective_config.get('host', '[dim]N/A[/dim]'))
            effective_table.add_row("Port", str(effective_config.get('port', '[dim]N/A[/dim]')))
            effective_table.add_row("Username", effective_config.get('username', '[dim]N/A[/dim]'))
            effective_table.add_row("Password", "[dim]********[/dim]" if effective_config.get('password') else '[dim]N/A[/dim]')
        else:
            effective_table.add_row("Status", "[bold red]DISABLED[/bold red]")
        self.console.print(Panel(effective_table, title="Effective Configuration", border_style="dim", expand=False))

        source_table = Table(caption="Settings from 'Session' override 'Global' settings from etc/config.json.", show_header=True, box=box.ROUNDED, header_style="bold magenta")
        source_table.add_column("Setting", style="bold blue", no_wrap=True)
        source_table.add_column("Active Value", style="green")
        source_table.add_column("Source", style="cyan")
        source_table.add_column("Global Default", style="dim")

        # Ensure the value from config is always a string before being used.
        global_enabled_str = str(global_settings.get("ENABLED", "false"))
        session_enabled_val = session_settings.get("enabled")
        if session_enabled_val is not None:
            source_table.add_row("enabled", str(session_enabled_val), "Session", global_enabled_str)
        else:
            source_table.add_row("enabled", global_enabled_str, "Global", global_enabled_str) # Now global_enabled_str is guaranteed to be a string

        for key in ['wrapper_command', 'wrapper_options', 'wrapper_needs_sudo', 'type', 'host', 'port', 'username', 'password', 'wrapper_template']:
            global_key = key.upper()
            global_val = global_settings.get(global_key)
            session_val = session_settings.get(key)

            if key == 'password' and global_val:
                global_display = "[dim]********[/dim]"
            else:
                global_display = str(global_val) if global_val is not None else '[i]Not set[/i]'

            if session_val is not None:
                session_display = "[dim]********[/dim]" if key == 'password' and session_val else str(session_val)
                source_table.add_row(key, session_display, "Session", global_display)
            else:
                source_table.add_row(key, global_display, "Global", global_display)
        self.console.print(Panel(source_table, title="Configuration Details", border_style="dim", expand=False))

    # --- Jobs Display ---
    def display_jobs_list(self, jobs):
        if not jobs:
            log.info("No active or finished jobs.")
            return

        table = Table(show_header=True, header_style="bold magenta", box=None, expand=True)
        table.add_column("ID", style="cyan", width=9)
        table.add_column("Session", style="cyan", no_wrap=True)
        table.add_column("Status", width=12)
        table.add_column("Duration", style="yellow", width=10, justify="right")
        table.add_column("Command", ratio=1, no_wrap=False)

        status_styles = {
            "running": "[bold green]Running[/bold green]",
            "finished": "[dim green]Finished[/dim green]",
            "failed": "[bold red]Failed[/bold red]",
            "killed": "[bold magenta]Killed[/bold magenta]",
            "pending": "[dim]Pending[/dim]"
        }

        for job in sorted(jobs, key=lambda j: j.id):
            status_text = status_styles.get(job.status, job.status)
            duration_str = f"{job.duration:.2f}s"
            table.add_row(str(job.id), job.session_name, status_text, duration_str, f"[dim]{job.command_str}[/dim]")
        
        panel = Panel(table, title="[bold]Background Jobs[/bold]", border_style="blue", expand=True)
        self.console.print(panel)

    def display_job_output(self, job):
        if not job:
            log.error(f"Job not found.")
            return

        # --- 1. Display the raw output ---
        self.console.rule(f"[bold blue]Output of Job {job.id}[/bold blue]")
        with job.lock:
            # Check if there is output before printing
            if job.output:
                self.console.file.write(job.output)
                self.console.file.flush()
                # Ensure a newline if the output doesn't have one
                if not job.output.endswith('\n'):
                    self.console.print()
            else:
                self.console.print("[dim]No output was captured for this job.[/dim]")

        self.console.rule(style="dim yellow")

        # --- 2. Build and display the summary panel ---
        status_map = {
            "finished": ("Finished", "bold green"),
            "failed": ("Failed", "bold red"),
            "killed": ("Killed", "bold magenta"),
            "running": ("Running", "bold yellow"),
            "pending": ("Pending", "dim default"),
        }
        status_text, status_style = status_map.get(job.status, (job.status.capitalize(), "bold yellow"))

        self.display_execution_summary(
            title="Job Summary",
            status_text=status_text,
            status_style=status_style,
            return_code=job.return_code,
            duration=job.duration,
            command_str=job.command_str,
            job_id=job.id,
            session_name=job.session_name
        )

    def display_execution_summary(self, title, status_text, status_style, return_code, duration, command_str, job_id=None, session_name=None, logbook_id=None):
        """Displays a standardized summary panel for command execution."""
        summary_table = Table(show_header=False, box=None, expand=True)
        summary_table.add_column(style="bold blue", width=12)
        summary_table.add_column()

        if job_id is not None:
            summary_table.add_row("Job ID", str(job_id)) # For background jobs
        if logbook_id is not None:
            summary_table.add_row("Logbook ID", str(logbook_id))
        if session_name:
            summary_table.add_row("Session", f"[cyan]{session_name}[/cyan]")
        
        summary_table.add_row("Status", f"[{status_style}]{status_text}[/{status_style}]")
        if return_code is not None:
            summary_table.add_row("Exit Code", str(return_code))
        summary_table.add_row("Time", f"{duration:.2f}s")
        summary_table.add_row("Command", command_str)
        if logbook_id:
            summary_table.add_row("", f"[dim]Use 'parser apply <parser> {logbook_id}' or 'logbook show {logbook_id}' to analyze.[/dim]")

        # Extract color from style string like "bold green" -> "green"
        border_color = status_style.split(' ')[-1]
        
        summary_panel = Panel(summary_table, title=f"[bold]{title}[/bold]", border_style=border_color, expand=True)
        self.console.print(summary_panel)

    # --- Session Display ---
    def display_session_status(self, session):
        if not session:
            log.warning("No active session.")
            return

        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column(style="bold blue", no_wrap=True, width=12)
        table.add_column(style="green")

        table.add_row("Target", session.target or "[dim]None[/dim]")
        table.add_row("Tool", session.tool or "[dim]None[/dim]")
        table.add_row("Wordlist", session.wordlist or "[dim]None[/dim]")

        panel = Panel(
            table,
            title=f":briefcase: [bold]Session: {session.name}[/bold]",
            border_style="cyan",
            expand=False
        )
        self.console.print(panel)

    def display_session_list(self, all_sessions, active_session_name):
        if not all_sessions:
            log.info("No sessions found.")
            return

        content = Text()
        for session_name in sorted(all_sessions):
            if session_name == active_session_name:
                content.append(f"• {session_name} (active)\n", style="bold cyan")
            else:
                content.append(f"• {session_name}\n", style="white")
        
        self.console.print(Panel(content, title="Available Sessions", border_style="dim", expand=False))

    def display_simple_list(self, items: list, title: str):
        """Displays a simple bulleted list of items inside a panel."""
        if not items:
            # The caller is responsible for logging a "not found" message.
            return

        # Use Text object for better control over styling in the future
        content = Text("\n".join([f"• {item}" for item in sorted(items)]))
        
        self.console.print(Panel(content, title=f"[bold]{title}[/bold]", border_style="dim", expand=False))

    def display_function_list(self, functions: list, title: str):
        """Displays a simple bulleted list of available functions."""
        if not functions:
            return

        content = Text("\n".join([f"• {func}" for func in sorted(functions)]))
        
        panel = Panel(content, title=f"[bold]{title}[/bold]", border_style="dim", expand=False)
        self.console.print(panel)
        self.console.print(Text.from_markup("[dim]Example: [green]print b64encode($target.name)[/green][/dim]"))

    def display_config(self, config_data: dict):
        """Displays the application configuration in a structured panel."""
        render_items = []
        for section, settings in config_data.items():
            if not isinstance(settings, dict):
                continue

            table = Table(show_header=False, box=None, padding=(0, 2))
            table.add_column(style="cyan", no_wrap=True)
            table.add_column() # No default style, we'll set it per row
            
            for key, value in sorted(settings.items()):
                if section == 'COLORS' and key != 'RESET':
                    # For colors, show a styled example instead of the raw code
                    reset_code = config_data.get('COLORS', {}).get('RESET', '')
                    # Directly use the ANSI escape codes for display
                    display_value = f"{value}Example Text{reset_code}"
                    table.add_row(key, display_value)
                elif key == 'LOOT_TYPES' and isinstance(value, list):
                    # For LOOT_TYPES, show a comma-separated string
                    table.add_row(key, Text(", ".join(value), style="green"))
                else:
                    # Default behavior for all other settings
                    table.add_row(key, Text(str(value), style="green"))
            
            panel = Panel(table, title=f"[bold]{section}[/bold]", border_style="dim", expand=True)
            render_items.append(panel)

        self.console.print(Panel(Group(*render_items), title="[bold]Application Configuration[/bold]", border_style="blue"))

    def display_hash_identification(self, hash_string: str, possible_types: list[str]):
        """Displays the results of a hash identification."""
        
        table = Table(show_header=False, box=None, expand=True)
        table.add_column(style="bold blue", width=15)
        table.add_column()

        table.add_row("Input String", f"[dim]{hash_string}[/dim]")
        table.add_row("Length", str(len(hash_string)))

        if possible_types:
            # Special case for MD5/NTLM ambiguity
            if "MD5" in possible_types and "NTLM" in possible_types:
                display_types = "[bold green]MD5, NTLM[/bold green]"
                table.add_row("Possible Types", Text.from_markup(display_types))
                table.add_row("Notes", "Indistinguishable by format. Common in Windows environments.")
            else:
                table.add_row("Possible Types", f"[bold green]{', '.join(possible_types)}[/bold green]")

            subtitle = "Based on length and character set."
            border_color = "green"
        else:
            table.add_row("Possible Types", "[bold red]Unknown or not a standard hash[/bold red]")
            subtitle = "The string does not match common hash formats."
            border_color = "red"

        panel = Panel(
            table,
            title="[bold]Hash Identification Results[/bold]",
            subtitle=f"[dim]{subtitle}[/dim]",
            border_style=border_color,
            expand=False
        )
        self.console.print(panel)


    def display_findings(self, findings: dict, title: str = "Parser Results", subtitle: str = None):
        """Displays the results of a parser run in a structured way."""
        if not findings:
            return

        render_items = []
        total_matches = 0

        for rule_name, matches in findings.items():
            total_matches += len(matches)
            table = Table(show_header=False, box=box.MINIMAL, expand=True)
            table.add_column(style="green")
            for match in matches:
                table.add_row(match)
            
            panel = Panel(table, title=f"[bold cyan]{rule_name}[/bold cyan] ({len(matches)} found)", border_style="dim", expand=True)
            render_items.append(panel)

        main_panel = Panel(
            Group(*render_items),
            title=f":mag: [bold]{title}[/bold] ({total_matches} total matches)",
            subtitle=f"[dim]{subtitle}[/dim]" if subtitle else None,
            border_style="magenta"
        )
        self.console.print(main_panel)