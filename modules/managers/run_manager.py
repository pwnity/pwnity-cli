# modules/managers/run_manager.py
import shlex
import subprocess
import tempfile
import os

from .base_manager import BaseManager
from ..services import log, config
from .. import placeholders
from rich.panel import Panel
from rich.text import Text
from rich.console import Group

class RunManager(BaseManager):
    def __init__(self):
        pass

    def _get_entity_type(self):
        return "Run"

    def _ensure_sudo_credentials(self) -> bool:
        """
        Checks if sudo credentials are valid. If not, it prompts the user interactively.
        Returns True if credentials are valid or become valid, False otherwise.
        """
        check_process = subprocess.run(['sudo', '-n', 'true'], capture_output=True)
        if check_process.returncode == 0:
            log.debug("Sudo credentials are valid (cached).")
            return True

        log.prompt("Sudo credentials required. Please enter your password.")
        interactive_process = subprocess.run(['sudo', '-v'])

        if interactive_process.returncode == 0:
            log.success("Sudo credentials accepted.")
            return True
        else:
            log.error("Failed to obtain sudo credentials. Aborting command.")
            return False

    def do_pwn(self, args, cli):
        """Handles the 'pwn' and 'run' commands."""
        if not args.pwn_args:
            cli.help_mgr.show_help_pwn()
            return

        pwn_args = args.pwn_args
        command_name = None
        is_per_param_execution = False
        run_now = 'now' in pwn_args
        run_bg = 'bg' in pwn_args

        if run_now: pwn_args.remove('now')
        if run_bg: pwn_args.remove('bg')

        if pwn_args and not pwn_args[0].startswith('-'):
            command_name = pwn_args.pop(0)
        
        extra_params = pwn_args

        if not cli.session.tool:
            log.error("No tool loaded in the current session. (e.g., 'tool load gobuster')")
            return
        tool_name = cli.session.tool

        tool_data = cli.tool_mgr.load(tool_name)
        defined_commands = tool_data.get("commands", [])
        if not defined_commands:
            log.warning(f"No commands configured for tool '{tool_name}'.")
            return

        if not command_name:
            if len(defined_commands) == 1 and defined_commands[0].get("name"):
                command_name = defined_commands[0].get("name")
                is_per_param_execution = defined_commands[0].get("execute_per_param", False)
                log.prompt(f"Only one command ('{command_name}') defined, selecting it automatically.")
            else:
                command_names = [cmd.get('name') for cmd in defined_commands]
                log.error(f"Multiple commands defined for '{tool_name}'. Please specify one.")
                log.prompt(f"Available commands: {', '.join(command_names)}")
                log.prompt(f"Example: pwn {command_names[0]} now")
                return
        else:
            cmd_obj = next((c for c in defined_commands if c.get("name") == command_name), None)
            if cmd_obj:
                is_per_param_execution = cmd_obj.get("execute_per_param", False)

        commands_to_run = cli.tool_mgr.build_command(
            tool_name, 
            session=cli.session, 
            command_to_run=command_name,
            extra_params=extra_params
        )
        if not commands_to_run:
            if defined_commands:
                command_names = [cmd.get('name') for cmd in defined_commands]
                log.prompt(f"Available commands: {', '.join(command_names)}")
            return

        final_commands = []
        execution_notes = []
        tool_needs_sudo = tool_data.get('sudo', False)
        proxy_config = cli.proxy_mgr.get_effective_config(cli.session)

        # --- NEW: Job-based temporary proxychains config file ---
        temp_proxy_conf_path = None
        if proxy_config and proxy_config.get('wrapper_template'):
            template_name = proxy_config['wrapper_template']
            template_dir = config.get_parameter("DIRS", "PROXY_TEMPLATES", "etc/proxy_templates")
            template_path = os.path.join(template_dir, template_name)

            if not os.path.exists(template_path):
                log.error(f"Proxy template file not found: {template_path}")
                proxy_config = None # Disable proxy for this run
            else:
                with open(template_path, 'r') as f:
                    template_content = f.read()

                # --- FINAL FIX: Manually replace placeholders for robustness ---
                # The main placeholder resolver is designed for the session context and can fail here.
                # A direct string replacement is safer and more direct for this specific task.
                conf_content = template_content
                for key, value in proxy_config.items():
                    if value is not None:  # Ensure we don't replace with 'None'
                        # --- FIX: Re-introduce robust localhost resolution ---
                        if key == 'host' and str(value).lower() == 'localhost':
                            value_to_replace = '127.0.0.1'
                        else:
                            value_to_replace = str(value)
                        conf_content = conf_content.replace(f"$proxy.{key}", value_to_replace)
                
                try:
                    # Use a secure, private directory within the application structure
                    run_dir = config.get_parameter("DIRS", "RUN", "data/run")
                    os.makedirs(run_dir, exist_ok=True)

                    # Create a temporary file within our secure run directory
                    with tempfile.NamedTemporaryFile(
                        mode='w', delete=False, suffix='.conf', 
                        prefix='pwnity_proxy_', dir=run_dir
                    ) as temp_f:
                        temp_f.write(conf_content)
                        temp_proxy_conf_path = temp_f.name
                    
                    # Prepend the -f option to the wrapper options for this run
                    # --- FIX: Combine session and global options more intelligently ---
                    # Use session options if they exist, otherwise fall back to global options.
                    # This prevents accidentally losing the global '-q'.
                    base_opts = cli.proxy_mgr.get_effective_config(cli.session).get('wrapper_options', '')
                    proxy_config['wrapper_options'] = f"-f {temp_proxy_conf_path} {base_opts}".strip()
                    log.debug(f"Created temporary proxychains config at: {temp_proxy_conf_path}")

                except Exception as e:
                    log.error(f"Failed to create temporary proxychains config: {e}")
                    # If we can't create the config, we should not proceed with the proxy.
                    # We can either abort or just disable the proxy for this run.
                    # For now, we'll let it proceed without the temp file, which might fail later.
                    proxy_config = None

        for cmd in commands_to_run:
            cmd = [placeholders.resolve_placeholders(part, cli.session) for part in cmd]
            current_cmd = cmd
            use_sudo_for_this_cmd = tool_needs_sudo
            sudo_reason = "Required by tool configuration." if tool_needs_sudo else ""

            if use_sudo_for_this_cmd or (proxy_config and proxy_config.get('wrapper_needs_sudo', False)):
                if not self._ensure_sudo_credentials():
                    return

            if proxy_config and proxy_config.get('wrapper_command'):
                wrapper_cmd_str = proxy_config['wrapper_command']
                wrapper_opts_str = proxy_config.get('wrapper_options', '')
                full_wrapper_str = f"{wrapper_cmd_str} {wrapper_opts_str}".strip()
                wrapper_cmd_list = shlex.split(full_wrapper_str)
                current_cmd = wrapper_cmd_list + current_cmd
                execution_notes.append(f"Proxy: Enabled ('{full_wrapper_str}')")
                if proxy_config.get('wrapper_needs_sudo', False):
                    use_sudo_for_this_cmd = True
                    sudo_reason = "Required by proxy wrapper."

            if use_sudo_for_this_cmd:
                current_cmd = ['sudo'] + current_cmd
                if not any("Sudo:" in note for note in execution_notes):
                    execution_notes.append(f"Sudo: Enabled ({sudo_reason})")

            final_commands.append(current_cmd)

        plan_items = [Text(f"▶️  {shlex.join(cmd_list)}", style="green") for cmd_list in final_commands]
        if execution_notes:
            plan_items.append(Text(""))
            for note in execution_notes:
                plan_items.append(Text(f"ℹ️  {note}", style="dim"))

        execution_plan_panel = Panel(
            Group(*plan_items), title="[bold]Execution Plan[/bold]", border_style="blue", expand=True
        )
        cli.console.print(execution_plan_panel)

        if run_bg or run_now:
            job_id = cli.executor.execute(
                command_lists=final_commands,
                session_obj=cli.session,
                tool_name=tool_name,
                tool_command_name=command_name,
                run_now=run_now,
                run_bg=run_bg,
                suppress_individual_summaries=is_per_param_execution and run_now,
                # --- FIX: Pass the temp file path to the executor to manage its lifecycle ---
                temp_proxy_conf_path=temp_proxy_conf_path
            )
            if run_bg and job_id:
                log.success(f"Job(s) {job_id} started in the background.")
        else:
            log.prompt("This is a preview. The command has not been executed yet.")
            preview_cmd = f"pwn {command_name or ''} {' '.join(shlex.quote(p) for p in extra_params)}".strip()
            log.prompt(f"Add 'now' to run it in the foreground: {preview_cmd} now")
            log.prompt(f"Add 'bg' to run it in the background: {preview_cmd} bg")