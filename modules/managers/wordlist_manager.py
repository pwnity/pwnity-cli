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