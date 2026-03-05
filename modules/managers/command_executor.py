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

# modules/command_executor.py
import subprocess
import shlex
import time
import os
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from ..services import log
import io
from typing import TYPE_CHECKING

# This prevents a circular import at runtime but allows type checkers to see the import.
if TYPE_CHECKING:
    from modules.managers.job_manager import JobManager

class CommandExecutor:
    def __init__(self, job_mgr: "JobManager", logbook_mgr, report_mgr, display_mgr):
        self.job_mgr = job_mgr
        self.logbook_mgr = logbook_mgr
        self.report_mgr = report_mgr
        self.display_mgr = display_mgr
        self.console = Console()

    def execute(self, command_lists: list[list[str]], session_obj, tool_name: str, tool_command_name: str, run_now: bool, run_bg: bool, suppress_individual_summaries: bool = False, temp_proxy_conf_path: str = None):
        """Executes a list of commands either in the background or foreground."""
        try:
            if run_bg:
                # --- FIX: The job start message was not being displayed immediately. ---
                # We now collect the job IDs and log the success message directly.
                # This ensures the user gets immediate feedback.
                return self.job_mgr.start_job(
                    command_lists[0], session_obj=session_obj,
                    tool_name=tool_name, tool_command_name=tool_command_name,
                    temp_proxy_conf_path=temp_proxy_conf_path
                )
            elif run_now:
                start_time = time.monotonic()
                success_count = 0
                fail_count = 0

                for cmd_list in command_lists:
                    return_code = self._run_foreground(
                        cmd_list, session_obj, tool_name, tool_command_name,
                        show_summary=not suppress_individual_summaries
                    )
                    if return_code == 0:
                        success_count += 1
                    else:
                        fail_count += 1
                
                if suppress_individual_summaries:
                    duration = time.monotonic() - start_time
                    status_text = "All steps completed"
                    status_style = "bold green"
                    border_color = "green"
                    if fail_count > 0:
                        status_text = f"{fail_count} step(s) failed"
                        status_style = "bold red"
                        border_color = "red"
                    
                    self.display_mgr.display_execution_summary(
                        title="[bold]Overall Summary[/bold]",
                        status_text=status_text,
                        status_style=status_style,
                        return_code=None, # No single return code for multiple commands
                        duration=duration,
                        command_str=f"{len(command_lists)} commands executed",
                        logbook_id=None,
                        session_name=session_obj.name,
                        border_color=border_color,
                        timestamp=time.strftime("%Y-%m-%d %H:%M:%S")
                    )
        finally:
            # --- FINAL FIX: Centralized cleanup logic ---
            # This block runs after the job is started in the background or after all foreground jobs are finished.
            # For background jobs, the JobManager is now responsible for cleanup.
            if run_now and temp_proxy_conf_path and os.path.exists(temp_proxy_conf_path):
                try:
                    os.remove(temp_proxy_conf_path)
                    log.debug(f"Cleaned up temporary proxy config file: {temp_proxy_conf_path}")
                except OSError as e:
                    log.warning(f"Failed to clean up temp proxy config file: {e}")

    def _run_foreground(self, cmd_list: list, session_obj, tool_name, tool_command_name, show_summary: bool = True) -> int:
        cmd_str = shlex.join(cmd_list)
        start_time = time.monotonic()
        return_code = -1
        process = None
        status_text = "Failed"
        status_style = "bold red"
        output_buffer = io.BytesIO()

        try:
            import pty
            import sys

            if show_summary:
                self.console.rule(style="dim yellow")

            def master_read(fd):
                data = os.read(fd, 1024)
                if data:
                    output_buffer.write(data)
                return data

            # Execute via pty.spawn to provide a TTY and allow interactivity.
            # This is synchronous and will block until the process finishes.
            # The master_read callback captures the output for the logbook.
            try:
                status = pty.spawn(cmd_list, master_read)
                return_code = os.WEXITSTATUS(status) if os.WIFEXITED(status) else (status if status >= 0 else 1)
            except Exception as e:
                self.console.print(f"[bold red]An error occurred during interactive execution: {e}[/bold red]")
                return -1

            if return_code == 0:
                status_text = "Success"
                status_style = "bold green"
            elif return_code == 130:
                status_text = "Interrupted"
                status_style = "bold yellow"
            else:
                status_text = "Failed"
                status_style = "bold red"

        except KeyboardInterrupt:
            self.console.print()
            log.warning("Command interrupted by user.")
            return_code = 130
            status_text = "Interrupted"
            status_style = "bold yellow"
        except FileNotFoundError:
            self.console.print(f"[bold red]Error: Command '{cmd_list[0]}' not found.[/bold red]")
            return -1
        except Exception as e:
            self.console.print(f"[bold red]Unexpected error: {e}[/bold red]")
            return -1

        duration = time.monotonic() - start_time
        output = output_buffer.getvalue().decode('utf-8', errors='replace')
        
        # --- Logbook and Report Integration ---
        # Generate a virtual job ID for foreground execution so it has a reference
        import uuid
        virtual_job_id = str(uuid.uuid4())

        logbook_id = self.logbook_mgr.create_entry(
            command_str=cmd_str,
            output=output,
            return_code=return_code,
            duration=duration,
            session_obj=session_obj,
            source_job_id=virtual_job_id)
        if session_obj.report:
            self.report_mgr.add_history_entry(session_obj.report, cmd_str, logbook_id, tool_name, tool_command_name)

        if show_summary:
            self.display_mgr.display_execution_summary(
                title="[bold]Execution Summary[/bold]",
                status_text=status_text,
                status_style=status_style,
                return_code=return_code,
                duration=duration,
                command_str=cmd_str,
                logbook_id=logbook_id,
                session_name=session_obj.name,
                timestamp=time.strftime("%Y-%m-%d %H:%M:%S")
            )
        
        return return_code