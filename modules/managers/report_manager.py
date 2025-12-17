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

# modules/managers/report_manager.py

import argparse
from .base_manager import JSONManager, _add_data_to_table_recursively
from modules.services import log
from rich.panel import Panel
from rich.table import Table
from rich.console import Group
from rich.text import Text
from datetime import datetime
import shlex
import os
from ..services import config
import csv
from rich.syntax import Syntax

class ReportManager(JSONManager):
    def __init__(self):
        super().__init__("REPORTS")

    def dispatch(self, subcommand, args, cli_instance):
        """
        Overrides BaseManager's dispatch to handle the case where no subcommand is given,
        and to route 'note' and 'loot' commands.
        """
        # This is a bit of a special case. The 'note' and 'loot' commands are
        # handled by this manager. We check the command from the CLI instance.
        command_invoked = cli_instance.last_command

        if command_invoked in ['note', 'loot']:
            # We need to construct the correct handler name, e.g., _cmd_add_note
            handler_method_name = f"_cmd_{subcommand}_{command_invoked}"
            handler = getattr(self, handler_method_name, None)
            if callable(handler):
                handler(args, cli_instance)
                return True
            return False # Let the caller know it wasn't handled

        return super().dispatch(subcommand, args, cli_instance)

    def list_files(self, report_name: str) -> list:
        """
        Lists files within a specific report's data folder.
        This is used for CLI suggestions.
        """
        if not report_name:
            return []
        report_dir = os.path.join(self.folder, report_name)
        if not os.path.isdir(report_dir):
            return []
        try:
            # Return only files, not directories, for the 'view' command context
            return sorted([f for f in os.listdir(report_dir) if os.path.isfile(os.path.join(report_dir, f))])
        except OSError:
            return []

    def list_files_details(self, report_name: str) -> list:
        """
        Lists files and directories within a report's data folder with details.
        This is the centralized method used by both the CLI and Web UI.
        Returns a list of dicts: [{'name': str, 'type': 'file'|'dir', 'size': int|None}]
        """
        if not report_name:
            return []
        report_dir = os.path.join(self.folder, report_name)
        if not os.path.isdir(report_dir):
            return []

        items = []
        for item_name in sorted(os.listdir(report_dir)):
            item_path = os.path.join(report_dir, item_name)
            try:
                if os.path.isdir(item_path):
                    items.append({'name': item_name, 'type': 'dir', 'size': None})
                else:
                    items.append({'name': item_name, 'type': 'file', 'size': os.path.getsize(item_path)})
            except OSError as e:
                log.warning(f"Could not stat item '{item_path}': {e}")
        return items

    def _cmd_load(self, args, cli):
        """Loads a report into the active session."""
        if not self.load(args.name):
            return # load() already logs an error
        cli.session.report = args.name
        log.success(f"Report '{args.name}' loaded into session.")

    def add_history_entry(self, report_name, command_str, logbook_id, tool_name, tool_command_name):
        """Adds a command execution to the report's history."""
        report_data = self.load(report_name)
        if not report_data:
            return

        history = report_data.setdefault('history', [])
        new_entry = {
            "timestamp": datetime.now().isoformat(),
            "command": command_str,
            "logbook_id": logbook_id,
            "tool": tool_name,
            "tool_command": tool_command_name
        }
        history.append(new_entry)
        self.update(report_name, 'history', history)

    def add_findings(self, report_name, source_log_id, parser_name, target_name, new_findings):
        """Adds parser findings to a report."""
        report_data = self.load(report_name)
        if not report_data:
            return

        findings = report_data.setdefault('findings', [])
        count = 0
        for category, matches in new_findings.items():
            for match in matches:
                # Create the full new finding object
                new_finding = {
                    "timestamp": datetime.now().isoformat(),
                    "source_log_id": source_log_id,
                    "parser": parser_name,
                    "target": target_name or "N/A",
                    "category": category,
                    "match": match
                }
                # A finding is a duplicate if another finding exists with the same source, parser, category, and match.
                is_duplicate = any(
                    f.get('source_log_id') == source_log_id and f.get('parser') == parser_name and f.get('category') == category and f.get('match') == match
                    for f in findings
                )

                if not is_duplicate:
                    findings.append(new_finding)
                    count += 1
        
        self.update(report_name, 'findings', findings)
        log.success(f"Added {count} new finding(s) to report '{report_name}'.")

    def _get_current_report(self, cli):
        """Helper method to get and validate the currently loaded report."""
        report_name = cli.session.report
        if not report_name:
            log.error("No report loaded. Please run 'report load <name>'.")
            return None, None
        report_data = self.load(report_name)
        if not report_data:
            return None, None # self.load() already logs an error message
        return report_name, report_data

    def _cmd_add_note(self, args, cli):
        """Adds a note to the currently loaded report."""
        if not cli.session.report:
            log.error("No report loaded. Notes can only be managed when a report is loaded.")
            log.prompt("Load a report with 'report load <name>'.")
            return
        report_name, report_data = self._get_current_report(cli)
        if not report_name: return

        notes = report_data.setdefault('notes', [])
        note_text = " ".join(args.text)
        new_note = {
            "timestamp": datetime.now().isoformat(),
            "text": note_text,
            "target": cli.session.target or "N/A" # Add context
        }
        notes.append(new_note)
        self.update(report_name, 'notes', notes)
        log.success(f"Note added to report '{report_name}'.")

    def _cmd_list_note(self, args, cli):
        """Lists all notes for the currently loaded report."""
        if not cli.session.report:
            log.error("No report loaded. Notes can only be managed when a report is loaded.")
            log.prompt("Load a report with 'report load <name>'.")
            return
        report_name, report_data = self._get_current_report(cli)
        if not report_name: return

        notes = report_data.get('notes', [])
        if not notes:
            log.info(f"No notes available in report '{report_name}'.")
            return

        table = Table(title=f"Notes in Report: {report_name}", show_header=True, header_style="bold magenta", expand=True)
        table.add_column("#", style="dim", width=3)
        table.add_column("Timestamp", style="cyan", min_width=20)
        table.add_column("Target Context", style="yellow")
        table.add_column("Note", style="white")
        
        for i, note in enumerate(notes, 1):
            table.add_row(str(i), note.get('timestamp', '').split('T')[0], note.get('target', 'N/A'), note.get('text', ''))
        cli.console.print(table)

    def _cmd_delete_note(self, args, cli):
        """Deletes a note by its index from the currently loaded report."""
        if not cli.session.report:
            log.error("No report loaded. Notes can only be managed when a report is loaded.")
            log.prompt("Load a report with 'report load <name>'.")
            return
        report_name, report_data = self._get_current_report(cli)
        if not report_name: return

        notes = report_data.get('notes', [])
        index = args.index - 1 # User-facing is 1-based
        if 0 <= index < len(notes):
            removed_note = notes.pop(index)
            self.update(report_name, 'notes', notes)
            log.success(f"Note {args.index} deleted from report '{report_name}'.")
        else:
            log.error(f"Invalid index. There are only {len(notes)} notes.")

    def _cmd_add_loot(self, args, cli):
        """Adds a loot entry to the currently loaded report."""
        if not cli.session.report:
            log.error("No report loaded. Loot can only be managed when a report is loaded.")
            log.prompt("Load a report with 'report load <name>'.")
            return
        report_name, report_data = self._get_current_report(cli)
        if not report_name: return

        loots = report_data.setdefault('loot', [])
        loot_value = " ".join(args.value)
        new_loot = {
            "timestamp": datetime.now().isoformat(),
            "type": args.type,
            "value": loot_value,
            "target": cli.session.target or "N/A" # Add context
        }
        loots.append(new_loot)
        self.update(report_name, 'loot', loots)
        log.success(f"Loot ({args.type}) added to report '{report_name}'.")

    def _cmd_list_loot(self, args, cli):
        """Lists all loot entries for the currently loaded report."""
        if not cli.session.report:
            log.error("No report loaded. Loot can only be managed when a report is loaded.")
            log.prompt("Load a report with 'report load <name>'.")
            return
        report_name, report_data = self._get_current_report(cli)
        if not report_name: return

        loots = report_data.get('loot', [])
        if not loots:
            log.info(f"No loot available in report '{report_name}'.")
            return

        table = Table(title=f"Loot in Report: {report_name}", show_header=True, header_style="bold magenta", expand=True)
        table.add_column("#", style="dim", width=3)
        table.add_column("Type", style="yellow", width=15)
        table.add_column("Target Context", style="yellow")
        table.add_column("Value", style="white")

        for i, loot in enumerate(loots, 1):
            table.add_row(str(i), loot.get('type', 'N/A'), loot.get('target', 'N/A'), loot.get('value', ''))
        cli.console.print(table)

    def _cmd_delete_loot(self, args, cli):
        """Deletes a loot entry by its index from the currently loaded report."""
        if not cli.session.report:
            log.error("No report loaded. Loot can only be managed when a report is loaded.")
            log.prompt("Load a report with 'report load <name>'.")
            return
        report_name, report_data = self._get_current_report(cli)
        if not report_name: return

        loots = report_data.get('loot', [])
        index = args.index - 1 # User-facing is 1-based
        if 0 <= index < len(loots):
            removed_loot = loots.pop(index)
            self.update(report_name, 'loot', loots)
            log.success(f"Loot entry {args.index} deleted from report '{report_name}'.")
        else:
            log.error(f"Invalid index. There are only {len(loots)} loot entries.")

    def _cmd_show(self, args, cli):
        """Handles 'report show [name]'."""
        report_name = args.name
        if not report_name:
            # If no name is provided, use the one from the session
            report_name = cli.session.report
            if not report_name:
                log.error("No report specified and no report loaded in the session.")
                log.prompt("Use 'report show <name>' or load one with 'report load <name>'.")
                return

        report_data = self.load(report_name)
        if not report_data:
            return # load() already logs an error

        self._format_and_show_entity(report_data, cli.console)

    def _cmd_delete(self, args, cli):
        """Handles 'report delete' as an alias for destroy."""
        log.info(f"For reports, 'delete' is an alias for 'destroy'. Deleting report '{args.name}'...")
        self.destroy(args.name)

    def _format_and_show_entity(self, entity, console):
        """Displays the contents of a report."""
        name = entity.get('name', 'N/A')
        
        panels = []
        
        # History Panel
        history = entity.get('history', [])
        if history:
            table = Table(show_header=True, header_style="bold blue", box=None, expand=True)
            table.add_column("Log ID", style="dim")
            table.add_column("Timestamp", style="dim")
            table.add_column("Tool", style="yellow")
            table.add_column("Command", style="green")
            for h in history:
                tool_name = h.get('tool')
                tool_cmd = h.get('tool_command')
                tool_display = f"{tool_name or ''}"
                if tool_cmd:
                    tool_display += f"([cyan]{tool_cmd}[/cyan])"

                table.add_row(str(h.get('logbook_id', '')), h.get('timestamp', '').replace('T', ' '), Text.from_markup(tool_display), h.get('command', ''))
            panels.append(Panel(table, title="[bold]Command History[/bold]", border_style="dim"))

        # Findings Panel
        findings = entity.get('findings', [])
        if findings:
            table = Table(show_header=True, header_style="bold blue", box=None, expand=True)
            table.add_column("Timestamp", style="dim")
            table.add_column("Source", style="dim")
            table.add_column("Target", style="green")
            table.add_column("Category", style="yellow")
            table.add_column("Match", style="default")
            for f in findings:
                table.add_row(f.get('timestamp', '').replace('T', ' '), f"Log #{f.get('source_log_id')}", f.get('target', 'N/A'), f.get('category', 'N/A'), f.get('match', ''))
            panels.append(Panel(table, title="[bold]Parser Findings[/bold]", border_style="dim"))

        # Notes Panel
        notes = entity.get('notes', [])
        if notes:
            table = Table(show_header=True, header_style="bold blue", box=None, expand=True)
            table.add_column("#", style="dim", width=3)
            table.add_column("Timestamp", style="dim")
            table.add_column("Target", style="green")
            table.add_column("Note", style="default")
            for i, n in enumerate(notes, 1):
                table.add_row(str(i), n.get('timestamp', '').replace('T', ' '), n.get('target', 'N/A'), n.get('text', ''))
            panels.append(Panel(table, title="[bold]Notes[/bold]", border_style="dim"))

        # Loot Panel
        loots = entity.get('loot', [])
        if loots:
            table = Table(show_header=True, header_style="bold blue", box=None, expand=True)
            table.add_column("#", style="dim", width=3)
            table.add_column("Timestamp", style="dim")
            table.add_column("Target", style="green")
            table.add_column("Type", style="yellow")
            table.add_column("Value", style="default")
            for i, l in enumerate(loots, 1):
                table.add_row(
                    str(i),
                    l.get('timestamp', '').replace('T', ' '),
                    l.get('target', 'N/A'),
                    l.get('type', 'N/A'),
                    l.get('value', '')
                )
            panels.append(Panel(table, title="[bold]Loot[/bold]", border_style="dim"))

        if not panels:
            console.print(Panel(f"[dim]Report '{name}' is empty.[/dim]", title=f":clipboard: [bold]Report: {name}[/bold]", border_style="yellow"))
            return
        
        main_panel = Panel(Group(*panels), title=f":clipboard: [bold]Report: {name}[/bold]", border_style="yellow", expand=True)
        console.print(main_panel)

    def _cmd_view(self, args, cli):
        """Handles 'report view <file_name>'."""
        # Determine report_name and file_name based on provided arguments
        if args.arg2:
            # Case: report view <report_name> <file_name>
            report_name = args.arg1
            file_name = args.arg2
        else:
            # Case: report view <file_name> (requires a loaded report)
            report_name, _ = self._get_current_report(cli)
            if not report_name:
                log.prompt("Or specify the report name: 'report view <report_name> <file_name>'")
                return
            file_name = args.arg1

        file_path = os.path.join(self.folder, report_name, file_name)

        if not os.path.isfile(file_path):
            log.error(f"File '{file_name}' not found in report '{report_name}'.")
            # Suggest available files
            files = self.list_files(report_name)
            if files:
                log.prompt(f"Available files: {', '.join(files)}")
            return

        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

            _, extension = os.path.splitext(file_name)
            file_type = extension.lstrip('.').lower()

            panel_title = f":page_facing_up: [bold]File: {file_name}[/bold] in Report: [cyan]{report_name}[/cyan]"

            if file_type == 'csv':
                reader = csv.reader(content.splitlines())
                rows = list(reader)
                if not rows:
                    cli.console.print(Panel("[dim]CSV file is empty.[/dim]", title=panel_title, border_style="blue"))
                    return

                table = Table(show_header=True, header_style="bold magenta")
                for header in rows[0]:
                    table.add_column(header)
                for row in rows[1:]:
                    table.add_row(*row)
                cli.console.print(Panel(table, title=panel_title, border_style="blue"))

            elif file_type in ['json', 'xml', 'yaml', 'yml']:
                syntax = Syntax(content, file_type, theme="monokai", line_numbers=True)
                cli.console.print(Panel(syntax, title=panel_title, border_style="blue"))
            else:
                # Plain text
                cli.console.print(Panel(Text(content), title=panel_title, border_style="blue"))

        except Exception as e:
            log.error(f"Error reading or displaying file '{file_name}': {e}")

    def _cmd_export(self, args, cli):
        """Generates the pwnity commands to reconstruct a report."""
        name = args.name
        data = self.load(name)
        if not data:
            return

        commands = []
        commands.append(f"report add {name}")
        commands.append(f"report load {name}")

        # Export notes
        for note in data.get('notes', []):
            if 'text' in note:
                commands.append(f"note add {shlex.quote(note['text'])}")

        # Export loot
        for item in data.get('loot', []):
            if 'type' in item and 'value' in item:
                commands.append(f"loot add {item['type']} {shlex.quote(item['value'])}")

        # Export parser findings by re-running the parser
        findings_sources = data.get('findings', [])
        if findings_sources:
            parser_commands = set()
            for finding_source in findings_sources:
                log_id = finding_source.get('source_log_id')
                parser_name = finding_source.get('parser')
                if log_id is not None and parser_name:
                    parser_commands.add(f"parser apply {parser_name} {log_id}")
            commands.extend(sorted(list(parser_commands)))

        output_content = "\n".join(commands)
        cli.poutput(output_content)

    def _cmd_render(self, args, cli):
        """Renders a human-readable summary of a report to a file."""
        name = args.name
        data = self.load(name)
        if not data:
            return

        # --- REFACTOR: Modularize the rendering process for clarity and better output ---
        lines = []
        lines.append(f"# pwnity Report: {name}")
        lines.append(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

        # --- NEW: Identify and summarize all targets involved in the report ---
        all_targets = set()
        for section in ['notes', 'loot', 'findings']:
            for item in data.get(section, []):
                if item.get('target') and item.get('target') != 'N/A':
                    all_targets.add(item.get('target'))
        if all_targets:
            lines.append("## Involved Targets\n")
            for target in sorted(list(all_targets)):
                lines.append(f"- `{target}`")
            lines.append("")

        # --- NEW: Render Command History ---
        history = data.get('history', [])
        if history:
            lines.append("## Command History\n")
            lines.append("| Timestamp | Tool | Command | Log ID |")
            lines.append("|---|---|---|---|")
            for item in history:
                ts = datetime.fromisoformat(item.get('timestamp', '')).strftime('%Y-%m-%d %H:%M')
                tool = item.get('tool', 'N/A')
                cmd = item.get('command', '')
                log_id = item.get('logbook_id', 'N/A')
                lines.append(f"| {ts} | `{tool}` | `{cmd}` | `{log_id}` |")
            lines.append("")

        # Render Notes
        notes = data.get('notes', [])
        if notes:
            lines.append("## Notes\n")
            lines.append("| Timestamp | Target | Note |")
            lines.append("|---|---|---|")
            for note in notes:
                ts = datetime.fromisoformat(note.get('timestamp', '')).strftime('%Y-%m-%d')
                target_ctx = note.get('target', 'N/A')
                text = note.get('text', '').replace('|', '\\|') # Escape pipe characters for Markdown table
                lines.append(f"| {ts} | `{target_ctx}` | {text} |")
            lines.append("")

        # Render Loot
        # --- REFACTORED: Render Loot grouped by type in tables ---
        loots = data.get('loot', [])
        if loots:
            lines.append("## Loot\n")
            for loot in loots:
                target_ctx = loot.get('target', 'N/A')
                lines.append(f"- **Type:** `{loot.get('type', 'N/A')}` | **Target:** `{target_ctx}`")
                lines.append(f"  - **Value:** `{loot.get('value', '')}`")
            grouped_loot = {}
            for item in loots:
                loot_type = item.get('type', 'Uncategorized')
                grouped_loot.setdefault(loot_type, []).append(item)
            
            for loot_type, items in sorted(grouped_loot.items()):
                lines.append(f"### Loot Type: `{loot_type}`\n")
                lines.append("| Target | Value |")
                lines.append("|---|---|")
                for item in items:
                    target = item.get('target', 'N/A')
                    value = item.get('value', '').replace('|', '\\|') # Escape pipe characters for Markdown table
                    lines.append(f"| `{target}` | `{value}` |")
                lines.append("")
            lines.append("")

        # Render Parser Findings
        # --- REFACTORED: Render Parser Findings grouped by category in tables ---
        findings = data.get('findings', [])
        if findings:
            lines.append("## Parser Findings\n")
            for finding in findings:
                lines.append(f"- **Category:** `{finding.get('category', 'N/A')}` | **Target:** `{finding.get('target', 'N/A')}` | **Source:** `Log #{finding.get('source_log_id')}`")
                lines.append(f"  - **Match:** `{finding.get('match', '')}`")
            grouped_findings = {}
            for item in findings:
                category = item.get('category', 'Uncategorized')
                grouped_findings.setdefault(category, []).append(item)

            for category, items in sorted(grouped_findings.items()):
                lines.append(f"### Finding Category: `{category}`\n")
                lines.append("| Target | Match | Source Log |")
                lines.append("|---|---|---|")
                unique_items = []
                for item in items:
                    # Create a tuple to identify unique findings within the category
                    unique_key = (item.get('target'), item.get('match'))
                    if unique_key not in [ui[0] for ui in unique_items]:
                        unique_items.append((unique_key, item))
                
                for _, item in unique_items:
                    target = item.get('target', 'N/A')
                    match = item.get('match', '').replace('|', '\\|') # Escape pipe characters for Markdown table
                    log_id = item.get('source_log_id', 'N/A')
                    lines.append(f"| `{target}` | `{match}` | `Log #{log_id}` |")
                lines.append("")
            lines.append("")

        output_content = "\n".join(lines)

        export_base_dir = config.get_parameter("DIRS", "EXPORTS", "exports")
        report_export_dir = os.path.join(export_base_dir, "reports")
        os.makedirs(report_export_dir, exist_ok=True)

        # Use .md as the default extension for Markdown
        output_filename = args.output_file or f"{name}.md"
        output_path = output_filename
        if not os.path.dirname(output_path):
            output_path = os.path.join(report_export_dir, output_path)

        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(output_content)
            log.success(f"Report '{name}' rendered successfully to '{output_path}'.")
        except Exception as e:
            log.error(f"Failed to write rendered file to '{output_path}': {e}")