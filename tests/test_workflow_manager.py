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

# tests/test_workflow_manager.py
import pytest
import os
import json
from modules.managers import workflow_manager as workflow_manager_module
import importlib
from modules.services import config, log

@pytest.fixture
def workflow_manager(tmp_path, monkeypatch):
    """
    Stellt einen sauberen WorkflowManager bereit, der in ein temporäres Verzeichnis schreibt.
    """
    workflows_dir = tmp_path / "workflows"
    workflows_dir.mkdir()

    # --- FIX: Patch the config service to point to the temporary directory ---
    # The WorkflowManager reads its path from the config service upon initialization.
    # We intercept the call for the 'WORKFLOWS' directory and return our temp path.
    original_get_parameter = config.get_parameter
    def mock_get_parameter(section, key, fallback=None):
        if section == "DIRS" and key == "WORKFLOWS":
            return str(workflows_dir)
        return original_get_parameter(section, key, fallback)
    monkeypatch.setattr(config, 'get_parameter', mock_get_parameter)

    # Logger stummschalten
    import logging
    monkeypatch.setattr(log, 'log_value', logging.CRITICAL + 1)

    # --- FINAL FIX: Reload the module to apply the patched config ---
    # The WorkflowManager reads its folder path upon module import. To ensure it uses
    # our patched temporary path for the test, we must reload the entire module
    # *after* the monkeypatch has been applied.
    importlib.reload(workflow_manager_module) # Reload the module to pick up the patched config
    return workflow_manager_module.WorkflowManager() # Instantiate the class from the reloaded module

@pytest.fixture
def mock_cli_for_workflow(mocker):
    """Provides a mock CLI instance for workflow tests."""
    cli = mocker.MagicMock()
    cli.session = mocker.MagicMock()
    cli.help_mgr = mocker.MagicMock()
    cli.console = mocker.MagicMock()
    return cli

def test_workflow_create_and_list(workflow_manager):
    """
    Testet, ob ein Workflow korrekt erstellt und in der Liste angezeigt wird.
    """
    workflow_name = "my-first-workflow"
    assert workflow_manager.exists(workflow_name) is False

    # Simuliere den Aufruf von `workflow add my-first-workflow`
    args = type('Args', (), {'name': workflow_name})()
    workflow_manager._cmd_add(args, cli=None)

    assert workflow_manager.exists(workflow_name) is True
    assert workflow_name in workflow_manager.list_all()

def test_workflow_destroy(workflow_manager, tmp_path):
    """
    Testet, ob ein Workflow und seine Datei korrekt gelöscht werden.
    """
    workflow_name = "to-be-deleted"
    workflow_manager.create(workflow_name)
    assert workflow_manager.exists(workflow_name) is True

    # Simuliere den Aufruf von `workflow destroy to-be-deleted`
    args = type('Args', (), {'name': workflow_name})()
    workflow_manager._cmd_destroy(args, cli=None)

    assert workflow_manager.exists(workflow_name) is False
    expected_file = tmp_path / "workflows" / f"{workflow_name}.json"
    assert not expected_file.exists()

def test_dispatch_shows_help_if_no_subcommand(workflow_manager, mock_cli_for_workflow):
    """
    Tests that the dispatch method calls the help manager if no subcommand is provided.
    """
    workflow_manager.dispatch(subcommand=None, args=None, cli_instance=mock_cli_for_workflow)
    mock_cli_for_workflow.help_mgr.show_help_workflow.assert_called_once()