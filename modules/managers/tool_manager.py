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

# modules/managers/tool_manager.py

from .base_manager import JSONManager
from modules.services import log
from modules.placeholders import resolve_placeholders
import os, json, shlex, shutil
from rich.panel import Panel
from rich.table import Table
from rich.columns import Columns
from rich.console import Group

class ToolManager(JSONManager):
    def __init__(self):
        super().__init__("TOOLS")

    def _cmd_reorder(self, args, cli):
        """Handles the 'tool reorder' command."""
        self.reorder_param(
            tool_name=args.name,
            command_name=args.command_name,
            old_index=args.old_index,
            new_index=args.new_index
        )

    def _cmd_delete(self, args, cli):
        """
        Intelligent, context-sensitive delete command specifically for tools.
        Infers the action based on the arguments.
        """
        tool_name = args.name
        delete_args = args.delete_args
        tool = self.load(tool_name)
        if not tool:
            # self.load() already logs an error if not found
            return

        if not delete_args:
            log.error("No arguments provided for deletion.")
            log.prompt("Example: 'tool delete <name> <field_name>' or 'tool delete <name> <cmd> param <param_value>'")
            return

        # --- Syntax 1: `... <cmd_name> param <parameter...>` ---
        if 'param' in delete_args:
            try:
                param_index = delete_args.index('param')
                if param_index == 1:
                    cmd_name = delete_args[0]
                    param_args = delete_args[2:]
                    if not param_args:
                        log.error(f"Parameter missing after '{cmd_name} param'.")
                        return

                    # Distinction: `delete param <index>` vs. `delete param <value>`
                    try:
                        idx = int(param_args[0])
                        self.delete_param_by_index(tool_name, cmd_name, idx)
                    except (ValueError, IndexError):
                        param_to_delete_val = " ".join(param_args)
                        self.delete_param(tool_name, cmd_name, param_to_delete_val)
                    return
                else:
                    log.error("Invalid syntax. 'param' must be in the second position.")
                    log.prompt("Example: 'tool delete <name> <cmd> param <param_value>'")
                    return
            except ValueError:
                pass # 'param' not in args, will be handled by the next blocks

        # --- Syntax 2: `... command <cmd_name>` ---
        if len(delete_args) == 2 and delete_args[0] == 'command':
            cmd_name = delete_args[1]
            self.delete_command(tool_name, cmd_name)
            return

        # --- Syntax: `... <cmd_name>` (where cmd_name is a single arg) ---
        # This handles the case from the help example: `tool delete nmap stealth-scan`
        if len(delete_args) == 1:
            potential_cmd_name = delete_args[0]
            if any(c.get("name") == potential_cmd_name for c in tool.get("commands", [])):
                self.delete_command(tool_name, potential_cmd_name)
                return

        # --- Syntax: `... <cmd_name>` (where cmd_name is a single arg) ---
        # This handles the case from the help example: `tool delete nmap stealth-scan`
        if len(delete_args) == 1:
            potential_cmd_name = delete_args[0]
            if any(c.get("name") == potential_cmd_name for c in tool.get("commands", [])):
                self.delete_command(tool_name, potential_cmd_name)
                return

        # --- NEW: Syntax `... <cmd_name> <field_to_delete>` ---
        # This handles deleting a field from within a command object.
        if len(delete_args) == 2:
            cmd_name, field_to_delete = delete_args
            cmd_to_update = next((c for c in tool.get("commands", []) if c.get("name") == cmd_name), None)

            if cmd_to_update:
                if field_to_delete in cmd_to_update:
                    del cmd_to_update[field_to_delete]
                    # Save the entire commands list back to the tool
                    self.update(tool_name, "commands", tool["commands"])
                    log.success(f"Field '{field_to_delete}' deleted from command '{cmd_name}' in tool '{tool_name}'.")
                else:
                    log.error(f"Field '{field_to_delete}' not found in command '{cmd_name}'.")
                return

        # --- Syntax 3 (Fallback): `... <field>` ---
        if len(delete_args) == 1:
            field_to_delete = delete_args[0]
            if field_to_delete == 'commands':
                log.error("The 'commands' list cannot be deleted directly.")
                log.prompt("Use 'tool delete <name> command <cmd_name>' to delete a command.")
                return
            if self.delete(tool_name, field_to_delete):
                 log.success(f"Tool '{tool_name}' field '{field_to_delete}' deleted.")
            return

        log.error("Invalid arguments for 'tool delete'.")
        log.prompt("Use 'tool -h' for help.")

    def reorder_param(self, tool_name, command_name, old_index, new_index):
        """
        Reorders a parameter. CLI uses 1-based indices. 
        Leverages the generic JSONManager.reorder for atomicity.
        """
        cmd_idx = self._get_command_index(tool_name, command_name)
        if cmd_idx == -1: return

        # JSONManager.reorder uses 0-based index for the path segment
        target_path = f"commands.{cmd_idx}.params.{old_index - 1}"
        # and 0-based new_index
        if self.reorder(tool_name, target_path, new_index - 1):
            log.success(f"Parameter in '{tool_name} {command_name}' moved from position {old_index} to {new_index}.")

    def _get_command_index(self, tool_name, command_name):
        """Helper to find the index of a command by name."""
        tool = self.load(tool_name)
        if not tool: return -1
        for i, cmd in enumerate(tool.get("commands", [])):
            if cmd.get("name") == command_name:
                return i
        log.error(f"Command '{command_name}' not found in tool '{tool_name}'.")
        return -1

    def update_param(self, tool_name, command_name, index, new_value):
        """Updates a parameter at a specific index using generic update logic."""
        cmd_idx = self._get_command_index(tool_name, command_name)
        if cmd_idx == -1: return

        path = f"commands.{cmd_idx}.params.{index - 1}"
        if self.update(tool_name, path, new_value):
            log.success(f"Parameter {index} in '{tool_name} {command_name}' updated.")

    def delete_param_by_index(self, tool_name, command_name, index):
        """Deletes a parameter at a specific index."""
        tool = self.load(tool_name)
        if not tool: return

        cmd = next((c for c in tool.get("commands", []) if c.get("name") == command_name), None)
        if not cmd:
            log.error(f"Command '{command_name}' not found in tool '{tool_name}'.")
            return

        params = cmd.get("params", [])
        real_index = index - 1

        if 0 <= real_index < len(params):
            removed_param = params.pop(real_index)
            self.update(tool_name, "commands", tool["commands"])
            log.success(f"Parameter {index} ('{removed_param}') deleted from '{tool_name}'.")
        else:
            log.error(f"Invalid index {index}. There are only {len(params)} parameters.")

    def _cmd_update(self, args, cli):
        """Dispatches tool update operations based on arguments."""
        tool_name = args.name
        # Reconstruct update_args from field and value for internal handlers
        update_args = [args.field] + args.value
        tool = self.load(tool_name)
        if not tool:
            return

        # Prioritize handlers from most specific to most general syntax
        if self._handle_param_update(tool_name, update_args, tool):
            return
        if self._handle_command_update(tool_name, update_args, tool):
            return
        if self._handle_top_level_update(tool_name, update_args, tool):
            return

        log.error("Invalid arguments for 'tool update'.")
        log.prompt("Use 'tool -h' for help.")

    def _handle_param_update(self, tool_name, update_args, tool):
        """Handles syntax related to adding or updating parameters."""
        if 'param' not in update_args:
            return False

        param_index = update_args.index('param')

        # Syntax: `... <cmd_name> param ...`
        if param_index == 1:
            cmd_name = update_args[0]
            param_args = update_args[2:]

            if not any(c.get("name") == cmd_name for c in tool.get("commands", [])):
                log.error(f"Command '{cmd_name}' not found in '{tool_name}'.")
                log.prompt(f"Create it first with: tool update {tool_name} command {cmd_name}")
                return True

            # Subcase: `... param <index> <new_value>`
            if len(param_args) >= 2:
                # Try to interpret the first argument as an index
                try:
                    idx = int(param_args[0])
                    new_value = " ".join(param_args[1:])
                    self.update_param(tool_name, cmd_name, idx, new_value)
                    return True
                except ValueError:
                    pass  # Fall through to add param

            # Subcase: `... param <value_to_add>`
            param_to_add = " ".join(param_args)
            if param_to_add:
                self.add_param(tool_name, cmd_name, param_to_add)
                log.success(f"Parameter added to '{tool_name} {cmd_name}': {param_to_add}")
            else:
                log.error(f"Parameter missing after '{cmd_name} param'.")
            return True

        log.error("Invalid syntax. 'param' keyword is in the wrong position.")
        return True # Handled (by showing an error)

    def _handle_command_update(self, tool_name, update_args, tool):
        """Handles syntax related to adding or updating command fields."""
        # Syntax: `... command <cmd_name>`
        if len(update_args) == 2 and update_args[0] == 'command':
            cmd_name = update_args[1]
            self.add_command(tool_name, cmd_name)
            log.success(f"Command '{cmd_name}' added to '{tool_name}'.")
            log.prompt(f"Now add parameters with: tool update {tool_name} {cmd_name} param <param>")
            return True

        # Syntax: `... <cmd_name> <field> <value>`
        if len(update_args) >= 3:
            cmd_name, field, value_str = update_args[0], update_args[1], " ".join(update_args[2:])
            cmd = next((c for c in tool.get("commands", []) if c.get("name") == cmd_name), None)

            if cmd:
                if field in ['name', 'params']:
                    log.error(f"Cannot update '{field}' directly. Use dedicated syntax.")
                    return True

                value = self._convert_value(field, value_str)
                if value is None and field == 'execute_per_param': # Conversion failed
                    return True

                cmd[field] = value
                self.update(tool_name, "commands", tool["commands"])
                log.success(f"Field '{field}' in command '{cmd_name}' updated to '{value}'.")
                return True

        return False

    def _handle_top_level_update(self, tool_name, update_args, tool):
        """Handles syntax for updating top-level tool fields."""
        if len(update_args) < 2:
            return False

        field, value_parts = update_args[0], update_args[1:]
        
        # --- FIX: Join with comma if field is 'tags', otherwise with space ---
        if field.lower() == 'tags':
            value_str = ",".join(value_parts)
        else:
            value_str = " ".join(value_parts)

        if field.lower() == 'name':
            self.rename(tool_name, value_str)
            return True

        if field == 'path' and value_str.lower() == 'auto':
            self._find_and_set_path(tool_name)
            return True

        if field in ['command_style', 'commands']:
            log.error(f"The '{field}' field cannot be updated directly.")
            return True

        value = self._convert_value(field, value_str)
        if value is None and field.lower() == 'sudo': # Conversion failed
            return True

        if '.' in field:
            self._handle_nested_update(tool_name, field, value)
        else:
            self.update(tool_name, field, value)
            log.success(f"Tool '{tool_name}' field '{field}' updated -> {value}")
        return True

    def _convert_value(self, field, value_str):
        """Converts string value to boolean if the field requires it."""
        if field.lower() in ['sudo', 'execute_per_param']:
            if value_str.lower() in ['true', '1', 'on', 'yes']:
                return True
            elif value_str.lower() in ['false', '0', 'off', 'no']:
                return False
            else:
                log.error(f"Invalid value for '{field}'. Please use 'true' or 'false'.")
                return None
        return value_str

    def _handle_nested_update(self, tool_name, field, value):
        """Handles nested field updates using dot notation."""
        data = self.load(tool_name)
        if not data: return

        keys = field.split('.')
        current_level = data
        for key in keys[:-1]:
            if key not in current_level or not isinstance(current_level[key], dict):
                current_level[key] = {}
            current_level = current_level[key]

        current_level[keys[-1]] = value
        self._save_data(tool_name, data)
        log.success(f"Tool '{tool_name}' nested field '{field}' updated -> {value}")

    def _find_and_set_path(self, tool_name):
        """Tries to find and set the path for a tool automatically."""
        log.info(f"Searching for executable for '{tool_name}' in system PATH...")
        executable_path = shutil.which(tool_name)

        if executable_path:
            self.update(tool_name, 'path', executable_path)
            log.success(f"Tool '{tool_name}' found and path set to '{executable_path}'.")
        else:
            log.warning(f"Executable for '{tool_name}' could not be found in the system PATH.")
            log.prompt(f"The path was not changed. Please provide the correct path manually if necessary.")


    def _cmd_export(self, args, cli):
        """Generates the pwnity commands to reconstruct a tool."""
        name = args.name
        data = self.load(name)
        if not data:
            return

        commands = [f"tool add {name}"]

        # Export the path if it is explicitly set and not identical to the name
        if 'path' in data and data['path'] != name:
            commands.append(f"tool update {name} path {shlex.quote(data['path'])}")
        
        # Export the sudo flag only if it is set to true
        if data.get('sudo'):
            commands.append(f"tool update {name} sudo true")

        if 'commands' in data and isinstance(data['commands'], list):
            for cmd in data['commands']:
                cmd_name = cmd.get('name')
                if not cmd_name: continue
                
                # Only run 'command add' if it's not the implicit command
                if cmd_name != name:
                    commands.append(f"tool update {name} command {cmd_name}")
                
                # Export execute_per_param if it's explicitly set to true
                if cmd.get('execute_per_param'):
                    commands.append(f"tool update {name} {cmd_name} execute_per_param true")

                # Export other custom fields within the command
                handled_cmd_keys = {'name', 'params', 'execute_per_param'}
                for key, value in cmd.items():
                    if key not in handled_cmd_keys:
                        val_str = json.dumps(value) if isinstance(value, (dict, list)) else str(value)
                        commands.append(f"tool update {name} {cmd_name} {key} {shlex.quote(val_str)}")

                if 'params' in cmd and isinstance(cmd['params'], list):
                    for param in cmd['params']:
                        commands.append(f"tool update {name} {cmd_name} param {shlex.quote(param)}")
                
                # Export other custom fields within the command
                handled_cmd_keys = {'name', 'params', 'execute_per_param'}
                for key, value in cmd.items():
                    pass # This block was moved up to ensure correct order

        # Export all other top-level custom fields
        handled_top_level_keys = {'name', 'path', 'sudo', 'commands'}
        for key, value in data.items():
            if key not in handled_top_level_keys:
                val_str = json.dumps(value) if isinstance(value, (dict, list)) else str(value)
                commands.append(f"tool update {name} {key} {shlex.quote(val_str)}")
        log.header(f"Export für Tool '{name}'")
        cli.poutput("\n".join(commands))

    def _cmd_add(self, args, cli):
        """
        Overrides the 'add' logic to set a sensible default for command_style.
        """
        entity_type = self._get_entity_type()
        
        path = os.path.join(self.folder, f"{args.name}.json")
        if os.path.exists(path):
            log.error(f"{entity_type} '{args.name}' already exists.")
            return

        # Try to find the tool's path automatically
        executable_path = shutil.which(args.name)

        data = {"name": args.name, "path": executable_path or args.name, "sudo": False, "commands": []}
        if not self._save_data(args.name, data):
            return # Error is logged by _save_data

        if executable_path:
            log.success(f"{entity_type} '{args.name}' added and found at '{executable_path}'.")
        else:
            log.warning(f"{entity_type} '{args.name}' added, but the executable was not found in the PATH.")
            log.prompt(f"Please set the path manually with: tool update {args.name} path /path/to/tool")

        log.prompt(f"Configure it now with 'tool update {args.name} ...'")

    def delete_command(self, tool_name, command_name):
        tool = self.load(tool_name)
        if not tool: return

        commands = tool.get("commands", [])
        original_len = len(commands)
        
        commands = [c for c in commands if c.get("name") != command_name]

        if len(commands) == original_len:
            log.warning(f"Command '{command_name}' not found in tool '{tool_name}'.")
        else:
            self.update(tool_name, "commands", commands)
            log.success(f"Command '{command_name}' deleted from tool '{tool_name}'.")

    def delete_param(self, tool_name, command_name, param_to_delete):
        tool = self.load(tool_name)
        if not tool: return

        commands = tool.get("commands", [])
        cmd = next((c for c in commands if c.get("name") == command_name), None)

        if not cmd:
            log.error(f"Command '{command_name}' not found in tool '{tool_name}'.")
            return

        params = cmd.get("params", [])
        original_len = len(params)
        
        params = [p for p in params if p != param_to_delete]

        if len(params) == original_len:
            log.warning(f"Parameter '{param_to_delete}' not found in command '{command_name}'.")
            log.prompt("Ensure the parameter matches exactly.")
        else:
            cmd["params"] = params
            self.update(tool_name, "commands", commands)
            log.success(f"Parameter '{param_to_delete}' deleted from command '{command_name}'.")
    
    def add_command(self, tool_name, command_name):
        tool = self.load(tool_name) or {"name": tool_name, "commands": []}
        if "commands" not in tool:
            tool["commands"] = []

        # Check if command already exists
        if any(c["name"] == command_name for c in tool["commands"]):
            log.warning(f"Command '{command_name}' already exists in {tool_name}.")
            return tool

        tool["commands"].append({"name": command_name, "params": []})
        self.update(tool_name, "commands", tool["commands"])
        log.info(f"Command '{command_name}' added to {tool_name}.")
        return tool

    def add_param(self, tool_name, command_name, param):
        """
        Adds a parameter.
        Uses the improved JSONManager.update with list-appending support.
        """
        cmd_idx = self._get_command_index(tool_name, command_name)
        if cmd_idx == -1: return None

        tool = self.load(tool_name)
        p_idx = len(tool["commands"][cmd_idx].get("params", []))
        
        # Always append using the next index
        path = f"commands.{cmd_idx}.params.{p_idx}"
        normalized_param = param.replace('\\"', '"')
        
        updated = self.update(tool_name, path, normalized_param)
        if updated:
            log.info(f"Param '{param}' added to {tool_name} {command_name}.")
            return updated["commands"][cmd_idx]
        return None

    def _cmd_destroy(self, args, cli):
        """
        Overrides the default destroy to prevent deletion if the tool is loaded in any session.
        """
        tool_to_delete = args.name

        # Check all active sessions
        for session_name, session_obj in cli.session_mgr.sessions.items():
            if session_obj.tool == tool_to_delete:
                log.error(f"Cannot delete tool '{tool_to_delete}' because it is currently loaded in session '{session_name}'.")
                log.prompt(f"Switch to session '{session_name}' and run 'tool unload' first.")
                return

        # If the check passes, proceed with the default destroy logic from the parent class.
        log.info(f"Tool '{tool_to_delete}' is not loaded in any active session. Proceeding with deletion...")
        super()._cmd_destroy(args, cli)


    def _cmd_show(self, args, cli):
        """Handles 'tool show [name]'."""
        tool_name = args.name
        if not tool_name:
            # If no name is provided, use the one from the session
            tool_name = cli.session.tool
            if not tool_name:
                log.error("No tool specified and no tool loaded in the session.")
                log.prompt("Use 'tool show <name>' or load one with 'tool load <name>'.")
                return

        tool_data = self.load(tool_name)
        if not tool_data:
            return # load() already logs an error
        self._format_and_show_entity(tool_data, cli.console)

    def build_command(self, tool_name, session=None, command_to_run=None, extra_params=None):
        """
        Builds commands for a tool.
        - tool_name: The name of the tool.
        - session: The active session for placeholder resolution.
        - command_to_run: Optional. The specific command (label) to be executed.
                          If None, all commands of the tool will be built.
        - extra_params: Optional. A list of temporary parameters to be appended at the end.
        """
        tool = self.load(tool_name)
        if not tool:
            return []

        # Get the path to the executable, with a fallback to the tool name
        executable = tool.get("path", tool_name)

        all_commands = tool.get("commands", [])
        target_commands = all_commands

        if command_to_run:
            target_commands = [cmd for cmd in all_commands if cmd.get("name") == command_to_run]
            if not target_commands:
                log.warning(f"Command '{command_to_run}' not found in tool '{tool_name}'.")
                return []

        built_commands = []
        for cmd in target_commands:
            # Check for the boolean flag 'execute_per_param'. Default is False.
            if cmd.get("execute_per_param", False):
                # Each parameter becomes its own command execution.
                # Ideal for 'echo' based checklists.
                for p in cmd.get("params", []):
                    resolved_param = resolve_placeholders(p, session=session)
                    # For this style, the parameter is treated as a single argument.
                    single_cmd = [executable, resolved_param]
                    # Note: extra_params are ignored in this mode as their context is ambiguous.
                    built_commands.append(single_cmd)
            else:
                # "single_line" - the original behavior.
                # 1. Resolve placeholders in the raw parameter strings.
                # The resolve_placeholders function now handles nested/recursive resolution internally.
                resolved_param_strings = [
                    resolve_placeholders(p, session=session, tool_name=tool_name, command_name=cmd.get("name"))
                    for p in cmd.get("params", [])
                ]

                # 2. Split each resolved string into individual arguments. This logic
                #    is designed to correctly handle three cases:
                #    a) A single string in JSON that represents multiple shell arguments (e.g., "-o /dev/null").
                #    b) A single string that should be treated as one argument despite spaces (e.g., "Origin: foo.com").
                #    c) A single string that should be treated as one argument and *retain* its quotes (e.g., "\"Header: value\"").
                #    The key is to use `posix=False` in shlex.split.
                final_params = []
                for s in resolved_param_strings:
                    # Filter out empty strings that can result from resolving an empty placeholder
                    if s:
                        # Use shlex.split with posix=True. This correctly handles quoted strings as single arguments
                        # and removes the quotes from the resulting tokens.
                        final_params.extend(shlex.split(s, posix=True))
                full_cmd = [executable] + final_params
                
                # 3. Append temporary extra parameters if present
                if extra_params:
                    full_cmd.extend(extra_params)
                built_commands.append(full_cmd)

        return built_commands

    def _format_and_show_entity(self, entity, console):
        """Overridden formatting for a nicer, tabular output of tool details."""
        data_to_show = entity.copy()
        name = entity.get('name', 'N/A')
        data_to_show.pop('name', None)
        commands_data = data_to_show.pop('commands', [])
        renderables = []
        
        # --- Teil 1: Allgemeine Tool-Informationen ---
        if data_to_show:
            from .base_manager import _add_data_to_table_recursively
            top_level_table = Table(show_header=False, box=None, padding=(0, 2))
            top_level_table.add_column(style="bold blue", no_wrap=True)
            top_level_table.add_column(style="green")
            _add_data_to_table_recursively(top_level_table, data_to_show)
            
            general_info_panel = Panel(
                top_level_table, title="[bold]General Information[/bold]", border_style="blue", expand=True
            )
            renderables.append(general_info_panel)

        # --- Part 2: Panels for each command ---
        command_panels = []
        if commands_data:
            for cmd in commands_data:
                cmd_name = cmd.get('name', 'N/A')

                # Erstelle eine Gruppe, um alle Details des Befehls zu halten
                cmd_details_group = []

                # Extrahiere andere Felder (wie execute_per_param) und zeige sie an
                other_fields = {k: v for k, v in cmd.items() if k not in ['name', 'params']}
                if other_fields:
                    fields_table = Table(show_header=False, box=None, padding=(0, 1))
                    fields_table.add_column(style="dim", no_wrap=True)
                    fields_table.add_column(style="default")
                    for key, value in other_fields.items():
                        fields_table.add_row(f"{key}:", str(value))
                    cmd_details_group.append(fields_table)
                
                # Zeige die Parameter an
                params = cmd.get('params', [])
                if params:
                    params_table = Table(show_header=False, box=None, padding=(0, 1))
                    params_table.add_column(style="dim", width=4, no_wrap=True)
                    params_table.add_column(style="green", ratio=1)
                    for i, param in enumerate(params, 1):
                        params_table.add_row(f"{i}:", str(param))
                    cmd_details_group.append(params_table)
                
                panel = Panel(Group(*cmd_details_group), title=f":arrow_forward: [cyan]{cmd_name}[/cyan]", border_style="dim", expand=True)
                command_panels.append(panel)

        # --- Part 3: Combine everything ---
        if command_panels:
            renderables.append(Columns(command_panels, equal=True, expand=True))

        # If nothing is configured, show a message
        if not renderables:
            content_group = Group(Panel("[dim]No configuration available for this tool.[/dim]", border_style="dim", expand=True))
        else:
            content_group = Group(*renderables)

        # Wrap the group with a main panel
        main_panel = Panel(
            content_group,
            title=f":wrench: [bold]Tool: {name}[/bold]",
            border_style="yellow",
            expand=True
        )
        console.print(main_panel)

    def _cmd_list(self, args, cli):
        """Overrides the default list to show a compact, clean 2-line layout."""
        items = self.list_all()
        if not items:
            log.info("No Tools found.")
            return

        from rich.text import Text
        items = sorted(items, key=lambda x: (1 if x.startswith("hub/") else 0, x))

        output = []
        for item_name in items:
            data = self.load(item_name)
            if not data: continue

            # 1. Identify origin
            is_hub = item_name.startswith("hub/")
            origin_tag = "[blue][L][/blue]"
            display_name = item_name
            
            if is_hub:
                parts = item_name.split("/")
                origin = parts[1].replace("_", ":")
                origin_tag = f"[cyan][H][/cyan]"
                base_name = parts[-1]
                prefix = "/".join(parts[:-1])
                display_name = f"[dim]{prefix}/[/dim][bold yellow]{base_name}[/bold yellow] [dim](@{origin})[/dim]"
            else:
                display_name = f"[bold green]{item_name}[/bold green]"

            # 2. Data
            desc = data.get('description', '')
            path = data.get('path', '')
            sudo_prefix = "[bold red]sudo[/bold red] " if data.get('sudo') else ""
            command_names = [cmd.get('name', '') for cmd in data.get('commands', [])]
            commands_str = ", ".join(command_names)

            # --- Row 1: [L] curl - description ---
            desc_part = f" - [italic grey50]{desc}[/italic grey50]" if desc else ""
            output.append(Text.from_markup(f" {origin_tag} {display_name}{desc_part}"))

            # --- Row 2: • sudo /path | cmds ---
            output.append(Text.from_markup(f"     [dim]•[/dim] {sudo_prefix}[cyan]{path}[/cyan] [dim]|[/dim] [magenta]{commands_str}[/magenta]"))

            # --- Row 3: Tags ---
            tags = self.normalize_tags(data.get('tags', ''))
            if tags:
                tag_str = " ".join([f"[cyan]#{t}[/cyan]" for t in tags])
                output.append(Text.from_markup(f"     [dim]• Tags: {tag_str}[/dim]"))
            
            # Spacer
            output.append(Text(""))

        cli.console.print(Panel(
            Group(*output),
            title="[bold]Available Tools[/bold]",
            border_style="dim",
            subtitle=f"{len(items)} Tools total"
        ))