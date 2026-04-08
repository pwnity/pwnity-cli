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

# modules/managers/base_manager.py

from modules.services import log, config
import json, os, re
from rich.table import Table
from rich.panel import Panel
from rich.console import Group
from rich.text import Text

class BaseManager:
    """Base class for all managers to provide common functionality."""
    def _get_config_dir(self, key, fallback):
        """
        Gets a directory path from the [DIRS] section of the config,
        with a fallback.
        """
        settings = config.get_section("DIRS")
        return settings.get(key, fallback)

    def get_available_subcommands(self):
        """
        Inspects the manager instance and returns a list of all available subcommands
        by finding all methods that start with '_cmd_'.
        """
        return [method_name.replace('_cmd_', '').replace('_', '-')
                for method_name in dir(self) if callable(getattr(self, method_name)) and method_name.startswith('_cmd_')]

    def dispatch(self, subcommand, args, cli):
        """
        Dynamically dispatches a subcommand to a handler method (_cmd_<subcommand>).
        Returns True if the command was handled, otherwise False.
        """
        # Replace hyphens in the subcommand name with underscores to form the method name.
        handler_method_name = f"_cmd_{subcommand.replace('-', '_')}"
        handler = getattr(self, handler_method_name, None)

        if callable(handler):
            handler(args, cli)
            return True
        
        # If no handler was found in the current class, False is returned.
        # This allows the caller (e.g., in pwnity.py) to know that the command was not handled.
        return False

    def _get_entity_type(self):
        """Helper method to get the entity type as a string (e.g., 'Target', 'Tool')."""
        return self.__class__.__name__.replace("Manager", "")

    def normalize_tags(self, tags_data):
        """Standardizes tags from both string (comma-separated) and list formats into a sorted list."""
        if isinstance(tags_data, str) and tags_data:
            return sorted([t.strip() for t in tags_data.split(',') if t.strip()])
        elif isinstance(tags_data, list):
            return sorted([str(t).strip() for t in tags_data if str(t).strip()])
        return []

def _add_data_to_table_recursively(table: Table, data, indent_level=0):
    """
    Traverses a nested dictionary or list and adds its content as rows to a rich Table,
    creating a clean, indented, tree-like view without JSON syntax.
    """
    indent = "  " * indent_level
    if isinstance(data, dict):
        for key, value in data.items():
            # Support both String and List for tags for smooth transition
            if key == 'tags':
                # Use a dummy instance of BaseManager to access normalize_tags if needed, 
                # but better to just use the logic directly here or make it a helper.
                # Since we are in a helper function outside classes:
                if isinstance(value, str) and value:
                    tags_list = [t.strip() for t in value.split(',') if t.strip()]
                elif isinstance(value, list):
                    tags_list = value
                else:
                    tags_list = []
                
                if tags_list:
                    tag_str = " ".join([f"[cyan]#{t}[/cyan]" for t in tags_list])
                    table.add_row(f"{indent}[bold blue]{key}[/bold blue]", tag_str)
                    continue

            styled_key = f"{indent}[bold blue]{key}[/bold blue]"
            
            if isinstance(value, dict) and value:
                table.add_row(styled_key, "")
                _add_data_to_table_recursively(table, value, indent_level + 1)
            elif isinstance(value, list) and value:
                table.add_row(styled_key, "")
                _add_data_to_table_recursively(table, value, indent_level + 1)
            else:
                table.add_row(styled_key, str(value))
    elif isinstance(data, list):
        for i, item in enumerate(data, 1):
            if isinstance(item, (dict, list)):
                table.add_row(f"{indent}  [dim]─ {i} ─[/dim]", "")
                _add_data_to_table_recursively(table, item, indent_level + 1)
            else:
                table.add_row(f"{indent}  [dim]{i}:[/dim]", str(item))

