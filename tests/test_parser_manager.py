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

# tests/test_parser_manager.py
import pytest
import argparse
from modules.managers.parser_manager import ParserManager
from modules.services import config, log

@pytest.fixture
def parser_manager(tmp_path, monkeypatch):
    """
    Stellt einen sauberen ParserManager bereit, der in ein temporäres Verzeichnis schreibt.
    """
    parsers_dir = tmp_path / "parsers"
    parsers_dir.mkdir()

    # Leite den Manager auf das temporäre Verzeichnis um
    original_get_parameter = config.get_parameter
    def mock_get_parameter(section, key, fallback=None):
        if section == "DIRS" and key == "PARSERS":
            return str(parsers_dir)
        return original_get_parameter(section, key, fallback)
    monkeypatch.setattr(config, 'get_parameter', mock_get_parameter)

    # Logger stummschalten
    import logging
    monkeypatch.setattr(log, 'log_value', logging.CRITICAL + 1)

    return ParserManager()

@pytest.fixture
def mock_cli_for_parser(mocker):
    """Provides a mock CLI instance with necessary managers for parser tests."""
    cli = mocker.MagicMock()
    cli.session = mocker.MagicMock()
    cli.session.report = "test-report" # Simulate a report being loaded
    cli.session.target = "test-target"
    cli.logbook_mgr = mocker.MagicMock()
    cli.report_mgr = mocker.MagicMock()
    cli.display_mgr = mocker.MagicMock()
    cli.console = mocker.MagicMock()
    cli.help_mgr = mocker.MagicMock() # For dispatch test
    
    cli.logbook_mgr.load.return_value = {"output": "IPs: 1.1.1.1, 2.2.2.2"}
    return cli

def test_parser_create_and_exists(parser_manager):
    """Testet, ob ein Parser korrekt erstellt wird und die Standardstruktur hat."""
    name = "test-parser"
    assert parser_manager.exists(name) is False

    args = type('Args', (), {'name': name})()
    parser_manager._cmd_add(args, cli=None)

    assert parser_manager.exists(name) is True
    data = parser_manager.load(name)
    assert data is not None
    assert data.get("name") == name
    assert "description" in data
    assert "rules" in data and isinstance(data["rules"], list)

def test_parser_update_and_delete_workflow(parser_manager):
    """Testet den kompletten Lebenszyklus von 'update' und 'delete' für Regeln."""
    name = "nmap-parser"
    parser_manager.create(name)

    # 1. Regel hinzufügen
    update_args_add = type('Args', (), {'name': name, 'update_args': ['add-rule', 'open-ports']})()
    parser_manager._cmd_update(update_args_add, cli=None)
    data = parser_manager.load(name)
    assert len(data["rules"]) == 1
    assert data["rules"][0]["name"] == "open-ports"

    # 2. Regex für die Regel setzen
    regex_pattern = r"^(\d+)/tcp\s+open"
    update_args_regex = type('Args', (), {'name': name, 'update_args': ['open-ports', 'regex', regex_pattern]})()
    parser_manager._cmd_update(update_args_regex, cli=None)
    data = parser_manager.load(name)
    assert data["rules"][0]["regex"] == regex_pattern

    # 3. Exclusion-Pattern hinzufügen
    exclude_pattern = r"filtered"
    update_args_exclude = type('Args', (), {'name': name, 'update_args': ['open-ports', 'exclude', exclude_pattern]})()
    parser_manager._cmd_update(update_args_exclude, cli=None)
    data = parser_manager.load(name)
    assert exclude_pattern in data["rules"][0]["exclude_patterns"]

    # 4. Exclusion-Pattern nach Index löschen
    delete_args_exclude = type('Args', (), {'name': name, 'delete_args': ['open-ports', 'exclude', '1']})()
    parser_manager._cmd_delete(delete_args_exclude, cli=None)
    data = parser_manager.load(name)
    assert not data["rules"][0]["exclude_patterns"]

    # 5. Ganze Regel löschen
    delete_args_rule = type('Args', (), {'name': name, 'delete_args': ['open-ports']})()
    parser_manager._cmd_delete(delete_args_rule, cli=None)
    data = parser_manager.load(name)
    assert not data["rules"]

@pytest.mark.parametrize("text_input, regex, excludes, expected_matches", [
    # Einfacher Match
    ("Found IP: 192.168.1.1 and 10.0.0.1", r"(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})", [], ["10.0.0.1", "192.168.1.1"]),
    # Match mit Exclusion
    ("IPs: 192.168.1.1, 127.0.0.1 (localhost)", r"(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})", [r"^127\.0\.0\.1$"], ["192.168.1.1"]),
    # Kein Match
    ("No IPs here", r"(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})", [], []),
    # Multiline-Match mit ^
    ("line1: no\nline2: yes\nline3: no", r"^line2: (\w+)", [], ["yes"]),
    # Match mit mehreren Capture Groups (sollte zusammengefügt werden)
    ("Port 80/tcp is open", r"(\d+)/(\w+)", [], ["80tcp"]),
])
def test_parser_apply_logic(parser_manager, text_input, regex, excludes, expected_matches):
    """Testet die Kernlogik von `parse_text` mit verschiedenen Szenarien."""
    name = "test-apply"
    rule_name = "test-rule"
    parser_data = {
        "name": name,
        "rules": [
            {"name": rule_name, "regex": regex, "exclude_patterns": excludes}
        ]
    }
    parser_manager._save_data(name, parser_data)

    findings = parser_manager.parse_text(name, text_input)

    if not expected_matches:
        assert not findings
    else:
        assert findings is not None
        assert rule_name in findings
        assert sorted(findings[rule_name]) == sorted(expected_matches)

