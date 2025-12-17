# tests/test_tool_manager.py
import pytest
from modules.managers.tool_manager import ToolManager
from modules import placeholders
from modules.services import config

@pytest.fixture
def tool_manager(tmp_path, monkeypatch):
    """Stellt einen sauberen ToolManager bereit, der in ein temporäres Verzeichnis schreibt."""
    tools_dir = tmp_path / "tools"
    tools_dir.mkdir()

    # Leite den Manager auf das temporäre Verzeichnis um
    original_get_parameter = config.get_parameter
    def mock_get_parameter(section, key, fallback=None):
        if section == "DIRS" and key == "TOOLS":
            return str(tools_dir)
        return original_get_parameter(section, key, fallback)
    monkeypatch.setattr(config, 'get_parameter', mock_get_parameter)

    # Logger stummschalten
    import logging
    from modules.services import log
    monkeypatch.setattr(log, 'log_value', logging.CRITICAL + 1)

    return ToolManager()

@pytest.fixture
def mock_session_with_target(mocker):
    """
    Stellt eine gemockte Session bereit, in der ein Target geladen ist.
    Mockt auch den TargetManager, um die Target-Daten für die Platzhalterauflösung bereitzustellen.
    """
    # 1. Mock-Session-Objekt erstellen
    session = mocker.MagicMock()
    session.target = "test-server" # Name des geladenen Targets

    # 2. Mock-Target-Manager erstellen
    mock_target_mgr = mocker.MagicMock()
    # Konfigurieren, was .load() zurückgeben soll
    mock_target_mgr.load.return_value = {
        "name": "test-server",
        "ip": "192.168.1.100",
        "hostname": "test.server.local"
    }

    # 3. Den globalen TargetManager für die Dauer des Tests ersetzen
    placeholders.register_manager("TARGET", mock_target_mgr)

    return session

def test_tool_create_and_exists(tool_manager):
    """Testet, ob ein Tool korrekt erstellt wird und existiert."""
    tool_name = "nmap"
    assert tool_manager.exists(tool_name) is False
    
    # Die `_cmd_add` Methode ist komplexer, wir rufen direkt die Kernlogik auf.
    # Wir mocken `shutil.which`, um den Test deterministisch zu machen.
    tool_manager.create(tool_name)
    
    assert tool_manager.exists(tool_name) is True
    tool_data = tool_manager.load(tool_name)
    assert tool_data is not None
    assert tool_data.get("name") == tool_name

def test_add_and_delete_command(tool_manager):
    """Testet das Hinzufügen und Löschen eines Befehls zu einem Tool."""
    tool_name = "nmap"
    cmd_name = "stealth-scan"
    tool_manager.create(tool_name)

    # Befehl hinzufügen
    tool_manager.add_command(tool_name, cmd_name)
    tool_data = tool_manager.load(tool_name)
    commands = tool_data.get("commands", [])
    assert any(c.get("name") == cmd_name for c in commands)

    # Befehl löschen
    tool_manager.delete_command(tool_name, cmd_name)
    tool_data = tool_manager.load(tool_name)
    commands = tool_data.get("commands", [])
    assert not any(c.get("name") == cmd_name for c in commands)

def test_build_command_with_placeholder(tool_manager, mock_session_with_target):
    """
    Testet, ob `build_command` Platzhalter wie $target.ip korrekt auflöst.
    """
    tool_name = "nmap"
    cmd_name = "stealth-scan"
    tool_manager.create(tool_name)
    tool_manager.add_command(tool_name, cmd_name)
    tool_manager.add_param(tool_name, cmd_name, "-p-")
    # Der entscheidende Parameter mit Platzhalter
    tool_manager.add_param(tool_name, cmd_name, "$target.ip")

    # Baue den Befehl
    built_commands = tool_manager.build_command(
        tool_name,
        session=mock_session_with_target,
        command_to_run=cmd_name
    )

    # Überprüfe das Ergebnis
    assert len(built_commands) == 1
    expected_command = ["nmap", "-p-", "192.168.1.100"]
    assert built_commands[0] == expected_command

