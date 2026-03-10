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

# modules/managers/run_manager.py

from .base_manager import JSONManager, _add_data_to_table_recursively
from modules.services import log
from rich.panel import Panel
from rich.table import Table
from rich.console import Group
from rich.text import Text
import time, uuid, sys

class LogbookManager(JSONManager):
    def __init__(self):
        super().__init__("LOGBOOK")
        # --- NEU: Aktiviere die verschachtelte Speicherstruktur für diesen Manager ---
        self.use_nested_structure = True

    def create_entry(self, command_str, output, return_code, duration, session_obj, source_job_id=None, additional_info=None):
        """Creates and saves a new logbook entry."""
        # --- FINAL FIX: Determine the next ID at the moment of creation ---
        # This prevents race conditions between different processes (e.g., UI and CLI).
        entry_id = str(uuid.uuid4())

        context_data = {}
        if session_obj:
            # --- FINAL FIX: Handle both CLISession objects and workflow context dicts ---
            # For CLI jobs, session_obj is a CLISession object with attributes.
            # For workflow jobs, session_obj is a dictionary from WorkflowContext.to_dict().
            if isinstance(session_obj, dict):
                context_data = {
                    "session": session_obj.get("session", "workflow"), # Workflows don't have a session name, provide a default.
                    "target": session_obj.get("target"),
                    "tool": session_obj.get("tool"),
                    "wordlist": session_obj.get("wordlist"),
                }
            else: # It's a CLISession object
                context_data = { "session": session_obj.name, "target": session_obj.target, "tool": session_obj.tool, "wordlist": session_obj.wordlist }

        entry_data = {
            "id": entry_id,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "command": command_str,
            "context": context_data,
            "execution": {
                "duration_seconds": round(duration, 2),
                "return_code": return_code,
            },
            "output": output,
            "source_job_id": source_job_id, # Store the originating job ID
            "additional_info": additional_info or {},
        }
        
        # Save the complete data object in a single, atomic operation.
        if self._save_data(str(entry_id), entry_data):
            log.debug(f"Logbook entry {entry_id} created and saved.")
            return entry_id
        return None

    def _display_entries_table(self, entries, title, subtitle, console):
        """Helper function to display a list of logbook entries in a table.""" # The 'entries' argument is now correctly used.
        if not entries:
            log.info("No logbook entries have been recorded yet.")
            return

        table = Table(show_header=True, header_style="bold blue", box=None, expand=True)
        table.add_column("Log ID", style="cyan", no_wrap=True, width=38) # UUIDs are 36 chars
        table.add_column("Timestamp", style="dim", width=20)
        table.add_column("Command", style="green", ratio=1, no_wrap=False)

        for entry_data in entries:
            if entry_data:
                table.add_row(
                    str(entry_data.get('id', 'N/A')),
                    entry_data.get('timestamp'),
                    entry_data.get('command')
                )

        panel = Panel(
            table,
            title=title,
            subtitle=subtitle,
            border_style="cyan",
            expand=True
        )
        console.print(panel)

    def _get_single_key(self):
        """Reads a single key press from the terminal (Linux only)."""
        import tty, termios
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(sys.stdin.fileno())
            ch = sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        return ch

    def _display_chunked_entries(self, entries, title, base_subtitle, cli, chunk_size=20):
        """Helper to display entries in chunks of 20 with a 'More' prompt."""
        total = len(entries)
        if total == 0:
            log.info("No matching logbook entries found.")
            return

        # If we are headless, don't chunk interactively
        if getattr(cli, 'headless_mode', False):
            self._display_entries_table(entries, title, base_subtitle, cli.console)
            return

        # If we have 20 or fewer entries, just show them all.
        if total <= chunk_size:
            self._display_entries_table(entries, title, base_subtitle, cli.console)
            return

        # Interactive chunking
        for i in range(0, total, chunk_size):
            chunk = entries[i:i + chunk_size]
            current_count = i + len(chunk)
            
            # Refined subtitle logic
            chunk_info = f"[dim](Showing {i+1}-{current_count} of {total})[/dim]"
            subtitle = f"{base_subtitle} {chunk_info}"

            self._display_entries_table(chunk, title, subtitle, cli.console)

            if current_count < total:
                prompt_line = Text.assemble(
                    ("-- Press ", "bold cyan"),
                    ("[Space]", "bold white"),
                    (" for next page, ", "bold cyan"),
                    ("[q]", "bold white"),
                    (" to quit -- ", "bold cyan"),
                    (f"({total - current_count} entries remaining)", "dim")
                )
                cli.console.print(prompt_line, end="\r")
                
                try:
                    while True:
                        key = self._get_single_key()
                        if key.lower() == 'q' or key == '\x03': # q or Ctrl+C
                            cli.console.print(" " * len(prompt_line.plain), end="\r") # Clear prompt
                            return
                        if key == ' ' or key == '\r' or key == '\n': # Space or Enter
                            cli.console.print(" " * len(prompt_line.plain), end="\r") # Clear prompt
                            break
                except Exception:
                    # Fallback for non-TTY or errors
                    if input().lower().startswith('q'):
                        break

    def _cmd_list(self, args, cli):
        """Handles 'logbook list'."""
        limit = args.limit
        all_entry_ids = self.list_all()
        all_entries_data = [self.load(entry_id) for entry_id in all_entry_ids if self.load(entry_id)]
        
        # Sort by timestamp and take the most recent ones
        sorted_entries = sorted(all_entries_data, key=lambda x: x.get('timestamp', ''), reverse=True)
        entries_to_show = sorted_entries[:limit] if limit > 0 else sorted_entries

        # Clearer base subtitle
        if limit > 0:
            subtitle = f"Showing the last {len(entries_to_show)} of {len(all_entries_data)} entries."
        else:
            subtitle = f"Showing all {len(all_entries_data)} entries."

        self._display_chunked_entries(
            entries=entries_to_show,
            title=":scroll: [bold]Execution Logbook[/bold]",
            base_subtitle=subtitle,
            cli=cli
        )

    def _cmd_filter(self, args, cli):
        """Handles 'logbook filter'."""
        all_entry_ids = self.list_all()
        all_entries_data = [self.load(entry_id) for entry_id in all_entry_ids if self.load(entry_id)]

        filtered_entries = []
        filter_type = args.type
        filter_value = args.value.lower()

        for entry in all_entries_data:
            if filter_type == 'status':
                rc = entry.get('execution', {}).get('return_code')
                is_success = rc == 0
                if (filter_value == 'success' and is_success) or (filter_value in ['failed', 'fail'] and not is_success):
                    filtered_entries.append(entry)
            else: # target, tool, session
                context_value = entry.get('context', {}).get(filter_type)
                if context_value and context_value.lower() == filter_value:
                    filtered_entries.append(entry)
        
        # Sort by timestamp and apply the limit
        sorted_filtered = sorted(filtered_entries, key=lambda x: x.get('timestamp', ''), reverse=True)
        entries_to_show = sorted_filtered[:args.limit] if args.limit > 0 else sorted_filtered

        # Clearer base subtitle
        if args.limit > 0:
            subtitle = f"Showing {len(entries_to_show)} of {len(filtered_entries)} matching entries."
        else:
            subtitle = f"Showing all {len(filtered_entries)} matching entries."

        self._display_chunked_entries(
            entries=entries_to_show,
            title=f":mag: [bold]Filtered Logbook: {args.type} = '{args.value}'[/bold]",
            base_subtitle=subtitle,
            cli=cli
        )

    def _cmd_show(self, args, cli):
        """Handles 'logbook show'."""
        entry_id = str(args.id)
        
        # --- NEW: Allow matching by UUID prefix ---
        all_ids = self.list_all()
        matching_ids = [full_id for full_id in all_ids if full_id.startswith(entry_id)]

        if len(matching_ids) == 1:
            entry_data = self.load(matching_ids[0])
            # Use the full ID for display purposes
            entry_id = matching_ids[0]
        elif len(matching_ids) > 1:
            log.error(f"Ambiguous logbook ID prefix '{entry_id}'. Multiple entries found.")
            return
        else:
            entry_data = self.load(entry_id) # Try exact match as a fallback

        if not entry_data:
            log.error(f"Logbook entry with ID {entry_id} not found.")
            return
        
        cli.console.rule(f"[bold blue]Output of Logbook Entry #{entry_id}[/bold blue]")
        cli.console.print(Text(entry_data.get('output', '[dim]No output captured.[/dim]')))
        cli.console.rule(style="dim yellow")

        # --- Display a consistent summary panel ---
        execution_data = entry_data.get('execution', {})
        context_data = entry_data.get('context', {})
        return_code = execution_data.get('return_code')

        if return_code == 0:
            status_text, status_style = "Finished", "bold green"
        else:
            status_text, status_style = "Failed", "bold red"

        cli.display_mgr.display_execution_summary(
            title="Logbook Entry Summary",
            status_text=status_text,
            status_style=status_style,
            return_code=return_code,
            duration=execution_data.get('duration_seconds', 0),
            command_str=entry_data.get('command', ''),
            logbook_id=entry_data.get('id'),
            session_name=context_data.get('session'),
            timestamp=entry_data.get('timestamp')
        )