def test_parser_handles_invalid_regex(parser_manager):
    """Stellt sicher, dass ein ungültiger Regex keinen Crash verursacht."""
    name = "invalid-regex-parser"
    rule_name = "bad-rule"
    parser_data = {
        "name": name,
        "rules": [
            {"name": rule_name, "regex": "([a-z"} # Ungültiger Regex, Klammer nicht geschlossen
        ]
    }
    parser_manager._save_data(name, parser_data)

    # Der Aufruf sollte keine Exception auslösen und None zurückgeben
    findings = parser_manager.parse_text(name, "some text")
    assert findings == {} # Erwartet ein leeres Dict, da die Regel fehlschlägt

def test_parser_export(parser_manager, mocker):
    """Testet, ob die Export-Funktion die korrekten Rekonstruktions-Befehle generiert."""
    name = "export-parser"
    parser_data = {
        "name": name,
        "description": "A test parser for export.",
        "rules": [
            {
                "name": "ips",
                "regex": "\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}",
                "exclude_patterns": ["^127\\.0\\.0\\.1$"]
            }
        ]
    }
    parser_manager._save_data(name, parser_data)

    mock_cli = mocker.MagicMock()
    captured_output = []
    mock_cli.poutput.side_effect = lambda x: captured_output.append(x)

    args = type('Args', (), {'name': name})()
    parser_manager._cmd_export(args, mock_cli)

    full_output = "\n".join(captured_output)
    assert "parser add export-parser" in full_output
    assert "parser update export-parser description 'A test parser for export.'" in full_output
    assert "parser update export-parser add-rule ips" in full_output
    assert "parser update export-parser ips regex '\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}'" in full_output
    assert "parser update export-parser ips exclude '^127\\.0\\.0\\.1$'" in full_output

def test_parser_handles_incomplete_rules(parser_manager):
    """Testet, ob eine Regel ohne Regex beim Parsen ignoriert wird."""
    name = "incomplete-parser"
    parser_data = {
        "name": name,
        "rules": [
            {"name": "no-regex-rule"}, # Regel ohne 'regex'-Schlüssel
            {"name": "ip-rule", "regex": r"(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"}
        ]
    }
    parser_manager._save_data(name, parser_data)

    # Der Aufruf sollte keine Exception auslösen und nur die gültige Regel anwenden
    findings = parser_manager.parse_text(name, "some text with 1.2.3.4")
    assert "ip-rule" in findings
    assert "no-regex-rule" not in findings

def test_update_and_delete_negative_paths(parser_manager):
    """Testet Fehlerfälle bei den `update` und `delete` Befehlen."""
    name = "negative-test-parser"
    parser_manager.create(name)
    parser_manager._cmd_update(type('Args', (), {'name': name, 'update_args': ['add-rule', 'my-rule']})(), cli=None)
    parser_manager._cmd_update(type('Args', (), {'name': name, 'update_args': ['my-rule', 'exclude', 'foo']})(), cli=None)

    # 1. Versuche, eine nicht existierende Regel zu aktualisieren
    update_args_fail = type('Args', (), {'name': name, 'update_args': ['nonexistent-rule', 'regex', '.*']})()
    # Sollte keine Exception auslösen, nur einen Fehler loggen (den wir hier nicht prüfen)
    parser_manager._cmd_update(update_args_fail, cli=None)

    # 2. Versuche, eine Regel mit einem ungültigen Feld zu aktualisieren
    update_args_invalid_field = type('Args', (), {'name': name, 'update_args': ['my-rule', 'invalidfield', 'value']})()
    parser_manager._cmd_update(update_args_invalid_field, cli=None)

    # 3. Versuche, ein Ausschluss-Pattern mit einem ungültigen Index zu löschen
    delete_args_fail = type('Args', (), {'name': name, 'delete_args': ['my-rule', 'exclude', '99']})()
    parser_manager._cmd_delete(delete_args_fail, cli=None)
    data = parser_manager.load(name)
    # Der 'foo'-Ausschluss sollte immer noch da sein
    assert "foo" in data["rules"][0]["exclude_patterns"] # type: ignore