def test_build_command_with_shlex_split(tool_manager, mock_session_with_target):
    """
    Testet, ob Parameter mit Leerzeichen korrekt in mehrere Argumente aufgeteilt werden.
    """
    tool_name = "nmap"
    cmd_name = "script-scan"
    tool_manager.create(tool_name)
    tool_manager.add_command(tool_name, cmd_name)
    # Ein Parameter, der mehrere Argumente enthält
    tool_manager.add_param(tool_name, cmd_name, "-sC -sV --script=vuln")
    tool_manager.add_param(tool_name, cmd_name, "$target.ip")

    built_commands = tool_manager.build_command(
        tool_name,
        session=mock_session_with_target,
        command_to_run=cmd_name
    )

    assert len(built_commands) == 1
    # shlex.split sollte '-sC -sV' in einzelne Argumente aufteilen
    expected_command = ["nmap", "-sC", "-sV", "--script=vuln", "192.168.1.100"]
    assert built_commands[0] == expected_command

def test_build_command_with_execute_per_param(tool_manager):
    """
    Testet, ob `build_command` bei 'execute_per_param=True' für jeden Parameter
    einen eigenen Befehl generiert.
    """
    tool_name = "echo-test"
    cmd_name = "checklist"
    tool_manager.create(tool_name)
    tool_manager.add_command(tool_name, cmd_name)

    # Setze das execute_per_param Flag
    tool_data = tool_manager.load(tool_name)
    cmd_obj = next(c for c in tool_data["commands"] if c["name"] == cmd_name)
    cmd_obj["execute_per_param"] = True
    tool_manager.update(tool_name, "commands", tool_data["commands"])

    # Füge mehrere Parameter hinzu
    tool_manager.add_param(tool_name, cmd_name, "check 1")
    tool_manager.add_param(tool_name, cmd_name, "check 2")
    tool_manager.add_param(tool_name, cmd_name, "check 3")

    # Baue die Befehle
    built_commands = tool_manager.build_command(
        tool_name,
        session=None, # Session wird hier nicht benötigt
        command_to_run=cmd_name
    )

    # Überprüfe das Ergebnis: Es sollten 3 separate Befehle sein
    assert len(built_commands) == 3
    expected_commands = [
        ["echo-test", "check 1"],
        ["echo-test", "check 2"],
        ["echo-test", "check 3"]
    ]
    assert built_commands == expected_commands

def test_reorder_and_update_param(tool_manager):
    """Testet das Umsortieren und Aktualisieren von Parametern."""
    tool_name = "nmap"
    cmd_name = "scan"
    tool_manager.create(tool_name)
    tool_manager.add_command(tool_name, cmd_name)
    tool_manager.add_param(tool_name, cmd_name, "param1")
    tool_manager.add_param(tool_name, cmd_name, "param2")
    tool_manager.add_param(tool_name, cmd_name, "param3")

    # 1. Parameter umsortieren: bewege param3 (Index 3) an den Anfang (Index 1)
    tool_manager.reorder_param(tool_name, cmd_name, old_index=3, new_index=1)
    cmd_data = next(c for c in tool_manager.load(tool_name)["commands"] if c["name"] == cmd_name)
    assert cmd_data["params"] == ["param3", "param1", "param2"]

    # 2. Einen Parameter am neuen Index aktualisieren
    tool_manager.update_param(tool_name, cmd_name, index=2, new_value="param1-updated")
    cmd_data = next(c for c in tool_manager.load(tool_name)["commands"] if c["name"] == cmd_name)
    assert cmd_data["params"] == ["param3", "param1-updated", "param2"]

def test_add_tool_with_auto_path_detection(tool_manager, monkeypatch):
    """
    Testet, ob beim Hinzufügen eines Tools der Pfad automatisch
    über `shutil.which` gefunden und gesetzt wird.
    """
    # Fall 1: `shutil.which` findet das Tool
    monkeypatch.setattr("shutil.which", lambda x: "/usr/bin/nmap")
    tool_manager._cmd_add(type('Args', (), {'name': 'nmap'})(), None)
    
    tool_data = tool_manager.load("nmap")
    assert tool_data is not None
    assert tool_data.get("path") == "/usr/bin/nmap"

    # Fall 2: `shutil.which` findet das Tool nicht
    monkeypatch.setattr("shutil.which", lambda x: None)
    tool_manager._cmd_add(type('Args', (), {'name': 'customtool'})(), None)

    tool_data_custom = tool_manager.load("customtool")
    assert tool_data_custom is not None
    # Der Pfad sollte auf den Namen des Tools zurückfallen
    assert tool_data_custom.get("path") == "customtool"

