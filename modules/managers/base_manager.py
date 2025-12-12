# modules/managers/base_manager.py

from modules.services import log, config
import json, os, re
from rich.table import Table
from rich.panel import Panel

class BaseManager:
    """Base class for all managers to provide common functionality."""
    def _get_config_dir(self, key, fallback):
        """
        Gets a directory path from the [DIRS] section of the config,
        with a fallback.
        """
        settings = config.get_section("DIRS")
        return settings.get(key, fallback)

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

def _add_data_to_table_recursively(table: Table, data, indent_level=0):
    """
    Traverses a nested dictionary or list and adds its content as rows to a rich Table,
    creating a clean, indented, tree-like view without JSON syntax.
    """
    indent = "  " * indent_level
    if isinstance(data, dict):
        for key, value in data.items():
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

    def _get_entity_path(self, name: str) -> str:
        """Gibt den vollständigen Pfad zu einer Entitätsdatei zurück, unter Berücksichtigung der Speicherstruktur."""
        sanitized_name = self._sanitize_filename(name)
        if self.use_nested_structure and len(sanitized_name) > 2:
            # Erstellt einen Pfad wie /data/logbook/a/b/ab12...
            nested_dir = os.path.join(self.folder, sanitized_name[0], sanitized_name[1])
            return os.path.join(nested_dir, f"{sanitized_name}.json")
        else:
            # Standard-Verhalten: flache Struktur
            return os.path.join(self.folder, f"{sanitized_name}.json")

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
        Replaces invalid characters with underscores.
        """
        return re.sub(r'[^a-zA-Z0-9_.-]', '_', name)

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
        """Listet alle Entitäten auf, entweder flach oder durch rekursives Durchsuchen."""
        names = []
        if self.use_nested_structure:
            # Rekursives Durchsuchen der Verzeichnisstruktur
            for root, _, files in os.walk(self.folder):
                for file in files:
                    if file.endswith(".json"):
                        names.append(file.replace(".json", ""))
        else:
            names = [f.replace(".json", "") for f in os.listdir(self.folder) if f.endswith(".json")]
        return sorted(names)

    def update(self, name, key, value):
        """Adds or changes a key/value pair in an existing JSON object."""
        # Load the object. This uses the cache or loads from the file.
        data = self.load(name)
        if not data:
            log.error(f"Cannot update '{name}', as it could not be loaded.")
            return None

        data[key] = value
        if self._save_data(name, data):
            return data
        return None

    def delete(self, name, key, silent=False):
        """Deletes a key from the JSON object."""
        # Load the object. This uses the cache or loads from the file.
        data = self.load(name)
        if not data:
            if not silent: log.error(f"Cannot delete from '{name}', as it could not be loaded.")
            return None

        if key in data:
            del data[key]
            if self._save_data(name, data):
                return data
            return None # Indicates save failure
        else:
            if not silent: log.warning(f"Key '{key}' not found in {name}.")
            return data

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

    def _cmd_update(self, args, cli):
        entity_type = self._get_entity_type()
        if len(args.update_args) < 2:
            log.error(f"Invalid update command. Expected: update <name> <field> <value>")
            return
        
        field = args.update_args[0]
        value = " ".join(args.update_args[1:])  # Value can contain spaces
        
        # --- FIX: Prevent accidental renames with complex values ---
        # The 'rename' action should only be triggered if the value is a single, simple word.
        # A value with spaces (like 'foo.bar foo') should not trigger a rename.
        if field.lower() == 'name':
            if ' ' in value.strip():
                log.error(f"Cannot rename {entity_type} to a name with spaces: '{value}'")
                log.prompt(f"Use 'target rename <old_name> <new_name>' with a single-word new name.")
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

        cli.display_mgr.display_simple_list(items, f"Available {entity_type_plural}")

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
        entity_type_lower = self._get_entity_type().lower()
        
        if not hasattr(cli.session, entity_type_lower):
            log.error(f"Session object has no attribute '{entity_type_lower}'. This is a bug.")
            return

        loaded_item = getattr(cli.session, entity_type_lower)
        if not loaded_item:
            log.info(f"No {entity_type_lower} is currently loaded.")
        else:
            log.success(f"Unloaded {entity_type_lower} '{loaded_item}'.")
            setattr(cli.session, entity_type_lower, None)

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