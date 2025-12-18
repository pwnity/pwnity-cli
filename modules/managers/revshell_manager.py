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

# modules/managers/revshell_manager.py

import json, os, shlex, socket
from modules.services import log, config
from modules.placeholders import resolve_placeholders
from rich.panel import Panel
from rich.text import Text
from rich.console import Group
from rich.rule import Rule
from .base_manager import BaseManager

class RevshellManager(BaseManager):
    def __init__(self):
        self.templates = self._load_templates()

    def _load_templates(self):
        """Loads revshell templates from the JSON file specified in the config."""
        path = config.get_parameter("DIRS", "REVSHELLS")
        if not path or not os.path.exists(path):
            log.error(f"Revshell templates file not found at '{path}'.")
            log.prompt("Please check the 'REVSHELLS' path in your 'etc/config.json'.")
            return {}
        try:
            with open(path, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            log.error(f"Error decoding revshell templates file '{path}': {e}")
            return {}

    def _get_local_ip(self):
        """
        Tries to determine the local IP address of the machine by connecting to an external resolver.
        Falls back to 127.0.0.1 if unable to determine.
        """
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.1) # Prevent long waits
        try:
            # doesn't even have to be reachable
            s.connect(('8.8.8.8', 1))
            IP = s.getsockname()[0]
        except Exception:
            IP = '127.0.0.1'
        finally:
            s.close()
        return IP

    def list_languages(self):
        """Returns a list of available languages for autocompletion."""
        return list(self.templates.keys())

    def generate(self, lang, lhost, lport, session):
        """
        Generates a revshell payload. This is a silent method for API use.
        It resolves placeholders using the provided session object.
        """
        if lang not in self.templates:
            return None

        # Resolve IP
        if lhost:
            resolved_ip = resolve_placeholders(lhost, session)
        else:
            resolved_ip = resolve_placeholders("$profile.lhost", session)
            if "$" in resolved_ip: # Placeholder didn't resolve
                resolved_ip = self._get_local_ip()

        # Resolve Port
        if lport:
            resolved_port = resolve_placeholders(str(lport), session)
        else:
            resolved_port = resolve_placeholders("$profile.lport", session)
            if "$" in resolved_port: # Placeholder didn't resolve
                resolved_port = "1337"

        # Use .replace() instead of .format() to avoid errors if the template
        # contains other curly braces (e.g., for shell brace expansion).
        raw_template = self.templates[lang]['template']
        payload = raw_template.replace("{ip}", resolved_ip).replace("{port}", resolved_port)
        return payload

    def dispatch(self, subcommand, args, cli) -> bool:
        """The main entry point for the 'revshell' command."""
        # This command doesn't use subcommands, so we handle the logic directly.
        if not args.language:
            cli.help_mgr.show_help_revshell()
            return True # Handled by showing help

        language = args.language
        if language not in self.templates:
            log.error(f"Unknown language '{language}'.")
            log.prompt(f"Available languages: {', '.join(self.list_languages())}")
            return

        # --- IP and Port Resolution ---
        # Step 1: Resolve IP
        if args.ip:
            resolved_ip = resolve_placeholders(args.ip, cli.session)
        else:
            resolved_ip = resolve_placeholders("$profile.lhost", cli.session)
            if "$" in resolved_ip:
                log.info("LHOST not set in profile, attempting to auto-detect...")
                resolved_ip = self._get_local_ip()
                log.success(f"  -> Auto-detected LHOST: {resolved_ip}")
                log.prompt("  -> Tip: Set it permanently with 'profile update lhost <ip>'")

        # Step 2: Resolve Port
        if args.port:
            resolved_port = resolve_placeholders(str(args.port), cli.session)
        else:
            resolved_port = resolve_placeholders("$profile.lport", cli.session)
            if "$" in resolved_port:
                resolved_port = "1337"
                log.info(f"LPORT not set in profile, using default: {resolved_port}")
                log.prompt("  -> Tip: Set it permanently with 'profile update lport <port>'")

        # Step 3: Generate the final payload
        raw_template = self.templates[language]['template']
        # Use .replace() for consistency and safety.
        example_payload = raw_template.replace("{ip}", resolved_ip).replace("{port}", resolved_port)

        # Display the results
        payload_panel = Panel(Text(example_payload, style="green"), title="[bold]Generated Payload (Copy & Paste)[/bold]", border_style="blue")
        cli.console.print(payload_panel)
        return True # Command successfully handled