class JSONManager(BaseManager):
    def __init__(self, folder):
        # --- REFACTOR for better testability ---
        # Always use get_parameter to fetch the directory path.
        # If 'folder' is a config key (e.g., "LIBRARY"), get_parameter will resolve it.
        # If 'folder' is a direct path, get_parameter will return it as a fallback.
        self.folder = config.get_parameter("DIRS", folder, fallback=folder)
        os.makedirs(self.folder, exist_ok=True)
        # --- NEU: Flag, um verschachtelte Speicherung pro Manager zu aktivieren ---
        # Der LogbookManager wird dieses Flag setzen.
        self.use_nested_structure = False
        self.cache = {}

    def _format_and_show_entity(self, data, console):
        """Standard Rich formatting for any JSON entity."""
        name = data.get('name', 'N/A')
        entity_type = self._get_entity_type()
        
        from rich.text import Text
        from rich.console import Group
        
        details_table = Table(show_header=False, box=None, padding=(0, 2))
        details_table.add_column(style="bold blue", no_wrap=True)
        details_table.add_column(style="green")
        
        # Skip only name as it's in the header. Tags is handled by the recursive renderer.
        display_data = {k: v for k, v in data.items() if k != 'name'}
        _add_data_to_table_recursively(details_table, display_data)
        
        console.print(Panel(
            details_table,
            title=f"[bold]{entity_type}: {name}[/bold]",
            border_style="blue",
            expand=True
        ))

    def list_all_tags(self):
        """Returns a unique, sorted list of all tags used across all entities of this type."""
        all_tags = set()
        for name in self.list_all():
            data = self.load(name) # load() handles exists and error logging
            if data and 'tags' in data:
                all_tags.update(self.normalize_tags(data['tags']))
        return sorted(list(all_tags))

    def _get_entity_path(self, name: str) -> str:
        """Gibt den vollständigen Pfad zu einer Entitätsdatei zurück, unter Berücksichtigung der Speicherstruktur."""
        sanitized_name = self._sanitize_filename(name)
        
        # 1. Namespaced handling: If the name contains a slash, it's a direct path
        if '/' in sanitized_name:
            return os.path.join(self.folder, f"{sanitized_name}.json")

        # 2. Check for specific nested structure (logbook style)
        if self.use_nested_structure and len(sanitized_name) > 2:
            nested_dir = os.path.join(self.folder, sanitized_name[0], sanitized_name[1])
            path = os.path.join(nested_dir, f"{sanitized_name}.json")
            if os.path.exists(path):
                return path

        # 3. Check flat structure (standard root)
        flat_path = os.path.join(self.folder, f"{sanitized_name}.json")
        if os.path.exists(flat_path):
            return flat_path

        # 4. Deep search for organized subdirectories (legacy lookup for local names)
        # This allows 'load nmap' to find 'remote/nmap.json' if root doesn't have it.
        for root, _, files in os.walk(self.folder):
            if f"{sanitized_name}.json" in files:
                return os.path.join(root, f"{sanitized_name}.json")

        # Fallback to standard flat path for creation
        return flat_path

    def _save_data(self, name, data):
        """
        Saves a data dictionary to its corresponding JSON file, ensuring it's synced to disk.
        This is the robust way to prevent race conditions with the UI.
        Returns True on success, False on failure.
        """
        path = self._get_entity_path(name)
        temp_file_path = path + ".tmp"
        try:
            # --- NEU: Sicherstellen, dass das verschachtelte Verzeichnis existiert ---
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(temp_file_path, "w") as f:
                json.dump(data, f, indent=2)
                f.flush()  # Ensure data is written to the OS buffer
                os.fsync(f.fileno())  # Force OS to write buffer to disk
            os.replace(temp_file_path, path)  # Atomically replace the old file
            return True
        except Exception as e:
            log.error(f"Error saving data for '{name}' to '{path}': {e}")
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
            return False

    def _sanitize_filename(self, name):
        """
        Sanitizes a string to make it safe for use as a filename.
        Replaces invalid characters with underscores. Allows / for subdirectories.
        """
        return re.sub(r'[^a-zA-Z0-9_/.-]', '_', name)

    def rename(self, old_name, new_name):
        """Renames an entity, including its JSON file and the 'name' field in the content."""
        entity_type = self._get_entity_type()

        sanitized_new_name = self._sanitize_filename(new_name)
        if sanitized_new_name != new_name:
            log.warning(f"The name '{new_name}' was sanitized to '{sanitized_new_name}' to be a valid filename.")
            new_name = sanitized_new_name

        if not new_name:
            log.error("The new name cannot be empty.")
            return False

        data = self.load(old_name)
        if not data:
            return False # self.load() already logs an error message

        # Case 1: Only correct the internal name if the filename remains the same
        if old_name == new_name:
            if data.get('name') != old_name:
                path = os.path.join(self.folder, f"{self._sanitize_filename(old_name)}.json")
                log.info(f"Filename '{old_name}.json' and internal name '{data.get('name')}' are inconsistent. Correcting...")
                # Directly update the data and save, do NOT call self.update() to avoid recursion.
                data['name'] = old_name
                with open(path, "w") as f:
                    json.dump(data, f, indent=2)
                # Update cache
                self.cache[old_name] = data
                log.success(f"Internal name in '{old_name}.json' has been corrected to '{old_name}'.")
            else:
                log.info("Names are identical and consistent. Nothing to do.")
            return True

        # Case 2: Actual renaming (file + content)
        new_path = os.path.join(self.folder, f"{new_name}.json")
        old_path = os.path.join(self.folder, f"{self._sanitize_filename(old_name)}.json")

        # Check for collision. Allow the operation if it is only a
        # change in the case of the same file.
        if os.path.exists(new_path):
            try:
                # os.path.samefile checks if two paths point to the same file.
                if not os.path.samefile(old_path, new_path):
                    log.error(f"A {entity_type} with the name '{new_name}' already exists.")
                    return False
            except FileNotFoundError:
                # Shouldn't happen since we checked with os.path.exists(), but as a safety net.
                log.error(f"A {entity_type} with the name '{new_name}' already exists.")
                return False

        data['name'] = new_name
        try:
            # We write to a temporary file and then atomically replace the target file.
            # This prevents corrupt files in case of errors and handles case-insensitive renames.
            temp_file_path = new_path + ".tmp"
            with open(temp_file_path, "w") as f:
                json.dump(data, f, indent=2)
                f.flush()
                os.fsync(f.fileno())

            os.replace(temp_file_path, new_path)

            # If the path differs case-sensitively and the old file still exists, delete it.
            if old_path != new_path and os.path.exists(old_path):
                os.remove(old_path)

            log.success(f"{entity_type} '{old_name}' has been renamed to '{new_name}'.")
            return True
        except Exception as e:
            log.error(f"Error renaming '{old_name}' to '{new_name}': {e}")
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
            return False

    def copy(self, source_name, dest_name):
        """Copies an entity to a new name."""
        entity_type = self._get_entity_type()

        if self.exists(dest_name):
            log.error(f"A {entity_type} with the name '{dest_name}' already exists.")
            return False

        source_data = self.load(source_name)
        if not source_data:
            # self.load() already logs the error
            return False

        # Update the internal name to the new name
        source_data['name'] = dest_name

        if self._save_data(dest_name, source_data):
            log.success(f"{entity_type} '{source_name}' successfully copied to '{dest_name}'.")
            return True
        return False

    def create(self, name):
        """Creates a new, empty JSON file for an entity, ensuring it's synced to disk."""
        path = os.path.join(self.folder, f"{self._sanitize_filename(name)}.json")
        if os.path.exists(path):
            log.error(f"{self._get_entity_type()} '{name}' already exists.")
            return False
        return self._save_data(name, {"name": name})

    def exists(self, name):
        """Checks if an entity's JSON file exists."""
        if not name: return False
        path = self._get_entity_path(name)
        return os.path.exists(path)
    
    def load(self, name):
        if not name:
            return None
        # Always load from file to ensure the disk is the source of truth.
        # This prevents any caching inconsistencies between the UI and the CLI.
        path = self._get_entity_path(name)
        if self.exists(name):
            try:
                log.trace(f"[Manager] Loading '{name}' from {path}")
                with open(path) as f:
                    # Handle empty files that would cause a JSONDecodeError
                    if os.fstat(f.fileno()).st_size == 0:
                        log.warning(f"File for '{name}' is empty: {path}")
                        return None
                    data = json.load(f)
                return data
            except json.JSONDecodeError as e:
                log.error(f"Failed to decode JSON for '{name}' from '{path}': {e}")
                return None
        else:
            return None


    def list_all(self) -> list[str]:
        """Listet alle Entitäten auf, indem der gesamte Ordner rekursiv durchsucht wird."""
        names = []
        for root, _, files in os.walk(self.folder):
            for file in files:
                if file.endswith(".json") and not file.endswith(".tmp"):
                    rel_dir = os.path.relpath(root, self.folder)
                    if rel_dir == ".":
                        name = file.replace(".json", "")
                    else:
                        name = os.path.join(rel_dir, file.replace(".json", ""))
                    names.append(name)
        return sorted(names)


    def update(self, name, field, value):
        """Adds or changes a key/value pair in an existing JSON object using dot notation."""
        data = self.load(name)
        if not data or field is None:
            return None

        # Support escaped newlines (e.g. \n) in strings if passed via CLI
        if isinstance(value, str):
            value = value.replace("\\n", "\n")

        # --- Handle simple/direct updates ---
        if "." not in field:
            data[field] = value
            if self._save_data(name, data):
                return data
            return None

        # --- Handle nested updates (dot notation: command.params.0) ---
        keys = field.split('.')
        curr = data
        for k in keys[:-1]:
            if isinstance(curr, dict):
                curr = curr.setdefault(k, {})
            elif isinstance(curr, list):
                try:
                    idx = int(k)
                    # If index is exactly len(curr), we want to append or create placeholder?
                    while len(curr) <= idx:
                        curr.append({}) # Default to object if not specified
                    curr = curr[idx]
                except (ValueError, IndexError):
                    return None
            else: return None

        last_key = keys[-1]
        
        if isinstance(curr, dict):
            curr[last_key] = value
        elif isinstance(curr, list):
            try:
                idx = int(last_key)
                if idx == len(curr):
                    curr.append(value)
                elif 0 <= idx < len(curr):
                    curr[idx] = value
                else: return None
            except: return None
        else: return None

        if self._save_data(name, data):
            return data
        return None

    def rename_key(self, name, old_key, new_key):
        """Renames a key (supports dot notation) for an existing JSON object."""
        data = self.load(name)
        if not data:
            return None

        def get_and_del(obj, path):
            keys = path.split('.')
            curr = obj
            for k in keys[:-1]:
                if k not in curr or not isinstance(curr[k], dict): return None, False
                curr = curr[k]
            if keys[-1] in curr:
                val = curr.pop(keys[-1])
                return val, True
            return None, False

        def set_nested(obj, path, val):
            keys = path.split('.')
            curr = obj
            for k in keys[:-1]:
                if k not in curr or not isinstance(curr[k], dict):
                    curr[k] = {}
                curr = curr[k]
            curr[keys[-1]] = val

        value, found = get_and_del(data, old_key)
        if found:
            set_nested(data, new_key, value)
            if self._save_data(name, data):
                return data
        return None
    def delete(self, name, key, silent=False):
        """Deletes a key from the JSON object."""
        data = self.load(name)
        if not data:
            if not silent: log.error(f"Cannot delete from '{name}', as it could not be loaded.")
            return None

        # Handle nested deletion
        if '.' in key:
            keys = key.split('.')
            curr = data
            for i, k in enumerate(keys[:-1]):
                if isinstance(curr, dict):
                    if k not in curr: return data
                    curr = curr[k]
                elif isinstance(curr, list):
                    try:
                        idx = int(k)
                        if 0 <= idx < len(curr):
                            curr = curr[idx]
                        else: return data
                    except ValueError: return data
                else: return data
            
            last_key = keys[-1]
            if isinstance(curr, dict):
                if last_key in curr:
                    del curr[last_key]
            elif isinstance(curr, list):
                try:
                    idx = int(last_key)
                    if 0 <= idx < len(curr):
                        curr.pop(idx)
                except ValueError: pass
        elif key in data:
            del data[key]
        else:
            if not silent: log.warning(f"Key '{key}' not found in {name}.")
            return data

        if self._save_data(name, data):
            return data
        return None

    def reorder(self, name, target_path, new_index):
        """
        Reorders a key in a dict or an item in a list.
        Supports dot notation (e.g., 'subdomains.0' or 'ssl_info.subject').
        """
        data = self.load(name)
        if not data: return None

        keys = target_path.split('.')
        
        # Traverse to the parent container
        parent = data
        container_path = keys[:-1]
        for k in container_path:
            if isinstance(parent, dict) and k in parent:
                parent = parent[k]
            elif isinstance(parent, list):
                try: parent = parent[int(k)]
                except: return None
            else: return None

        last_key = keys[-1]

        if isinstance(parent, dict):
            if last_key not in parent: return None
            items = list(parent.items())
            idx = next((i for i, (k, v) in enumerate(items) if k == last_key), -1)
            if idx == -1: return None
            item = items.pop(idx)
            new_index = max(0, min(new_index, len(items)))
            items.insert(new_index, item)
            # Replace dict in parent
            parent.clear()
            parent.update(dict(items))
        elif isinstance(parent, list):
            try:
                idx = int(last_key)
                if idx < 0 or idx >= len(parent): return None
                item = parent.pop(idx)
                new_index = max(0, min(new_index, len(parent)))
                parent.insert(new_index, item)
            except: return None
        else: return None

        if self._save_data(name, data):
            return data
        return None

    def destroy(self, name):
        """Completely deletes the JSON file of an object."""
        path = self._get_entity_path(name)
        if not self.exists(name):
            return False

        try:
            folder_path = os.path.dirname(path)
            os.remove(path)
            # Sync the directory to make the deletion visible across processes.
            # This is crucial for the web UI to see the change immediately.
            dir_fd = os.open(folder_path, os.O_RDONLY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
            log.info(f"Object '{name}' and its file '{path}' have been deleted.")
            return True
        except Exception as e:
            log.error(f"Error deleting file '{path}': {e}")
            return False

    def _cmd_rename(self, args, cli):
        """Handles the 'rename' subcommand."""
        old_name = args.old_name
        new_name = args.new_name
        
        # Perform the rename operation
        success = self.rename(old_name, new_name)
        
        # If successful, update the session if the renamed entity was loaded
        if success and cli.session:
            # Check all relevant session attributes and update if the renamed entity was loaded
            for attr in ['target', 'tool', 'wordlist', 'report']: # Added 'report'
                if hasattr(cli.session, attr) and getattr(cli.session, attr) == old_name:
                    setattr(cli.session, attr, new_name)
                    log.info(f"Active session has been updated: {attr} '{old_name}' -> '{new_name}'.")

    def _cmd_add(self, args, cli):
        entity_type = self._get_entity_type()
        created = self.create(args.name)
        if created:
            log.success(f"{entity_type} '{args.name}' added.")
        return created

    def _cmd_copy(self, args, cli):
        """Handles the 'copy' subcommand."""
        source_name = args.source_name
        dest_name = args.dest_name
        self.copy(source_name, dest_name)

    def _cmd_update(self, args, cli):
        entity_type = self._get_entity_type()
        
        field = args.field
        # --- FIX: Join with comma if field is 'tags', otherwise with space ---
        if field.lower() == 'tags':
            value = ",".join(args.value) if args.value else ""
        else:
            value = " ".join(args.value) if args.value else ""  # Join REMAINDER back together
        
        # --- FIX: Prevent accidental renames with complex values ---
        if field.lower() == 'name':
            if ' ' in value.strip():
                log.error(f"Cannot rename {entity_type} to a name with spaces: '{value}'")
                log.prompt(f"Use '{entity_type.lower()} rename <old_name> <new_name>' with a single-word new name.")
            else:
                self.rename(args.name, value)
        else:
            self.update(args.name, field, value)
            log.success(f"{entity_type} '{args.name}' field '{field}' updated -> {value}")
        
    def _cmd_delete(self, args, cli):
        entity_type = self._get_entity_type()
        if args.field:
            # Behavior as before: delete a field
            if self.delete(args.name, args.field):
                log.success(f"{entity_type} '{args.name}' field '{args.field}' deleted.")
        else:
            # New behavior: delete the whole object (like 'destroy')
            if self.destroy(args.name):
                log.success(f"{entity_type} '{args.name}' has been completely deleted.")

    def _cmd_destroy(self, args, cli):
        entity_type = self._get_entity_type()
        if self.destroy(args.name):
            log.success(f"{entity_type} '{args.name}' has been completely deleted.")
        else:
            log.error(f"Error deleting {entity_type} '{args.name}'. See log for details.")

    def _cmd_list(self, args, cli):
        entity_type = self._get_entity_type()
        plural_map = {"Target": "Targets", "Tool": "Tools", "Wordlist": "Wordlists", "Preset": "Presets"}
        entity_type_plural = plural_map.get(entity_type, f"{entity_type}s")

        items = self.list_all()
        if not items:
            log.info(f"No {entity_type_plural} found.")
            return

        from rich.text import Text
        items = sorted(items, key=lambda x: (1 if x.startswith("hub/") else 0, x))
        
        output = []
        for item in items:
            data = self.load(item)
            is_hub = item.startswith("hub/")
            origin_tag = "[blue][L][/blue]"
            display_name = item
            
            if is_hub:
                parts = item.split("/")
                origin = parts[1].replace("_", ":")
                origin_tag = f"[cyan][H][/cyan]"
                base_name = parts[-1]
                prefix = "/".join(parts[:-1])
                display_name = f"[dim]{prefix}/[/dim][bold yellow]{base_name}[/bold yellow] [dim](@{origin})[/dim]"
            else:
                display_name = f"[bold green]{item}[/bold green]"

            # Row 1: [Tag] Name - Description
            desc = data.get('description', '') if data else ""
            author = data.get('author', '') if data else ""
            author_part = f" [dim](by {author})[/dim]" if author else ""
            desc_part = f" - [italic grey50]{desc}[/italic grey50]" if desc else ""
            output.append(Text.from_markup(f" {origin_tag} {display_name}{author_part}{desc_part}"))
            
            # --- NEU: Tags Reihe ---
            tags_raw = data.get('tags', '') if data else ''
            if isinstance(tags_raw, str) and tags_raw:
                tags_list = [t.strip() for t in tags_raw.split(',') if t.strip()]
            elif isinstance(tags_raw, list):
                tags_list = tags_raw
            else:
                tags_list = []
            if tags_list:
                tag_str = " ".join([f"[cyan]#{t}[/cyan]" for t in tags_list])
                output.append(Text.from_markup(f"     [dim]• Tags: {tag_str}[/dim]"))

            # Row 2: Secondary info (e.g. Rules for parsers)
            if entity_type == "Parser" and data:
                rules = data.get('rules', [])
                if isinstance(rules, dict):
                    rule_names = ", ".join(rules.keys())
                elif isinstance(rules, list):
                    rule_names = ", ".join([r.get('name', 'unnamed') for r in rules if isinstance(r, dict)])
                else:
                    rule_names = ""
                
                if rule_names:
                    output.append(Text.from_markup(f"     [dim]• Rules: {rule_names}[/dim]"))

            # Empty spacer
            output.append(Text(""))

        cli.console.print(Panel(Group(*output), title=f"Available {entity_type_plural}", border_style="dim", expand=True))

    def _cmd_load(self, args, cli):
        entity_type = self._get_entity_type()
        if args.name in self.list_all():
            # e.g., 'target', 'tool', 'wordlist'
            setattr(cli.session, cli.last_command, args.name)
            log.success(f"{entity_type} '{args.name}' loaded into active session '{cli.session.name}'.")
        else:
            log.error(f"{entity_type} '{args.name}' not found.")

    def _cmd_show(self, args, cli):
        entity_type = self._get_entity_type()
        entity = self.load(args.name)
        if not entity:
            log.error(f"{entity_type} '{args.name}' not found.")
            return

        if args.field:
            value = entity.get(args.field)
            cli.poutput(value if value is not None else f"Field '{args.field}' not found.")
        else:
            # The _format_and_show_entity method of the respective manager is responsible for the complete display including the title.
            self._format_and_show_entity(entity, cli.console)

    def _cmd_unload(self, args, cli):
        """Handles the 'unload' subcommand for entities that can be loaded into a session."""
        # Determine if 'force' was used. The 'name' argument will hold the entity name,
        # and 'force' will be a separate flag.
        force_unload = hasattr(args, 'force') and args.force == 'force'
        entity_type_lower = self._get_entity_type().lower()

        if not hasattr(cli.session, entity_type_lower):
            log.error(f"Session object has no attribute '{entity_type_lower}'. This is a bug.")
            return

        if force_unload:
            # --- FIX: Prioritize the name given in the command for 'force' unload. ---
            # If 'tool unload foo force' is run, args.name will be 'foo'.
            # If 'tool unload force' is run (without a name), args.name will be None.
            item_to_unload_name = args.name

            # If no name was provided with the force command, fall back to the currently loaded item.
            if not item_to_unload_name:
                item_to_unload_name = getattr(cli.session, entity_type_lower)

            if not item_to_unload_name:
                log.error(f"No {entity_type_lower} specified and none is loaded in the current session to identify what to unload globally.")
                return

            unloaded_count = 0
            for session_obj in cli.session_mgr.sessions.values():
                if getattr(session_obj, entity_type_lower) == item_to_unload_name:
                    setattr(session_obj, entity_type_lower, None)
                    unloaded_count += 1
            
            if unloaded_count > 0:
                log.success(f"Force-unloaded {entity_type_lower} '{item_to_unload_name}' from {unloaded_count} session(s).")
            else:
                log.info(f"{entity_type_lower.capitalize()} '{item_to_unload_name}' was not found loaded in any session.")
        else:
            # Unload from current session only.
            # If a name is provided (e.g., 'tool unload foo'), unload that specific one if it's loaded.
            # If no name is provided ('tool unload'), unload whatever is currently loaded.
            item_to_unload = args.name or getattr(cli.session, entity_type_lower)

            if not item_to_unload:
                log.info(f"No {entity_type_lower} specified and none is currently loaded in this session.")
            elif getattr(cli.session, entity_type_lower) == item_to_unload:
                setattr(cli.session, entity_type_lower, None)
                log.success(f"Unloaded {entity_type_lower} '{item_to_unload}' from the current session.")
            else:
                log.warning(f"{entity_type_lower.capitalize()} '{item_to_unload}' is not the one currently loaded in this session.")

    def _format_and_show_entity(self, entity, console):
        """Generic formatting for the details of an entity with rich.panel and rich.table."""
        entity_type = self._get_entity_type()

        data_to_show = entity.copy()
        name = data_to_show.pop('name', 'N/A')

        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column(style="white", no_wrap=True)
        table.add_column(style="green", ratio=1)

        _add_data_to_table_recursively(table, data_to_show)

        console.print(Panel(table, title=f"[bold]{entity_type}: {name}[/bold]", border_style="dim", expand=False))