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

# modules/managers/wordlist_manager.py

from .base_manager import JSONManager
from modules.services import log
import shlex, os

class WordlistManager(JSONManager):
    def __init__(self):
        super().__init__("WORDLISTS")

    def _cmd_add(self, args, cli):
        """
        Overrides the default 'add' to include a 'path' field from the start.
        This ensures the UI can immediately display an editable path field.
        """
        entity_type = self._get_entity_type()
        
        path = os.path.join(self.folder, f"{args.name}.json")
        if os.path.exists(path):
            log.error(f"{entity_type} '{args.name}' already exists.")
            return

        # Create the data structure with an empty path.
        data = {"name": args.name, "path": ""}
        if self._save_data(args.name, data):
            log.success(f"{entity_type} '{args.name}' added.")
            log.prompt(f"Set the path now with: wordlist update {args.name} path /path/to/wordlist.txt")

    def _cmd_show(self, args, cli):
        """Handles 'wordlist show [name]'."""
        wordlist_name = args.name
        if not wordlist_name:
            # If no name is provided, use the one from the session
            wordlist_name = cli.session.wordlist
            if not wordlist_name:
                log.error("No wordlist specified and no wordlist loaded in the session.")
                log.prompt("Use 'wordlist show <name>' or load one with 'wordlist load <name>'.")
                return

        wordlist_data = self.load(wordlist_name)
        if not wordlist_data:
            return # load() already logs an error
        self._format_and_show_entity(wordlist_data, cli.console)

    def _cmd_export(self, args, cli):
        """Generates the pwnity commands to reconstruct a wordlist."""
        name = args.name
        data = self.load(name)
        if not data: return

        commands = [f"wordlist add {name}"]
        for key, value in data.items():
            if key != 'name':
                commands.append(f"wordlist update {name} {key} {shlex.quote(str(value))}")
        
        log.header(f"Export für Wordlist '{name}'")
        cli.poutput("\n".join(commands))