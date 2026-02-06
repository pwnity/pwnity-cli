"""
Pwnity Headless API - Direct CLI Command Execution
This module provides a programmatic interface to execute Pwnity commands
without going through the interactive shell, avoiding race conditions.
"""

import threading
import queue
import time
from typing import Optional, Dict, Any, Callable
import io
import sys

class HeadlessCommandExecutor:
    """
    Executes Pwnity CLI commands in a background thread without shell interference.
    Commands are queued and executed sequentially with proper state management.
    """
    
    def __init__(self, cli_instance, socketio_instance=None):
        """
        Initialize the headless executor.
        
        Args:
            cli_instance: Instance of MyCLI (pwnity_cli.MyCLI)
            socketio_instance: Optional Flask-SocketIO instance for state updates
        """
        self.cli = cli_instance
        self.socketio = socketio_instance
        self.command_queue = queue.Queue()
        self.result_callbacks = {}
        self.worker_thread = None
        self.running = False
        self._lock = threading.Lock()
        
    def start(self):
        """Start the background worker thread."""
        if self.running:
            return
            
        self.running = True
        self.worker_thread = threading.Thread(target=self._worker, daemon=True)
        self.worker_thread.start()
        
    def stop(self):
        """Stop the background worker thread."""
        self.running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=2)
            
    def execute_command(self, command: str, callback: Optional[Callable] = None) -> str:
        """
        Execute a Pwnity command programmatically.
        
        Args:
            command: The command string (e.g., "target add example.com")
            callback: Optional callback function(result_dict) called when done
            
        Returns:
            Command ID for tracking
        """
        cmd_id = f"cmd_{int(time.time() * 1000)}"
        
        self.command_queue.put({
            'id': cmd_id,
            'command': command,
            'callback': callback
        })
        
        return cmd_id
        
    def _worker(self):
        """Background worker that processes commands sequentially."""
        while self.running:
            try:
                # Wait for next command (with timeout to allow clean shutdown)
                cmd_data = self.command_queue.get(timeout=0.5)
            except queue.Empty:
                continue
                
            cmd_id = cmd_data['id']
            command = cmd_data['command']
            callback = cmd_data.get('callback')
            
            # Execute command and capture output
            result = self._execute_single_command(command)
            
            # Emit state update if socketio is available
            # This ensures the UI stays in sync when automation changes state
            if self.socketio and result['success']:
                try:
                    # Read session state directly from file to avoid Flask import issues
                    import json
                    from modules.services import config
                    
                    session_file = config.get_parameter("GLOBAL", "SESSION_STATE_FILE", "data/.session.json")
                    try:
                        with open(session_file, 'r') as f:
                            state = json.load(f)
                    except (FileNotFoundError, json.JSONDecodeError):
                        state = {
                            "session_name": None, "target": None, "tool": None,
                            "wordlist": None, "report": None, "proxy_enabled": False
                        }
                    
                    self.socketio.emit('state_update', state)
                except Exception as e:
                    print(f"[Headless] State update error: {e}")
            
            # Call callback if provided
            if callback:
                try:
                    callback(result)
                except Exception as e:
                    print(f"[Headless] Callback error: {e}")
                    
            self.command_queue.task_done()
            
    def _execute_single_command(self, command: str) -> Dict[str, Any]:
        """
        Execute a single command and return structured result.
        
        Args:
            command: Command string to execute
            
        Returns:
            Dict with 'success', 'output', 'error' keys
        """
        # CRITICAL: Acquire lock to ensure only ONE command executes at a time
        # This prevents race conditions in cmd2's internal state
        with self._lock:
            # Capture stdout/stderr
            old_stdout = sys.stdout
            old_stderr = sys.stderr
            
            captured_output = io.StringIO()
            captured_error = io.StringIO()
            
            sys.stdout = captured_output
            sys.stderr = captured_error
            
            success = False
            error_msg = None
            
            try:
                # Use onecmd_plus_hooks() which properly handles the full command
                # including subcommands like "target load <name>"
                stop = self.cli.onecmd_plus_hooks(command)
                success = not stop
                
                # CRITICAL: Manually sync session state to file
                # The headless CLI doesn't have web_ui_mode=True, so it won't auto-sync
                if success and hasattr(self.cli, '_sync_session_state_for_ui'):
                    self.cli._sync_session_state_for_ui(signal_command_completion=False)
                    
            except Exception as e:
                error_msg = str(e)
                success = False
            finally:
                # ALWAYS restore stdout/stderr
                sys.stdout = old_stdout
                sys.stderr = old_stderr
                
            output = captured_output.getvalue()
            error = captured_error.getvalue() or error_msg
            
            return {
                'success': success,
                'output': output,
                'error': error,
                'command': command
            }


# Global executor instance (initialized by web UI)
_executor_instance: Optional[HeadlessCommandExecutor] = None

def get_executor() -> Optional[HeadlessCommandExecutor]:
    """Get the global headless executor instance."""
    return _executor_instance

def initialize_executor(cli_instance, socketio_instance=None):
    """Initialize the global executor with a CLI instance and optional Socket.IO."""
    global _executor_instance
    if _executor_instance is None:
        _executor_instance = HeadlessCommandExecutor(cli_instance, socketio_instance)
        _executor_instance.start()
    return _executor_instance