def test_invalid_command_syntax_is_handled(parser_manager, mocker):
    """
    Testet, ob die Kommando-Handler (`_cmd_update`, `_cmd_delete`) bei
    ungültiger Syntax nicht abstürzen.
    """
    name = "syntax-test-parser"
    parser_manager.create(name)

    # Mocke den Logger, um zu prüfen, ob eine Fehlermeldung ausgegeben wird.
    mock_log_error = mocker.patch("modules.services.log.error")
    mock_log_prompt = mocker.patch("modules.services.log.prompt")

    # 1. `update` ohne Argumente
    update_args_empty = type('Args', (), {'name': name, 'update_args': []})()
    parser_manager._cmd_update(update_args_empty, cli=None)
    mock_log_error.assert_called_with("No update arguments provided.")
    mock_log_prompt.assert_called_with("Use 'parser update -h' for help.")

    # 2. `delete` ohne Argumente (sollte auf 'destroy' hinweisen)
    delete_args_empty = type('Args', (), {'name': name, 'delete_args': []})()
    parser_manager._cmd_delete(delete_args_empty, cli=None)
    mock_log_error.assert_called_with("No delete arguments provided. To delete the entire parser, use 'parser destroy'.")
    mock_log_prompt.assert_called_with("Use 'parser delete -h' for help.")

    mock_log_error.reset_mock()

def test_cmd_apply_workflow_no_interactive(parser_manager, mock_cli_for_parser, mocker):
    """
    Tests the _cmd_apply workflow without interactive selection (questionary not available).
    """
    parser_name = "test-parser"
    logbook_id = 1
    findings = {"ips": ["1.1.1.1", "2.2.2.2"]}

    parser_manager.create(parser_name)
    mocker.patch.object(parser_manager, 'parse_text', return_value=findings)
    mocker.patch("modules.managers.parser_manager.questionary", None) # Simulate questionary not installed
    mock_log_error = mocker.patch("modules.services.log.error")
    mock_log_prompt = mocker.patch("modules.services.log.prompt")

    args = type('Args', (), {'name': parser_name, 'logbook_id': str(logbook_id)})()
    parser_manager._cmd_apply(args, mock_cli_for_parser)

    mock_cli_for_parser.display_mgr.display_findings.assert_called_once_with(findings, title="Parser Results")
    mock_log_error.assert_any_call("Optional dependency 'questionary' not found. Interactive selection is disabled.")
    mock_log_prompt.assert_called_with("Saving all findings to the report.")
    mock_cli_for_parser.report_mgr.add_findings.assert_called_once()

def test_cmd_apply_no_report_loaded(parser_manager, mock_cli_for_parser, mocker):
    """
    Tests that _cmd_apply logs an error if no report is loaded.
    """
    parser_name = "test-parser"
    logbook_id = 1
    findings = {"ips": ["1.1.1.1"]}

    parser_manager.create(parser_name)
    mocker.patch.object(parser_manager, 'parse_text', return_value=findings)
    mock_cli_for_parser.session.report = None # Simulate no report loaded
    mock_log_error = mocker.patch("modules.services.log.error")
    mock_log_prompt = mocker.patch("modules.services.log.prompt")

    args = type('Args', (), {'name': parser_name, 'logbook_id': str(logbook_id)})()
    parser_manager._cmd_apply(args, mock_cli_for_parser)

    mock_log_error.assert_called_with("No report loaded. Findings were found but cannot be saved.")
    mock_log_prompt.assert_any_call("Create and load a report to save findings from future parser runs:")
    mock_cli_for_parser.report_mgr.add_findings.assert_not_called()

def test_cmd_apply_no_findings(parser_manager, mock_cli_for_parser, mocker):
    """
    Tests that _cmd_apply logs an info message if no findings are found.
    """
    parser_name = "test-parser"
    logbook_id = 1

    parser_manager.create(parser_name)
    mocker.patch.object(parser_manager, 'parse_text', return_value={}) # Simulate no findings
    mock_log_info = mocker.patch("modules.services.log.info")

    args = type('Args', (), {'name': parser_name, 'logbook_id': str(logbook_id)})()
    parser_manager._cmd_apply(args, mock_cli_for_parser)

    mock_log_info.assert_called_with("Parser finished with no findings.")
    mock_cli_for_parser.display_mgr.display_findings.assert_not_called()
    mock_cli_for_parser.report_mgr.add_findings.assert_not_called()

def test_dispatch_shows_help_if_no_subcommand(parser_manager, mock_cli_for_parser):
    """
    Tests that the dispatch method calls the help manager if no subcommand is provided.
    """
    parser_manager.dispatch(subcommand=None, args=None, cli_instance=mock_cli_for_parser)
    mock_cli_for_parser.help_mgr.show_help_parser.assert_called_once()

def test_dispatch_routes_other_subcommands(parser_manager, mock_cli_for_parser, mocker):
    """
    Tests that the dispatch method correctly routes other subcommands.
    """
    mock_add = mocker.patch.object(parser_manager, '_cmd_add')
    args = argparse.Namespace(subcommand="add", name="new-parser")
    parser_manager.dispatch("add", args, mock_cli_for_parser)
    mock_add.assert_called_once_with(args, mock_cli_for_parser)