# modules/job_manager.py

from modules import placeholders
import subprocess, os, fcntl
import threading, pty, signal
import time
import shlex, re, uuid
from collections import deque
from itertools import count
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from modules.managers import LogbookManager, ReportManager
from modules.managers.base_manager import BaseManager
from modules.services import log
import argparse

ANSI_ESCAPE_PATTERN = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')

def strip_ansi(text: str) -> str:
    """
    Removes ANSI escape codes from a string. Also handles the carriage return
    by processing lines to keep only the last version of a line updated by \r.
    """
    # First, handle carriage returns to correctly process progress bars
    # and interactive sessions.
    # Normalize CRLF to LF first to avoid issues with the carriage return logic.
    normalized_text = text.replace('\r\n', '\n')
    processed_lines = []
    for line in normalized_text.split('\n'):
        # Handle carriage returns within a single line by splitting on `\r`
        # and taking the last part, which simulates the line being overwritten.
        last_part = line.split('\r')[-1]
        processed_lines.append(last_part)
    text_without_cr = "\n".join(processed_lines)
    
    # Then, remove all other ANSI escape codes
    return ANSI_ESCAPE_PATTERN.sub('', text_without_cr)

class Job:
    """Represents a single background process."""
    def __init__(self, job_id, command_list, session_obj, tool_name=None, tool_command_name=None, additional_info=None, display_command=None):
        self.id = job_id
        self.command = command_list
        self.session_obj = session_obj
        # --- SECURITY: Use a separate command string for display purposes ---
        # If a display_command is provided, use it. Otherwise, build from the real command.
        # This prevents passwords from ever being stored in the command_str.
        if display_command:
            self.command_str = shlex.join(display_command)
        else:
            self.command_str = shlex.join(command_list)

        # --- FIX: Handle session-less execution for workflows ---
        # --- NEW: Store PID directly instead of a Popen object ---
        if session_obj:
            self.session_name = session_obj.name
            self.tool_name = tool_name or session_obj.tool
        else:
            self.session_name = "workflow"
            self.tool_name = tool_name

        self.tool_command_name = tool_command_name
        self.pid = None
        self.status = "pending"  # pending, running, finished, failed, killed
        self.start_time = None
        self.end_time = None
        self.output = "" # Stores the raw output as a single string
        self.return_code = None
        self.thread = None
        self.logbook_id = None # To link this job to a logbook entry
        self.pty_master_fd = None # File descriptor for the pseudo-terminal
        self.killed_by_user = False
        self.lock = threading.RLock() # A single lock for the job's state
        self.stop_event = threading.Event() # For cooperative shutdown of the output reader
        # --- NEW: Store arbitrary additional information, e.g., from a workflow node ---
        self.additional_info = additional_info or {}
        # --- FIX: Re-add executor_instance to allow callback on completion ---
        self.executor_instance = None

    @property
    def duration(self):
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        elif self.start_time:
            return time.time() - self.start_time
        return 0

    def to_dict(self):
        """Converts the job object to a dictionary for JSON serialization."""
        with self.lock:
            return {
                "id": self.id,
                "command_str": self.command_str,
                "session_name": self.session_name,
                "tool_name": self.tool_name,
                "tool_command_name": self.tool_command_name,
                "status": self.status,
                "start_time": self.start_time,
                "end_time": self.end_time,
                "duration": self.duration,
                "return_code": self.return_code,
                "logbook_id": self.logbook_id,
                "additional_info": self.additional_info,
                # We don't include the full output here to keep the payload small.
            }

