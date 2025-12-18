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

# tests/test_display_manager.py
import pytest
import os
from modules.managers.display_manager import DisplayManager
from rich.console import Console
from rich.panel import Panel
from rich.columns import Columns
from rich.table import Table
from rich.text import Text
from modules.services import log # Import log to mock it

@pytest.fixture
def mock_console(mocker):
    """Stellt eine gemockte rich Console bereit."""
    mock = mocker.MagicMock(spec=Console)
    mock.width = 120  # Eine realistische Breite für Layout-Tests

    # Erstelle eine echte Konsole, um ihre Render-Fähigkeiten zu nutzen,
    # aber leite die Ausgabe ins Nichts um.
    real_console = Console(file=open(os.devnull, 'w'))
    # Binde die echte Render-Methode an den Mock
    mock.render = real_console.render
    return mock

@pytest.fixture
def display_manager(mock_console):
    """Stellt eine DisplayManager-Instanz mit einer gemockten Konsole bereit."""
    return DisplayManager(console=mock_console)

@pytest.fixture
def mock_cli_for_overview(mocker):
    """Provides a mock CLI instance with all necessary managers and data for overview tests."""
    cli = mocker.MagicMock()
    cli.session = mocker.MagicMock()
    cli.session.name = "test-session"
    cli.session.target = "test-target"
    cli.session.tool = "nmap"
    cli.session.wordlist = "common"
    cli.session.report = "test-report"

    cli.target_mgr.load.return_value = {"name": "test-target", "ip": "1.1.1.1"}
    cli.tool_mgr.load.return_value = {"name": "nmap", "commands": [{"name": "scan"}]}
    cli.wordlist_mgr.load.return_value = {"name": "common", "path": "/path/to/common.txt"}
    cli.profile_mgr.load.return_value = {"lhost": "10.10.14.5"}
    cli.proxy_mgr.get_effective_config.return_value = {"type": "http", "host": "127.0.0.1"}
    cli.report_mgr.load.return_value = {"name": "test-report", "notes": [{"text": "a note"}], "loot": [], "findings": [], "history": []}
    mocker.patch("modules.services.log.get_history", return_value=["log message 1", "log message 2"])
    return cli

def test_display_jobs_list(display_manager, mock_console, mocker):
    """
    Testet, ob die Job-Liste korrekt als Tabelle mit den richtigen Stilen angezeigt wird.
    """
    # Erstelle einige Mock-Jobs mit unterschiedlichen Status
    job1 = mocker.MagicMock(id=1, session_name="sess1", status="running", duration=10.5, command_str="sleep 10")
    job2 = mocker.MagicMock(id=2, session_name="sess2", status="finished", duration=2.1, command_str="echo 'done'")
    jobs = [job1, job2]

    display_manager.display_jobs_list(jobs)

    # Überprüfe, ob `console.print` mit einem Panel aufgerufen wurde, das eine Tabelle enthält
    mock_console.print.assert_called_once()
    call_args, _ = mock_console.print.call_args
    printed_panel = call_args[0]

    assert isinstance(printed_panel, Panel)
    table = printed_panel.renderable
    assert isinstance(table, Table)
    assert len(table.rows) == 2
    # Überprüfe, ob die Status-Stile korrekt angewendet werden (rich verwendet Markup)
    # Wir können nicht direkt die gerenderte Ausgabe prüfen, aber wir können die Zelleninhalte prüfen
    # .cells ist ein Generator, wir müssen ihn in eine Liste umwandeln.
    running_cell_text = list(table.columns[2].cells)[0]
    assert "Running" in running_cell_text and "bold green" in running_cell_text

def test_display_jobs_list_empty(display_manager, mock_console, mocker):
    """
    Testet, ob eine informative Nachricht geloggt wird, wenn die Job-Liste leer ist.
    """
    mock_log_info = mocker.patch("modules.services.log.info")
    display_manager.display_jobs_list([])

    # Es sollte eine Nachricht geloggt und nichts an die Konsole gedruckt werden.
    mock_log_info.assert_called_once_with("No active or finished jobs.")
    mock_console.print.assert_not_called()

def test_display_execution_summary_success(display_manager, mock_console):
    """
    Testet, ob eine erfolgreiche Ausführungszusammenfassung korrekt angezeigt wird.
    """
    display_manager.display_execution_summary(
        title="Test Summary",
        status_text="Success",
        status_style="bold green",
        return_code=0,
        duration=5.123,
        command_str="test command",
        logbook_id=101
    )

    mock_console.print.assert_called_once()
    call_args, _ = mock_console.print.call_args
    panel = call_args[0]

    assert isinstance(panel, Panel)
    assert panel.border_style == "green" # Die Rahmenfarbe sollte dem Status entsprechen
    # .cells ist ein Generator, wir müssen ihn in eine Liste umwandeln.
    assert "Logbook ID" in list(panel.renderable.columns[0].cells) # Überprüfe, ob die Zeile existiert

def test_display_execution_summary_failure(display_manager, mock_console):
    """
    Testet, ob eine fehlgeschlagene Ausführungszusammenfassung korrekt angezeigt wird.
    """
    display_manager.display_execution_summary(
        title="Test Failure",
        status_text="Failed",
        status_style="bold red",
        return_code=1,
        duration=2.0,
        command_str="failing command"
    )

    mock_console.print.assert_called_once()
    panel = mock_console.print.call_args[0][0]
    assert panel.border_style == "red" # Rahmenfarbe sollte rot sein

