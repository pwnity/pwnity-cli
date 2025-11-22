# tests/test_report_manager.py
import pytest
import os
from modules.managers.report_manager import ReportManager
import argparse
from modules.cli_sessions import CLISession
from modules.services import config, log

@pytest.fixture
def report_manager(tmp_path, monkeypatch):
    """
    Stellt einen sauberen ReportManager bereit, der in ein temporäres Verzeichnis schreibt.
    """
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()

    # Leite den Manager auf das temporäre Verzeichnis um
    original_get_parameter = config.get_parameter
    def mock_get_parameter(section, key, fallback=None):
        if section == "DIRS" and key == "REPORTS":
            return str(reports_dir)
        if section == "DIRS" and key == "EXPORTS":
            return str(tmp_path / "exports")
        return original_get_parameter(section, key, fallback)
    monkeypatch.setattr(config, 'get_parameter', mock_get_parameter)

    # Logger stummschalten
    import logging
    monkeypatch.setattr(log, 'log_value', logging.CRITICAL + 1)

    return ReportManager()

@pytest.fixture
def mock_cli(mocker):
    """
    Stellt ein gemocktes CLI-Objekt mit einer Session bereit.
    """
    cli = mocker.MagicMock()
    cli.session = CLISession("test-session")
    cli.last_command = "note" # Set a default for testing
    return cli

def test_report_create_and_load_unload(report_manager, mock_cli):
    """Testet das Erstellen, Laden und Entladen eines Reports."""
    report_name = "project-x"
    report_manager.create(report_name)
    assert report_manager.exists(report_name)

    # 1. Laden
    load_args = type('Args', (), {'name': report_name})()
    report_manager._cmd_load(load_args, mock_cli)
    assert mock_cli.session.report == report_name

    # 2. Entladen
    unload_args = type('Args', (), {})()
    report_manager._cmd_unload(unload_args, mock_cli)
    assert mock_cli.session.report is None

def test_add_history_and_findings(report_manager):
    """Testet das Hinzufügen von History-Einträgen und Parser-Findings."""
    report_name = "data-agg-report"
    report_manager.create(report_name)

    # 1. History-Eintrag hinzufügen
    report_manager.add_history_entry(report_name, "nmap -sV", 1, "nmap", "version-scan")
    data = report_manager.load(report_name)
    assert len(data["history"]) == 1
    assert data["history"][0]["command"] == "nmap -sV"

    # 2. Findings hinzufügen
    findings = {"open_ports": ["80", "443"]}
    report_manager.add_findings(report_name, 2, "nmap-parser", "target1", findings)
    data = report_manager.load(report_name)
    assert len(data["findings"]) == 2
    assert data["findings"][0]["category"] == "open_ports"

    # 3. Gleiche Findings erneut hinzufügen (sollte keine Duplikate erzeugen)
    report_manager.add_findings(report_name, 2, "nmap-parser", "target1", findings)
    data = report_manager.load(report_name)
    assert len(data["findings"]) == 2 # Anzahl sollte gleich bleiben

def test_notes_and_loot_workflow(report_manager, mock_cli):
    """Testet den kompletten CRUD-Zyklus für Notizen und Loot."""
    report_name = "notes-loot-report"
    report_manager.create(report_name)
    mock_cli.session.report = report_name # Report in Session laden

    # --- Notizen ---
    # 1. Hinzufügen
    add_note_args = type('Args', (), {'text': "Found admin panel".split()})()
    report_manager._cmd_add_note(add_note_args, mock_cli)
    data = report_manager.load(report_name)
    assert len(data["notes"]) == 1
    assert data["notes"][0]["text"] == "Found admin panel"

    # 2. Löschen
    delete_note_args = type('Args', (), {'index': 1})()
    report_manager._cmd_delete_note(delete_note_args, mock_cli)
    data = report_manager.load(report_name)
    assert len(data["notes"]) == 0

    # --- Loot ---
    # 1. Hinzufügen
    add_loot_args = type('Args', (), {'type': 'credential', 'value': "user:pass".split()})()
    report_manager._cmd_add_loot(add_loot_args, mock_cli)
    data = report_manager.load(report_name)
    assert len(data["loot"]) == 1
    assert data["loot"][0]["value"] == "user:pass"

    # 2. Löschen
    delete_loot_args = type('Args', (), {'index': 1})()
    report_manager._cmd_delete_loot(delete_loot_args, mock_cli)
    data = report_manager.load(report_name)
    assert len(data["loot"]) == 0

def test_report_export_and_render(report_manager, mock_cli, tmp_path):
    """Testet die Export- und Render-Funktionen."""
    report_name = "export-render-report"
    report_manager.create(report_name)
    mock_cli.session.report = report_name

    # Füge einige Daten hinzu
    report_manager._cmd_add_note(type('Args', (), {'text': "Test note".split()})(), mock_cli)
    report_manager._cmd_add_loot(type('Args', (), {'type': 'flag', 'value': "THM{...}".split()})(), mock_cli)

    # --- Export testen ---
    captured_output = []
    mock_cli.poutput.side_effect = lambda x: captured_output.append(x)
    export_args = type('Args', (), {'name': report_name})()
    report_manager._cmd_export(export_args, mock_cli)
    
    full_output = "\n".join(captured_output)
    assert f"report add {report_name}" in full_output
    assert f"report load {report_name}" in full_output
    assert "note add 'Test note'" in full_output
    assert "loot add flag 'THM{...}'" in full_output

    # --- Render testen ---
    render_args = type('Args', (), {'name': report_name, 'output_file': None})()
    report_manager._cmd_render(render_args, mock_cli)

    # Überprüfe, ob die Markdown-Datei erstellt wurde
    expected_file = tmp_path / "exports" / "reports" / f"{report_name}.md"
    assert expected_file.is_file()
    content = expected_file.read_text()
    assert "## Notes" in content
    assert "## Loot" in content
    assert "Test note" in content
    assert "THM{...}" in content

