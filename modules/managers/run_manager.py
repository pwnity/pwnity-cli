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

    def _ensure_sudo_credentials(self, cli, run_bg=False) -> bool:
        """
        Checks if sudo credentials are valid. If not, it prompts the user interactively,
        unless running in a non-interactive environment (Web UI, Background).
        Returns True if credentials are valid or become valid (or if we skip the check), False otherwise.
        """
        check_process = subprocess.run(['sudo', '-n', 'true'], capture_output=True)
        if check_process.returncode == 0:
            log.debug("Sudo credentials are valid (cached).")
            return True

        # Determine if we are in a headless/non-interactive context
        is_headless = getattr(cli, 'headless_mode', False) or getattr(cli, 'web_ui_mode', False)
        
        if run_bg or is_headless:
            # We cannot prompt interactively here.
            # We return True anyway, assuming the user will handle the sudo prompt
            # in the job's PTY/output screen via 'jobs input'.
            log.info("Sudo credentials required. Prepending sudo and allowing process to prompt for password in its PTY.")
            return True

        log.prompt("Sudo credentials required. Please enter your password.")
        interactive_process = subprocess.run(['sudo', '-v'])

        if interactive_process.returncode == 0:
            log.success("Sudo credentials accepted.")
            return True
        else:
            log.error("Failed to obtain sudo credentials. Aborting command.")
            return False

    def _parse_pwn_arguments(self, pwn_args: list) -> tuple[str | None, list[str], bool, bool]:
        """Parses the raw pwn arguments to extract command name, extra params, and execution modes."""
        command_name = None
        run_now = 'now' in pwn_args
        run_bg = 'bg' in pwn_args

        # Create a mutable copy to remove flags
        args_copy = list(pwn_args)
        if run_now: args_copy.remove('now')
        if run_bg: args_copy.remove('bg')

        if args_copy and not args_copy[0].startswith('-'):
            command_name = args_copy.pop(0)
        
        # --- FIX: Correctly handle the '--' separator for extra parameters ---
        # Find the '--' separator. If it exists, all subsequent arguments are extra_params.
        try:
            separator_index = args_copy.index('--')
            extra_params = args_copy[separator_index + 1:]
        except ValueError:
            # No '--' found, so all remaining args are extra_params.
            extra_params = args_copy
        return command_name, extra_params, run_now, run_bg

    def _get_effective_tool_command(self, tool_data: dict, command_name_arg: str | None, cli) -> tuple[str | None, bool]:
        """Determines the effective command name and if it's a per-param execution."""
        defined_commands = tool_data.get("commands", [])
        if not defined_commands:
            log.warning(f"No commands configured for tool '{tool_data.get('name', 'N/A')}'.")
            return None, False

        effective_command_name = command_name_arg
        is_per_param_execution = False

        if not effective_command_name:
            if len(defined_commands) == 1 and defined_commands[0].get("name"):
                effective_command_name = defined_commands[0].get("name")
                is_per_param_execution = defined_commands[0].get("execute_per_param", False)
                log.prompt(f"Only one command ('{effective_command_name}') defined, selecting it automatically.")
            else:
                command_names = [cmd.get('name') for cmd in defined_commands]
                log.error(f"Multiple commands defined for '{tool_data.get('name', 'N/A')}'. Please specify one.")
                log.prompt(f"Available commands: {', '.join(command_names)}")
                log.prompt(f"Example: pwn {command_names[0]} now")
                return None, False
        else:
            cmd_obj = next((c for c in defined_commands if c.get("name") == effective_command_name), None)
            if cmd_obj:
                is_per_param_execution = cmd_obj.get("execute_per_param", False)
            else:
                log.error(f"Command '{effective_command_name}' not found in tool '{tool_data.get('name', 'N/A')}'.")
                command_names = [cmd.get('name') for cmd in defined_commands]
                log.prompt(f"Available commands: {', '.join(command_names)}")
                return None, False
        
        return effective_command_name, is_per_param_execution

    def _prepare_proxy_environment(self, cli, initial_proxy_config: dict | None) -> tuple[dict | None, str | None]:
        """
        Prepares the proxy configuration and the content for a temporary config file.
        Returns (modified_proxy_config, temp_proxy_conf_content).
        """
        processed_proxy_config = initial_proxy_config.copy() if initial_proxy_config else None
        temp_proxy_conf_content = None

        if processed_proxy_config and processed_proxy_config.get('wrapper_template'):
            template_name = processed_proxy_config['wrapper_template']
            template_dir = config.get_parameter("DIRS", "PROXY_TEMPLATES", "etc/proxy_templates")
            template_path = os.path.join(template_dir, template_name)

            if not os.path.isfile(template_path):
                log.error(f"Proxy template file not found: {template_path}")
                processed_proxy_config = None # Disable proxy for this run
            else:
                with open(template_path, 'r') as f:
                    template_content = f.read()

                temp_proxy_conf_content = template_content
                for key, value in processed_proxy_config.items():
                    value_to_replace = str(value) if value is not None else ""
                    if key == 'host' and str(value_to_replace).lower() == 'localhost':
                        value_to_replace = '127.0.0.1'
                    temp_proxy_conf_content = temp_proxy_conf_content.replace(f"$proxy.{key}", value_to_replace)

        return processed_proxy_config, temp_proxy_conf_content

    def _build_single_final_command(self, raw_cmd_list: list[str], tool_name: str, tool_needs_sudo: bool, proxy_config: dict | None, temp_proxy_conf_path: str | None, cli, run_bg=False) -> tuple[list[str], list[str]]:
        """
        Resolves placeholders, applies proxy wrappers and sudo to a single command list.
        Returns (final_command_list, command_notes).
        """
        command_notes = []
        
        # 1. Resolve placeholders
        final_cmd = [placeholders.resolve_placeholders(part, cli.session) for part in raw_cmd_list]

        # 2. Apply proxy wrapper if configured
        if proxy_config and proxy_config.get('wrapper_command'):
            wrapper_cmd_str = proxy_config['wrapper_command']
            wrapper_opts_str = proxy_config.get('wrapper_options', '')
            full_wrapper_str = f"{wrapper_cmd_str} {wrapper_opts_str}".strip()
            wrapper_cmd_list = shlex.split(full_wrapper_str)
            final_cmd = wrapper_cmd_list + final_cmd
            # Note: Proxy note is now added in _prepare_proxy_environment

        # 3. Determine if sudo is needed and prepend it to the *entire* command
        use_sudo_for_this_cmd = tool_needs_sudo or (proxy_config and proxy_config.get('wrapper_needs_sudo', False))
        sudo_reason = ""
        if tool_needs_sudo:
            sudo_reason = "Required by tool configuration."
        elif proxy_config and proxy_config.get('wrapper_needs_sudo', False):
            sudo_reason = "Required by proxy wrapper."
        if use_sudo_for_this_cmd:
            if not self._ensure_sudo_credentials(cli, run_bg=run_bg):
                return [], [] # Abort if sudo fails
            final_cmd = ['sudo'] + final_cmd
            command_notes.append(f"Sudo: Enabled ({sudo_reason})")

        return final_cmd, command_notes

    def do_pwn(self, args, cli):
        """Handles the 'pwn' and 'run' commands."""
        if not args.pwn_args:
            cli.help_mgr.show_help_pwn()
            return

        command_name_arg, extra_params, run_now, run_bg = self._parse_pwn_arguments(args.pwn_args)

        if not cli.session.tool:
            log.error("No tool loaded in the current session. (e.g., 'tool load gobuster')")
            return
        tool_name = cli.session.tool

        tool_data = cli.tool_mgr.load(tool_name)
        if not tool_data: # tool_mgr.load already logs an error if not found
            return

        command_name, is_per_param_execution = self._get_effective_tool_command(tool_data, command_name_arg, cli)
        if not command_name:
            return
        
        commands_to_run = cli.tool_mgr.build_command(
            tool_name, 
            session=cli.session, 
            command_to_run=command_name,
            extra_params=extra_params
        )
        if not commands_to_run:
            return

        final_commands = []
        execution_notes = []
        tool_needs_sudo = tool_data.get('sudo', False)
        initial_proxy_config = cli.proxy_mgr.get_effective_config(cli.session)
        processed_proxy_config, temp_proxy_conf_content = self._prepare_proxy_environment(cli, initial_proxy_config)
        temp_proxy_conf_path = None # Will be set only on execution

        # --- FIX: Create temp file only on execution, not for preview ---
        if processed_proxy_config:
            # For preview, use a placeholder name. For execution, create the real file.
            if run_now or run_bg:
                try:
                    run_dir = config.get_parameter("DIRS", "RUN", "data/run")
                    os.makedirs(run_dir, exist_ok=True)
                    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.conf', prefix='pwnity_proxy_', dir=run_dir) as temp_f:
                        temp_f.write(temp_proxy_conf_content)
                        temp_proxy_conf_path = temp_f.name
                    log.debug(f"Created temporary proxy config at: {temp_proxy_conf_path}")
                except Exception as e:
                    log.error(f"Failed to create temporary proxy config: {e}")
                    processed_proxy_config = None # Disable proxy for this run
            else:
                # For preview mode, just generate a representative path.
                run_dir = config.get_parameter("DIRS", "RUN", "data/run")
                temp_proxy_conf_path = os.path.join(run_dir, "pwnity_proxy_preview.conf")

            # If we have a path (real or fake), update the wrapper options for display/execution
            if temp_proxy_conf_path:
                base_opts = cli.proxy_mgr.get_effective_config(cli.session).get('wrapper_options', '')
                processed_proxy_config['wrapper_options'] = f"-f {temp_proxy_conf_path} {base_opts}".strip()

        # Build execution notes for the plan display
        if processed_proxy_config and processed_proxy_config.get('wrapper_command'):
            wrapper_cmd_str = processed_proxy_config['wrapper_command']
            wrapper_opts_str = processed_proxy_config.get('wrapper_options', '')
            full_wrapper_str = f"{wrapper_cmd_str} {wrapper_opts_str}".strip()
            execution_notes.append(f"Proxy: Enabled ('{full_wrapper_str}')")

        for raw_cmd_list in commands_to_run:
            final_cmd_list, cmd_notes = self._build_single_final_command(
                raw_cmd_list, tool_name, tool_needs_sudo, processed_proxy_config, temp_proxy_conf_path, cli, run_bg=run_bg
            )
            if not final_cmd_list: # Sudo credentials failed
                return
            final_commands.append(final_cmd_list)
            execution_notes.extend(cmd_notes)

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