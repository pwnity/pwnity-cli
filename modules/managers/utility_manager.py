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

# modules/managers/utility_manager.py
from .base_manager import BaseManager
from ..services import log
from .. import placeholders
from .. import functions as pwn_functions

class UtilityManager(BaseManager):
    def __init__(self, cli_instance):
        self.cli = cli_instance

    def _get_entity_type(self):
        return "Utility"

    def get_all_placeholders(self, session) -> list[str]:
        """
        Gathers all possible placeholders from the current session state.
        This is used by the completer for the 'print' command.
        """
        if not session:
            return []

        cli = self.cli
        data_map = {
            'target': cli.target_mgr.load(session.target),
            'tool': cli.tool_mgr.load(session.tool),
            'wordlist': cli.wordlist_mgr.load(session.wordlist),
            'profile': cli.profile_mgr.load(),
            'proxy': cli.proxy_mgr.get_placeholder_config(session),
            'report': self._get_report_data_for_placeholders(cli)
        }

        placeholders = []
        for prefix, data in data_map.items():
            if data:
                self._generate_placeholders_recursively(placeholders, data, f"${prefix}")
        
        return sorted(placeholders)

    def _generate_placeholders_recursively(self, placeholder_list: list, data, current_path: str):
        """Recursively builds a flat list of placeholder strings."""
        if isinstance(data, dict):
            for key, value in data.items():
                new_path = f"{current_path}.{key}"
                if isinstance(value, (dict, list)):
                    self._generate_placeholders_recursively(placeholder_list, value, new_path)
                else:
                    placeholder_list.append(new_path)
        elif isinstance(data, list):
            for i, item in enumerate(data):
                new_path = f"{current_path}.{i}"
                self._generate_placeholders_recursively(placeholder_list, item, new_path)

    def _get_report_data_for_placeholders(self, cli):
        """
        Loads the current report and augments it with parsed file data,
        making it suitable for placeholder display or autocompletion.
        """
        if not cli.session.report:
            return None

        report_data = cli.report_mgr.load(cli.session.report)
        if not report_data:
            return None

        try:
            file_data = placeholders.get_parsed_report_file_data(
                cli.report_mgr, cli.session.report
            )
            if file_data:
                report_data['file'] = file_data
        except Exception as e:
            log.debug(f"[Placeholder Data Error] Failed to parse report files: {e}")
        return report_data

    def do_placeholders(self, args, cli):
        """Handles the 'placeholders' command."""
        if not cli.session:
            log.warning("No active session.")
            return

        entity_to_show = args.subcommand
        if not entity_to_show:
            cli.help_mgr.show_help_placeholders()
            return

        if entity_to_show == 'functions':
            all_functions = pwn_functions.list_all()
            cli.display_mgr.display_function_list(all_functions, "Available Functions")
            return

        data_map = {}
        if entity_to_show in ['all', 'target']:
            data_map['target'] = cli.target_mgr.load(cli.session.target)
        if entity_to_show in ['all', 'tool']:
            data_map['tool'] = cli.tool_mgr.load(cli.session.tool)
        if entity_to_show in ['all', 'wordlist']:
            data_map['wordlist'] = cli.wordlist_mgr.load(cli.session.wordlist)
        if entity_to_show in ['all', 'profile']:
            data_map['profile'] = cli.profile_mgr.load()
        if entity_to_show in ['all', 'proxy']:
            data_map['proxy'] = cli.proxy_mgr.get_placeholder_config(cli.session)
        if entity_to_show in ['all', 'report']:
            data_map['report'] = self._get_report_data_for_placeholders(cli)
        
        data_to_display = {k: v for k, v in data_map.items() if v}

        if not data_to_display:
            log.info(f"The '{entity_to_show}' entity is not loaded or has no data to show placeholders for.")
        else:
            cli.display_mgr.display_placeholders(data_to_display)

    def do_print(self, statement, cli):
        """Handles the 'print' command."""
        line = statement.raw.lstrip('print').strip()

        if not line or line in ['-h', '--help']:
            cli.help_mgr.show_help_print()
            return

        parts = line.split(maxsplit=1)
        potential_func = parts[0]

        if len(parts) > 1 and potential_func in pwn_functions.FUNCTION_REGISTRY:
            func_to_run = pwn_functions.FUNCTION_REGISTRY[potential_func]
            text_to_process = parts[1]

            if (text_to_process.startswith('"') and text_to_process.endswith('"')) or \
               (text_to_process.startswith("'") and text_to_process.endswith("'")):
                text_to_process = text_to_process[1:-1]

            resolved_argument = placeholders.resolve_placeholders(text_to_process, cli.session)
            
            try:
                final_result = func_to_run(resolved_argument)
                cli.poutput(final_result)
            except Exception as e:
                log.error(f"Error executing function '{potential_func}': {e}")
        else:
            resolved_text = placeholders.resolve_placeholders(line, cli.session)
            cli.poutput(resolved_text)

    def do_identify(self, statement, cli):
        """Handles the 'identify' command."""
        line = statement.raw.lstrip('identify').strip()

        if not line or line in ['-h', '--help']:
            cli.help_mgr.show_help_identify()
            return

        if (line.startswith('"') and line.endswith('"')) or \
           (line.startswith("'") and line.endswith("'")):
            line = line[1:-1]

        resolved_hash = placeholders.resolve_placeholders(line, cli.session)
        possible_types = pwn_functions.identify_hash(resolved_hash)
        cli.display_mgr.display_hash_identification(resolved_hash, possible_types)