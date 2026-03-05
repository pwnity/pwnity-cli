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

# tests/test_logbook_manager.py
import pytest
from modules.managers.logbook_manager import LogbookManager
import argparse
from modules.services import config, log

@pytest.fixture
def logbook_manager(tmp_path, monkeypatch):
    """
    Stellt einen sauberen LogbookManager bereit, der in ein temporäres Verzeichnis schreibt.
    """
    logbook_dir = tmp_path / "logbook"
    logbook_dir.mkdir()

    # Leite den Manager auf das temporäre Verzeichnis um
    original_get_parameter = config.get_parameter
    def mock_get_parameter(section, key, fallback=None):
        if section == "DIRS" and key == "LOGBOOK":
            return str(logbook_dir)
        return original_get_parameter(section, key, fallback)
    monkeypatch.setattr(config, 'get_parameter', mock_get_parameter)

    # Logger stummschalten
    import logging
    monkeypatch.setattr(log, 'log_value', logging.CRITICAL + 1)

    return LogbookManager()

@pytest.fixture
def mock_session(mocker):
    """Stellt ein gemocktes Session-Objekt bereit."""
    session = mocker.MagicMock()
    session.name = "test-session"
    session.target = "test-target"
    session.tool = "nmap"
    session.wordlist = None
    return session

def test_create_log_entry(logbook_manager, mock_session):
    """
    Testet, ob ein Log-Eintrag korrekt erstellt und mit den richtigen Daten gespeichert wird.
    """
    entry_id = logbook_manager.create_entry(
        command_str="nmap -sV test.com",
        output="Port 80 is open",
        return_code=0,
        duration=5.12,
        session_obj=mock_session
    )

    assert isinstance(entry_id, str) and len(entry_id) > 10 # Check if it looks like a UUID
    
    # Lade die Daten direkt, um sie zu überprüfen
    data = logbook_manager.load(str(entry_id))
    assert data is not None
    assert data["id"] == entry_id
    assert data["command"] == "nmap -sV test.com"
    assert data["context"]["session"] == "test-session"
    assert data["execution"]["return_code"] == 0
    assert data["output"] == "Port 80 is open"

def test_create_entry_with_job_id(logbook_manager, mock_session):
    """
    Testet, ob die source_job_id korrekt in einem Log-Eintrag gespeichert wird.
    """
    entry_id = logbook_manager.create_entry(
        command_str="sleep 5", output="", return_code=None,
        duration=0, session_obj=mock_session, source_job_id="abc-123"
    )
    data = logbook_manager.load(str(entry_id))
    assert data is not None
    assert data["source_job_id"] == "abc-123"

def test_create_entry_without_session(logbook_manager):
    """
    Testet, ob ein Log-Eintrag korrekt erstellt wird, auch wenn kein Session-Objekt
    übergeben wird (z.B. in einem Workflow).
    """
    entry_id = logbook_manager.create_entry(
        command_str="workflow_cmd", output="out", return_code=0,
        duration=1.0, session_obj=None
    )
    data = logbook_manager.load(str(entry_id))
    assert data is not None
    assert "context" in data
    assert data["context"] == {} # Der Kontext sollte leer sein, aber existieren

def test_show_log_entry(logbook_manager, mock_session, mocker):
    """
    Testet, ob 'logbook show' die korrekten Daten an den DisplayManager übergibt.
    """
    # Erstelle einen Eintrag zum Anzeigen
    entry_id = logbook_manager.create_entry("echo 'test'", "test", 0, 0.1, mock_session)

    # Mocke das CLI-Objekt und seine Manager
    mock_cli = mocker.MagicMock()
    mock_cli.display_mgr = mocker.MagicMock()

    # Führe den 'show'-Befehl aus
    args = type('Args', (), {'id': entry_id})()
    logbook_manager._cmd_show(args, mock_cli)

    # Überprüfe, ob die Anzeigemethode mit den richtigen Argumenten aufgerufen wurde
    mock_cli.display_mgr.display_execution_summary.assert_called_once()
    # Die Methode wird mit Keyword-Argumenten aufgerufen, also müssen wir auf .kwargs zugreifen
    call_kwargs = mock_cli.display_mgr.display_execution_summary.call_args.kwargs
    assert call_kwargs['logbook_id'] == entry_id
    assert call_kwargs['command_str'] == "echo 'test'"

def test_show_nonexistent_entry(logbook_manager, mocker):
    """Testet, ob eine Fehlermeldung geloggt wird, wenn ein Eintrag nicht existiert."""
    mock_log_error = mocker.patch("modules.services.log.error")
    mock_cli = mocker.MagicMock()

    args = type('Args', (), {'id': 999})()
    # With UUIDs, any non-existent string is a valid test case.
    args_uuid = type('Args', (), {'id': 'non-existent-uuid'})()
    logbook_manager._cmd_show(args_uuid, mock_cli)

    mock_log_error.assert_called_with("Logbook entry with ID non-existent-uuid not found.")

def test_list_log_entries(logbook_manager, mock_session, mocker):
    """
    Testet, ob 'logbook list' eine Tabelle mit den korrekten Einträgen anzeigt.
    """
    # Erstelle einige Einträge
    logbook_manager.create_entry("cmd1", "out1", 0, 1, mock_session) # type: ignore
    logbook_manager.create_entry("cmd2", "out2", 1, 2, mock_session) # type: ignore

    mock_cli = mocker.MagicMock()
    mock_cli.console = mocker.MagicMock()

    # Simulate the args object that argparse would create, including the default limit.
    logbook_manager._cmd_list(args=argparse.Namespace(limit=0), cli=mock_cli)

    # Überprüfe, ob eine Tabelle gedruckt wurde
    mock_cli.console.print.assert_called_once()
    call_args, _ = mock_cli.console.print.call_args
    panel = call_args[0]
    assert "Execution Logbook" in panel.title
    table = panel.renderable
    assert len(table.rows) == 2

def test_list_log_entries_empty(logbook_manager, mocker):
    """Testet, ob 'logbook list' eine Info-Nachricht anzeigt, wenn keine Logs vorhanden sind."""
    mock_log_info = mocker.patch("modules.services.log.info")
    mock_cli = mocker.MagicMock()

    # Simulate the args object that argparse would create.
    logbook_manager._cmd_list(args=argparse.Namespace(limit=0), cli=mock_cli)
    mock_log_info.assert_called_with("No matching logbook entries found.")

def test_load_corrupt_entry(logbook_manager, tmp_path, mocker):
    """Testet, ob das Laden einer beschädigten Log-Datei fehlschlägt und einen Fehler loggt."""
    (tmp_path / "logbook" / "1.json").write_text("{'invalid-json':,}")
    mock_log_error = mocker.patch("modules.services.log.error")

    result = logbook_manager.load("1")
    assert result is None
    # The error message from the manager wraps the path in single quotes.
    # We need to match that format exactly.
    expected_msg = f"Failed to decode JSON for '1' from '{tmp_path / 'logbook' / '1.json'}': Expecting property name enclosed in double quotes: line 1 column 2 (char 1)"
    mock_log_error.assert_called_with(expected_msg)