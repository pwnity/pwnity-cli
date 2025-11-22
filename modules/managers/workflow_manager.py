from modules.services import log
import os
import json
import shutil
from .base_manager import BaseManager

class WorkflowManager(BaseManager):
    """
    Manages workflows, including their definition files and history directories.
    Each workflow resides in its own dedicated folder.
    """
    def __init__(self):
        # This is the base directory containing all individual workflow folders.
        from modules.services import config
        self.folder = config.get_parameter("DIRS", "WORKFLOWS", "data/workflows")
        os.makedirs(self.folder, exist_ok=True)

    def _get_workflow_path(self, name: str) -> str:
        return os.path.join(self.folder, name)

    def dispatch(self, subcommand, args, cli_instance):
        """Handles subcommands for the workflow manager."""
        if not subcommand:
            cli_instance.help_mgr.show_help_workflow()
            return True

        # 'run' will be implemented later.
        if subcommand == 'run':
            log.info(f"Running workflow '{args.name}'... (not implemented yet)")
            return True
        
        # Let the parent class handle 'add', 'list', 'show', 'rename', 'destroy', 'delete'
        return super().dispatch(subcommand, args, cli_instance)

    def _cmd_add(self, args, cli):
        """Creates a new workflow with its directory structure."""
        if self.create(args.name):
            log.success(f"Workflow '{args.name}' created successfully.")
            log.prompt("You can now load it in the Web UI to start building.")

    def _cmd_destroy(self, args, cli):
        """Destroys a workflow and its entire history."""
        # This requires interactive confirmation, which we can't do here.
        # For now, we just call the core logic. The UI will handle confirmation.
        if self.destroy(args.name):
            log.success(f"Workflow '{args.name}' and all its history have been deleted.")

    def create(self, name: str) -> bool:
        """Creates the directory structure for a new workflow."""
        workflow_path = self._get_workflow_path(name)
        if os.path.exists(workflow_path):
            log.error(f"A workflow (or directory) named '{name}' already exists.")
            return False
        try:
            history_path = os.path.join(workflow_path, "history")
            os.makedirs(history_path)
            # Create an empty workflow file
            self.save({"name": name, "nodes": [], "links": []})
            return True
        except OSError as e:
            log.error(f"Failed to create directory structure for workflow '{name}': {e}")
            return False

    def destroy(self, name: str) -> bool:
        """Recursively deletes the entire directory for a workflow."""
        workflow_path = self._get_workflow_path(name)
        if not os.path.isdir(workflow_path):
            log.error(f"Workflow directory for '{name}' not found.")
            return False
        try:
            shutil.rmtree(workflow_path)
            return True
        except OSError as e:
            log.error(f"Failed to delete workflow directory '{workflow_path}': {e}")
            return False

    def exists(self, name: str) -> bool:
        """Checks if a workflow directory exists."""
        return os.path.isdir(self._get_workflow_path(name))

    def list_all(self) -> list[str]:
        """Lists all workflows by listing the directories."""
        if not os.path.exists(self.folder):
            return []
        return sorted([d for d in os.listdir(self.folder) if os.path.isdir(os.path.join(self.folder, d))])

    def load(self, name: str):
        """Loads a workflow definition from its JSON file."""
        workflow_path = self._get_workflow_path(name)
        file_path = os.path.join(workflow_path, f"{name}.json")
        if not os.path.isfile(file_path):
            return None
        try:
            with open(file_path, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            log.error(f"Failed to load workflow '{name}': {e}")
            return None

    def save(self, data: dict):
        """
        Saves a workflow. This is a special method for the API to call,
        as it receives the full data blob which includes the name.
        """
        name = data.get('name')
        if not name:
            log.error("Cannot save workflow without a 'name' property in the data.")
            return False

        # --- FIX: Only ensure the base folder exists, not the final workflow path ---
        # The final path component is the workflow name, which should be a directory created by the manager's `create` method.
        os.makedirs(self.folder, exist_ok=True)
        
        # --- FIX: Correctly construct the file path ---
        # The file should be directly in the workflow's own directory.
        file_path = os.path.join(self._get_workflow_path(name), f"{name}.json")
        temp_file_path = file_path + ".tmp"
        try:
            with open(temp_file_path, 'w') as f:
                json.dump(data, f, indent=2)
            os.replace(temp_file_path, file_path)
            return True
        except Exception as e:
            log.error(f"Failed to save workflow '{name}': {e}")
            return False