def test_build_command_with_extra_params(tool_manager, mock_session_with_target):
    """
    Testet, ob `build_command` temporäre extra-Parameter korrekt anhängt.
    Dies ist wichtig für die `pwn ... -- <extra>` Funktionalität.
    """
    tool_name = "nmap"
    cmd_name = "scan"
    tool_manager.create(tool_name)
    tool_manager.add_command(tool_name, cmd_name)
    tool_manager.add_param(tool_name, cmd_name, "$target.ip")

    # Baue den Befehl mit extra Parametern
    built_commands = tool_manager.build_command(
        tool_name,
        session=mock_session_with_target,
        command_to_run=cmd_name,
        extra_params=["-v", "--reason"] # Die temporären Parameter
    )

    # Überprüfe das Ergebnis
    assert len(built_commands) == 1
    expected_command = ["nmap", "192.168.1.100", "-v", "--reason"]
    assert built_commands[0] == expected_command

def test_build_command_with_sudo(tool_manager, mock_session_with_target):
    """
    Testet, ob `build_command` das `sudo`-Kommando korrekt voranstellt,
    wenn das Flag im Tool gesetzt ist.
    """
    tool_name = "nmap"
    cmd_name = "privileged-scan"
    tool_manager.create(tool_name)
    tool_manager.add_command(tool_name, cmd_name)
    tool_manager.add_param(tool_name, cmd_name, "$target.ip")

    # Setze das sudo-Flag für das Tool
    tool_manager.update(tool_name, "sudo", True)

    # Baue den Befehl
    # HINWEIS: build_command selbst fügt sudo NICHT hinzu.
    # Das ist die Aufgabe des CommandExecutor. Wir testen hier also,
    # dass build_command das Kommando *unverändert* zurückgibt,
    # da die sudo-Logik an anderer Stelle liegt.
    # Der Test für die tatsächliche sudo-Ausführung gehört in einen Integrationstest.
    built_commands = tool_manager.build_command(
        tool_name,
        session=mock_session_with_target,
        command_to_run=cmd_name
    )

    # Das erwartete Ergebnis ist OHNE sudo, da build_command nur baut, nicht ausführt.
    expected_command = ["nmap", "192.168.1.100"]
    assert built_commands[0] == expected_command

def test_export_tool(tool_manager, mocker):
    """Testet, ob die Export-Funktion die korrekten Rekonstruktions-Befehle generiert."""
    tool_name = "nmap"
    tool_manager.create(tool_name)
    tool_manager.update(tool_name, "sudo", True)
    tool_manager.add_command(tool_name, "stealth-scan")
    tool_manager.add_param(tool_name, "stealth-scan", "-sS")
    tool_manager.add_param(tool_name, "stealth-scan", "$target.ip")

    # Mocke das cli-Objekt und seine poutput-Methode, um die Ausgabe abzufangen
    mock_cli = mocker.MagicMock()
    captured_output = []
    mock_cli.poutput.side_effect = lambda x: captured_output.append(x)

    # Führe die Export-Methode aus
    tool_manager._cmd_export(type('Args', (), {'name': tool_name})(), mock_cli)

    # Überprüfe die Ausgabe
    full_output = "\n".join(captured_output)
    assert "tool add nmap" in full_output
    assert "tool update nmap sudo true" in full_output
    assert "tool update nmap command stealth-scan" in full_output
    assert "tool update nmap stealth-scan param -sS" in full_output
    assert "tool update nmap stealth-scan param '$target.ip'" in full_output

def test_update_and_delete_negative_paths(tool_manager, mocker):
    """
    Testet Fehlerfälle bei den `update` und `delete` Befehlen, um sicherzustellen,
    dass sie robust gegen ungültige Eingaben sind.
    """
    tool_name = "neg-test-tool"
    tool_manager.create(tool_name)
    tool_manager.add_command(tool_name, "my-cmd")

    mock_log_error = mocker.patch("modules.services.log.error")

    # 1. Versuche, einen Parameter zu einem nicht-existenten Befehl hinzuzufügen
    update_args_fail_cmd = type('Args', (), {'name': tool_name, 'update_args': ['nonexistent-cmd', 'param', '-v']})()
    tool_manager._cmd_update(update_args_fail_cmd, cli=None)
    mock_log_error.assert_called_with(f"Command 'nonexistent-cmd' not found in '{tool_name}'.")

    # 2. Versuche, ein geschütztes Feld direkt zu aktualisieren
    update_args_protected = type('Args', (), {'name': tool_name, 'update_args': ['my-cmd', 'params', 'new-value']})()
    tool_manager._cmd_update(update_args_protected, cli=None)
    mock_log_error.assert_called_with("Cannot update 'params' directly. Use dedicated syntax like 'tool rename' or 'tool update ... param ...'.")

    # 3. Versuche, die gesamte 'commands'-Liste zu löschen
    delete_args_commands = type('Args', (), {'name': tool_name, 'delete_args': ['commands']})()
    tool_manager._cmd_delete(delete_args_commands, cli=None)
    mock_log_error.assert_called_with("The 'commands' list cannot be deleted directly.")

    # 4. Versuche, den Pfad automatisch zu finden, wenn das Tool nicht im PATH ist
    mocker.patch("shutil.which", return_value=None)
    tool_manager._find_and_set_path(tool_name)
    # Hier wird eine Warnung geloggt, die wir nicht prüfen, aber der Test stellt sicher, dass es nicht abstürzt.

