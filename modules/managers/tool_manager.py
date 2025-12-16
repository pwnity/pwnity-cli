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
        tool = self.load(tool_name)
        if not tool: return

        cmd = next((c for c in tool.get("commands", []) if c.get("name") == command_name), None)
        if not cmd:
            log.error(f"Command '{command_name}' not found in tool '{tool_name}'.")
            return

        params = cmd.get("params", [])
        
        # Convert 1-based user index to 0-based list index
        old_idx_0 = old_index - 1
        new_idx_0 = new_index - 1

        if not (0 <= old_idx_0 < len(params)):
            log.error(f"Invalid old index {old_index}. There are only {len(params)} parameters (index 1 to {len(params)}).")
            return

        if not (0 <= new_idx_0 < len(params)):
            log.error(f"Invalid new index {new_index}. Must be between 1 and {len(params)}).")
            return

        param_to_move = params.pop(old_idx_0)
        params.insert(new_idx_0, param_to_move)

        self.update(tool_name, "commands", tool["commands"])
        log.success(f"Parameter in '{tool_name} {command_name}' moved from position {old_index} to {new_index}.")

    def update_param(self, tool_name, command_name, index, new_value):
        """Updates a parameter at a specific index."""
        tool = self.load(tool_name)
        if not tool: return

        cmd = next((c for c in tool.get("commands", []) if c.get("name") == command_name), None)
        if not cmd:
            log.error(f"Command '{command_name}' not found in tool '{tool_name}'.")
            return

        params = cmd.get("params", [])
        # User index is 1-based, list index is 0-based
        real_index = index - 1

        if 0 <= real_index < len(params):
            old_value = params[real_index]
            params[real_index] = new_value
            self.update(tool_name, "commands", tool["commands"])
            log.success(f"Parameter {index} in '{tool_name} {command_name}' updated: '{old_value}' -> '{new_value}'")
        else:
            log.error(f"Invalid index {index}. There are only {len(params)} parameters (index 1 to {len(params)}).")

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
        """
        Intelligent, context-sensitive update command specifically for tools.
        Infers the action based on the arguments.
        """
        tool_name = args.name
        update_args = args.update_args
        tool = self.load(tool_name)
        if not tool:
            # self.load() already logs an error if not found
            return

        # --- Syntax: `... param ...` ---
        if 'param' in update_args:
            param_index = update_args.index('param')

            # Case: `... <cmd_name> param ...`
            if param_index == 1:
                cmd_name = update_args[0]
                param_args = update_args[2:]

                if not any(c.get("name") == cmd_name for c in tool.get("commands", [])):
                    log.error(f"Command '{cmd_name}' not found in '{tool_name}'.")
                    log.prompt(f"Create it first with: tool update {tool_name} command {cmd_name}")
                    return

                # Subcase: `... param <index> <new_value>`
                if len(param_args) >= 2:
                    try:
                        idx = int(param_args[0])
                        new_value = " ".join(param_args[1:])
                        self.update_param(tool_name, cmd_name, idx, new_value)
                        return
                    except ValueError:
                        pass  # Fall through to add param

                # Subcase: `... param <value_to_add>`
                param_to_add = " ".join(param_args)
                if param_to_add:
                    self.add_param(tool_name, cmd_name, param_to_add)
                    log.success(f"Parameter added to '{tool_name} {cmd_name}': {param_to_add}")
                else:
                    log.error(f"Parameter missing after '{cmd_name} param'.")
                return

            # Case: `... param ...` (implicit command)
            elif param_index == 0:
                cmd_name = tool_name  # implicit command name
                param_to_add = " ".join(update_args[1:])
                if not param_to_add:
                    log.error("Parameter fehlt nach 'param'.")
                    return
                if not any(c.get("name") == cmd_name for c in tool.get("commands", [])):
                    self.add_command(tool_name, cmd_name)
                self.add_param(tool_name, cmd_name, param_to_add)
                log.success(f"Parameter added to '{tool_name}': {param_to_add}")
                return

            else:  # 'param' at weird position
                log.error("Invalid syntax for 'param'.")
                return

        # --- Syntax: `... command ...` ---
        if 'command' in update_args:
            if len(update_args) == 2 and update_args[0] == 'command':
                cmd_name = update_args[1]
                self.add_command(tool_name, cmd_name)
                log.success(f"Command '{cmd_name}' added to '{tool_name}'.")
                log.prompt(f"Now add parameters with: tool update {tool_name} {cmd_name} param <param>")
                return
            else:
                log.error("Invalid syntax for 'command'.")
                log.prompt("Example: 'tool update <name> command <cmd_name>'")
                return

        # --- Syntax: `... <cmd_name> <field> <value>` (update command field) ---
        if len(update_args) >= 3:
            potential_cmd_name = update_args[0]
            cmd = next((c for c in tool.get("commands", []) if c.get("name") == potential_cmd_name), None)
            if cmd:
                # We found a command, so this is the syntax we're looking for.
                cmd_name = potential_cmd_name
                field_to_update = update_args[1]
                value_to_set_str = " ".join(update_args[2:])

                # Prevent direct modification of protected fields
                if field_to_update in ['name', 'params']:
                    log.error(f"Cannot update '{field_to_update}' directly. Use dedicated syntax like 'tool rename' or 'tool update ... param ...'.")
                    return

                value_to_set = value_to_set_str
                # Handle boolean conversion for special fields
                if field_to_update == 'execute_per_param':
                    if value_to_set_str.lower() in ['true', '1', 'on', 'yes']:
                        value_to_set = True
                    elif value_to_set_str.lower() in ['false', '0', 'off', 'no']:
                        value_to_set = False
                    else:
                        log.error(f"Invalid value for '{field_to_update}'. Please use 'true' or 'false'.")
                        return

                cmd[field_to_update] = value_to_set
                self.update(tool_name, "commands", tool["commands"])
                log.success(f"Field '{field_to_update}' in command '{cmd_name}' updated to '{value_to_set}'.")
                return

        # --- Fallback: `... <field> <value>` ---
        if len(update_args) >= 2:
            field, value_str = update_args[0], " ".join(update_args[1:])
            value = value_str # Default to string

            if field.lower() == 'name':
                self.rename(tool_name, value_str)
                return

            if field == 'path' and value_str.lower() == 'auto':
                self._find_and_set_path(tool_name)
                return

            # Handle boolean conversion for special top-level fields
            if field.lower() == 'sudo':
                if value_str.lower() in ['true', '1', 'on', 'yes']:
                    value = True
                elif value_str.lower() in ['false', '0', 'off', 'no']:
                    value = False
                else:
                    log.error(f"Invalid value for 'sudo'. Please use 'true' or 'false'.")
                    return

            if field == 'command_style':
                log.warning("The 'command_style' field is deprecated and no longer used.")
                return
            if field == 'commands':
                log.error("The 'commands' list cannot be updated directly.")
                log.prompt("Use 'tool update <name> command <cmd_name>' to edit a command.")
                return

            # --- NEW: Handle nested updates using dot notation ---
            if '.' in field:
                data = self.load(tool_name)
                if not data: return

                keys = field.split('.')
                current_level = data
                # Traverse/create path until the last key
                for key in keys[:-1]:
                    if key not in current_level or not isinstance(current_level[key], dict):
                        current_level[key] = {} # Create a dict if it doesn't exist or isn't a dict
                    current_level = current_level[key]
                
                # Set the value at the final key
                final_key = keys[-1]
                current_level[final_key] = value
                self._save_data(tool_name, data) # Use _save_data to write the whole modified object
                log.success(f"Tool '{tool_name}' nested field '{field}' updated -> {value}")
                return

            self.update(tool_name, field, value)
            log.success(f"Tool '{tool_name}' field '{field}' updated -> {value}")
        else:
            log.error("Invalid arguments for 'tool update'.")
            log.prompt("Use 'tool -h' for help.")

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
            log.error(f"{entity_type} '{args.name}' existiert bereits.")
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
        tool = self.load(tool_name)
        if not tool:
            log.error(f"Tool '{tool_name}' not found.")
            return None
        
        cmd = next((c for c in tool["commands"] if c["name"] == command_name), None)
        if not cmd:
            log.error(f"Command '{command_name}' not found in {tool_name}.")
            return None

        # Ensure the 'params' list exists.
        if "params" not in cmd:
            cmd["params"] = []

        # Always append new parameters for predictable behavior.
        # The "intelligent" logic of inserting before a target placeholder was
        # causing parameters to be added in reverse order. The user can
        # use 'tool reorder' for fine-tuning the order.
        cmd["params"].append(param)
            
        self._save_data(tool_name, tool)
        log.info(f"Param '{param}' added to {tool_name} {command_name}.")
        return cmd

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
                resolved_param_strings = [resolve_placeholders(p, session=session, tool_name=tool_name, command_name=cmd.get("name")) for p in cmd.get("params", [])]

                # 2. Split each resolved string into individual arguments.
                final_params = []
                for s in resolved_param_strings:
                    final_params.extend(shlex.split(s))
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
            top_level_table = Table(show_header=False, box=None, padding=(0, 2))
            top_level_table.add_column(style="bold blue", no_wrap=True)
            top_level_table.add_column(style="green")
            for key, value in data_to_show.items():
                top_level_table.add_row(key, str(value))
            
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