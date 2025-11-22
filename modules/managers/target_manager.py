# modules/managers/target_manager.py

from .base_manager import JSONManager, _add_data_to_table_recursively
from modules.services import log
from modules.recon import ReconService
import socket, shlex, json, sys
from urllib.parse import urlparse, parse_qs, parse_qsl, uses_netloc
from datetime import datetime
import ipaddress
from rich.table import Table
from rich.panel import Panel
from rich.columns import Columns
from rich.console import Group

try:
    import tldextract
except ImportError:
    tldextract = None
    # Log error only once, not every time the module is imported.
    if 'tldextract' not in sys.modules:
        log.error("Dependency 'tldextract' not found. Domain parsing is disabled.")
        log.error("Please install with 'pip install tldextract'.")

class TargetManager(JSONManager):
    def __init__(self):
        super().__init__("TARGETS")

    def _cmd_add(self, args, cli):
        """Provides a context-sensitive hint after creation."""
        # Calls the parent class's _cmd_add to actually create the target
        super()._cmd_add(args, cli)
        log.prompt(f"Tip: Define the target's URL now with 'target update {args.name} url <your-url-here>'")

    def _is_local_target(self, target):
        """Checks if the target is a local/private address."""
        hostname = target.get('hostname')
        if hostname and hostname.lower() == 'localhost':
            return True
        
        ip_str = target.get('ip')
        if ip_str:
            try:
                ip = ipaddress.ip_address(ip_str)
                return ip.is_private or ip.is_loopback or ip.is_link_local
            except ValueError:
                # Not a valid IP address, so can't be a local one in that sense.
                return False
        return False

    def _cmd_update(self, args, cli):
        """Overrides the update logic to handle URLs intelligently."""
        if len(args.update_args) >= 2 and args.update_args[0].lower() == 'url':
            url_string = " ".join(args.update_args[1:])
            self._parse_and_update_from_url(args.name, url_string, cli)
        else:
            # Default behavior for all other fields
            super()._cmd_update(args, cli)

    def _parse_and_update_from_url(self, name, url_string, cli):
        """Parses a URL and updates multiple fields of the target."""
        target_data = self.load(name)
        if not target_data:
            log.error(f"Target '{name}' not found.")
            return

        log.info(f"Analyzing URL: {url_string}...")
        try:
            parsed = urlparse(url_string)
            
            current_data = target_data.copy()
            updates = {}
            deletions = []

            # Username and Password
            if parsed.username:
                updates['username'] = parsed.username

            if parsed.password:
                updates['password'] = parsed.password

            # Protocol
            protocol = parsed.scheme or 'http'
            updates['protocol'] = protocol
            
            # Hostname
            if parsed.hostname:
                updates['hostname'] = parsed.hostname
                # Resolve IP address
                try:
                    updates['ip'] = socket.gethostbyname(parsed.hostname)
                except socket.gaierror:
                    log.warning(f"  -> Could not resolve hostname '{parsed.hostname}'.")

                # Parse domain parts with tldextract
                if tldextract:
                    extracted = tldextract.extract(parsed.hostname)
                    updates['domain'] = extracted.registered_domain
                    updates['domain_name'] = extracted.domain
                    updates['tld'] = extracted.suffix
                    updates['subdomains'] = extracted.subdomain.split('.') if extracted.subdomain else []
                else:
                    log.warning("  -> 'tldextract' not installed, skipping domain parsing.")

            # Port
            port = parsed.port
            if not port:
                try:
                    port = socket.getservbyname(protocol)
                except OSError:
                    port = None
            
            if port:
                updates['port'] = str(port)

            # Build and save the base URL (protocol://hostname:port)
            if 'hostname' in updates:
                base_url = f"{updates['protocol']}://{updates['hostname']}"
                # Only add port if it's non-standard for the protocol
                if 'port' in updates:
                    port_for_url = updates['port']
                    if not ((updates['protocol'] == 'http' and str(port_for_url) == '80') or (updates['protocol'] == 'https' and str(port_for_url) == '443')):
                        base_url += f":{port_for_url}"
                updates['base_url'] = base_url
            elif 'base_url' in current_data:
                deletions.append('base_url')

            # URI/Path
            updates['uri'] = parsed.path or '/'

            # Extract and parse query parameters into two formats for flexibility
            if parsed.query:
                updates['query_values'] = parse_qs(parsed.query, keep_blank_values=True)
                query_params_list_of_tuples = parse_qsl(parsed.query, keep_blank_values=True)
                updates['query_params'] = [f"{k}={v}" for k, v in query_params_list_of_tuples]
            else:
                if 'query_values' in current_data: deletions.append('query_values')
                if 'query_params' in current_data: deletions.append('query_params')

            # Also save the original URL
            updates['url'] = url_string

            # --- Apply all changes ---
            for key in deletions:
                self.delete(name, key, silent=True)

            for key, value in updates.items():
                self.update(name, key, value)

            # --- Log success messages ---
            if 'username' in updates: log.success(f"  -> Found and saved username: '{updates['username']}'")
            if 'password' in updates: log.success(f"  -> Found and saved password.")
            if 'ip' in updates: log.success(f"  -> Resolved hostname '{updates['hostname']}' to IP '{updates['ip']}'.")
            if 'domain' in updates: log.success(f"  -> Parsed domain: Subdomains={updates['subdomains']}, Domain='{updates['domain']}', TLD='{updates['tld']}'")
            if not parsed.port and 'port' in updates: log.info(f"  -> No port specified, using default for '{updates['protocol']}': {updates['port']}.")
            elif not port and 'port' in deletions: log.warning(f"  -> Could not determine default port for unknown protocol '{protocol}'. Port removed.")
            if 'query_params' in updates: log.info(f"  -> Found and parsed {len(updates['query_params'])} query parameter(s).")
            
            log.success(f"Target '{name}' updated with data extracted from the URL.")

        except Exception as e:
            log.error(f"Error parsing URL: {e}")

    def _cmd_gather(self, args, cli):
        """Gathers additional information like WHOIS."""
        target_name = args.name
        target = self.load(target_name)
        if not target:
            return

        if not (target.get('ip') or target.get('hostname')):
            log.error(f"Target '{target_name}' has no IP or hostname. Run 'target update {target_name} url ...' first.")
            return
        
        try:
            recon = ReconService(target)
            gather_type = args.type
            
            if gather_type == 'all':
                updates = recon.gather_all()
            else:
                gather_method = getattr(recon, f"gather_{gather_type}", None)
                if not gather_method:
                    log.error(f"Unknown gather type: {gather_type}")
                    return
                updates = gather_method()

        except ImportError:
            # Error is already logged during ReconService import
            return

        if not updates:
            log.info("No new information found or an error occurred during the query.")
            return

        # Write all collected data to the target object at once
        for key, value in updates.items():
            self.update(target_name, key, value)

        log.success(f"Target '{target_name}' updated with new information.")
        log.prompt("Use 'target show " + target_name + "' to see the details.")

    def _cmd_fork_domain(self, args, cli):
        """Creates a new target from the main domain of an existing target."""
        source_name = args.name
        source_target = self.load(source_name)
        if not source_target:
            return # load() already logs an error message

        main_domain = source_target.get('domain')
        if not main_domain:
            log.error(f"Target '{source_name}' has no 'domain' field. Run 'target update {source_name} url ...' first.")
            return

        if main_domain == source_target.get('hostname'):
            log.info(f"Hostname '{main_domain}' is already the main domain. No fork necessary.")
            return

        if self.load(main_domain):
            log.warning(f"A target named '{main_domain}' already exists. Nothing to do.")
        else:
            log.info(f"Creating new target '{main_domain}' from the domain of '{source_name}'...")
            self.create(main_domain)
            self._parse_and_update_from_url(main_domain, f"https://{main_domain}", cli)

    def add_findings(self, target_name, new_findings):
        """
        Adds findings from a parser to a target. Merges with existing findings.
        """
        target_data = self.load(target_name)
        if not target_data:
            return

        # Get existing findings or create a new dict
        existing_findings = target_data.setdefault('findings', {})

        for category, matches in new_findings.items():
            # Get existing matches for the category or create a new list
            category_matches = existing_findings.setdefault(category, [])
            
            # Add only new, unique matches to the list
            for match in matches:
                if match not in category_matches:
                    category_matches.append(match)
        
        self.update(target_name, 'findings', existing_findings)
        log.success(f"Findings saved to target '{target_name}'.")

    def add_findings_as_notes(self, target_name, findings):
        """Adds a dictionary of findings as structured notes to the target."""
        target_data = self.load(target_name)
        if not target_data:
            return

        notes = target_data.setdefault('notes', [])
        count = 0
        for category, matches in findings.items():
            for match in matches:
                note_text = f"[Parser Finding][{category}] {match}"
                # Avoid adding duplicate notes
                if not any(n.get('text') == note_text for n in notes):
                    new_note = {
                        "timestamp": datetime.now().isoformat(),
                        "text": note_text
                    }
                    notes.append(new_note)
                    count += 1
        self.update(target_name, 'notes', notes)
        log.success(f"Promoted {count} new finding(s) as notes to target '{target_name}'.")

    def _cmd_export(self, args, cli):
        """Generates the pwnity commands to reconstruct a target object."""
        target_name = args.name
        target_data = self.load(target_name)
        if not target_data:
            return

        commands = []
        # The first command is always creating the target
        commands.append(f"target add {target_name}")

        # Priority 1: Set URL, as this fills many fields
        if 'url' in target_data:
            commands.append(f"target update {target_name} url {shlex.quote(target_data['url'])}")

        # Priority 2: Semantic 'gather' commands for derived data
        gathered_types = set()
        gather_map = {
            'whois_info': 'whois',
            'ssl_info': 'http',
            'http_headers': 'http',
            'mx_records': 'mx',
            'ptr_record': 'dns',
            'txt_records': 'dns',
            'name_servers': 'dns',
            'ipv6_addresses': 'dns',
            'cname_records': 'dns',
        }
        for key, value in target_data.items():
            if key in gather_map:
                gather_type = gather_map[key]
                if gather_type not in gathered_types:
                    commands.append(f"target gather {target_name} {gather_type}")
                    gathered_types.add(gather_type)

        # Priority 3: Notes and Loot
        if 'notes' in target_data and isinstance(target_data['notes'], list):
            for note in target_data['notes']:
                commands.append(f"note add {shlex.quote(note.get('text', ''))}")
        
        if 'loot' in target_data and isinstance(target_data['loot'], list):
            for loot_item in target_data['loot']:
                loot_type = loot_item.get('type', 'unknown')
                loot_value = loot_item.get('value', '')
                commands.append(f"loot add {loot_type} {shlex.quote(loot_value)}")

        # Priority 4: All other custom fields
        # Fields already covered by other commands
        derived_from_url = {'protocol', 'hostname', 'ip', 'port', 'uri', 'query_params', 'query_values', 'domain', 'domain_name', 'tld', 'subdomains', 'base_url', 'username', 'password'}
        handled_keys = {'name', 'url'} | set(gather_map.keys())
        # If a URL is present, we also consider all fields derived from it as "handled"
        # to avoid redundant export commands.
        if 'url' in target_data:
            derived_from_url = {'protocol', 'hostname', 'ip', 'port', 'uri', 'query_params', 'query_values', 'domain', 'domain_name', 'tld', 'subdomains', 'base_url', 'username', 'password'}
            handled_keys.update(derived_from_url)
        
        for key, value in target_data.items():
            if key not in handled_keys:
                val_str = json.dumps(value) if isinstance(value, (dict, list)) else str(value)
                commands.append(f"target update {target_name} {key} {shlex.quote(val_str)}")

        log.header(f"Export for Target '{target_name}'")
        cli.poutput("\n".join(commands))
        log.prompt("These commands can be copied to recreate the target elsewhere.")

    def _format_and_show_entity(self, entity, console):
        """Overridden formatting for a nicer, tabular output of target details."""
        data = entity.copy()
        name = entity.get('name', 'N/A')

        # Obfuscate password for display
        if 'password' in data and data['password']:
            data['password'] = '********'

        # Create panels for each group
        panels = {}
        handled_keys = set()
        key_groups = {
            "Primary Information": ['url', 'base_url', 'protocol', 'hostname', 'username', 'password', 'subdomains', 'domain', 'domain_name', 'tld', 'ip', 'port', 'uri'],
            "Query Parameters": ['query_params', 'query_values'],
            "DNS Information": ['cname_records', 'ipv6_addresses', 'ptr_record', 'name_servers', 'mx_records', 'txt_records'],
            "HTTP & SSL Information": ['http_headers', 'ssl_info'],
            "WHOIS Information": ['whois_info'],
        }
        for title, keys in key_groups.items():
            group_data = {key: data[key] for key in keys if key in data}
            if not group_data:
                continue

            table = Table(show_header=False, box=None, padding=(0, 2))
            table.add_column(style="white", no_wrap=True)
            table.add_column(style="green", ratio=1)
            _add_data_to_table_recursively(table, group_data)
            panels[title] = Panel(table, title=f"[bold]{title}[/bold]", border_style="dim", expand=True)
            handled_keys.update(group_data.keys())

        # Handle remaining, uncategorized data
        other_data = {k: v for k, v in data.items() if k not in handled_keys}
        if other_data:
            table = Table(show_header=False, box=None, padding=(0, 2))
            table.add_column(style="white", no_wrap=True)
            table.add_column(style="green", ratio=1)
            _add_data_to_table_recursively(table, other_data)
            panels["Other Data"] = Panel(table, title="[bold]Other Data[/bold]", border_style="dim", expand=True)

        if not panels:
            console.print(Panel(f"[dim]No data available for Target '{name}'.[/dim]", title=f":dart: [bold]Target: {name}[/bold]", border_style="green"))
            return

        # Arrange panels in two columns
        left_col_panels = [panels.get("Primary Information"), panels.get("Query Parameters"), panels.get("DNS Information")]
        right_col_panels = [panels.get("HTTP & SSL Information"), panels.get("WHOIS Information"), panels.get("Other Data")]

        # Filter out None values if a panel was not created
        left_col = Group(*(p for p in left_col_panels if p))
        right_col = Group(*(p for p in right_col_panels if p))

        # Wrap the columns with a main panel
        main_layout = Columns([left_col, right_col], expand=True, equal=True)
        main_panel = Panel(
            main_layout,
            title=f":dart: [bold]Target: {name}[/bold]",
            border_style="green",
            expand=True
        )
        console.print(main_panel)