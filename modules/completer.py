# modules/completer.py
import shlex
from cmd2 import CompletionItem
from . import functions as pwn_functions

class Completer:
    """
    A dedicated class to handle all command completion logic for the pwnity shell.
    This centralizes completion logic, making it easier to manage and test.
    """
    def __init__(self, cli_instance):
        """
        Initializes the Completer with a reference to the main CLI application instance,
        which it uses to access managers and session state.
        """
        self.cli = cli_instance

    def _basic_manager_completion(self, text, line, begidx, endidx, manager, subcommands):
        """A generic completion helper for manager-based commands."""
        try:
            tokens = shlex.split(line[:begidx])
        except ValueError:
            tokens = line[:begidx].split()

        if len(tokens) == 1:  # Completing the subcommand
            return [s for s in subcommands if s.startswith(text)]
        
        if len(tokens) == 2:  # Completing the item name
            return [item for item in manager.list_all() if item.startswith(text)]

        return []

    def _filter_completions(self, text, suggestions):
        """
        A robust filter that handles both lists of strings and lists of CompletionItem objects.
        """
        filtered = []
        # If the user is typing a nested path, we should only suggest direct children.
        # For example, if text is "http_headers.", we should suggest "http_headers.Connection",
        # but not "http_headers.Connection.some_sub_field".
        is_nested_path = '.' in text and text.endswith('.')

        for s in suggestions:
            # --- FINAL, ROBUST FIX for cmd2 version incompatibility ---
            # The CompletionItem API changed across cmd2 versions.
            # Older versions use '.text', newer versions use '.completion'.
            # This code now robustly handles both cases.
            if isinstance(s, CompletionItem):
                completion_text = getattr(s, 'completion', getattr(s, 'text', ''))
            else:
                completion_text = s # It's just a string

            if is_nested_path and completion_text.startswith(text) and text.count('.') == completion_text.count('.'):
                continue # Skip suggestions that are not direct children of the nested path

            if completion_text.startswith(text):
                filtered.append(s)
        return filtered

    def _generate_paths_recursively(self, data, current_path="", suggestions=None):
        """
        Recursively traverses a dictionary or list to generate all possible dot-notation paths
        for autocompletion.
        """
        if suggestions is None:
            suggestions = set()

        if isinstance(data, dict):
            for key, value in data.items():
                new_path = f"{current_path}.{key}" if current_path else key
                suggestions.add(new_path)
                self._generate_paths_recursively(value, new_path, suggestions)
        # We don't recurse into lists for 'update' completion, as path-based updates on list elements are not supported.
        return suggestions

    def _get_value_from_path(self, data, path):
        """
        Retrieves a value from a nested dictionary using a dot-notation path.
        """
        try:
            keys = path.split('.')
            current = data
            for key in keys:
                if isinstance(current, dict):
                    current = current[key]
                else:
                    return None # Path is invalid
            return current
        except (KeyError, TypeError):
            return None

    def _create_completion_items_from_paths(self, data, paths):
        """Creates CompletionItem objects with values as descriptions."""
        for path in sorted(list(paths)):
            value = self._get_value_from_path(data, path)
            yield CompletionItem(path, description=f"({value})") if value is not None and not isinstance(value, (dict, list)) else path

    def complete_tool(self, text, line, begidx, endidx):
        """Autocompletion for the 'tool' command."""
        try:
            tokens = shlex.split(line[:begidx])
        except ValueError:
            tokens = line[:begidx].split()
        num_tokens = len(tokens)

        # 1. Complete subcommand (add, list, update, etc.)
        if num_tokens == 1:
            subcommands = ['add', 'list', 'update', 'delete', 'reorder', 'destroy', 'load', 'show', 'export', 'help']
            return [s for s in subcommands if s.startswith(text)]

        # 2. Complete tool name for most subcommands
        if num_tokens == 2:
            if tokens[1] in ['update', 'delete', 'reorder', 'destroy', 'load', 'show', 'export']:
                return [t for t in self.cli.tool_mgr.list_all() if t.startswith(text)]

        # 3. Context-sensitive completion for 'tool update <name> ...'
        if num_tokens == 3 and tokens[1] == 'update':
            tool_name = tokens[2]
            tool_data = self.cli.tool_mgr.load(tool_name)
            if not tool_data:
                return []

            # --- FIX: Dynamically add all top-level keys from the tool's data to the suggestions ---
            # The previous implementation had a hardcoded list.
            base_suggestions = ['path', 'sudo', 'name', 'command']
            # --- NEW: Use recursive helper to get all nested paths ---
            dynamic_suggestions = self._generate_paths_recursively(tool_data)
            command_names = [cmd.get('name') for cmd in tool_data.get("commands", []) if cmd.get('name')]
            # Combine all, use a set to remove duplicates, then convert back to a sorted list.
            all_suggestions = set(base_suggestions + command_names) | dynamic_suggestions
            # --- FIX: Exclude 'commands' (plural) as it cannot be directly modified. ---
            # The user should use 'command' (singular) to interact with specific commands.
            filtered_suggestions = [s for s in all_suggestions if s != 'commands']
            return self._filter_completions(text, sorted(filtered_suggestions))

        # --- NEW: Context-sensitive completion for 'tool delete <name> ...' ---
        if num_tokens == 3 and tokens[1] == 'delete':
            tool_name = tokens[2]
            tool_data = self.cli.tool_mgr.load(tool_name)
            if not tool_data:
                return []

            # Suggestions should include top-level fields and command names.
            base_suggestions = ['path', 'sudo', 'name', 'command']
            dynamic_suggestions = self._generate_paths_recursively(tool_data)
            command_names = [cmd.get('name') for cmd in tool_data.get("commands", []) if cmd.get('name')]
            
            all_suggestions = set(base_suggestions + command_names) | dynamic_suggestions
            # --- FIX: Exclude 'commands' (plural) for the same reason as in 'update'. ---
            filtered_suggestions = [s for s in all_suggestions if s != 'commands']
            return self._filter_completions(text, sorted(filtered_suggestions))

        # 4. Context-sensitive completion for 'tool update <name> <command> ...'
        if num_tokens == 4 and tokens[1] == 'update':
            tool_name = tokens[2]
            command_name = tokens[3]
            tool_data = self.cli.tool_mgr.load(tool_name)
            if not tool_data:
                return []

            # Check if the third token is a valid command for the tool
            is_command = any(cmd.get('name') == command_name for cmd in tool_data.get("commands", []))
            if is_command:
                # Suggest actions for a command: add a parameter or update a command-level field
                suggestions = ['param', 'execute_per_param']
                return self._filter_completions(text, suggestions)

        # --- NEW: Context-sensitive completion for 'tool delete <name> <command> ...' ---
        if num_tokens == 4 and tokens[1] == 'delete':
            tool_name = tokens[2]
            command_name = tokens[3]
            tool_data = self.cli.tool_mgr.load(tool_name)
            if not tool_data:
                return []

            # Check if the third token is a valid command for the tool
            is_command = any(cmd.get('name') == command_name for cmd in tool_data.get("commands", []))
            if is_command:
                # Suggest 'param' to delete a parameter from the command
                return self._filter_completions(text, ['param'])

        # 5. --- NEW: Suggest parameter indices for 'tool update <name> <cmd> param <TAB>' ---
        if num_tokens == 5 and tokens[1] == 'update' and tokens[4] == 'param':
            tool_name = tokens[2]
            command_name = tokens[3]
            tool_data = self.cli.tool_mgr.load(tool_name)
            if not tool_data:
                return []

            command = next((c for c in tool_data.get("commands", []) if c.get("name") == command_name), None)
            if not command or not command.get("params"):
                return []

            # Create CompletionItem suggestions for each parameter index.
            # The completion value is the index (1-based), and the description is the parameter's value.
            # --- FIX: Directly format the string for display, as CompletionItem description is not always shown. ---
            # This ensures the value is visible in the completion suggestions.
            suggestions = [f"{i} ({(param_value[:75] + '...') if len(param_value) > 75 else param_value})"
                           for i, param_value in enumerate(command.get("params", []), 1)]
            return self._filter_completions(text, suggestions)

        # 6. --- NEW: Suggest parameter indices for 'tool delete <name> <cmd> param <TAB>' ---
        if num_tokens == 5 and tokens[1] == 'delete' and tokens[4] == 'param':
            tool_name = tokens[2]
            command_name = tokens[3]
            tool_data = self.cli.tool_mgr.load(tool_name)
            if not tool_data:
                return []

            command = next((c for c in tool_data.get("commands", []) if c.get("name") == command_name), None)
            if not command or not command.get("params"):
                return []

            # --- FIX: Use direct string formatting for consistency with 'update' completion. ---
            suggestions = [f"{i} ({(param_value[:75] + '...') if len(param_value) > 75 else param_value})"
                           for i, param_value in enumerate(command.get("params", []), 1)]
            return self._filter_completions(text, suggestions)

        return []

    def complete_target(self, text, line, begidx, endidx):
        """Autocompletion for the 'target' command."""
        try:
            tokens = shlex.split(line[:begidx])
        except ValueError:
            tokens = line[:begidx].split()
        num_tokens = len(tokens)

        # 1. Complete subcommand (add, list, update, etc.)
        if num_tokens == 1:
            subcommands = ['add', 'list', 'update', 'delete', 'destroy', 'load', 'show', 'gather', 'fork-domain', 'export', 'help']
            return [s for s in subcommands if s.startswith(text)]

        # 2. Complete target name for most subcommands
        if num_tokens == 2:
            if tokens[1] in ['update', 'delete', 'destroy', 'load', 'show', 'gather', 'fork-domain', 'export']:
                return [t for t in self.cli.target_mgr.list_all() if t.startswith(text)]

        # 3. Context-sensitive completion for 'target update <name> ...' or 'target delete <name> ...'
        if num_tokens == 3 and tokens[1] in ['update', 'delete', 'show']:
            target_name = tokens[2]
            target_data = self.cli.target_mgr.load(target_name)
            if not target_data:
                return []
            # --- FIX: Dynamically add all top-level keys from the target's data ---
            # The previous implementation had a hardcoded list.
            base_suggestions = ['url'] # Keep 'url' as a default suggestion
            # --- NEW: Use recursive helper to get all nested paths ---
            dynamic_suggestions = self._generate_paths_recursively(target_data)
            all_suggestions = list(self._create_completion_items_from_paths(target_data, dynamic_suggestions)) + base_suggestions

            # --- FINAL FIX for nested path completion ---
            # This correctly filters suggestions whether the text is a partial top-level field or a partial nested path.
            return [s for s in all_suggestions if getattr(s, 'completion', s).startswith(text)]

        return []

    def complete_preset(self, text, line, begidx, endidx):
        """Autocompletion for the 'preset' command."""
        try:
            tokens = shlex.split(line[:begidx])
        except ValueError:
            tokens = line[:begidx].split()
        num_tokens = len(tokens)

        # 1. Complete subcommand
        if num_tokens == 1:
            subcommands = ['add', 'list', 'update', 'delete', 'destroy', 'load', 'show', 'save', 'export', 'help']
            return [s for s in subcommands if s.startswith(text)]

        # 2. Complete preset name for most subcommands
        if num_tokens == 2:
            if tokens[1] in ['update', 'delete', 'destroy', 'load', 'show', 'export']:
                return [p for p in self.cli.preset_mgr.list_all() if p.startswith(text)]

        # 3. Context-sensitive completion for 'preset update <name> ...'
        if num_tokens == 3 and tokens[1] == 'update':
            suggestions = ['target', 'tool', 'wordlist', 'report']
            return [s for s in suggestions if s.startswith(text)]

        # 4. Context-sensitive completion for 'preset update <name> <field> ...'
        if num_tokens == 4 and tokens[1] == 'update':
            field = tokens[3]
            if field == 'target':
                return [t for t in self.cli.target_mgr.list_all() if t.startswith(text)]
            elif field == 'tool':
                return [t for t in self.cli.tool_mgr.list_all() if t.startswith(text)]
            elif field == 'wordlist':
                return [w for w in self.cli.wordlist_mgr.list_all() if w.startswith(text)]
            elif field == 'report':
                return [r for r in self.cli.report_mgr.list_all() if r.startswith(text)]

        return []

    def complete_wordlist(self, text, line, begidx, endidx):
        """Autocompletion for the 'wordlist' command."""
        try:
            tokens = shlex.split(line[:begidx])
        except ValueError:
            tokens = line[:begidx].split()
        num_tokens = len(tokens)

        # 1. Complete subcommand
        if num_tokens == 1:
            subcommands = ['add', 'list', 'update', 'delete', 'destroy', 'load', 'show', 'rename', 'export', 'help']
            return [s for s in subcommands if s.startswith(text)]

        # 2. Complete wordlist name for most subcommands
        if num_tokens == 2:
            if tokens[1] in ['update', 'delete', 'destroy', 'load', 'show', 'rename', 'export']:
                return [w for w in self.cli.wordlist_mgr.list_all() if w.startswith(text)]

        # 3. Context-sensitive completion for 'wordlist update <name> ...' or 'wordlist delete <name> ...'
        if num_tokens == 3 and tokens[1] in ['update', 'delete']:
            # A wordlist object primarily has a 'path' field that can be modified.
            return [s for s in ['path'] if s.startswith(text)]

        return []

    def complete_help(self, text, line, begidx, endidx):
        """Autocompletion for the help command, including subcommands."""
        try:
            tokens = shlex.split(line[:begidx])
        except ValueError:
            tokens = line[:begidx].split()

        if len(tokens) == 1:
            all_commands = self.cli.get_all_commands()
            return [c for c in all_commands if c.startswith(text)]
        
        elif len(tokens) == 2:
            command_name = tokens[1]
            parser = getattr(self.cli, f"{command_name}_parser", None)
            if not parser: return []

            subparsers_action = next((action for action in parser._actions if isinstance(action, self.cli.argparse._SubParsersAction)), None)
            if not subparsers_action or not subparsers_action.choices: return []

            subcommand_names = list(subparsers_action.choices.keys())
            for sub_parser in subparsers_action.choices.values():
                subcommand_names.extend(getattr(sub_parser, 'aliases', []))

            return sorted([s for s in subcommand_names if s.startswith(text)])
        return []

    def complete_manual(self, text, line, begidx, endidx):
        topics = self.cli.manual_mgr.list_topics()
        return [t for t in topics if t.startswith(text)]

    def complete_parser(self, text, line, begidx, endidx):
        try:
            tokens = shlex.split(line[:begidx])
        except ValueError: tokens = line[:begidx].split()
        num_tokens = len(tokens)

        if num_tokens == 1:
            return [s for s in ['add', 'list', 'show', 'apply', 'delete', 'destroy', 'rename', 'update', 'export'] if s.startswith(text)]
        if num_tokens == 2:
            if tokens[1] in ['show', 'apply', 'delete', 'destroy', 'rename', 'update', 'export']:
                return [p for p in self.cli.parser_mgr.list_all() if p.startswith(text)]
        if num_tokens == 3:
            if tokens[1] == 'apply':
                return [str(l_id) for l_id in self.cli.logbook_mgr.list_all() if str(l_id).startswith(text)]
            if tokens[1] in ['update', 'delete']:
                parser_data = self.cli.parser_mgr.load(tokens[2])
                if not parser_data: return []
                rule_names = [r.get('name') for r in parser_data.get('rules', [])]
                suggestions = ['description', 'add-rule'] + rule_names
                return [s for s in suggestions if s.startswith(text)]
        if num_tokens == 4:
            if tokens[1] == 'update' and tokens[3] != 'add-rule':
                return [s for s in ['regex', 'exclude'] if s.startswith(text)]
            if tokens[1] == 'delete':
                return [s for s in ['exclude'] if s.startswith(text)]
        if num_tokens == 5:
            if tokens[1] == 'delete' and tokens[3] == 'exclude':
                parser_data = self.cli.parser_mgr.load(tokens[2])
                if not parser_data: return []
                rule = next((r for r in parser_data.get('rules', []) if r.get('name') == tokens[3]), None)
                if not rule: return []
                exclude_patterns = rule.get('exclude_patterns', [])
                suggestions = [CompletionItem(str(i), description=f"({(p[:40] + '...') if len(p) > 40 else p})") for i, p in enumerate(exclude_patterns, 1)]
                return [s for s in suggestions if s.startswith(text)]
        return []

    def complete_logbook(self, text, line, begidx, endidx):
        return self._basic_manager_completion(text, line, begidx, endidx, self.cli.logbook_mgr, ['list', 'show'])

    def complete_report(self, text, line, begidx, endidx):
        try:
            tokens = shlex.split(line[:begidx])
        except ValueError: tokens = line[:begidx].split()
        num_tokens = len(tokens)

        if num_tokens == 1:
            return [s for s in ['add', 'load', 'unload', 'list', 'show', 'rename', 'destroy', 'delete', 'export', 'reverse', 'render', 'view', 'help'] if s.startswith(text)]
        
        if num_tokens == 2:
            # If 'view' is the subcommand and a report is loaded, prioritize suggesting files from it.
            if tokens[1] == 'view':
                if self.cli.session.report: # If a report is loaded, suggest its files.
                    files = self.cli.report_mgr.list_files(self.cli.session.report)
                    return [f for f in files if f.startswith(text)] if files else []
                # If no report is loaded, 'view' expects a report name next.
                return [r_name for r_name in self.cli.report_mgr.list_all() if r_name.startswith(text)]
            # For other commands, suggest report names.
            if tokens[1] in ['load', 'show', 'rename', 'destroy', 'delete', 'export', 'reverse', 'render']:
                return [r_name for r_name in self.cli.report_mgr.list_all() if r_name.startswith(text)]

        if num_tokens == 3 and tokens[1] == 'view':
            # Autocomplete files for 'report view <report_name> <file_to_complete>'
            report_name_arg = tokens[2]
            files = self.cli.report_mgr.list_files(report_name_arg)
            return [f for f in files if f.startswith(text)] if files else []

        return []

    def complete_revshell(self, text, line, begidx, endidx):
        try:
            tokens = shlex.split(line[:begidx])
        except ValueError: tokens = line[:begidx].split()
        if len(tokens) == 1:
            return [lang for lang in self.cli.revshell_mgr.list_languages() if lang.startswith(text)]
        return []

    def complete_heartbeat(self, text, line, begidx, endidx):
        try:
            tokens = shlex.split(line[:begidx])
        except ValueError: tokens = line[:begidx].split()
        num_tokens = len(tokens)

        if num_tokens == 1:
            return [s for s in ['start', 'stop', 'show', 'list', 'destroy'] if s.startswith(text)]
        if num_tokens == 2 and tokens[1] in ['stop', 'show', 'destroy']:
            return [t for t in self.cli.heartbeat_mgr.list_all() if t.startswith(text)]
        if num_tokens > 1 and tokens[1] == 'start':
            used_options = {tokens[i] for i in range(2, num_tokens) if (i - 2) % 2 == 0}
            if (num_tokens - 2) % 2 == 0:
                available_options = ['delaymin', 'delaymax', 'timelimit']
                return [opt for opt in available_options if opt not in used_options and opt.startswith(text)]
        return []

    def complete_library(self, text, line, begidx, endidx):
        import argparse # Import the argparse module
        try:
            tokens = shlex.split(line[:begidx])
        except ValueError: tokens = line[:begidx].split()
        num_tokens = len(tokens)

        subparsers_action = next((action for action in self.cli.library_parser._actions if isinstance(action, argparse._SubParsersAction)), None)
        if not subparsers_action: return []
        subcommand_names = list(subparsers_action.choices.keys())
        for sub_parser in subparsers_action.choices.values():
            subcommand_names.extend(getattr(sub_parser, 'aliases', []))

        if num_tokens == 1:
            # Provide suggestions for the subcommand itself
            return [s for s in sorted(list(set(subcommand_names))) if s.startswith(text)]

        if num_tokens == 2:
            # Provide suggestions for the entity name for commands that require it
            if tokens[1] in ['show', 'rename', 'update', 'delete', 'destroy', 'open', 'export', 'reverse', 'check', 'add']:
                # Use the new method to get sanitized names for completion
                completions = self.cli.library_mgr.list_sanitized_names()
                if tokens[1] == 'check': completions.append('all')
                return [t for t in completions if t.startswith(text)]

        return []

    def complete_workflow(self, text, line, begidx, endidx):
        return self._basic_manager_completion(text, line, begidx, endidx, self.cli.workflow_mgr, ['add', 'list', 'show', 'rename', 'destroy', 'delete', 'run'])

    def complete_config(self, text, line, begidx, endidx):
        try:
            tokens = shlex.split(line[:begidx])
        except ValueError: tokens = line[:begidx].split()
        num_tokens = len(tokens)

        if num_tokens == 1:
            return [s for s in ['list', 'get', 'set'] if s.startswith(text)]
        if num_tokens == 2 and tokens[1] in ['get', 'set']:
            all_keys = []
            for section, settings in self.cli.config.get_all_data().items():
                if isinstance(settings, dict):
                    for key in settings:
                        all_keys.append(f"{section}.{key}")
            return [k for k in all_keys if k.startswith(text)]
        return []

    def complete_print(self, text, line, begidx, endidx):
        """
        Provides autocompletion for the 'print' command, suggesting placeholders
        and functions.
        """
        # Get all available placeholders from the utility manager
        placeholders = self.cli.utility_mgr.get_all_placeholders(self.cli.session)
        
        # Get all available functions and append '()'
        functions = [f"{name}()" for name in pwn_functions.FUNCTION_REGISTRY.keys()]

        # Combine placeholders and functions for suggestions
        suggestions = placeholders + functions

        # Tell cmd2 not to add a space after completing a function.
        # This is the compatible way for older cmd2 versions.
        self.cli.allow_appended_space = False

        # The text to complete might already have a '$'
        if text.startswith('$'):
            return [s for s in placeholders if s.startswith(text)]
        
        # If we are inside a function call, e.g., print b64encode($tar...)
        # we should suggest placeholders.
        line_before_cursor = line[:begidx]
        if '(' in line_before_cursor:
            # Find the start of the current argument
            last_paren = line_before_cursor.rfind('(')
            last_comma = line_before_cursor.rfind(',')
            arg_start = max(last_paren, last_comma) + 1
            
            # Check if the argument starts with '$'
            if line[arg_start:].strip().startswith('$'):
                 return [s for s in placeholders if s.startswith(text)]

        # Default case: suggest anything that matches
        return [s for s in suggestions if s.startswith(text)]

    def complete_identify(self, text, line, begidx, endidx):
        """
        Provides autocompletion for the 'identify' command.
        Currently, it does not offer any suggestions.
        """
        # No specific completions for a hash string.
        return []

    def complete_session(self, text, line, begidx, endidx):
        """Autocompletion for the 'session' command."""
        try:
            tokens = shlex.split(line[:begidx])
        except ValueError:
            tokens = line[:begidx].split()
        num_tokens = len(tokens)

        # 1. Complete subcommand
        if num_tokens == 1:
            subcommands = ['new', 'switch', 'list', 'destroy', 'export', 'show', 'help']
            return [s for s in subcommands if s.startswith(text)]

        # 2. Complete session name for 'switch' and 'destroy'
        if num_tokens == 2 and tokens[1] in ['switch', 'destroy']:
            return [s_name for s_name in self.cli.session_mgr.list() if s_name.startswith(text)]

    def _get_pwn_completions(self, text, line, begidx, endidx):
        if not self.cli.session or not self.cli.session.tool: return []
        tool_data = self.cli.tool_mgr.load(self.cli.session.tool)
        tool_commands = [cmd.get('name') for cmd in tool_data.get("commands", []) if cmd.get('name')]

        try:
            tokens = shlex.split(line[:endidx])
        except ValueError: tokens = line[:endidx].split()
        args = tokens[1:]

        suggestions = []

        # If no arguments have been typed yet, or the first argument is not a full command,
        # suggest tool commands.
        if not args or (len(args) >= 1 and args[0] not in tool_commands):
            suggestions.extend(tool_commands)
        
        # If a tool command has been identified as the first argument,
        # then suggest 'now' and 'bg' (if they haven't been used yet).
        if args and args[0] in tool_commands:
            if 'now' not in args: suggestions.append('now')
            if 'bg' not in args: suggestions.append('bg')
        
        return [s for s in suggestions if s.startswith(text)]

    def complete_pwn(self, text, line, begidx, endidx):
        return self._get_pwn_completions(text, line, begidx, endidx)

    def complete_run(self, text, line, begidx, endidx):
        return self._get_pwn_completions(text, line, begidx, endidx)