# /home/kali/pwnity/modules/managers/library_manager.py
from .base_manager import JSONManager
from modules.services import log, config
import webbrowser
import os, json, threading, time
from datetime import datetime, timezone, timedelta

try:
    import requests
except ImportError:
    requests = None

class LibraryManager(JSONManager):
    def __init__(self):
        # Use the key from config.json to be consistent with other managers.
        super().__init__("LIBRARY")
        self.url_check_refresh_days = config.get_parameter("LIBRARY", "URL_CHECK_REFRESH_DAYS", 7)
        self.entity_name_singular = "Library entry"
        self.entity_name_plural = "Library entries"

    # --- Name Sanitization Helpers ---
    def _sanitize_name(self, name: str) -> str:
        """Replaces spaces with underscores for filename safety."""
        if not name: return name
        return name.replace(' ', '_')

    def _desanitize_name(self, sanitized_name: str) -> str:
        """Replaces underscores with spaces for display."""
        if not sanitized_name: return sanitized_name
        return sanitized_name.replace('_', ' ')

    # --- Overridden JSONManager Methods to handle name sanitization ---

    def create(self, name: str, category: str = None) -> bool:
        """Creates a new entity, storing the original name and using a sanitized filename."""
        if self.exists(name):
            sanitized_name = self._sanitize_name(name)
            log.error(f"{self.entity_name_singular} '{name}' (or '{sanitized_name}') already exists.")
            return False
        
        data = {"name": name}
        if category:
            data["category"] = category

        return self._save_data(self._sanitize_name(name), data)

    def load(self, name: str) -> dict:
        """Loads an entity by its name (which will be sanitized)."""
        sanitized_name = self._sanitize_name(name)
        return super().load(sanitized_name)

    def save(self, name: str, data: dict) -> bool:
        """Saves data to an entity's file by its name (which will be sanitized)."""
        # Use the robust _save_data method from the parent class for atomic writes
        return self._save_data(self._sanitize_name(name), data)

    def destroy(self, name: str) -> bool:
        """Destroys an entity's file by its name (which will be sanitized)."""
        sanitized_name = self._sanitize_name(name)
        return super().destroy(sanitized_name)

    def exists(self, name: str) -> bool:
        """Checks if an entity exists by its name (which will be sanitized)."""
        sanitized_name = self._sanitize_name(name)
        path = os.path.join(self.folder, f"{sanitized_name}.json")
        return os.path.exists(path)

    def rename(self, old_name: str, new_name: str) -> bool:
        """Renames an entity, handling sanitized filenames and internal name property."""
        sanitized_old_name = self._sanitize_name(old_name)
        sanitized_new_name = self._sanitize_name(new_name)
        # The base rename will rename the file and set the internal name to sanitized_new_name
        if super().rename(sanitized_old_name, sanitized_new_name):
            # Now we must correct the internal name to the proper display name
            return super().update(sanitized_new_name, 'name', new_name) is not None
        return False

    def list_all(self) -> list:
        """Lists all entities by their display names."""
        sanitized_names = super().list_all()
        display_names = []
        for s_name in sanitized_names:
            data = super().load(s_name)
            if data:
                display_names.append(data.get('name', self._desanitize_name(s_name)))
        return sorted(display_names, key=str.lower)

    # --- Custom Command Handlers ---

    def dispatch(self, subcommand, args, cli_instance):
        """Overrides BaseManager's dispatch to handle the case where no subcommand is given."""
        if not subcommand:
            cli_instance.help_mgr.show_help_library()
            return True
        
        # Let the parent class handle the actual dispatch to _cmd_* methods
        return super().dispatch(subcommand, args, cli_instance)

    def _cmd_list(self, args, cli):
        """Overrides BaseManager's list to show items grouped by category."""
        from rich.panel import Panel
        from rich.table import Table

        items = []
        for name in self.list_all():
            item_data = self.load(name)
            if item_data:
                items.append(item_data)
        
        if not items:
            log.info("No library entries found.")
            return

        grouped_items = {}
        for item in items:
            category = item.get('category', 'Uncategorized')
            if category not in grouped_items:
                grouped_items[category] = []
            grouped_items[category].append(item)

        # Sort items within each category by name
        for category in grouped_items:
            grouped_items[category].sort(key=lambda x: x.get('name', '').lower())

        # Get category order from config
        categories_str = config.get_parameter("LIBRARY", "CATEGORIES", "")
        sorted_categories = [cat.strip() for cat in categories_str.split(',') if cat.strip()]
        
        all_found_categories = list(grouped_items.keys())
        for cat in all_found_categories:
            if cat not in sorted_categories:
                sorted_categories.append(cat)
        
        for category in sorted_categories:
            if category in grouped_items:
                cli.display_mgr.display_simple_list([item.get('name') for item in grouped_items[category]], category)

    def check_all_entries_on_startup(self):
        """
        Checks all library entries on startup if they are stale or have errors.
        This is designed to run in a background thread to not block the CLI.
        """
        log.info("Starting background check of library URLs...")
        entries_to_check = []
        all_entries = self.list_all()

        for name in all_entries:
            entry = self.load(name)
            if not entry or not entry.get('url'):
                continue

            last_checked_str = entry.get('url_last_checked')
            status_code = entry.get('url_status_code')

            # Condition 1: Never checked or has an error
            if not last_checked_str or status_code == "Error":
                entries_to_check.append(name)
                continue

            # Condition 2: Stale check
            try:
                last_checked_dt = datetime.fromisoformat(last_checked_str)
                # Ensure last_checked_dt is offset-aware for comparison
                if last_checked_dt.tzinfo is None:
                    last_checked_dt = last_checked_dt.replace(tzinfo=timezone.utc)
                
                if datetime.now(timezone.utc) - last_checked_dt > timedelta(days=self.url_check_refresh_days):
                    entries_to_check.append(name)
            except ValueError:
                # If the date is malformed, check it anyway
                entries_to_check.append(name)

        if not entries_to_check:
            log.info("All library URLs are up-to-date. No background check needed.")
            return

        log.info(f"Found {len(entries_to_check)} library URLs to check/refresh.")
        for name in entries_to_check:
            self._check_url(name)
            time.sleep(0.5) # Small delay to avoid overwhelming servers
        log.success("Finished background check of library URLs.")

    def _check_url(self, name: str):
        """Internal helper to check a URL and save the status."""
        if not requests:
            log.error("The 'requests' library is not installed. Cannot check URL.")
            log.prompt("Install it with: pip install requests")
            return False

        entry = self.load(name)
        if not entry:
            # self.load() logs errors, so we just return
            return False
        
        url = entry.get('url')
        if not url:
            log.warning(f"Library entry '{name}' has no URL to check.")
            return False

        log.info(f"Checking URL for '{name}': {url} ...")
        status_code = None
        
        # Some servers block HEAD requests or requests without a User-Agent.
        # We use a streaming GET request with a common User-Agent to be more
        # compatible, while still being efficient by not downloading the body.
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36'
        }

        try:
            # Use a streaming GET request to read only headers, which is more compatible than HEAD.
            with requests.get(url, timeout=5, allow_redirects=True, stream=True, headers=headers) as response:
                status_code = response.status_code
        except requests.exceptions.RequestException as e:
            log.debug(f"URL check for '{name}' failed with exception: {e}")
            status_code = "Error"

        entry['url_status_code'] = status_code
        entry['url_last_checked'] = datetime.now(timezone.utc).isoformat()
        
        if self.save(name, entry):
            if status_code == "Error":
                log.error(f"URL for '{name}' is unreachable.")
            else:
                log.success(f"URL for '{name}' is reachable. Status: {status_code}")
            return True
        else:
            log.error(f"Failed to save updated status for '{name}'.")
            return False

    def _cmd_check(self, args, cli_instance):
        """Handles 'library check <name|all>'."""
        if args.name.lower() == 'all':
            log.header(f"Checking all library entries...")
            for name in self.list_all():
                self._check_url(name)
            log.header("Finished checking all entries.")
        else:
            self._check_url(args.name)

    def _cmd_add(self, args, cli_instance):
        """Overrides BaseManager's add to provide a helpful prompt."""
        if self.create(args.name, category=args.category if hasattr(args, 'category') else None): # Uses the overridden create method
            log.success(f"Added new, empty library entry: '{args.name}'.")
            # Quote the name in the prompt to handle spaces
            log.prompt(f"Now add a URL with: library update \"{args.name}\" url <your_url>")

    def _cmd_update(self, args, cli):
        """Handles 'library update' and triggers a check if URL is changed."""
        entity_type = self._get_entity_type()
        if len(args.update_args) < 2:
            log.error(f"Invalid update command. Expected: update <name> <field> <value>")
            return
        
        field = args.update_args[0]
        value = " ".join(args.update_args[1:])

        if self.update(args.name, field, value):
            log.success(f"{entity_type} '{args.name}' field '{field}' updated -> {value}")

    def _cmd_open(self, args, cli_instance):
        """Handles 'library open <name>'."""
        entry = self.load(args.name)
        if not entry:
            log.error(f"Library entry '{args.name}' not found.")
            return
        
        url = entry.get('url')
        if not url:
            log.error(f"Library entry '{args.name}' does not have a URL defined.")
            log.prompt(f"You can add one with: library update \"{args.name}\" url <your_url>")
            return
            
        try:
            log.info(f"Opening '{url}' in your default web browser...")
            webbrowser.open(url, new=2)
        except Exception as e:
            log.error(f"Could not open URL: {e}")