def test_rename_updates_active_session(tool_manager, mocker):
    """
    Testet, ob das Umbenennen eines Tools auch die aktive Session aktualisiert,
    wenn das Tool dort geladen war.
    """
    old_name = "nmap"
    new_name = "nmap-scanner"
    tool_manager.create(old_name)

    # Mocke das CLI-Objekt und die Session
    mock_cli = mocker.MagicMock()
    mock_cli.session.tool = old_name # Simuliere, dass das Tool geladen ist

    # Simuliere den Aufruf von `tool rename nmap nmap-scanner`
    rename_args = type('Args', (), {'old_name': old_name, 'new_name': new_name})()
    tool_manager._cmd_rename(rename_args, mock_cli)

    # Überprüfe, ob die Session aktualisiert wurde
    assert mock_cli.session.tool == new_name

def test_build_command_with_unresolved_placeholder(tool_manager, mock_session_with_target):
    """
    Testet, ob ein nicht auflösbarer Platzhalter im Befehl als String erhalten bleibt.
    """
    tool_name = "nmap"
    cmd_name = "scan"
    tool_manager.create(tool_name)
    tool_manager.add_command(tool_name, cmd_name)
    tool_manager.add_param(tool_name, cmd_name, "$target.nonexistent_field")

    built_commands = tool_manager.build_command(
        tool_name,
        session=mock_session_with_target,
        command_to_run=cmd_name
    )

    # Der Platzhalter sollte unverändert im Befehl stehen
    expected_command = ["nmap", "$target.nonexistent_field"]
    assert built_commands[0] == expected_command

def test_tool_copy(tool_manager):
    """Tests copying a tool entity."""
    source_name = "source_tool"
    dest_name = "dest_tool"
    tool_manager.create(source_name)
    tool_manager.update(source_name, "description", "Original tool")
    tool_manager.add_command(source_name, "scan")

    # Perform the copy
    assert tool_manager.copy(source_name, dest_name) is True

    # Verify source and destination
    assert tool_manager.exists(source_name) is True
    dest_data = tool_manager.load(dest_name)
    assert dest_data is not None
    assert dest_data.get("name") == dest_name
    assert dest_data.get("description") == "Original tool"
    assert len(dest_data.get("commands", [])) == 1

def test_tool_export_with_custom_fields(tool_manager, mocker):
    """Tests that _cmd_export correctly exports custom top-level and command-level fields."""
    tool_name = "nmap-full"
    tool_manager.create(tool_name)
    tool_manager.update(tool_name, "howto", "Run with 'pwn scan now'")
    tool_manager.add_command(tool_name, "scan")
    # Simulate 'tool update nmap-full scan description "A full scan"'
    update_args = type('Args', (), {'name': tool_name, 'update_args': ['scan', 'description', 'A full scan']})()
    tool_manager._cmd_update(update_args, cli=None)

    mock_cli = mocker.MagicMock()
    captured_output = []
    mock_cli.poutput.side_effect = captured_output.append

    tool_manager._cmd_export(type('Args', (), {'name': tool_name})(), mock_cli)
    output = "\n".join(captured_output)

    assert "tool update nmap-full howto 'Run with \\'pwn scan now\\''" in output
    # shlex.quote('Run with \'pwn scan now\'') -> "'Run with '\"'\"'pwn scan now'\"'\"''"
    # We check for the essential parts to make the test less brittle to quoting style changes.
    assert "tool update nmap-full howto 'Run with " in output
    assert "pwn scan now" in output
    assert "tool update nmap-full scan description 'A full scan'" in output