def test_report_file_view(report_manager, mock_cli, tmp_path):
    """Testet das Anzeigen einer Datei, die im Report-Verzeichnis gespeichert ist."""
    report_name = "file-view-report"
    report_manager.create(report_name)
    mock_cli.session.report = report_name

    # Erstelle eine Dummy-Datei im Report-Verzeichnis
    report_dir = tmp_path / "reports" / report_name
    report_dir.mkdir(exist_ok=True)
    dummy_file = report_dir / "scan.txt"
    dummy_file.write_text("Port 80 is open")

    # Mocke die `console.print`-Methode, um die Ausgabe abzufangen
    captured_panel = None
    def capture_print(panel):
        nonlocal captured_panel
        captured_panel = panel
    mock_cli.console.print = capture_print

    # Führe den `view`-Befehl aus
    # Simuliert den Aufruf 'report view scan.txt', wobei 'scan.txt' zu arg1 wird.
    view_args = type('Args', (), {'arg1': "scan.txt", 'arg2': None})()
    report_manager._cmd_view(view_args, mock_cli)

    # Überprüfe, ob das Panel mit dem korrekten Inhalt "gedruckt" wurde
    assert captured_panel is not None
    # Die genaue Struktur des Panels zu prüfen ist komplex, aber wir können den Inhalt prüfen.
    # `rich` macht es schwer, den reinen Text zu extrahieren, aber dieser Ansatz funktioniert.
    text_content = "".join(segment.text for segment in captured_panel.renderable.render(mock_cli.console))
    assert "Port 80 is open" in text_content

def test_note_and_loot_commands_fail_without_loaded_report(report_manager, mock_cli, mocker):
    """
    Tests that note and loot commands fail gracefully if no report is loaded in the session.
    """
    # Ensure no report is loaded
    mock_cli.session.report = None
    mock_log_error = mocker.patch("modules.services.log.error")

    # Test note add
    report_manager._cmd_add_note(type('Args', (), {'text': "test".split()})(), mock_cli)
    mock_log_error.assert_called_with("No report loaded. Notes can only be managed when a report is loaded.")

    # Test loot add
    report_manager._cmd_add_loot(type('Args', (), {'type': 'flag', 'value': "test".split()})(), mock_cli)
    mock_log_error.assert_called_with("No report loaded. Loot can only be managed when a report is loaded.")

def test_dispatch_routes_note_and_loot(report_manager, mock_cli, mocker):
    """Tests that the dispatch method correctly routes note and loot subcommands."""
    # Mock the underlying handler to verify it gets called
    mock_add_note = mocker.patch.object(report_manager, '_cmd_add_note')
    mock_add_loot = mocker.patch.object(report_manager, '_cmd_add_loot')

    # Simulate 'note add ...'
    mock_cli.last_command = "note"
    args = argparse.Namespace(subcommand="add", text="test note")
    report_manager.dispatch("add", args, mock_cli)
    mock_add_note.assert_called_once_with(args, mock_cli)

    # Simulate 'loot add ...'
    mock_cli.last_command = "loot"
    args = argparse.Namespace(subcommand="add", type="flag", value="test flag")
    report_manager.dispatch("add", args, mock_cli)
    mock_add_loot.assert_called_once_with(args, mock_cli)

def test_delete_with_invalid_index(report_manager, mock_cli, mocker):
    """
    Testet, ob das Löschen von Notizen/Loot mit einem ungültigen Index fehlschlägt.
    """
    report_name = "invalid-index-report"
    report_manager.create(report_name)
    mock_cli.session.report = report_name
    mock_log_error = mocker.patch("modules.services.log.error")

    # Füge eine Notiz hinzu
    add_note_args = type('Args', (), {'text': "A single note".split()})()
    report_manager._cmd_add_note(add_note_args, mock_cli)

    # Versuche, mit ungültigem Index zu löschen
    for invalid_index in [0, -1, 2]:
        delete_args = type('Args', (), {'index': invalid_index})()
        report_manager._cmd_delete_note(delete_args, mock_cli)
        mock_log_error.assert_called_with(f"Invalid index. There are only 1 notes.")

    # Überprüfe, ob die Notiz noch vorhanden ist
    data = report_manager.load(report_name)
    assert len(data["notes"]) == 1

def test_list_files_details(report_manager, tmp_path):
    """
    Testet die `list_files_details` Methode, um sicherzustellen, dass sie
    Dateien und Verzeichnisse korrekt auflistet.
    """
    report_name = "file-list-report"
    report_dir = tmp_path / "reports" / report_name
    report_dir.mkdir()

    # Erstelle Test-Dateien und -Verzeichnisse
    (report_dir / "scan.txt").write_text("content")
    (report_dir / "screenshots").mkdir()
    (report_dir / "screenshots" / "login.png").touch()

    # Führe die Methode aus
    files_details = report_manager.list_files_details(report_name)

    # Überprüfe die Ergebnisse
    assert len(files_details) == 2
    
    scan_txt_info = next((item for item in files_details if item['name'] == 'scan.txt'), None)
    screenshots_dir_info = next((item for item in files_details if item['name'] == 'screenshots'), None)

    assert scan_txt_info is not None
    assert scan_txt_info['type'] == 'file'
    assert scan_txt_info['size'] == 7

    assert screenshots_dir_info is not None
    assert screenshots_dir_info['type'] == 'dir'
    assert screenshots_dir_info['size'] is None