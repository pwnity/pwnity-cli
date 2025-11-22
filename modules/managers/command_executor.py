# modules/command_executor.py
import subprocess
import shlex
import time
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

    def execute(self, command_lists: list[list[str]], session_obj, tool_name: str, tool_command_name: str, run_now: bool, run_bg: bool, suppress_individual_summaries: bool = False):
        """Executes a list of commands either in the background or foreground."""
        if run_bg:
            # --- FIX: The job start message was not being displayed immediately. ---
            # We now collect the job IDs and log the success message directly.
            # This ensures the user gets immediate feedback.
            return self.job_mgr.start_job(
                command_lists[0], session_obj=session_obj, 
                tool_name=tool_name, tool_command_name=tool_command_name
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
                    border_color=border_color
                )

    def _run_foreground(self, cmd_list: list, session_obj, tool_name, tool_command_name, show_summary: bool = True) -> int:
        cmd_str = shlex.join(cmd_list)
        start_time = time.monotonic()
        return_code = -1
        process = None
        status_text = "Failed"
        status_style = "bold red"
        output_buffer = io.BytesIO()

        try:
            process = subprocess.Popen(
                cmd_list,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                bufsize=0 # Unbuffered binary stream
            )

            if show_summary:
                self.console.rule(style="dim yellow")

            with process.stdout:
                for byte in iter(lambda: process.stdout.read(1), b''):
                    output_buffer.write(byte)
                    char = byte.decode('utf-8', errors='replace')
                    self.console.file.write(char)
                    self.console.file.flush()

            process.wait()
            return_code = process.returncode

            if return_code == 0:
                status_text = "Success"
                status_style = "bold green"

        except KeyboardInterrupt:
            self.console.print()
            log.warning("Command interrupted by user.")
            if process:
                process.terminate()
                process.wait()
            return_code = 130
            status_text = "Interrupted"
            status_style = "bold yellow"
        except FileNotFoundError:
            self.console.print(f"[bold red]Error: Command '{cmd_list[0]}' not found. Is the tool installed and in your PATH?[/bold red]")
            return -1
        except Exception as e:
            self.console.print(f"[bold red]An unexpected error occurred during execution: {e}[/bold red]")
            return -1

        duration = time.monotonic() - start_time
        output = output_buffer.getvalue().decode('utf-8', errors='replace')
        
        # --- Logbook and Report Integration ---
        # --- FIX: Use keyword arguments to match the updated create_entry signature ---
        # Foreground commands don't have a job_id, so we pass None.
        logbook_id = self.logbook_mgr.create_entry(
            command_str=cmd_str,
            output=output,
            return_code=return_code,
            duration=duration,
            session_obj=session_obj,
            source_job_id=None)
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
                session_name=session_obj.name
            )
        
        return return_code