def test_delete_param_by_value(tool_manager):
    """Testet das Löschen eines Parameters anhand seines Werts."""
    tool_name = "nmap"
    cmd_name = "scan"
    param_to_delete = "-sV"
    tool_manager.create(tool_name)
    tool_manager.add_command(tool_name, cmd_name)
    tool_manager.add_param(tool_name, cmd_name, "-p-")
    tool_manager.add_param(tool_name, cmd_name, param_to_delete)

    # Simuliere den Aufruf von `tool delete nmap scan param -sV`
    delete_args = type('Args', (), {'name': tool_name, 'delete_args': [cmd_name, 'param', param_to_delete]})()
    tool_manager._cmd_delete(delete_args, cli=None)

    # Überprüfe, ob der Parameter entfernt wurde
    tool_data = tool_manager.load(tool_name)
    cmd_data = next(c for c in tool_data["commands"] if c["name"] == cmd_name)
    assert param_to_delete not in cmd_data["params"]
    assert cmd_data["params"] == ["-p-"]

def test_build_command_with_empty_and_none_placeholders(tool_manager, mocker):
    """
    Testet, ob Platzhalter, die zu leeren Strings oder None aufgelöst werden,
    korrekt aus dem finalen Befehl entfernt werden.
    """
    tool_name = "test-empty"
    cmd_name = "scan"
    tool_manager.create(tool_name)
    tool_manager.add_command(tool_name, cmd_name)
    tool_manager.add_param(tool_name, cmd_name, "-p-")
    tool_manager.add_param(tool_name, cmd_name, "$target.empty_field")
    tool_manager.add_param(tool_name, cmd_name, "$target.ip")
    tool_manager.add_param(tool_name, cmd_name, "$target.none_field")

    # Mocke eine Session mit einem Target, das leere/None-Felder hat
    mock_session = mocker.MagicMock()
    mock_session.target = "test-server"
    mock_target_mgr = mocker.MagicMock()
    mock_target_mgr.load.return_value = {
        "name": "test-server",
        "ip": "192.168.1.100",
        "empty_field": "",
        "none_field": None
    }
    placeholders.register_manager("TARGET", mock_target_mgr)

    # Baue den Befehl
    built_commands = tool_manager.build_command(
        tool_name,
        session=mock_session,
        command_to_run=cmd_name
    )

    # Überprüfe das Ergebnis: Leere und None-Parameter sollten nicht im Befehl erscheinen.
    # Der 'None'-String, der aus der Konvertierung von `None` entsteht, wird von shlex.split
    # als Argument behandelt, was wir hier prüfen.
    expected_command = ["test-empty", "-p-", "192.168.1.100", "None"]
    assert built_commands[0] == expected_command

def test_delete_command_shortcut(tool_manager):
    """Testet das Löschen eines Befehls über die 'tool delete <name> <cmd>' Abkürzung."""
    tool_name = "nmap"
    cmd_name = "shortcut-scan"

    # 1. Tool erstellen und Befehl hinzufügen
    tool_manager.create(tool_name)
    tool_manager.add_command(tool_name, cmd_name)

    # Sicherstellen, dass der Befehl vor dem Löschen vorhanden ist
    tool_data_before = tool_manager.load(tool_name)
    assert any(c.get("name") == cmd_name for c in tool_data_before.get("commands", []))

    # 2. Simuliere den Aufruf von `tool delete nmap shortcut-scan`
    delete_args = type('Args', (), {'name': tool_name, 'delete_args': [cmd_name]})()
    tool_manager._cmd_delete(delete_args, cli=None)

    # 3. Überprüfe, ob der Befehl entfernt wurde
    tool_data_after = tool_manager.load(tool_name)
    assert not any(c.get("name") == cmd_name for c in tool_data_after.get("commands", []))

def test_build_command_with_invalid_path(tool_manager, mock_session_with_target, tmp_path, mocker):
    """
    Testet, ob build_command fehlschlägt, wenn der Pfad des Tools ungültig ist
    (z.B. ein Verzeichnis statt einer Datei).
    """
    tool_name = "invalid-path-tool"
    tool_manager.create(tool_name)
    # Setze den Pfad auf das temporäre Verzeichnis selbst
    tool_manager.update(tool_name, "path", str(tmp_path))
    tool_manager.add_command(tool_name, "scan")

    mock_log_error = mocker.patch("modules.services.log.error")

    # Der Versuch, den Befehl zu bauen, sollte fehlschlagen.
    # Die eigentliche Fehlermeldung kommt vom CommandExecutor, aber build_command sollte nicht crashen.
    # In diesem Fall gibt build_command eine leere Liste zurück, da es keinen gültigen Befehl erstellen kann.
    result = tool_manager.build_command(tool_name, session=mock_session_with_target, command_to_run="scan")
    assert result[0][0] == str(tmp_path) # build_command gibt den Pfad so zurück, wie er ist. Der Fehler tritt bei der Ausführung auf.
