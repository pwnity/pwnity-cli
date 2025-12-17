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

# modules/managers/parser_manager.py
import os
import re, shlex
from .base_manager import JSONManager
from modules.services import log
from rich.table import Table
from rich.panel import Panel
import argparse

try:
    import questionary
except ImportError:
    questionary = None
from rich.text import Text

class ParserManager(JSONManager):
    def __init__(self):
        # --- FIX: Use the config system to get the directory path ---
        # This makes the manager respect the temporary test environment configuration
        # instead of always writing to the default 'data/parsers' directory.
        super().__init__("PARSERS")

    def dispatch(self, subcommand, args, cli_instance):
        """Overrides BaseManager's dispatch to handle the case where no subcommand is given."""
        if not subcommand:
            cli_instance.help_mgr.show_help_parser()
            return True
        
        # Let the parent class handle the actual dispatch to _cmd_* methods
        return super().dispatch(subcommand, args, cli_instance)

    def _get_entity_type(self):
        return "Parser"

    def _cmd_add(self, args, cli):
        """Handles 'parser add'."""
        name = args.name
        if self.exists(name):
            log.error(f"Parser '{name}' already exists.")
            return

        # Create a basic parser structure
        new_parser_data = {
            "name": name,
            "description": "A new custom parser.",
            "rules": []
        }
        self._save_data(name, new_parser_data)
        log.success(f"Parser '{name}' created successfully.")
        log.prompt(f"Add rules with: parser update {name} rule <rule_name>")

    def _cmd_update(self, args, cli):
        """Handles 'parser update'."""
        parser_name = args.name
        update_args = args.update_args
        parser_data = self.load(parser_name)
        if not parser_data:
            return

        if not update_args:
            log.error("No update arguments provided.")
            log.prompt("Use 'parser update -h' for help.")
            return

        # Syntax: `... description "new description"`
        if update_args[0] == 'description':
            new_desc = " ".join(update_args[1:])
            self.update(parser_name, 'description', new_desc)
            log.success(f"Description for parser '{parser_name}' updated.")
            return

        # Syntax: `... add-rule <rule_name>`
        if len(update_args) == 2 and update_args[0] == 'add-rule':
            rule_name = update_args[1]
            rules = parser_data.setdefault('rules', [])
            if any(r.get('name') == rule_name for r in rules):
                log.warning(f"Rule '{rule_name}' already exists in parser '{parser_name}'.")
                return
            rules.append({'name': rule_name, 'regex': '', 'exclude_patterns': []})
            self.update(parser_name, 'rules', rules)
            log.success(f"Added new rule '{rule_name}' to parser '{parser_name}'.")
            log.prompt(f"Set its pattern with: parser update {parser_name} {rule_name} regex \"...\"")
            return

        # Syntax: `... <rule_name> regex "..."` or `... <rule_name> exclude "..."`
        if len(update_args) >= 3:
            rule_name, field, value = update_args[0], update_args[1], " ".join(update_args[2:])
            
            rules = parser_data.get('rules', [])
            rule_to_update = next((r for r in rules if r.get('name') == rule_name), None)

            # If the rule doesn't exist, we can't proceed with setting a field.
            if not rule_to_update:
                log.error(f"Rule '{rule_name}' not found in parser '{parser_name}'.")
                return

            if field == 'regex':
                rule_to_update['regex'] = value
                self.update(parser_name, 'rules', rules)
                log.success(f"Regex for rule '{rule_name}' updated.")
            elif field == 'exclude':
                excludes = rule_to_update.setdefault('exclude_patterns', [])
                excludes.append(value)
                self.update(parser_name, 'rules', rules)
                log.success(f"Exclusion pattern added to rule '{rule_name}'.")
            else:
                log.error(f"Invalid field '{field}'. Use 'regex' or 'exclude'.")
            return

        log.error("Invalid syntax for 'parser update'. Use 'parser update -h' for help.")

    def _cmd_delete(self, args, cli):
        """Handles 'parser delete'."""
        parser_name = args.name
        delete_args = args.delete_args
        parser_data = self.load(parser_name)
        if not parser_data:
            return

        if not delete_args:
            log.error("No delete arguments provided. To delete the entire parser, use 'parser destroy'.")
            log.prompt("Use 'parser delete -h' for help.")
            return

        # Syntax: `... description`
        if len(delete_args) == 1 and delete_args[0] == 'description':
            if self.delete(parser_name, 'description'):
                log.success(f"Description field deleted from parser '{parser_name}'.")
            return

        # --- NEW: Simplified rule deletion ---
        # Syntax: `... <rule_name>` (deletes the whole rule)
        if len(delete_args) == 1:
            rule_name_to_delete = delete_args[0]
            rules = parser_data.get('rules', [])
            # Check if it's a rule name and not 'description'
            if any(r.get('name') == rule_name_to_delete for r in rules):
                original_len = len(rules)
                rules = [r for r in rules if r.get('name') != rule_name_to_delete]
                if len(rules) < original_len:
                    self.update(parser_name, 'rules', rules)
                    log.success(f"Rule '{rule_name_to_delete}' deleted from parser '{parser_name}'.")
                return

        # Syntax: `... <rule_name> exclude <index>` (deletes an exclusion pattern)
        if len(delete_args) == 3 and delete_args[1] == 'exclude':
            rule_name, _, index_str = delete_args
            rules = parser_data.get('rules', [])
            rule_to_update = next((r for r in rules if r.get('name') == rule_name), None)
            if not rule_to_update:
                log.error(f"Rule '{rule_name}' not found.")
                return
            
            excludes = rule_to_update.get('exclude_patterns', [])
            try:
                # Extract only the number from formats like "1" or "1(some_value)"
                index_num_str = re.match(r'^(\d+)', index_str)
                if not index_num_str: raise ValueError("Index is not a number.")
                index = int(index_num_str.group(1)) - 1 # 1-based index for user
                if 0 <= index < len(excludes):
                    removed = excludes.pop(index)
                    self.update(parser_name, 'rules', rules)
                    log.success(f"Exclusion pattern #{index+1} ('{removed}') deleted from rule '{rule_name}'.")
                else:
                    log.error(f"Invalid index. There are only {len(excludes)} exclusion patterns.")
            except ValueError:
                log.error("Invalid index provided. Must be a number.")
            return

        log.error("Invalid syntax for 'parser delete'. Use 'parser delete -h' for help.")

    def apply_to_text(self, parser_name, text_content):
        """
        Applies a parser to a raw string of text.
        This is a variant of parse_text used by the Web UI's Regex Tester.
        It doesn't log to the console to keep the API response clean.
        """
        return self._parse_text_internal(parser_name, text_content, silent=True)

    def parse_text(self, parser_name, text_content):
        """
        Parses the given text content using the rules of the specified parser.
        Returns a dictionary of findings.
        """
        parser_data = self.load(parser_name)
        if not parser_data:
            return None
        log.info(f"Applying parser '{parser_data.get('name', parser_name)}'...")
        findings = self._parse_text_internal(parser_name, text_content, silent=False)
        if not findings:
            log.info("No matches found for any rule in the parser.")
        return findings

    def _parse_text_internal(self, parser_name, text_content, silent=False):
        """Internal parsing logic that can be run with or without console logging."""
        parser_data = self.load(parser_name)
        if not parser_data:
            if not silent: log.error(f"Parser '{parser_name}' not found.")
            return None
        findings = {}
        for rule in parser_data.get("rules", []):
            rule_name = rule.get("name")
            pattern = rule.get("regex") # Changed from 'pattern' to 'regex' for consistency
            exclude_patterns = rule.get("exclude_patterns", [])
            if not rule_name or not pattern:
                continue
            
            try:
                # Find all unique matches
                # This might return a list of strings or a list of tuples.
                raw_matches = re.findall(pattern, text_content, re.MULTILINE)

                # Process matches to ensure they are all strings for rendering.
                # If a match is a tuple (from multiple capture groups), join its parts.
                processed_matches = []
                for match in raw_matches:
                    match_str = ""
                    if isinstance(match, tuple):
                        # Join all non-empty parts of the tuple to form a single string.
                        match_str = "".join(filter(None, match))
                    else:
                        # It's already a string.
                        match_str = match

                    # Check against exclude patterns
                    is_excluded = False
                    for exclude_pattern in exclude_patterns:
                        # Using re.search to find the pattern anywhere in the matched string.
                        # Using anchors (^, $) in the exclude pattern YAML is recommended for exact matches.
                        if re.search(exclude_pattern, match_str):
                            is_excluded = True
                            break # No need to check other exclude patterns
                    
                    if not is_excluded:
                        processed_matches.append(match_str)

                # Get the final list of unique, sorted matches.
                matches = sorted(list(set(processed_matches)))
                if matches:
                    if not silent: log.success(f"Found {len(matches)} unique matches for rule '{rule_name}'.")
                    findings[rule_name] = matches
            except re.error as e:
                if not silent: log.error(f"Regex error in rule '{rule_name}': {e}")

        return findings

    def _cmd_apply(self, args, cli):
        """Applies a parser to a logbook entry and saves findings to the report."""
        logbook_id = args.logbook_id
        # The manager's load method expects a string for the name/ID.
        log_data = cli.logbook_mgr.load(str(logbook_id))
        if not log_data:
            log.error(f"Logbook entry with ID {logbook_id} not found.")
            return

        text_content = log_data.get('output') or ''

        if not text_content:
            log.warning(f"Logbook entry #{logbook_id} has no output to parse.")
            return

        findings = self.parse_text(args.name, text_content)

        if findings:
            # Display all findings first so the user can see what was found
            cli.display_mgr.display_findings(findings, title="Parser Results")

            if not cli.session.report:
                log.error("No report loaded. Findings were found but cannot be saved.")
                log.prompt("Create and load a report to save findings from future parser runs:")
                log.prompt("  report add my-report")
                log.prompt("  report load my-report")
                return

            # --- Re-implement interactive selection ---
            if not questionary:
                log.error("Optional dependency 'questionary' not found. Interactive selection is disabled.")
                log.error("For a better experience, please install with: pip install questionary")
                log.prompt("Saving all findings to the report.")
                findings_to_save = findings
            else:
                # Flatten findings for individual selection
                flat_findings = []
                for category, matches in findings.items():
                    for match in matches:
                        flat_findings.append({'match': match, 'category': category})
                
                if not flat_findings:
                    return

                cli.console.print() # Spacer
                max_match_len = max(len(item['match']) for item in flat_findings) if flat_findings else 0

                choices = []
                for item in flat_findings:
                    match_text = item['match']
                    category_text = item['category']
                    separator = " " + "." * (max_match_len - len(match_text) + 2) + " "
                    formatted_title = [
                        ("class:match", match_text),
                        ("class:separator", separator),
                        ("class:category", f"({category_text})")
                    ]
                    choices.append(
                        questionary.Choice(
                            title=formatted_title,
                            value=item,
                            checked=True
                        )
                    )

                selected_items = questionary.checkbox(
                    "Select findings to add to the report:",
                    choices=choices,
                    style=questionary.Style([
                        ('selected', 'fg:#673ab7 bold'), ('pointer', 'fg:#673ab7 bold bg:#eadcfc'),
                        ('highlighted', 'fg:#673ab7 bold bg:#eadcfc'),
                        ('text', 'ansidefault'), ('instruction', 'fg:#a9a9a9 italic'),
                        ('match', 'fg:ansigreen bold'), ('separator', 'fg:ansibrightblack'),
                        ('category', 'fg:ansicyan')
                    ]),
                    instruction=" (Press <space> to deselect, <a> to toggle all, <i> to invert, <enter> to confirm)"
                ).ask()

                if selected_items is None:
                    log.info("Selection cancelled. No findings will be added to the report.")
                    return
                
                findings_to_save = {}
                for item in selected_items:
                    findings_to_save.setdefault(item['category'], []).append(item['match'])

            if findings_to_save:
                cli.report_mgr.add_findings(
                    report_name=cli.session.report, source_log_id=logbook_id,
                    parser_name=args.name, target_name=cli.session.target,
                    new_findings=findings_to_save
                )
        else:
            log.info("Parser finished with no findings.")

    def _cmd_show(self, args, cli):
        """Handles 'parser show'."""
        name = args.name
        parser_data = self.load(name)
        if not parser_data:
            log.error(f"Parser '{name}' not found.")
            return
        
        from rich.columns import Columns
        from rich.console import Group

        rule_panels = []
        for rule in parser_data.get("rules", []):
            rule_name = rule.get("name", "Unnamed Rule")
            regex_pattern = rule.get("regex", "[dim]Not set[/dim]")
            exclude_patterns = rule.get('exclude_patterns', [])

            details_table = Table(show_header=False, box=None, padding=(0, 1))
            details_table.add_column(style="bold blue", no_wrap=True, width=12)
            details_table.add_column(style="default")

            details_table.add_row("Regex", Text(regex_pattern, overflow="fold", style="green"))

            if exclude_patterns:
                # Add a separator line for better visual distinction
                details_table.add_row("", "") # Empty row for spacing
                details_table.add_row("[dim]Exclusions[/dim]", Text("\n".join(f"{i}: {p}" for i, p in enumerate(exclude_patterns, 1)), style="red"))

            rule_panel = Panel(details_table, title=f"[cyan]{rule_name}[/cyan]", border_style="dim", expand=True)
            rule_panels.append(rule_panel)

        if not rule_panels:
            content = Panel("[dim]No rules defined for this parser.[/dim]", border_style="dim")
        else:
            # Arrange rule panels in columns for better readability
            content = Columns(rule_panels, equal=True, expand=True)

        main_panel = Panel(
            content,
            title=f"Parser: [bold]{parser_data.get('name', name)}[/bold]",
            subtitle=f"[dim]{parser_data.get('description', '')}[/dim]",
            border_style="magenta",
            expand=True
        )
        cli.console.print(main_panel)

    def _cmd_export(self, args, cli):
        """Generates the pwnity commands to reconstruct a parser."""
        name = args.name
        data = self.load(name)
        if not data:
            return

        commands = [f"parser add {name}"]
        if 'description' in data:
            commands.append(f"parser update {name} description {shlex.quote(data['description'])}")
        
        for rule in data.get('rules', []):
            rule_name = rule.get('name')
            commands.append(f"parser update {name} add-rule {rule_name}")
            if rule.get('regex'):
                commands.append(f"parser update {name} {rule_name} regex {shlex.quote(rule['regex'])}")
            for ex_pattern in rule.get('exclude_patterns', []):
                commands.append(f"parser update {name} {rule_name} exclude {shlex.quote(ex_pattern)}")

        log.header(f"Export for Parser '{name}'")
        cli.poutput("\n".join(commands))