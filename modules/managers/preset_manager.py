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

# modules/managers/preset_manager.py

from .base_manager import JSONManager
from modules.services import log
import os, json, shlex
from rich.panel import Panel
from rich.table import Table
from rich.console import Group
from rich.text import Text

class PresetManager(JSONManager):
    def __init__(self):
        super().__init__("PRESETS")

    def dispatch(self, subcommand, args, cli_instance):
        """Overrides BaseManager's dispatch to handle the case where no subcommand is given."""
        if not subcommand:
            cli_instance.help_mgr.show_help_preset()
            return True
        
        # Let the parent class handle the actual dispatch to _cmd_* methods
        return super().dispatch(subcommand, args, cli_instance)

    def _cmd_save(self, args, cli):
        """Saves the current session, including its proxy settings, as a new preset."""
        session = cli.session
        if not session:
            log.error("No active session found to save.")
            return

        preset_data = {
            "name": args.name,
            "target": session.target,
            "tool": session.tool,
            "wordlist": session.wordlist,
            "report": session.report
        }

        # Always save the session's proxy settings if they exist
        if session.proxy_settings:
            preset_data["proxy_settings"] = session.proxy_settings
            log.info("Including session's proxy settings in the preset.")

        if not self._save_data(args.name, preset_data):
            return # Error is logged by _save_data
        
        # Invalidate cache if the preset was already loaded
        if hasattr(self, 'cache') and args.name in self.cache:
            del self.cache[args.name]
            
        log.success(f"Current session saved as preset '{args.name}'.")
        log.prompt(f"  -> Target: {session.target or 'None'}")
        log.prompt(f"  -> Tool: {session.tool or 'None'}")
        log.prompt(f"  -> Wordlist: {session.wordlist or 'None'}")
        log.prompt(f"  -> Report: {session.report or 'None'}")

    def _cmd_load(self, args, cli):
        """Loads a preset, creates a session of the same name (or switches to it) and populates it."""
        preset_name = args.name
        preset_data = self.load(preset_name)
        if not preset_data:
            return
 
        session_mgr = cli.session_mgr
        
        # This will log "Session created..." or "Switched to session..."
        if preset_name in session_mgr.sessions:
            cli.session = session_mgr.switch(preset_name)
        else:
            cli.session = session_mgr.new(preset_name)
        
        if not cli.session:
            return
 
        # --- Build new output panel ---
        render_items = []
        
        # Table for loaded items
        table = Table(show_header=False, box=None, expand=True)
        table.add_column(style="bold blue", width=12)
        table.add_column(style="green")
 
        target = preset_data.get("target")
        tool = preset_data.get("tool")
        wordlist = preset_data.get("wordlist")
        report = preset_data.get("report")
 
        cli.session.target = target
        cli.session.tool = tool
        cli.session.wordlist = wordlist
        cli.session.report = report
 
        table.add_row("Target", target or "[dim]None[/dim]")
        table.add_row("Tool", tool or "[dim]None[/dim]")
        table.add_row("Wordlist", wordlist or "[dim]None[/dim]")
        table.add_row("Report", report or "[dim]None[/dim]")
        
        render_items.append(table)
 
        # Apply and report proxy settings
        if 'proxy_settings' in preset_data:
            proxy_settings = preset_data['proxy_settings']
            if isinstance(proxy_settings, dict):
                cli.session.proxy_settings = proxy_settings
                render_items.append(Text("")) # Spacer
                render_items.append(Text("ℹ️ Proxy settings from preset have been applied.", style="dim"))
 
        panel = Panel(
            Group(*render_items),
            title=f"[bold]Preset Loaded: {preset_name}[/bold]",
            border_style="green",
            expand=False
        )
        
        cli.console.print(panel)

    def _cmd_export(self, args, cli):
        """Generates the 'load' commands stored in the preset."""
        name = args.name
        data = self.load(name)
        if not data: return

        commands = []
        if data.get("target"): commands.append(f"target load {data['target']}")
        if data.get("tool"): commands.append(f"tool load {data['tool']}")
        if data.get("wordlist"): commands.append(f"wordlist load {data['wordlist']}")
        if data.get("report"): commands.append(f"report load {data['report']}")

        # Export proxy settings as 'proxy' commands
        if 'proxy_settings' in data:
            commands.append("\n# --- Proxy Settings From Preset ---")
            # Command to reset all proxy settings first for a clean state
            commands.append("proxy reset all")
            for proxy_key, value in data['proxy_settings'].items():
                if proxy_key == 'enabled':
                    if str(value).lower() in ('true', '1', 'yes'):
                        commands.append("proxy on")
                    else:
                        commands.append("proxy off")
                else:
                    # Use shlex.quote to handle values with spaces
                    commands.append(f"proxy set {proxy_key} {shlex.quote(str(value))}")
        log.header(f"Export für Preset '{name}'")
        if commands:
            cli.poutput("\n".join(commands))
        else:
            log.info("Preset is empty.")

    def _format_and_show_entity(self, entity, console):
        """Overridden formatting for a nicer, tabular output of preset details."""
        name = entity.get('name', 'N/A')
        
        # Main panel content
        render_items = []

        # --- Part 1: Loaded Items ---
        items_table = Table(show_header=False, box=None, padding=(0, 2))
        items_table.add_column(style="bold blue", no_wrap=True, width=12)
        items_table.add_column(style="green")
        
        items_table.add_row("Target", entity.get('target') or "[dim]None[/dim]")
        items_table.add_row("Tool", entity.get('tool') or "[dim]None[/dim]")
        items_table.add_row("Wordlist", entity.get('wordlist') or "[dim]None[/dim]")
        
        render_items.append(Panel(items_table, title="[bold]Loaded Items[/bold]", border_style="dim", expand=True))

        # --- Part 2: Proxy Settings ---
        proxy_settings = entity.get('proxy_settings')
        if proxy_settings and isinstance(proxy_settings, dict):
            proxy_table = Table(show_header=False, box=None, padding=(0, 2))
            proxy_table.add_column(style="bold blue", no_wrap=True)
            proxy_table.add_column(style="green")
            
            if 'enabled' in proxy_settings:
                 proxy_table.add_row("enabled", str(proxy_settings['enabled']))
            for key, value in sorted(proxy_settings.items()):
                if key != 'enabled':
                    proxy_table.add_row(key, str(value))
            render_items.append(Panel(proxy_table, title="[bold]Saved Proxy Settings[/bold]", border_style="dim", expand=True))
        else:
            render_items.append(Panel("[dim]No proxy settings saved in this preset.[/dim]", title="[bold]Saved Proxy Settings[/bold]", border_style="dim", expand=True))
        
        main_panel = Panel(
            Group(*render_items),
            title=f":floppy_disk: [bold]Preset: {name}[/bold]",
            border_style="magenta",
            expand=True
        )
        console.print(main_panel)