def test_display_hash_identification(display_manager, mock_console):
    """
    Testet die Anzeige der Hash-Identifikation für bekannte und unbekannte Hashes.
    """
    # Fall 1: Bekannter Hash
    display_manager.display_hash_identification("5f4dcc3b5aa765d61d8327deb882cf99", ["MD5", "NTLM"])
    panel1 = mock_console.print.call_args_list[0][0][0]
    # Um den Textinhalt zu erhalten, müssen wir die Render-Methode simulieren
    text_content1 = "".join(segment.text for segment in mock_console.render(panel1.renderable))
    assert panel1.border_style == "green"
    assert "MD5, NTLM" in text_content1

    # Fall 2: Unbekannter Hash
    display_manager.display_hash_identification("not-a-hash", [])
    panel2 = mock_console.print.call_args_list[1][0][0]
    text_content2 = "".join(segment.text for segment in mock_console.render(panel2.renderable))
    assert panel2.border_style == "red"
    assert "Unknown" in text_content2

def test_display_simple_list(display_manager, mock_console):
    """
    Testet, ob eine einfache Liste korrekt als Panel mit Aufzählungspunkten angezeigt wird.
    """
    items = ["item1", "item2", "item3"]
    display_manager.display_simple_list(items, "Test List")

    mock_console.print.assert_called_once()
    panel = mock_console.print.call_args[0][0]
    assert isinstance(panel, Panel)
    assert "• item1" in str(panel.renderable)
    assert "• item2" in str(panel.renderable)

def test_display_overview_verbose(display_manager, mock_console, mock_cli_for_overview):
    """
    Testet die detaillierte (verbose) Übersichtsanzeige.
    """
    args = type('Args', (), {'short': False})()
    display_manager.do_overview(args, mock_cli_for_overview)

    # Überprüfe, ob die Haupt-Panels gedruckt wurden.
    # Die genaue Anzahl der Aufrufe kann variieren, aber wir prüfen die wichtigsten.
    print_calls = mock_console.print.call_args_list
    assert len(print_calls) > 2 # Titel, Target-Panel, Sub-Columns, Report-Panel, Log-Panel

    # Überprüfe, ob die display_overview-Methode aufgerufen wurde (die jetzt intern ist)
    # Wir können dies tun, indem wir sie für den Test mocken.
    # In diesem Fall ist es einfacher, einfach zu prüfen, ob die Ausgabe wie erwartet aussieht.
    assert any("Session Overview" in str(call) for call in print_calls)

def test_display_overview_short(display_manager, mock_console, mock_cli_for_overview):
    """
    Testet die kompakte (short) Übersichtsanzeige.
    """
    args = type('Args', (), {'short': True})()
    display_manager.do_overview(args, mock_cli_for_overview)

    # Im Short-Modus werden Target und Sub-Columns in einem einzigen Columns-Objekt gedruckt.
    columns_call = mock_console.print.call_args_list[1]
    assert isinstance(columns_call[0][0], Columns)

def test_display_proxy_status(display_manager, mock_console):
    """
    Testet die Anzeige des Proxy-Status.
    """
    global_settings = {"ENABLED": "true", "HOST": "global.proxy", "PORT": "8080"}
    session_settings = {"host": "session.proxy"}
    effective_config = {"host": "session.proxy", "port": "8080"}

    display_manager.display_proxy_status(global_settings, session_settings, effective_config)

    # Es sollten zwei Panels gedruckt werden (Effective und Details)
    assert mock_console.print.call_count == 2
    
    # Überprüfe das erste Panel (Effective Configuration)
    effective_panel = mock_console.print.call_args_list[0][0][0]
    assert isinstance(effective_panel, Panel)
    assert "Effective Configuration" in effective_panel.title

    # Überprüfe das zweite Panel (Configuration Details)
    details_panel = mock_console.print.call_args_list[1][0][0]
    assert isinstance(details_panel, Panel)
    assert "Configuration Details" in details_panel.title

def test_display_job_output(display_manager, mock_console, mocker):
    """
    Testet die Anzeige der Ausgabe eines einzelnen Jobs.
    """
    job = mocker.MagicMock(id=1, output="Line 1\nLine 2", status="finished", return_code=0, duration=1.23, command_str="echo test", session_name="test-session")
    
    # Mocke die display_execution_summary, da sie separat getestet wird
    mock_display_summary = mocker.patch.object(display_manager, 'display_execution_summary')

    display_manager.display_job_output(job)

    # Überprüfe, ob die Regeln und die Ausgabe gedruckt wurden
    assert mock_console.rule.call_count == 2
    mock_console.file.write.assert_called_with("Line 1\nLine 2")
    
    # Überprüfe, ob die Zusammenfassung am Ende aufgerufen wurde
    mock_display_summary.assert_called_once()

def test_display_session_list(display_manager, mock_console):
    """
    Testet die Anzeige der Session-Liste.
    """
    sessions = ["default", "project-x", "test-session"]
    active_session = "project-x"

    display_manager.display_session_list(sessions, active_session)

    mock_console.print.assert_called_once()
    panel = mock_console.print.call_args[0][0]
    assert isinstance(panel, Panel)
    # Überprüfe, ob die aktive Session korrekt markiert ist
    assert "project-x (active)" in str(panel.renderable)
    assert "default" in str(panel.renderable)

def test_display_findings(display_manager, mock_console):
    """Testet die Anzeige von Parser-Findings."""
    findings = {"open_ports": ["80", "443"], "hostnames": ["test.local"]}
    display_manager.display_findings(findings, "Test Parser Results")

    mock_console.print.assert_called_once()
    panel = mock_console.print.call_args[0][0]
    assert isinstance(panel, Panel)
    assert "Test Parser Results" in panel.title
    assert "3 total matches" in panel.title