class JobManager(BaseManager):
    """Manages all background jobs."""
    def __init__(self, cli_instance, logbook_mgr: LogbookManager, report_mgr: ReportManager, executor_instance=None):
        self.jobs = {}
        self._lock = threading.Lock()
        self.cli = cli_instance # Store a reference to the main CLI instance
        self.logbook_mgr = logbook_mgr
        self.report_mgr = report_mgr
        self.notifications = deque()
        # --- NEW: Store a reference to the executor for live output callbacks ---
        self.executor = executor_instance

    def _cmd_list(self, args, cli):
        """Handles 'jobs list'."""
        jobs = self.list_jobs()
        cli.display_mgr.display_jobs_list(jobs)

    def _cmd_show(self, args, cli):
        """Handles 'jobs show'."""
        job = self.get_job(str(args.id))
        if not job:
            log.error(f"Job {args.id} not found.")
            return

        if job.logbook_id:
            log.info(f"Job #{job.id} is linked to Logbook Entry #{job.logbook_id}. Showing log details...")
            import argparse
            log_args = argparse.Namespace(id=str(job.logbook_id))
            cli.logbook_mgr.dispatch("show", log_args, cli)
        else:
            cli.display_mgr.display_job_output(job)

    def _cmd_kill(self, args, cli):
        """Handles 'jobs kill'."""
        self.kill_job(str(args.id))

    def _cmd_clear(self, args, cli):
        """Handles 'jobs clear'."""
        self.clear_finished_jobs()

    def _cmd_input(self, args, cli):
        """Handles 'jobs input'."""
        text_to_send = " ".join(args.text) if isinstance(args.text, list) else args.text
        # --- FINAL, CORRECT FIX for b64decode ---
        # Resolve any functions (like b64decode) in the input string before sending it.
        # We pass the cli.session object to provide context for the resolver,
        # even though it's not strictly needed for b64decode.
        resolved_input = placeholders.resolve_placeholders(text_to_send, cli.session)
        self.send_input(str(args.id), resolved_input)

    def _get_entity_type(self):
        """Required by BaseManager, though not used for display in JobManager."""
        return "Job"

    def dispatch(self, subcommand, args, cli):
        """Overrides BaseManager's dispatch to handle the case where no subcommand is given."""
        if not subcommand:
            cli.help_mgr.show_help_jobs()
            return True
        
        return super().dispatch(subcommand, args, cli)

    def _read_output(self, job: Job):
        """Reads the output of a process in a separate thread."""
        # --- FINAL FIX for interactive jobs like 'nc -l' ---
        # The previous implementation would stop reading when a client disconnected,
        # even if the main nc process was still alive. This new implementation
        # uses a non-blocking read loop that continues as long as the PTY's
        # file descriptor is open, correctly capturing output from multiple connections.
        try:
            # --- NEW: Use the PTY master file descriptor for reading ---
            master_fd = job.pty_master_fd
            # Set the master_fd to non-blocking mode.
            fl = fcntl.fcntl(master_fd, fcntl.F_GETFL)
            fcntl.fcntl(master_fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)

            while not job.stop_event.is_set():
                try:
                    # Read available bytes from the PTY master without blocking.
                    output_bytes = os.read(master_fd, 1024)
                    if output_bytes:
                        char = output_bytes.decode('utf-8', errors='replace')
                        with job.lock:
                            job.output += char
                        # --- NEW: Emit live output update if an executor is attached ---
                        if self.executor:
                            self.executor._emit_job_output_update(job.id, char)
                except (IOError, TypeError):
                    pass # No data available, loop will check process status immediately.

                # --- FINAL, ROBUST FIX for race conditions ---
                # Actively check if the process has terminated in a non-blocking way.
                # This is the key to correctly handling very fast-exiting processes.
                if job.pid:
                    try:
                        # WNOHANG makes waitpid non-blocking. It returns (pid, status) on exit, or (0, 0) if still running.
                        pid, exit_status = os.waitpid(job.pid, os.WNOHANG)
                        if pid != 0: # A non-zero PID means the process has terminated.
                            if os.WIFSIGNALED(exit_status):
                                with job.lock: job.return_code = -os.WTERMSIG(exit_status)
                            elif os.WIFEXITED(exit_status):
                                with job.lock: job.return_code = os.WEXITSTATUS(exit_status)
                            break # Exit the reading loop
                    except (OSError, ChildProcessError):
                        # This can happen if the process is already reaped by another part of the system.
                        # We mark it as failed and exit the loop.
                        with job.lock: job.return_code = -1
                        break
                else: # This case handles if the process failed to start (e.g. execve error)
                    break

        except Exception as e:
            # This might happen if the process terminates unexpectedly.
            log.debug(f"Exception in non-blocking read for job {job.id}: {e}")
        finally:
            # --- FINAL, ROBUST FIX for race condition with fast-exiting processes ---
            # After the process has terminated, there might still be unread data in the PTY buffer.
            # We perform one final, blocking read to ensure we capture all of it before finalizing the job.
            with job.lock:
                if job.status in ['running', 'killing']: # type: ignore
                    # --- FINAL, ROBUST FIX for fast-exiting processes ---
                    # If the return code was already set by the waitpid() loop, use it.
                    # Otherwise, it means the process exited before the loop could even run once.
                    # We perform a final blocking waitpid() to get the definitive exit status.
                    if job.return_code is None and job.pid:
                        try:
                            # This is a blocking call that will wait for the child to exit
                            # and return its status. This is the ultimate guarantee.
                            _, exit_status = os.waitpid(job.pid, 0)
                            if os.WIFSIGNALED(exit_status):
                                job.return_code = -os.WTERMSIG(exit_status)
                            elif os.WIFEXITED(exit_status):
                                job.return_code = os.WEXITSTATUS(exit_status)
                        except (OSError, ChildProcessError):
                            job.return_code = -1 # Fallback if process is already gone or reaped
                    job.end_time = time.time()
                    if job.killed_by_user:
                        job.status = "killed"
                    else:
                        job.status = "finished" if job.return_code == 0 else "failed"

                    # --- FINAL, ROBUST FIX for race condition with fast-exiting processes ---
                    # Read any remaining output AFTER the status is determined but BEFORE notifying anyone.
                    # This ensures the final output (like an error message) is captured.
                    try:
                        remaining_bytes = os.read(job.pty_master_fd, 1024 * 64) # Read up to 64KB
                        if remaining_bytes:
                            job.output += remaining_bytes.decode('utf-8', errors='replace')
                    except (IOError, OSError):
                        pass # This is expected if the fd is already closed or has no more data.
                    
                    # --- FINAL FIX: If this is a workflow job, notify the executor directly ---
                    # This solves the race condition for very fast jobs.
                    if job.executor_instance:
                        # Find which node this job belongs to
                        node_id_for_job = None
                        for nid, jid in job.executor_instance.job_monitor.active_jobs.items():
                            if jid == job.id:
                                node_id_for_job = nid
                                break
                        
                        if node_id_for_job is not None:
                            job_output = {
                                "stdout": job.output,
                                "status": job.status,
                                "return_code": job.return_code,
                            }
                            job_output['on_finish'] = job_output.copy()
                            job.executor_instance.on_node_finished(node_id_for_job, job.status, job_output)
                            log.debug(f"[JobManager] Notified executor about completion of job {job.id} for node {node_id_for_job}.")

                    self.notifications.append(job.id)

            # --- NEW: Close the PTY master file descriptor when done ---
            if job.pty_master_fd:
                os.close(job.pty_master_fd)

                # --- Logbook and Report Finalization ---
                # Only create a logbook entry if one doesn't exist for this job yet.
                # This prevents race conditions with check_job_status.
                if job.logbook_id is None:
                    session_for_log = None
                    # For regular CLI jobs, use the session object.
                    if job.session_obj:
                        session_for_log = job.session_obj
                    # For workflow jobs, use the context object passed via overrides.
                    elif job.session_obj is None and hasattr(job, 'workflow_context') and job.workflow_context:
                        # The workflow_context object has a to_dict() method for serialization.
                        if hasattr(job.workflow_context, 'to_dict'):
                            session_for_log = job.workflow_context.to_dict()
                        else: # Fallback for other object types that might be passed
                            session_for_log = vars(job.workflow_context)
                    
                    clean_output = strip_ansi(job.output)
                    logbook_id = self.logbook_mgr.create_entry(
                        command_str=job.command_str,
                        output=clean_output,
                        return_code=job.return_code,
                        duration=job.duration,                        
                        additional_info=job.additional_info, # --- NEW: Pass additional info to the logbook ---
                        source_job_id=job.id, # --- FIX: Store the job ID in the log ---
                        session_obj=session_for_log
                    )
                    job.logbook_id = logbook_id

                    # --- FIX: Add to report history if a report is loaded in the session ---
                    if job.session_obj and job.session_obj.report:
                        self.report_mgr.add_history_entry(
                            job.session_obj.report, job.command_str, logbook_id,
                            job.tool_name, job.tool_command_name
                    ) # type: ignore

    def add_job(self, tool_name, command_name, session, workflow_placeholder_overrides=None, additional_info=None):
        """
        Builds a command and starts it as a job. This is the main entry point.
        It can resolve placeholders from a session or from workflow override data.
        """
        # For workflows, `session` will be None. We need to handle this gracefully.
        is_workflow_job = session is None

        # --- NEW: Sudo handling for workflows ---
        tool_data = self.cli.tool_mgr.load(tool_name)
        needs_sudo = tool_data.get('sudo', False)
        sudo_password = self.executor.sudo_password if self.executor else None

        try:
            # Build the command template from the tool definition
            built_commands = self.cli.tool_mgr.build_command(tool_name, session, command_name)
            if not built_commands:
                # --- FIX: Log an error if command building fails ---
                log.error(f"Could not build command for {tool_name}/{command_name}.")
                return None

            # --- Placeholder Resolution ---
            # For workflow jobs, the 'session' argument is the virtual session object (argparse.Namespace).
            # For regular CLI jobs, it's the CLISession object.
            # --- FIX: Use placeholder overrides for workflows ---
            # This keeps the session object clean for logging and uses a separate data
            # dictionary for placeholder resolution, which is more robust.
            if is_workflow_job:
                # For workflows, the override object is the entire context.
                resolved_command = [
                    placeholders.resolve_placeholders(part, workflow_placeholder_overrides)
                    for part in built_commands[0]
                ]
            else:
                # For regular CLI jobs, resolve placeholders using the session object.
                resolved_command = [
                    placeholders.resolve_placeholders(part, session)
                    for part in built_commands[0]
                ]

            # --- NEW: Sudo command construction ---
            command_to_execute = resolved_command
            command_for_display = None

            if is_workflow_job and needs_sudo:
                if sudo_password:
                    # The command that will be executed, with the password piped to sudo.
                    # The '-S' flag tells sudo to read the password from stdin.
                    # The '-p ""' part prevents sudo from printing its own prompt.
                    command_to_execute = ['/bin/sh', '-c', f"echo '{sudo_password}' | sudo -S -p '' {' '.join(shlex.quote(arg) for arg in resolved_command)}"]
                    # The command that will be displayed in logs and the UI (without the password).
                    command_for_display = ['sudo'] + resolved_command
                else:
                    # If sudo is needed but no password was provided, log an error and fail.
                    log.error(f"Tool '{tool_name}' requires sudo, but no password was provided for the workflow.")
                    return None

            return self.start_job(command_to_execute, session, tool_name, command_name, additional_info=additional_info, display_command=command_for_display)

        except Exception as e:
            log.error(f"Failed to add job for {tool_name}/{command_name}: {e}")
            return None

    def start_job(self, command_list, session_obj, tool_name=None, tool_command_name=None, additional_info=None, display_command=None):
        """Starts a new command as a background job."""
        job_id = str(uuid.uuid4()) # Use UUIDs for job IDs
        job = Job(job_id, command_list, session_obj, tool_name=tool_name, tool_command_name=tool_command_name, additional_info=additional_info, display_command=display_command)
        # --- FIX: Attach the manager's executor instance (if any) to the job object ---
        job.executor_instance = self.executor
        # job.workflow_context = None # Initialize attribute
        
        try:
            # --- FINAL, ROBUST FIX: Use pty.fork() to spawn the process in a pseudo-terminal ---
            # This correctly handles interactive prompts (like `read -p`) and stderr merging.
            pid, master_fd = pty.fork()
            if pid == 0: # This is the child process
                # We are in the child. Replace this process with the command.
                # --- SECURITY FIX: If we used `sh -c`, we must use execvpe with the shell. ---
                if command_list[0] == '/bin/sh' and command_list[1] == '-c':
                    # For `sh -c "..."`, the third argument is the command string.
                    # We pass the shell, its flags, and the command string to execvp.
                    os.execvp(command_list[0], command_list)
                else:
                    os.execvp(command_list[0], command_list)
            else: # This is the parent process
                job.pty_master_fd = master_fd # Store the master fd for I/O
                job.pid = pid


            job.status = "running"
            job.start_time = time.time()

            # Start the thread that reads the output
            job.thread = threading.Thread(target=self._read_output, args=(job,))
            job.thread.daemon = True # Thread dies with the main program
            job.thread.start()

            with self._lock:
                self.jobs[job_id] = job
            
            # The CommandExecutor is now responsible for logging the success message.
            return job_id
        except (OSError, FileNotFoundError) as e:
            # This is the key to fixing the race condition for nonexistent commands.
            # If execvp() fails in the child, the child exits immediately. The parent's
            # first attempt to read from the PTY will then raise an OSError (Input/output error).
            # We catch this specific error (and FileNotFoundError as a fallback), mark the job as failed, and return its ID.
            job.status = "failed"
            job.return_code = -1
            job.start_time = time.time()
            job.end_time = time.time()
            job.output = f"pwnity: command not found: {command_list[0]}\n"
            # Ensure the job is added to the manager's dictionary before returning the ID
            with self._lock:
                self.jobs[job_id] = job
            log.debug(f"Caught exception on job start, likely a nonexistent command: {e}")
            return job_id
        except Exception as e:
            log.error(f"Error trying to start job for command '{shlex.join(command_list)}': {e}", exc_info=True)
            return None

    def send_input(self, job_id, text_to_send):
        """Sends a line of text to a running job's stdin."""
        job = self.get_job(str(job_id))
        if not job:
            log.error(f"Job {job_id} not found.")
            return False
        
        with job.lock:
            if job.status != "running" or not job.pty_master_fd:
                return False
            
            try:
                # --- FINAL FIX: Ensure a newline is always sent to the process ---
                # This is crucial for interactive tools like nc that are line-buffered.
                if job.pty_master_fd is not None:
                    full_input = text_to_send if text_to_send.endswith('\n') else text_to_send + '\n'
                    os.write(job.pty_master_fd, full_input.encode('utf-8'))
                return True
            except (IOError, ValueError) as e:
                log.error(f"Error sending input to job {job_id}: {e}")
                return False

    def get_job(self, job_id):
        with self._lock:
            job_id_str = str(job_id)
            # First, try a direct lookup for the full UUID.
            job = self.jobs.get(job_id_str)
            if job:
                return job
            
            # If not found, it might be a truncated ID.
            # Find all jobs whose ID starts with the provided string.
            matching_jobs = [j for j in self.jobs.values() if j.id.startswith(job_id_str)]
            
            if len(matching_jobs) == 1:
                return matching_jobs[0]
            elif len(matching_jobs) > 1:
                log.error(f"Ambiguous job ID prefix '{job_id_str}'. Multiple jobs found.")
                return None

            # If still not found, return None.
            return None

    def list_jobs(self):
        with self._lock:
            return list(self.jobs.values())

    def check_job_status(self, job: Job):
        """
        Checks if a running job's process has terminated and updates its status.
        This is called periodically by the main thread to catch jobs that have
        finished but whose output-reading thread might not have updated the status yet.
        This ensures the UI is responsive.
        """
        with job.lock:
            # Only check jobs that are supposedly running
            if job.status not in ['running', 'killing']:
                return

            # --- FIX for PTY conversion ---
            # The job object no longer has a 'process' attribute. We must check
            # the status using the PID.
            if not job.pid:
                return
            
            return_code = None
            try:
                # Use os.waitpid with WNOHANG for a non-blocking check.
                # It returns (0, 0) if the process is still running.
                pid, exit_status = os.waitpid(job.pid, os.WNOHANG)
                if pid == 0:
                    return # Process is still running, do nothing.
                # If pid is not 0, the process has terminated. Extract the return code.
                return_code = os.WEXITSTATUS(exit_status)
            except OSError:
                return # Process likely already reaped, do nothing.

            # --- The process has finished, update the state for the UI ---
            job.return_code = return_code
            job.end_time = time.time()

            if job.killed_by_user:
                job.status = "killed"
            else:
                job.status = "finished" if job.return_code == 0 else "failed"
            
            # The _read_output thread is responsible for the final logbook entry,
            # but we can add the notification here to make the UI responsive.
            self.notifications.append(job.id)

    def kill_job(self, job_id):
        job = self.get_job(str(job_id))
        if not job:
            log.error(f"Job {job_id} not found.")
            return False
        
        with job.lock:
            if job.status not in ["running", "pending"]:
                log.warning(f"Job {job_id} has already finished (Status: {job.status}).")
                return False
        
        try:
            job.killed_by_user = True
            with job.lock:
                job.status = "killing"
            os.kill(job.pid, signal.SIGTERM) # Send SIGTERM
            log.success(f"Kill signal sent to job {job_id}. It will be marked as 'killed' upon termination.")
            return True
        except (ProcessLookupError, AttributeError):
            # Process already terminated, which is fine.
            log.debug(f"Job {job_id} process already terminated.")
            return True
        except Exception as e:
            log.error(f"Error killing job {job_id}: {e}")
            return False

    def find_job_by_id(self, job_id: str) -> dict | None:
        """
        Finds a job by its ID, looking first in the active jobs list,
        and then searching the logbook for a matching finished job.
        This is the single source of truth for retrieving job data for the UI.
        """
        # 1. Check active jobs first
        job = self.get_job(str(job_id))
        if job:
            with job.lock:
                # --- FIX: job.to_dict() excludes the output. We must add it back manually. ---
                # This is critical for workflows that need the job's output as their input.
                job_data = job.to_dict()
                # Add the output field, which is intentionally excluded from the base to_dict()
                job_data['output'] = job.output
                return job_data

        # 2. If not active, search the logbook for a matching entry
        logbook_id_for_job = None
        all_log_ids = self.logbook_mgr.list_all()
        for log_id in all_log_ids:
            log_data_temp = self.logbook_mgr.load(log_id)
            if log_data_temp and str(log_data_temp.get("source_job_id")) == str(job_id):
                logbook_id_for_job = log_id
                break

        if logbook_id_for_job:
            log_data = self.logbook_mgr.load(logbook_id_for_job)
            if log_data:
                # Adapt the logbook data to look like a finished job object for the UI.
                return {
                    "id": log_data.get("source_job_id", job_id),
                    "command_str": log_data.get("command", ""),
                    "name": f"Job #{job_id} (Finished)",
                    "status": "finished" if log_data.get("execution", {}).get("return_code") == 0 else "failed",
                    "output": log_data.get("output", ""),
                    "return_code": log_data.get("execution", {}).get("return_code"),
                    "duration": log_data.get("execution", {}).get("duration_seconds"),
                    "start_time": log_data.get("timestamp"),
                    "logbook_id": logbook_id_for_job,
                }

        return None

    def clear_finished_jobs(self):
        """Removes all finished, failed, or killed jobs from the list."""
        with self._lock:
            finished_ids = [
                job_id for job_id, job in self.jobs.items() 
                if job.status in ["finished", "failed", "killed"]
            ]
            for job_id in finished_ids:
                del self.jobs[job_id]
        log.info(f"{len(finished_ids)} finished jobs removed from the list.")

    def shutdown(self):
        """Terminates all running jobs when the application shuts down."""
        log.info("Shutting down all running background jobs...")
        with self._lock:
            running_jobs = [job for job in self.jobs.values() if job.status == "running"]
        
        if not running_jobs:
            log.info("No active jobs to shut down.")
            return

        for job in running_jobs:
            self.kill_job(job.id)

        # Give the threads a moment to terminate
        for job in running_jobs:
            job.thread.join(timeout=2)