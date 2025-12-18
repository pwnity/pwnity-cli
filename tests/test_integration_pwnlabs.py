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

# tests/test_integration_pwnity.py
import subprocess
import sys
import os
import pytest
import json
import re
import pty
import pathlib
import select

class pwnityApp:
    """Eine Wrapper-Klasse, um mit einem laufenden pwnity-Prozess zu interagieren."""
    def __init__(self, process, master_fd):
        self.process = process
        self.master_fd = master_fd
        # --- FINAL, MORE ROBUST FIX for race conditions and PTY rendering issues ---
        # The previous regex was too specific and failed when the '└' character was
        # not rendered correctly in the test's pseudo-terminal. This new regex is
        # more generic, matching the final prompt line (e.g., "└─$ " or "─$ ")
        # by looking for a line ending with "$ ".
        self.prompt_pattern = re.compile(r"^\S*\$\s*$", re.MULTILINE)
        self.ansi_escape_pattern = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')

    def _strip_ansi(self, text: str) -> str:
        """Removes ANSI escape codes from a string."""
        # First, normalize line endings which can be mixed in pty output
        text_normalized_crlf = text.replace('\r\n', '\n')
        # Then, remove the ANSI codes
        return self.ansi_escape_pattern.sub('', text_normalized_crlf)
        
    def read_until_prompt(self, timeout=10):
        """Liest die Ausgabe des Prozesses, bis der Prompt erscheint."""
        output = ""
        start_time = os.times().elapsed
        while True:
            # Prüfe, ob der Prozess unerwartet beendet wurde
            if self.process.poll() is not None:
                # Lese die restliche Ausgabe
                remaining_output_bytes = os.read(self.master_fd, 1024)
                output += remaining_output_bytes.decode('utf-8', errors='ignore')
                pytest.fail(f"pwnity-Prozess unerwartet beendet. Ausgabe:\n{output}")

            # Warte, bis Daten zum Lesen verfügbar sind
            ready, _, _ = select.select([self.master_fd], [], [], 0.1)
            if ready:
                try:
                    data = os.read(self.master_fd, 1024).decode('utf-8', errors='ignore')
                    output += data
                    if self.prompt_pattern.search(output):
                        return output
                except OSError:
                    # Kann passieren, wenn der Prozess genau jetzt beendet wird
                    break
            
            if (os.times().elapsed - start_time) > timeout:
                pytest.fail(f"Timeout: Prompt nicht innerhalb von {timeout}s gefunden. Bisherige Ausgabe:\n{output}")
        return output

    def run_command(self, command: str):
        """Sendet einen Befehl an den Prozess und gibt die Ausgabe zurück."""
        full_command = command + "\n"
        os.write(self.master_fd, full_command.encode('utf-8'))
        return self.read_until_prompt()

    def close(self):
        """Beendet den Prozess sauber."""
        if self.process.poll() is None:
            try:
                self.run_command("quit")
                self.process.wait(timeout=5)
            except Exception:
                self.process.kill()
        os.close(self.master_fd)
        
@pytest.fixture
def pwnity_env(tmp_path, monkeypatch):
    """
    Eine Fixture, die eine isolierte Testumgebung für pwnity erstellt.
    - Erstellt eine temporäre Konfigurationsdatei.
    - Leitet alle Datenverzeichnisse in ein temporäres Verzeichnis um.
    - Setzt eine Umgebungsvariable, damit der pwnity-Prozess diese Konfiguration verwendet.
    """
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    original_config_path = os.path.join(project_root, 'etc', 'config.json')

    # Lade die Originalkonfiguration
    with open(original_config_path, 'r') as f:
        config_data = json.load(f)

    # --- FIX: Force INFO log level for tests ---
    # This ensures that all informational messages the tests assert on are
    # actually printed, regardless of the default setting in config.json (which
    # might be WARN or ERROR for production).
    config_data["GLOBAL"]["DEBUG_LEVEL"] = "INFO"

    # Überschreibe alle Pfade im DIRS-Abschnitt, um auf das tmp_path zu zeigen.
    # Unterscheide zwischen Verzeichnissen und Dateipfaden, indem wir auf die Dateiendung des WERTS schauen.
    for key in config_data.get("DIRS", {}):
        original_path = config_data["DIRS"][key]
        # Wenn der ursprüngliche Pfad eine bekannte Dateiendung hat, behandeln wir ihn als Datei.
        if original_path.endswith(('.json', '.txt')):
            new_path = tmp_path / os.path.basename(original_path)
            config_data["DIRS"][key] = str(new_path)

            # --- FIX: Copy data files, but explicitly SKIP profile.json ---
            # This ensures tests always start with a clean, empty profile and are not
            # affected by the user's local configuration.
            source_file = os.path.join(project_root, original_path)
            # Do not copy the profile file to ensure a clean state for tests.
            if os.path.basename(source_file) != 'profile.json' and os.path.exists(source_file):
                new_path.write_text(open(source_file).read())
        else:
            # Andernfalls ist es ein Verzeichnispfad, erstelle das Verzeichnis.
            temp_dir_for_key = tmp_path / key.lower()
            temp_dir_for_key.mkdir(exist_ok=True)
            config_data["DIRS"][key] = str(temp_dir_for_key)

    # Schreibe die neue Test-Konfiguration
    test_config_path = tmp_path / "test_config.json"
    with open(test_config_path, 'w') as f:
        json.dump(config_data, f, indent=2)

    # Setze die Umgebungsvariable für den Subprozess
    monkeypatch.setenv("pwnity_CONFIG_PATH", str(test_config_path))
    # Setze die Umgebungsvariable, um den Testmodus in der App zu aktivieren
    # Dies verhindert echte, blockierende Netzwerkaufrufe.
    monkeypatch.setenv("pwnity_TEST_MODE", "1")

    
    return {
        "project_root": project_root,
        "script_path": os.path.join(project_root, 'pwnity_cli.py'),
        "targets_dir": config_data["DIRS"]["TARGETS"]
    }

# By setting autouse=True, this fixture will be automatically used for every
# test function in this file. This ensures that each test gets a fresh,
# isolated pwnity instance, preventing state from leaking between tests.
@pytest.fixture(autouse=True)
def running_pwnity(pwnity_env):
    """
    Eine Fixture, die die pwnity-Anwendung als Subprozess startet und
    ein Objekt zur Interaktion zurückgibt. Der Prozess läuft für die Dauer
    aller Tests in diesem Modul.
    """
    master_fd, slave_fd = pty.openpty()
    process = subprocess.Popen(
        [sys.executable, pwnity_env["script_path"]],
        stdin=slave_fd,
        stdout=slave_fd,
        stderr=slave_fd,
        text=True,
        cwd=pwnity_env["project_root"],
        bufsize=1, # Line-buffered
    )
    os.close(slave_fd)

    app = pwnityApp(process, master_fd)
    
    # Lese den initialen Banner und Prompt, um sicherzustellen, dass die App bereit ist
    initial_output = app.read_until_prompt()
    assert "pwnity" in initial_output

    yield app

    # Aufräumen nach allen Tests
    app.close()

@pytest.mark.integration
class TestConfigIntegration:
    """Gruppiert Integrationstests für das 'config'-Modul."""

    def test_config_list(self, running_pwnity):
        """Testet den 'config list' Befehl."""
        output = running_pwnity.run_command("config list")
        assert "Application Configuration" in output
        assert "GLOBAL" in output
        assert "PROXY" in output

    def test_config_get(self, running_pwnity):
        """Testet den 'config get' Befehl."""
        # Wir wissen, dass GLOBAL.DEBUG_LEVEL existiert und standardmäßig INFO ist.
        output = running_pwnity.run_command("config get GLOBAL.DEBUG_LEVEL")
        clean_output = running_pwnity._strip_ansi(output).strip()
        # Die Ausgabe sollte nur den Wert und den Prompt enthalten.
        output_lines = clean_output.splitlines()
        assert len(output_lines) > 1 and output_lines[1] == "INFO"

    def test_config_set(self, running_pwnity):
        """Testet den 'config set' Befehl und überprüft die Änderung mit 'config get'."""
        test_key = "GLOBAL.TEST_SETTING"
        test_value = "integration_test_value"

        set_output = running_pwnity.run_command(f"config set {test_key} {test_value}")
        assert f"Configuration updated: [{test_key.split('.')[0].upper()}].{test_key.split('.')[1]} = {test_value}" in set_output

        get_output = running_pwnity.run_command(f"config get {test_key}")
        output_lines = running_pwnity._strip_ansi(get_output).strip().splitlines()
        assert len(output_lines) > 1 and output_lines[1] == test_value

@pytest.mark.integration
class TestTargetIntegration:

    def test_target_add(self, running_pwnity, pwnity_env):
        """Testet das Hinzufügen eines Targets."""
        target_name = "test-add"
        output = running_pwnity.run_command(f"target add {target_name}")
        assert f"Target '{target_name}' added." in output
        
        expected_file = os.path.join(pwnity_env["targets_dir"], f"{target_name}.json")
        assert os.path.isfile(expected_file)

    def test_target_update_url(self, running_pwnity):
        """Testet das Aktualisieren der URL eines Targets."""
        target_name = "test-update"
        running_pwnity.run_command(f"target add {target_name}")

        raw_output = running_pwnity.run_command(f"target update {target_name} url http://test.local:8080")
        clean_output = running_pwnity._strip_ansi(raw_output)
        assert f"Target '{target_name}' updated with data extracted from the URL." in clean_output

        raw_show_output = running_pwnity.run_command(f"target show {target_name}")
        # Wir müssen die Ausgabe bereinigen, bevor wir re.search verwenden
        clean_show_output = running_pwnity._strip_ansi(raw_show_output)
        assert re.search(r"hostname\s+test\.local", clean_show_output), "Hostname wurde in der Ausgabe nicht gefunden"
        assert re.search(r"port\s+8080", clean_show_output), "Port wurde in der Ausgabe nicht gefunden"

    def test_target_load_unload(self, running_pwnity):
        """Testet das Laden und Entladen eines Targets."""
        target_name = "test-load"
        running_pwnity.run_command(f"target add {target_name}")

        load_output = running_pwnity.run_command(f"target load {target_name}")
        clean_load_output = running_pwnity._strip_ansi(load_output)
        assert f"Target '{target_name}' loaded into active session" in clean_load_output
        # Der Prompt sollte sich geändert haben. Wir prüfen den bereinigten Text.
        assert f"- [ {target_name} ]" in clean_load_output

        unload_output = running_pwnity.run_command("target unload")
        assert f"Unloaded target '{target_name}' from the current session." in running_pwnity._strip_ansi(unload_output)
        assert f"- [ {target_name} ]" not in unload_output # Der Prompt sollte wieder normal sein

    def test_target_destroy(self, running_pwnity, pwnity_env):
        """Testet das Zerstören eines Targets."""
        target_name = "test-destroy"
        running_pwnity.run_command(f"target add {target_name}")

        destroy_output = running_pwnity.run_command(f"target destroy {target_name}")
        assert f"Target '{target_name}' has been completely deleted." in destroy_output

        list_output = running_pwnity.run_command("target list")
        # Prüfe den bereinigten Text
        assert "No Targets found." in running_pwnity._strip_ansi(list_output)

        expected_file = os.path.join(pwnity_env["targets_dir"], f"{target_name}.json")
        assert not os.path.isfile(expected_file)

    def test_target_gather(self, running_pwnity):
        """
        Testet den 'target gather' Befehl. Im Test-Modus werden Netzwerkaufrufe
        abgefangen und geben vorhersagbare Werte zurück (z.B. IP 127.0.0.1).
        """
        target_name = "test-gather"
        running_pwnity.run_command(f"target add {target_name}")
        running_pwnity.run_command(f"target update {target_name} url http://{target_name}")

        gather_output = running_pwnity.run_command(f"target gather {target_name} dns")
        clean_gather_output = running_pwnity._strip_ansi(gather_output)
        assert "Target 'test-gather' updated with new information." in clean_gather_output

        show_output = running_pwnity.run_command(f"target show {target_name}")
        clean_show_output = running_pwnity._strip_ansi(show_output)
        # Überprüfe, ob die vom Test-Modus-Patch zurückgegebene IP korrekt gespeichert wurde.
        assert re.search(r"ip\s+127\.0\.0\.1", clean_show_output)

    def test_target_export(self, running_pwnity):
        """Testet den 'target export' Befehl."""
        target_name = "test-export"
        url = "http://export-test.com"
        custom_value = "custom_value"
        running_pwnity.run_command(f"target add {target_name}")
        # Update a core field and a custom field
        running_pwnity.run_command(f"target update {target_name} url {url}")
        running_pwnity.run_command(f"target update {target_name} custom_field {custom_value}")

        export_output = running_pwnity.run_command(f"target export {target_name}")

        assert f"target add {target_name}" in export_output
        assert f"target update {target_name} url {url}" in export_output
        assert f"target update {target_name} custom_field {custom_value}" in export_output

    def test_target_list_multiple(self, running_pwnity):
        """Testet den 'target list' Befehl mit mehreren Einträgen."""
        running_pwnity.run_command("target add target-a")
        running_pwnity.run_command("target add target-b")

        list_output = running_pwnity.run_command("target list")
        clean_output = running_pwnity._strip_ansi(list_output)

        assert "target-a" in clean_output
        assert "target-b" in clean_output
        assert "Available Targets" in clean_output # Überprüfe den Panel-Titel

    def test_target_rename_updates_session(self, running_pwnity):
        """Testet, ob 'target rename' auch das geladene Target in der Session aktualisiert."""
        old_name = "old-name"
        new_name = "new-name"
        running_pwnity.run_command(f"target add {old_name}")
        load_output = running_pwnity.run_command(f"target load {old_name}")

        # Überprüfe den Prompt vor dem Umbenennen (nachdem ANSI-Codes entfernt wurden)
        assert f"- [ {old_name} ]" in running_pwnity._strip_ansi(load_output)

        # Benenne das Target um
        rename_output = running_pwnity.run_command(f"target rename {old_name} {new_name}")
        clean_rename_output = running_pwnity._strip_ansi(rename_output)
        assert f"Target '{old_name}' has been renamed to '{new_name}'" in clean_rename_output
        assert f"Active session has been updated: target '{old_name}' -> '{new_name}'" in clean_rename_output

        # Überprüfe, ob der Prompt und die Session aktualisiert wurden (im bereinigten Output)
        assert f"- [ {new_name} ]" in clean_rename_output

    def test_target_delete_field(self, running_pwnity):
        """Testet das Löschen eines Feldes von einem Target."""
        target_name = "delete-field-test"
        running_pwnity.run_command(f"target add {target_name}")
        running_pwnity.run_command(f"target update {target_name} custom_field to_be_deleted")

        # Überprüfe, ob das Feld existiert
        show_before = running_pwnity.run_command(f"target show {target_name}")
        assert "to_be_deleted" in show_before

        # Lösche das Feld
        running_pwnity.run_command(f"target delete {target_name} custom_field")

        # Überprüfe, ob das Feld verschwunden ist
        show_after = running_pwnity.run_command(f"target show {target_name}")
        assert "to_be_deleted" not in show_after

    def test_target_fork_domain(self, running_pwnity):
        """Testet den 'target fork-domain' Befehl auf Integrationsebene."""
        subdomain_name = "sub.fork-test.com"
        domain_name = "fork-test.com"
        running_pwnity.run_command(f"target add {subdomain_name}")
        running_pwnity.run_command(f"target update {subdomain_name} url https://{subdomain_name}")

        fork_output = running_pwnity.run_command(f"target fork-domain {subdomain_name}")
        clean_output = running_pwnity._strip_ansi(fork_output)
        assert f"Creating new target '{domain_name}' from the domain of '{subdomain_name}'" in clean_output

        list_output = running_pwnity.run_command("target list")
        assert domain_name in list_output

    def test_target_delete_is_alias_for_destroy(self, running_pwnity, pwnity_env):
        """Testet, ob 'target delete <name>' sich wie 'target destroy <name>' verhält."""
        target_name = "delete-alias-test"
        running_pwnity.run_command(f"target add {target_name}")

        # Überprüfe, ob die Datei existiert
        expected_file = os.path.join(pwnity_env["targets_dir"], f"{target_name}.json")
        assert os.path.isfile(expected_file)

        # Führe 'delete' aus
        delete_output = running_pwnity.run_command(f"target delete {target_name}")
        assert f"Target '{target_name}' has been completely deleted." in delete_output

        # Überprüfe, ob die Datei entfernt wurde
        assert not os.path.isfile(expected_file)

    def test_target_show_single_field(self, running_pwnity):
        """Testet, ob 'target show <name> <field>' nur den Wert des Feldes ausgibt."""
        target_name = "show-field-test"
        running_pwnity.run_command(f"target add {target_name}")
        running_pwnity.run_command(f"target update {target_name} ip 1.2.3.4")

        show_output = running_pwnity.run_command(f"target show {target_name} ip")
        clean_output = running_pwnity._strip_ansi(show_output).strip()

        # Die Ausgabe enthält das Befehls-Echo, den Wert und den Prompt. Wir prüfen,
        # ob der Wert in einer der Zeilen nach dem Befehls-Echo vorkommt.
        output_lines = clean_output.splitlines()
        assert "1.2.3.4" in output_lines

    def test_target_copy_command(self, running_pwnity, pwnity_env):
        """Testet den 'target copy' Befehl auf Integrationsebene."""
        source_name = "copy_source_target"
        dest_name = "copy_dest_target"
        running_pwnity.run_command(f"target add {source_name}")
        running_pwnity.run_command(f"target update {source_name} url http://source.com")

        # Führe den Kopierbefehl aus
        copy_output = running_pwnity.run_command(f"target copy {source_name} {dest_name}")
        assert f"Target '{source_name}' successfully copied to '{dest_name}'" in copy_output

        # Überprüfe, ob beide Dateien existieren
        targets_dir = pwnity_env["targets_dir"]
        assert os.path.isfile(os.path.join(targets_dir, f"{source_name}.json"))
        assert os.path.isfile(os.path.join(targets_dir, f"{dest_name}.json"))

        # Überprüfe den Inhalt der neuen Datei
        with open(os.path.join(targets_dir, f"{dest_name}.json"), 'r') as f:
            dest_data = json.load(f)
        
        assert dest_data.get('name') == dest_name
        assert dest_data.get('url') == "http://source.com"




@pytest.mark.integration
class TestToolIntegration:
    """Gruppiert Integrationstests für das 'tool'-Modul."""

    def test_tool_add_and_update(self, running_pwnity):
        """Testet das Hinzufügen eines Tools und das Konfigurieren eines Befehls."""
        tool_name = "nmap-test"
        cmd_name = "stealth-scan"
        param1 = "-sS"
        param2 = "$target.ip"

        # Tool hinzufügen
        output = running_pwnity.run_command(f"tool add {tool_name}")
        assert f"Tool '{tool_name}' added" in output

        # Befehl hinzufügen
        output = running_pwnity.run_command(f"tool update {tool_name} command {cmd_name}")
        assert f"Command '{cmd_name}' added to '{tool_name}'" in output

        # Parameter hinzufügen
        output = running_pwnity.run_command(f"tool update {tool_name} {cmd_name} param {param1}")
        assert f"Parameter added to '{tool_name} {cmd_name}': {param1}" in output
        output = running_pwnity.run_command(f"tool update {tool_name} {cmd_name} param '{param2}'")
        assert f"Parameter added to '{tool_name} {cmd_name}': {param2}" in output

        # Überprüfen mit 'tool show'
        show_output = running_pwnity.run_command(f"tool show {tool_name}")
        clean_output = running_pwnity._strip_ansi(show_output)
        assert cmd_name in clean_output
        assert param1 in clean_output
        assert param2 in clean_output

    def test_pwn_command_preview(self, running_pwnity):
        """Testet die Vorschau des 'pwn'-Befehls mit Platzhalterauflösung."""
        # Setup: Erstelle ein Target und ein Tool
        running_pwnity.run_command("target add test-server-pwn")
        running_pwnity.run_command("target update test-server-pwn url http://test-pwn.local")
        running_pwnity.run_command("tool add nmap-pwn")
        running_pwnity.run_command("tool update nmap-pwn command full-scan")
        running_pwnity.run_command("tool update nmap-pwn full-scan param '-p- -A'")
        running_pwnity.run_command("tool update nmap-pwn full-scan param '$target.ip'")

        # Lade die Entitäten in die Session
        running_pwnity.run_command("target load test-server-pwn")
        running_pwnity.run_command("tool load nmap-pwn")

        # Führe den 'pwn'-Befehl aus (nur Vorschau, ohne 'now' oder 'bg')
        preview_output = running_pwnity.run_command("pwn full-scan")
        clean_output = running_pwnity._strip_ansi(preview_output)

        # Überprüfe, ob der Platzhalter korrekt durch die IP (aus dem Test-Modus) ersetzt wurde
        assert "nmap-pwn -p- -A 127.0.0.1" in clean_output
        assert "This is a preview. The command has not been executed yet." in clean_output

    def test_pwn_now_creates_logbook_entry(self, running_pwnity):
        """Testet, ob 'pwn ... now' einen korrekten Logbook-Eintrag erstellt."""
        # 1. Setup: Ein einfaches 'echo' Tool erstellen
        tool_name = "echo"  # Use the actual command name
        cmd_name = "say-hello"
        test_string = "Hello Logbook from pwn now"
        running_pwnity.run_command(f"tool add {tool_name}")
        running_pwnity.run_command(f"tool update {tool_name} command {cmd_name}")
        # The string must be quoted to be treated as a single parameter
        running_pwnity.run_command(f"tool update {tool_name} {cmd_name} param \"{test_string}\"")
        running_pwnity.run_command(f"tool load {tool_name}")

        # 2. Befehl mit 'now' ausführen
        pwn_output = running_pwnity.run_command(f"pwn {cmd_name} now")

        # 3. Logbook-ID aus der Zusammenfassung extrahieren
        # The ID is now a UUID. We match on a hex string that can contain hyphens.
        match = re.search(r"Logbook ID\s+([0-9a-fA-F\-]+)", running_pwnity._strip_ansi(pwn_output))
        assert match, f"Konnte die Logbook-ID aus der 'pwn now' Ausgabe nicht extrahieren. Ausgabe war:\n{pwn_output}"
        log_id = match.group(1)

        # 4. Logbook-Eintrag überprüfen
        log_show_output = running_pwnity.run_command(f"logbook show {log_id}")
        clean_log_show_output = running_pwnity._strip_ansi(log_show_output)
        assert f"Output of Logbook Entry #{log_id}" in clean_log_show_output
        assert test_string in clean_log_show_output

    def test_tool_list_and_destroy(self, running_pwnity):
        """Testet das Auflisten und endgültige Löschen von Tools."""
        running_pwnity.run_command("tool add tool-a")
        running_pwnity.run_command("tool add tool-b")

        # 1. 'list' testen
        list_output = running_pwnity.run_command("tool list")
        clean_list = running_pwnity._strip_ansi(list_output)
        assert "tool-a" in clean_list
        assert "tool-b" in clean_list

        # 2. 'destroy' testen
        destroy_output = running_pwnity.run_command("tool destroy tool-a")
        assert "Tool 'tool-a' has been completely deleted" in destroy_output

        # 3. Überprüfen, ob das Tool aus der Liste verschwunden ist
        list_after_destroy = running_pwnity.run_command("tool list")
        clean_list_after = running_pwnity._strip_ansi(list_after_destroy)
        assert "tool-a" not in clean_list_after
        assert "tool-b" in clean_list_after

    def test_tool_load_unload(self, running_pwnity):
        """Testet das Laden und Entladen eines Tools in die Session."""
        tool_name = "test-load-tool"
        running_pwnity.run_command(f"tool add {tool_name}")

        # Laden und Prompt überprüfen
        load_output = running_pwnity.run_command(f"tool load {tool_name}")
        assert f"Tool '{tool_name}' loaded into active session" in load_output
        assert f"- [ {tool_name} ]" in running_pwnity._strip_ansi(load_output)

        # Entladen und Prompt überprüfen
        unload_output = running_pwnity.run_command("tool unload")
        assert f"Unloaded tool '{tool_name}' from the current session." in running_pwnity._strip_ansi(unload_output)
        assert f"- [ {tool_name} ]" not in running_pwnity._strip_ansi(unload_output)

    def test_tool_delete_param_and_command(self, running_pwnity):
        """Testet das kontextsensitive Löschen von Parametern und Befehlen."""
        tool_name = "deleter-tool"
        cmd_name = "scan"
        running_pwnity.run_command(f"tool add {tool_name}")
        running_pwnity.run_command(f"tool update {tool_name} command {cmd_name}")
        running_pwnity.run_command(f"tool update {tool_name} {cmd_name} param -p-")
        running_pwnity.run_command(f"tool update {tool_name} {cmd_name} param -sV")

        # 1. Parameter löschen
        delete_param_output = running_pwnity.run_command(f"tool delete {tool_name} {cmd_name} param -sV")
        assert "Parameter '-sV' deleted" in delete_param_output
        show_after_param_delete = running_pwnity.run_command(f"tool show {tool_name}")
        assert "-sV" not in show_after_param_delete

        # 2. Befehl löschen
        delete_cmd_output = running_pwnity.run_command(f"tool delete {tool_name} command {cmd_name}")
        assert f"Command '{cmd_name}' deleted" in delete_cmd_output
        show_after_cmd_delete = running_pwnity.run_command(f"tool show {tool_name}")
        assert cmd_name not in show_after_cmd_delete

    def test_tool_export(self, running_pwnity):
        """Testet den 'tool export' Befehl."""
        tool_name = "export-tool"
        running_pwnity.run_command(f"tool add {tool_name}")
        running_pwnity.run_command(f"tool update {tool_name} sudo true")
        running_pwnity.run_command(f"tool update {tool_name} command scan")
        running_pwnity.run_command(f"tool update {tool_name} scan param -p-")

        export_output = running_pwnity.run_command(f"tool export {tool_name}")
        clean_output = running_pwnity._strip_ansi(export_output)

        assert f"tool add {tool_name}" in clean_output
        assert f"tool update {tool_name} sudo true" in clean_output
        # shlex.quote does NOT add quotes for safe strings like '-p-'.
        assert f"tool update {tool_name} scan param -p-" in clean_output

    def test_tool_copy_command(self, running_pwnity, pwnity_env):
        """Testet den 'tool copy' Befehl auf Integrationsebene."""
        source_name = "copy_source_tool"
        dest_name = "copy_dest_tool"
        running_pwnity.run_command(f"tool add {source_name}")
        running_pwnity.run_command(f"tool update {source_name} description 'A test tool'")
        running_pwnity.run_command(f"tool update {source_name} command mycmd")

        # Führe den Kopierbefehl aus
        copy_output = running_pwnity.run_command(f"tool copy {source_name} {dest_name}")
        assert f"Tool '{source_name}' successfully copied to '{dest_name}'" in copy_output

        # Ermittle das Tool-Verzeichnis aus der Konfiguration
        tools_dir_raw = running_pwnity.run_command("config get DIRS.TOOLS")
        match = re.search(r"config get DIRS.TOOLS\n(.*?)\s*$", running_pwnity._strip_ansi(tools_dir_raw), re.MULTILINE)
        tools_dir = match.group(1).strip()

        # Überprüfe, ob die neue Datei existiert
        assert os.path.isfile(os.path.join(tools_dir, f"{dest_name}.json"))



    def test_pwn_bg_creates_job(self, running_pwnity):
        """Testet, ob 'pwn ... bg' einen Hintergrund-Job erstellt."""
        tool_name = "sleep-tool"
        running_pwnity.run_command(f"tool add {tool_name}")
        running_pwnity.run_command(f"tool update {tool_name} path /bin/sleep")
        running_pwnity.run_command(f"tool update {tool_name} command wait")
        running_pwnity.run_command(f"tool update {tool_name} wait param 5")
        running_pwnity.run_command(f"tool load {tool_name}")

        # Job im Hintergrund starten
        running_pwnity.run_command("pwn wait bg")
        
        # Job-Liste überprüfen
        jobs_list_output = running_pwnity.run_command("jobs list")
        assert "Running" in jobs_list_output
        assert "/bin/sleep 5" in jobs_list_output

    def test_tool_rename_updates_session(self, running_pwnity):
        """Testet, ob 'tool rename' auch das geladene Tool in der Session aktualisiert."""
        old_name = "old-tool"
        new_name = "new-tool"
        running_pwnity.run_command(f"tool add {old_name}")
        load_output = running_pwnity.run_command(f"tool load {old_name}")

        # Überprüfe den Prompt vor dem Umbenennen (nachdem ANSI-Codes entfernt wurden)
        assert f"- [ {old_name} ]" in running_pwnity._strip_ansi(load_output)

        # Benenne das Tool um
        rename_output = running_pwnity.run_command(f"tool rename {old_name} {new_name}")
        clean_rename_output = running_pwnity._strip_ansi(rename_output)
        assert f"Tool '{old_name}' has been renamed to '{new_name}'" in clean_rename_output
        assert f"Active session has been updated: tool '{old_name}' -> '{new_name}'" in clean_rename_output

        # Überprüfe, ob der Prompt und die Session aktualisiert wurden (im bereinigten Output)
        assert f"- [ {new_name} ]" in clean_rename_output

    def test_tool_reorder_param(self, running_pwnity):
        """Testet das Umsortieren von Parametern eines Tools."""
        tool_name = "reorder-tool"
        cmd_name = "test-cmd"
        running_pwnity.run_command(f"tool add {tool_name}")
        running_pwnity.run_command(f"tool update {tool_name} command {cmd_name}")
        running_pwnity.run_command(f"tool update {tool_name} {cmd_name} param param1")
        running_pwnity.run_command(f"tool update {tool_name} {cmd_name} param param2")
        running_pwnity.run_command(f"tool update {tool_name} {cmd_name} param param3")

        # Reorder param3 (index 3) to position 1
        reorder_output = running_pwnity.run_command(f"tool reorder {tool_name} {cmd_name} 3 1")
        assert "Parameter in 'reorder-tool test-cmd' moved from position 3 to 1." in reorder_output

        show_output = running_pwnity.run_command(f"tool show {tool_name}")
        clean_show_output = running_pwnity._strip_ansi(show_output)
        # Check the order in the output by finding the parameter lines
        param_lines = re.findall(r"(\d+):\s+(param\d+)", clean_show_output)
        assert len(param_lines) == 3
        assert param_lines[0][1] == "param3"
        assert param_lines[1][1] == "param1"
        assert param_lines[2][1] == "param2"

    def test_tool_update_command_field(self, running_pwnity):
        """Testet das Aktualisieren eines Feldes eines Befehls (z.B. execute_per_param)."""
        tool_name = "cmd-field-tool"
        cmd_name = "my-cmd"
        running_pwnity.run_command(f"tool add {tool_name}")
        running_pwnity.run_command(f"tool update {tool_name} command {cmd_name}")

        # Update execute_per_param to true
        update_output = running_pwnity.run_command(f"tool update {tool_name} {cmd_name} execute_per_param true")
        assert f"Field 'execute_per_param' in command '{cmd_name}' updated to 'True'." in update_output

        show_output = running_pwnity.run_command(f"tool show {tool_name}")
        clean_show_output = running_pwnity._strip_ansi(show_output)
        assert "execute_per_param" in clean_show_output
        assert "True" in clean_show_output

    def test_tool_update_top_level_field(self, running_pwnity):
        """Testet das Aktualisieren eines Top-Level-Feldes eines Tools (z.B. description)."""
        tool_name = "top-level-tool"
        description = "This is a test tool."
        running_pwnity.run_command(f"tool add {tool_name}")

        update_output = running_pwnity.run_command(f"tool update {tool_name} description \"{description}\"")
        assert f"Tool '{tool_name}' field 'description' updated -> {description}" in update_output

        show_output = running_pwnity.run_command(f"tool show {tool_name}")
        clean_show_output = running_pwnity._strip_ansi(show_output)
        assert "description" in clean_show_output
        assert description in clean_show_output

    def test_tool_delete_top_level_field(self, running_pwnity):
        """Testet das Löschen eines Top-Level-Feldes eines Tools."""
        tool_name = "delete-field-tool"
        running_pwnity.run_command(f"tool add {tool_name}")
        running_pwnity.run_command(f"tool update {tool_name} description \"Some description\"")

        show_before = running_pwnity.run_command(f"tool show {tool_name}")
        assert "Some description" in show_before

        delete_output = running_pwnity.run_command(f"tool delete {tool_name} description")
        assert f"Tool '{tool_name}' field 'description' deleted." in delete_output

        show_after = running_pwnity.run_command(f"tool show {tool_name}")
        assert "Some description" not in show_after

@pytest.mark.integration
class TestReportIntegration:
    """Gruppiert Integrationstests für das 'report'-Modul, inklusive notes und loot."""

    def test_report_add_load_and_show(self, running_pwnity):
        """Testet das Erstellen, Laden und Anzeigen eines Reports."""
        report_name = "project-alpha"
        
        # Report erstellen
        output = running_pwnity.run_command(f"report add {report_name}")
        assert f"Report '{report_name}' added." in output

        # Report laden
        output = running_pwnity.run_command(f"report load {report_name}")
        assert f"Report '{report_name}' loaded into session." in output
        
        # Prompt sollte sich geändert haben
        assert f"- [ {report_name} ]" in running_pwnity._strip_ansi(output)

        # Report anzeigen (sollte leer sein)
        show_output = running_pwnity.run_command(f"report show {report_name}")
        assert f"Report: {report_name}" in show_output
        assert "Report 'project-alpha' is empty." in show_output

    def test_note_and_loot_workflow(self, running_pwnity):
        """Testet den kompletten CRUD-Zyklus für Notizen und Loot."""
        report_name = "project-beta"
        running_pwnity.run_command(f"report add {report_name}")
        running_pwnity.run_command(f"report load {report_name}")

        # Notiz und Loot hinzufügen
        add_note_output = running_pwnity.run_command("note add Found admin panel at /secret-admin")
        assert "Note added to report" in add_note_output
        add_loot_output = running_pwnity.run_command("loot add credential admin:password123")
        assert "Loot (credential) added to report" in add_loot_output

        # Überprüfen, ob die Daten im Report sind
        show_output_before = running_pwnity.run_command("report show")
        clean_output_before = running_pwnity._strip_ansi(show_output_before)
        assert "Found admin panel" in clean_output_before
        assert "admin:password123" in clean_output_before

        # Notiz und Loot löschen
        delete_note_output = running_pwnity.run_command("note delete 1")
        assert "Note 1 deleted" in delete_note_output
        delete_loot_output = running_pwnity.run_command("loot delete 1")
        assert "Loot entry 1 deleted" in delete_loot_output

        # Überprüfen, ob die Daten entfernt wurden
        show_output_after = running_pwnity.run_command("report show")
        assert "Report 'project-beta' is empty." in show_output_after

    def test_report_unload(self, running_pwnity):
        """Testet das Entladen eines Reports aus der Session."""
        report_name = "unload-report"
        running_pwnity.run_command(f"report add {report_name}")
        load_output = running_pwnity.run_command(f"report load {report_name}")
        assert f"- [ {report_name} ]" in running_pwnity._strip_ansi(load_output)

        unload_output = running_pwnity.run_command("report unload")
        assert f"Unloaded report '{report_name}' from the current session." in running_pwnity._strip_ansi(unload_output)
        assert f"- [ {report_name} ]" not in running_pwnity._strip_ansi(unload_output)

    def test_report_rename_updates_session(self, running_pwnity):
        """Testet, ob 'report rename' auch den geladenen Report in der Session aktualisiert."""
        old_name = "old-report"
        new_name = "new-report"
        running_pwnity.run_command(f"report add {old_name}")
        running_pwnity.run_command(f"report load {old_name}")

        rename_output = running_pwnity.run_command(f"report rename {old_name} {new_name}")
        clean_rename_output = running_pwnity._strip_ansi(rename_output)
        assert f"Report '{old_name}' has been renamed to '{new_name}'" in clean_rename_output
        assert f"Active session has been updated: report '{old_name}' -> '{new_name}'" in clean_rename_output

        # Überprüfe, ob der Prompt den neuen Namen anzeigt
        assert f"- [ {new_name} ]" in clean_rename_output

    def test_report_destroy(self, running_pwnity):
        """Testet das endgültige Löschen eines Reports."""
        report_name = "destroy-report"
        running_pwnity.run_command(f"report add {report_name}")

        # Überprüfe, ob der Report in der Liste ist
        list_before = running_pwnity.run_command("report list")
        assert report_name in list_before

        # Zerstöre den Report
        destroy_output = running_pwnity.run_command(f"report destroy {report_name}")
        assert f"Report '{report_name}' has been completely deleted" in destroy_output

        # Überprüfe, ob der Report aus der Liste verschwunden ist
        list_after = running_pwnity.run_command("report list")
        assert report_name not in list_after

    def test_report_export_and_render(self, running_pwnity):
        """Testet die 'export' und 'render' Befehle für einen Report."""
        report_name = "export-render-report"
        running_pwnity.run_command(f"report add {report_name}")
        running_pwnity.run_command(f"report load {report_name}")
        running_pwnity.run_command("note add 'Test note for export'")
        running_pwnity.run_command("loot add flag 'FLAG{...}'")

        # 1. Export testen
        export_output = running_pwnity.run_command(f"report export {report_name}")
        clean_export = running_pwnity._strip_ansi(export_output)
        assert "note add 'Test note for export'" in clean_export
        assert "loot add flag 'FLAG{...}'" in clean_export

        # 2. Render testen
        render_output = running_pwnity.run_command(f"report render {report_name}")
        assert f"Report '{report_name}' rendered successfully" in render_output

    def test_report_view_file(self, running_pwnity):
        """Testet den 'report view' Befehl."""
        report_name = "view-file-report" # Erstelle manuell eine Datei im Report-Verzeichnis
        running_pwnity.run_command(f"report add {report_name}")
        running_pwnity.run_command(f"report load {report_name}")

        # Wir müssen den Pfad über den 'config'-Befehl ermitteln
        reports_dir_raw = running_pwnity.run_command("config get DIRS.REPORTS")
        # --- FIX for flaky test ---
        # This regex is more robust. It waits for the command echo, a newline,
        # the path, and then another newline before the prompt. This prevents a race
        # condition where the test reads the prompt before the command output is written.
        command_str = "config get DIRS.REPORTS" # This regex is more robust. It waits for the command echo, a newline,
        match = re.search(rf"^{re.escape(command_str)}\n(.*?)\s*$", running_pwnity._strip_ansi(reports_dir_raw), re.MULTILINE) # the path, and then another newline before the prompt. This prevents a race
        assert match, "Konnte das Reports-Verzeichnis nicht aus der Konfiguration extrahieren."
        reports_dir = match.group(1).strip()
        
        report_path = os.path.join(reports_dir, report_name)
        os.makedirs(report_path, exist_ok=True)
        (pathlib.Path(report_path) / "test.txt").write_text("File content for view test.")

        # 'view' ausführen und die Ausgabe überprüfen
        view_output = running_pwnity.run_command("report view test.txt")
        assert "File content for view test." in view_output

@pytest.mark.integration
class TestWordlistIntegration:
    """Gruppiert Integrationstests für das 'wordlist'-Modul."""

    def test_wordlist_add_and_update(self, running_pwnity):
        """Testet das Hinzufügen und Aktualisieren einer Wordlist."""
        wordlist_name = "common-test"
        wordlist_path = "/usr/share/wordlists/dirb/common.txt"

        # Wordlist hinzufügen
        output = running_pwnity.run_command(f"wordlist add {wordlist_name}")
        assert f"Wordlist '{wordlist_name}' added." in output

        # Pfad aktualisieren
        output = running_pwnity.run_command(f"wordlist update {wordlist_name} path {wordlist_path}")
        assert f"field 'path' updated" in output

        # Überprüfen mit 'wordlist show'
        show_output = running_pwnity.run_command(f"wordlist show {wordlist_name}")
        assert wordlist_path in show_output

    def test_wordlist_load_and_placeholder(self, running_pwnity):
        """Testet das Laden einer Wordlist und die Auflösung des $wordlist.path Platzhalters."""
        running_pwnity.run_command("wordlist add rockyou-test")
        running_pwnity.run_command("wordlist update rockyou-test path /usr/share/wordlists/rockyou.txt")
        running_pwnity.run_command("wordlist load rockyou-test")

        # Überprüfe, ob der Platzhalter korrekt aufgelöst wird
        output = running_pwnity.run_command("print $wordlist.path")
        assert "/usr/share/wordlists/rockyou.txt" in running_pwnity._strip_ansi(output)

    def test_wordlist_list_multiple(self, running_pwnity):
        """Testet den 'wordlist list' Befehl mit mehreren Einträgen."""
        running_pwnity.run_command("wordlist add list-a")
        running_pwnity.run_command("wordlist add list-b")

        list_output = running_pwnity.run_command("wordlist list")
        clean_output = running_pwnity._strip_ansi(list_output)

        assert "list-a" in clean_output
        assert "list-b" in clean_output
        assert "Available Wordlists" in clean_output

    def test_wordlist_show_details(self, running_pwnity):
        """Testet den 'wordlist show' Befehl für detaillierte Informationen."""
        wordlist_name = "show-list"
        path = "/tmp/my-custom-list.txt"
        description = "A custom list for testing."

        running_pwnity.run_command(f"wordlist add {wordlist_name}")
        running_pwnity.run_command(f"wordlist update {wordlist_name} path {path}")
        running_pwnity.run_command(f"wordlist update {wordlist_name} description \"{description}\"")

        show_output = running_pwnity.run_command(f"wordlist show {wordlist_name}")
        clean_output = running_pwnity._strip_ansi(show_output)

        assert f"Wordlist: {wordlist_name}" in clean_output
        assert re.search(rf"path\s+{re.escape(path)}", clean_output)
        assert re.search(rf"description\s+{re.escape(description)}", clean_output)

    def test_wordlist_rename_updates_session(self, running_pwnity):
        """Testet, ob 'wordlist rename' auch die geladene Wordlist in der Session aktualisiert."""
        old_name = "old-wordlist"
        new_name = "new-wordlist"
        running_pwnity.run_command(f"wordlist add {old_name}")
        load_output = running_pwnity.run_command(f"wordlist load {old_name}")

        # Überprüfe den Prompt vor dem Umbenennen
        assert f"- [ {old_name} ]" in running_pwnity._strip_ansi(load_output)

        # Benenne die Wordlist um
        rename_output = running_pwnity.run_command(f"wordlist rename {old_name} {new_name}")
        clean_rename_output = running_pwnity._strip_ansi(rename_output)
        assert f"Wordlist '{old_name}' has been renamed to '{new_name}'" in clean_rename_output
        assert f"Active session has been updated: wordlist '{old_name}' -> '{new_name}'" in clean_rename_output

        # Überprüfe, ob der Prompt und die Session aktualisiert wurden
        assert f"- [ {new_name} ]" in clean_rename_output

    def test_wordlist_delete_field(self, running_pwnity):
        """Testet das Löschen eines Feldes von einer Wordlist."""
        wordlist_name = "delete-field-list"
        running_pwnity.run_command(f"wordlist add {wordlist_name}")
        running_pwnity.run_command(f"wordlist update {wordlist_name} description \"Temporary description\"")

        show_before = running_pwnity.run_command(f"wordlist show {wordlist_name}")
        assert "Temporary description" in show_before

        running_pwnity.run_command(f"wordlist delete {wordlist_name} description")

        show_after = running_pwnity.run_command(f"wordlist show {wordlist_name}")
        assert "Temporary description" not in show_after

    def test_wordlist_destroy_command(self, running_pwnity, pwnity_env):
        """Testet das endgültige Löschen einer Wordlist mit 'destroy'."""
        wordlist_name = "destroy-list"
        running_pwnity.run_command(f"wordlist add {wordlist_name}")

        expected_file = os.path.join(pwnity_env["project_root"], "data", "wordlists", f"{wordlist_name}.json")
        # Da wir im Testmodus sind, ist der Pfad anders. Wir müssen den Pfad aus der Konfiguration holen.
        wordlists_dir = running_pwnity.run_command("config get DIRS.WORDLISTS")
        # --- FIX for flaky test ---
        # This regex is more robust. It waits for the command echo, a newline,
        # the path, and then another newline before the prompt. This prevents a race
        # condition where the test reads the prompt before the command output is written.
        command_str = "config get DIRS.WORDLISTS"
        match = re.search(rf"^{re.escape(command_str)}\n(.*?)\s*$", running_pwnity._strip_ansi(wordlists_dir), re.MULTILINE)
        assert match, "Could not extract wordlists directory from config."
        wordlists_dir_path = match.group(1).strip()
        expected_file = os.path.join(wordlists_dir_path, f"{wordlist_name}.json")

        assert os.path.isfile(expected_file)

        running_pwnity.run_command(f"wordlist destroy {wordlist_name}")
        assert not os.path.isfile(expected_file)

    def test_wordlist_unload_command(self, running_pwnity):
        """Testet das Entladen einer Wordlist aus der Session."""
        wordlist_name = "unload-list"
        running_pwnity.run_command(f"wordlist add {wordlist_name}")
        running_pwnity.run_command(f"wordlist load {wordlist_name}")

        unload_output = running_pwnity.run_command("wordlist unload")
        assert f"Unloaded wordlist '{wordlist_name}' from the current session." in running_pwnity._strip_ansi(unload_output)
        assert f"- [ {wordlist_name} ]" not in running_pwnity._strip_ansi(unload_output)

    def test_wordlist_export_command(self, running_pwnity):
        """Testet den 'wordlist export' Befehl auf Integrationsebene."""
        wordlist_name = "export-list"
        path = "/opt/wordlists/custom.txt"
        description = "My custom export list."

        running_pwnity.run_command(f"wordlist add {wordlist_name}")
        running_pwnity.run_command(f"wordlist update {wordlist_name} path {path}")
        running_pwnity.run_command(f"wordlist update {wordlist_name} description \"{description}\"")

        export_output = running_pwnity.run_command(f"wordlist export {wordlist_name}")
        clean_output = running_pwnity._strip_ansi(export_output)

        assert f"wordlist add {wordlist_name}" in clean_output
        # shlex.quote does not add quotes for safe strings like a file path without spaces.
        assert f"wordlist update {wordlist_name} path {path}" in clean_output
        assert f"wordlist update {wordlist_name} description '{description}'" in clean_output

@pytest.mark.integration
class TestSessionManagement:
    """Gruppiert Integrationstests für 'session', 'preset' und 'profile'."""

    def test_session_switching_and_state(self, running_pwnity):
        """Testet das Erstellen, Wechseln und die Zustandsisolierung von Sessions."""
        # Setup: Ein Target erstellen, das wir laden können
        running_pwnity.run_command("target add state-test-target")

        # 1. Neue Session erstellen und etwas laden
        output = running_pwnity.run_command("session new project-a")
        assert "Session 'project-a' created" in output
        running_pwnity.run_command("target load state-test-target")
        
        # 2. Zweite Session erstellen und prüfen, ob sie leer ist
        output = running_pwnity.run_command("session new project-b")
        assert "Session 'project-b' created" in output
        raw_show_output_b = running_pwnity.run_command("session show")
        clean_show_output_b = running_pwnity._strip_ansi(raw_show_output_b)
        assert re.search(r"Target\s+None", clean_show_output_b)

        # 3. Zurück zur ersten Session wechseln und Zustand prüfen
        output = running_pwnity.run_command("session switch project-a")
        assert "Switched to session 'project-a'" in output
        raw_show_output_a = running_pwnity.run_command("session show")
        clean_show_output_a = running_pwnity._strip_ansi(raw_show_output_a)
        assert re.search(r"Target\s+state-test-target", clean_show_output_a)

    def test_preset_save_and_load(self, running_pwnity):
        """Testet das Speichern einer Session als Preset und das anschließende Laden."""
        # Setup: Ein Target und ein Tool erstellen und laden
        running_pwnity.run_command("target add preset-target")
        running_pwnity.run_command("tool add preset-tool")
        running_pwnity.run_command("target load preset-target")
        running_pwnity.run_command("tool load preset-tool")

        # 1. Aktuelle Session als Preset speichern
        output = running_pwnity.run_command("preset save my-scan-preset")
        assert "session saved as preset 'my-scan-preset'" in output

        # 2. Zu einer leeren Session wechseln
        running_pwnity.run_command("session new clean-slate")

        # 3. Das Preset laden (sollte eine neue Session erstellen und alles laden)
        raw_output = running_pwnity.run_command("preset load my-scan-preset")
        clean_output = running_pwnity._strip_ansi(raw_output)
        assert "Preset Loaded: my-scan-preset" in clean_output
        assert re.search(r"Target\s+preset-target", clean_output)
        assert re.search(r"Tool\s+preset-tool", clean_output)

    def test_profile_update_and_placeholder(self, running_pwnity):
        """Testet das Setzen eines globalen Profil-Wertes und dessen Verwendung als Platzhalter."""
        lhost_ip = "10.10.14.5"
        output = running_pwnity.run_command(f"profile update lhost {lhost_ip}")
        assert f"Profile setting 'lhost' updated" in output

        # Überprüfe, ob der Platzhalter korrekt aufgelöst wird
        output = running_pwnity.run_command("print $profile.lhost")
        assert lhost_ip in output

    def test_profile_show_and_delete(self, running_pwnity):
        """Testet 'profile show' und 'profile delete'."""
        # 1. Setze einige Werte
        running_pwnity.run_command("profile update test_key_1 value1")
        running_pwnity.run_command("profile update test_key_2 'value with spaces'")

        # 2. Teste 'profile show'
        show_output = running_pwnity.run_command("profile show")
        clean_show = running_pwnity._strip_ansi(show_output)
        assert "test_key_1" in clean_show
        assert "value1" in clean_show
        assert "test_key_2" in clean_show
        assert "value with spaces" in clean_show

        # 3. Teste 'profile delete'
        delete_output = running_pwnity.run_command("profile delete test_key_1")
        assert "Profile setting 'test_key_1' deleted" in delete_output

        # 4. Überprüfe mit 'profile show' erneut
        show_after_delete = running_pwnity.run_command("profile show")
        clean_after_delete = running_pwnity._strip_ansi(show_after_delete)
        assert "test_key_1" not in clean_after_delete
        assert "value1" not in clean_after_delete
        assert "test_key_2" in clean_after_delete # Stelle sicher, dass andere Schlüssel unberührt bleiben

@pytest.mark.integration
class TestHelpIntegration:
    """Gruppiert Integrationstests für den 'help'-Befehl."""

    def test_help_main_overview(self, running_pwnity):
        """Testet, ob 'help' ohne Argumente die Hauptübersicht anzeigt."""
        output = running_pwnity.run_command("help")
        clean_output = running_pwnity._strip_ansi(output)
        assert "Available Commands" in clean_output
        assert "Core Workflow" in clean_output
        assert "target" in clean_output
        assert "tool" in clean_output

    def test_help_for_top_level_command(self, running_pwnity):
        """Testet, ob 'help <command>' die detaillierte Hilfe für einen Befehl anzeigt."""
        output = running_pwnity.run_command("help target")
        clean_output = running_pwnity._strip_ansi(output)
        assert "Help: `target`" in clean_output
        assert "Manages targets, which store all relevant information" in clean_output # Description
        assert "Available Actions" in clean_output # Subcommands
        assert "Common Examples" in clean_output

    def test_help_for_subcommand(self, running_pwnity):
        """Testet, ob 'help <command> <subcommand>' die Hilfe für einen Unterbefehl anzeigt."""
        output = running_pwnity.run_command("help target add")
        clean_output = running_pwnity._strip_ansi(output)
        assert "Help: `target add`" in clean_output
        assert "Usage: target add" in clean_output
        assert "Positional Arguments" in clean_output

    def test_tool_help_subcommand(self, running_pwnity):
        """Testet, ob 'tool help' die detaillierte Hilfe für den 'tool'-Befehl anzeigt."""
        output = running_pwnity.run_command("tool help")
        clean_output = running_pwnity._strip_ansi(output)
        assert "Help: `tool`" in clean_output
        assert "Configures external command-line tools." in clean_output # Description
        assert "Available Actions" in clean_output
        assert "Common Examples" in clean_output

    def test_tool_dash_h_flag(self, running_pwnity):
        """Testet, ob 'tool -h' die detaillierte Hilfe für den 'tool'-Befehl anzeigt."""
        output = running_pwnity.run_command("tool -h")
        clean_output = running_pwnity._strip_ansi(output)
        assert "Help: `tool`" in clean_output
        assert "Configures external command-line tools." in clean_output # Description
        assert "Available Actions" in clean_output
        assert "Common Examples" in clean_output

    def test_target_help_subcommand(self, running_pwnity):
        """Testet, ob 'target help' die detaillierte Hilfe für den 'target'-Befehl anzeigt."""
        output = running_pwnity.run_command("target help")
        clean_output = running_pwnity._strip_ansi(output)
        assert "Help: `target`" in clean_output
        assert "Manages targets, which store all relevant information" in clean_output
        assert "Available Actions" in clean_output
        assert "Common Examples" in clean_output

    def test_wordlist_help_subcommand(self, running_pwnity):
        """Testet, ob 'wordlist help' die detaillierte Hilfe für den 'wordlist'-Befehl anzeigt."""
        output = running_pwnity.run_command("wordlist help")
        clean_output = running_pwnity._strip_ansi(output)
        assert "Help: `wordlist`" in clean_output
        assert "Manages references to wordlist files" in clean_output
        assert "Available Actions" in clean_output
        assert "Common Examples" in clean_output

    def test_profile_help_subcommand(self, running_pwnity):
        """Testet, ob 'profile help' die detaillierte Hilfe für den 'profile'-Befehl anzeigt."""
        output = running_pwnity.run_command("profile help")
        clean_output = running_pwnity._strip_ansi(output)
        assert "Help: `profile`" in clean_output
        assert "Manages global key-value settings" in clean_output
        assert "Available Actions" in clean_output
        assert "Common Examples" in clean_output

    def test_preset_help_subcommand(self, running_pwnity):
        """Testet, ob 'preset help' die detaillierte Hilfe für den 'preset'-Befehl anzeigt."""
        output = running_pwnity.run_command("preset help")
        clean_output = running_pwnity._strip_ansi(output)
        assert "Help: `preset`" in clean_output
        assert "Manages presets, which are saved sessions" in clean_output
        assert "Available Actions" in clean_output
        assert "Common Examples" in clean_output


@pytest.mark.integration
class TestLibraryIntegration:
    """Gruppiert Integrationstests für das 'library'-Modul."""

    def test_library_add_update_and_list(self, running_pwnity):
        """Testet das Hinzufügen, Aktualisieren und Auflisten von Bibliothekseinträgen."""
        entry_name = "GTFOBins"
        entry_url = "https://gtfobins.github.io/"
        entry_category = "Cheatsheet"

        # 1. Eintrag hinzufügen (mit Anführungszeichen, um Leerzeichen zu handhaben)
        output = running_pwnity.run_command(f"library add \"{entry_name}\"")
        assert "Added new, empty library entry" in output

        # 2. URL und Kategorie aktualisieren
        running_pwnity.run_command(f"library update \"{entry_name}\" url {entry_url}")
        running_pwnity.run_command(f"library update \"{entry_name}\" category {entry_category}")

        # 3. Überprüfen mit 'library list' und 'library show'
        list_output = running_pwnity.run_command("library list")
        assert entry_name in list_output
        assert entry_category in list_output

        show_output = running_pwnity.run_command(f"library show \"{entry_name}\"")
        assert entry_url in show_output

    def test_library_check_and_open(self, running_pwnity, mocker):
        """Testet die 'check' und 'open' Befehle, indem Netzwerkaufrufe gemockt werden."""
        entry_name = "Test Check"
        running_pwnity.run_command(f"library add \"{entry_name}\"")
        running_pwnity.run_command(f"library update \"{entry_name}\" url http://test-check.local")

        # Mocke 'requests.get', um einen erfolgreichen Check zu simulieren
        mock_response = mocker.MagicMock()
        mock_response.status_code = 200
        mocker.patch("modules.managers.library_manager.requests.get", return_value=mock_response)

        # 1. 'check' ausführen und die Ausgabe überprüfen
        check_output = running_pwnity.run_command(f"library check \"{entry_name}\"")
        assert "URL for 'Test Check' is reachable. Status: 200" in check_output

        # 2. 'open' ausführen und die Ausgabe überprüfen. Der pwnity_TEST_MODE verhindert das Öffnen eines echten Browsers.
        open_output = running_pwnity.run_command(f"library open \"{entry_name}\"")
        assert "Opening 'http://test-check.local' in your default web browser..." in open_output

@pytest.mark.integration
class TestRevshellIntegration:
    """Gruppiert Integrationstests für das 'revshell'-Modul."""

    def test_revshell_generation_scenarios(self, running_pwnity):
        """Testet die Generierung von Revshells mit und ohne Profil-Einstellungen."""
        
        # 1. Generate with auto-detected IP and default port
        # The test environment might not have a default route, so we check for either 127.0.0.1 or another IP.
        # The default port is 1337.
        output1 = running_pwnity.run_command("revshell bash-tcp")
        clean_output1 = running_pwnity._strip_ansi(output1)
        assert "/dev/tcp/" in clean_output1
        assert "1337" in clean_output1
        assert "LHOST not set in profile, attempting to auto-detect..." in clean_output1

        # 2. Generate with explicit IP and port
        output2 = running_pwnity.run_command("revshell python3 10.20.30.40 4444")
        clean_output2 = running_pwnity._strip_ansi(output2)
        assert "10.20.30.40" in clean_output2
        assert "4444" in clean_output2

        # 3. Set profile values and generate again
        running_pwnity.run_command("profile update lhost 10.10.14.5")
        running_pwnity.run_command("profile update lport 9001")
        output3 = running_pwnity.run_command("revshell bash-tcp")
        assert "10.10.14.5" in output3
        assert "9001" in output3

@pytest.mark.integration
class TestJobManagerIntegration:
    """Gruppiert Integrationstests für das 'jobs'-Modul."""

    def test_job_lifecycle(self, running_pwnity):
        """Testet den kompletten Lebenszyklus eines Hintergrund-Jobs: bg, list, show, kill, clear."""
        # 1. Setup: Ein Tool erstellen, das einen langlebigen Befehl ausführt
        # We use the actual 'sleep' command which is universally available.
        tool_name = "sleep"
        cmd_name = "wait-5"
        running_pwnity.run_command(f"tool add {tool_name}")
        running_pwnity.run_command(f"tool update {tool_name} command {cmd_name}")
        running_pwnity.run_command(f"tool update {tool_name} {cmd_name} param 5")
        running_pwnity.run_command(f"tool load {tool_name}")

        # 2. Job im Hintergrund starten
        # Start the job and ignore the immediate output, as it can be flaky in tests.
        running_pwnity.run_command(f"pwn {cmd_name} bg")

        # 3. Verify the job by checking the job list, which is more robust.
        # We add a small sleep to give the background thread time to start the job and update the list.
        import time; time.sleep(0.2)
        list_output = running_pwnity.run_command("jobs list")
        # Find the line with the running job and extract its UUID prefix.
        # The regex now specifically captures only the hex characters and hyphens,
        # ignoring the ellipsis (...) that might follow a truncated ID.
        match = re.search(r"^\s*│?\s*([0-9a-fA-F\-]+)[\s…]+.*Running", running_pwnity._strip_ansi(list_output), re.MULTILINE)
        assert match, f"Konnte keinen laufenden Job in der 'jobs list' Ausgabe finden. Ausgabe war:\n{list_output}"
        job_id = match.group(1)

        # 4. 'jobs list' überprüfen
        list_output = running_pwnity.run_command("jobs list")
        clean_list_output = running_pwnity._strip_ansi(list_output)
        assert job_id in clean_list_output
        assert "Running" in clean_list_output

        # 5. 'jobs kill' ausführen
        kill_output = running_pwnity.run_command(f"jobs kill {job_id}")
        assert f"Kill signal sent to job {job_id}" in kill_output

        # 6. 'jobs clear' ausführen
        # Wir warten kurz, damit der Job-Status auf 'killed' aktualisiert wird, bevor wir aufräumen.
        import time; time.sleep(0.5)
        clear_output = running_pwnity.run_command("jobs clear")
        assert "1 finished jobs removed" in clear_output

@pytest.mark.integration
class TestProxyIntegration:
    """Gruppiert Integrationstests für das 'proxy'-Modul."""

    def test_proxy_on_off_and_show(self, running_pwnity):
        """Testet das Ein- und Ausschalten des Proxys und die 'show'-Ausgabe."""
        # Proxy ist standardmäßig aus
        initial_output = running_pwnity.run_command("proxy show")
        assert "DISABLED" in initial_output

        # Proxy einschalten
        on_output = running_pwnity.run_command("proxy on")
        assert "Proxy enabled" in on_output
        show_after_on = running_pwnity.run_command("proxy show")
        assert "ENABLED" in show_after_on

        # Proxy ausschalten
        off_output = running_pwnity.run_command("proxy off")
        assert "Proxy disabled" in off_output
        show_after_off = running_pwnity.run_command("proxy show")
        assert "DISABLED" in show_after_off

    def test_proxy_set_reset_and_placeholder(self, running_pwnity):
        """Testet das Setzen, Zurücksetzen und die Platzhalterauflösung für Proxy-Einstellungen."""
        # Globale Standardeinstellung aus config.json ist 127.0.0.1:8080
        
        # 1. Session-spezifischen Host setzen und Platzhalter prüfen
        running_pwnity.run_command("proxy set host localhost")
        output1 = running_pwnity.run_command("print $proxy.host")
        assert "localhost" in output1

        # 2. Session-spezifischen Host zurücksetzen und Platzhalter erneut prüfen
        running_pwnity.run_command("proxy reset host")
        output2 = running_pwnity.run_command("print $proxy.host")
        # Sollte jetzt auf den globalen Standardwert aus config.json zurückfallen
        assert "localhost" in output2

@pytest.mark.integration
class TestUtilityCommands:
    """Gruppiert Integrationstests für verschiedene Utility-Befehle."""

    def test_print_and_placeholders_command(self, running_pwnity):
        """Testet den 'print'-Befehl mit Platzhaltern und den 'placeholders'-Befehl."""
        # Setup
        running_pwnity.run_command("target add print-target")
        running_pwnity.run_command("target update print-target url http://print-test.local")
        running_pwnity.run_command("target load print-target")

        # 1. Test 'print' with a simple placeholder
        output = running_pwnity.run_command("print $target.ip")
        assert "127.0.0.1" in output

        # 2. Test 'print' with a function
        output = running_pwnity.run_command("print b64encode($target.name)")
        assert "cHJpbnQtdGFyZ2V0" in output # b64("print-target")

        # 3. Test 'placeholders' command
        output = running_pwnity.run_command("placeholders target")
        clean_output = running_pwnity._strip_ansi(output)
        assert "$target.ip" in clean_output
        assert "$target.hostname" in clean_output

    def test_identify_command(self, running_pwnity):
        """Testet den 'identify'-Befehl zur Hash-Identifikation."""
        md5_hash = "5f4dcc3b5aa765d61d8327deb882cf99" # "hello"
        output = running_pwnity.run_command(f"identify {md5_hash}")
        clean_output = running_pwnity._strip_ansi(output)
        assert "MD5" in clean_output
        assert "NTLM" in clean_output

@pytest.mark.integration
class TestParserIntegration:
    """Gruppiert Integrationstests für das 'parser'-Modul."""

    def test_parser_apply_workflow(self, running_pwnity):
        """
        Testet den kompletten Workflow:
        1. Parser erstellen
        2. Befehl ausführen, um einen Logbook-Eintrag zu erzeugen
        3. Report laden
        4. Parser auf den Logbook-Eintrag anwenden
        5. Überprüfen, ob die Ergebnisse im Report gespeichert wurden
        """
        # 1. Parser erstellen
        running_pwnity.run_command("parser add ip-finder")
        running_pwnity.run_command("parser update ip-finder add-rule ips")
        running_pwnity.run_command("parser update ip-finder ips regex \"(\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}\\.\\d{1,3})\"")

        # 2. Report laden (VOR der Befehlsausführung)
        running_pwnity.run_command("report add parser-test-report")
        running_pwnity.run_command("report load parser-test-report")

        # 3. Logbook-Eintrag erzeugen
        running_pwnity.run_command("tool add echo")
        running_pwnity.run_command("tool update echo command say")
        running_pwnity.run_command("tool update echo say param 'IPs found: 1.1.1.1 and 8.8.8.8'")
        running_pwnity.run_command("tool load echo")
        running_pwnity.run_command("pwn say now") # Logbook-Eintrag #1 wird erstellt

        # 4. Parser anwenden
        running_pwnity.run_command("parser apply ip-finder 1")

        # 5. Ergebnisse im Report überprüfen
        show_output = running_pwnity.run_command("report show")
        clean_output = running_pwnity._strip_ansi(show_output)
        assert "1.1.1.1" in clean_output
        assert "8.8.8.8" in clean_output

    def test_parser_apply_fails_without_report(self, running_pwnity):
        """Testet, dass der Parser eine Fehlermeldung ausgibt, wenn kein Report geladen ist."""
        # 1. Parser und Log-Eintrag erstellen
        running_pwnity.run_command("parser add ip-finder-no-report")
        running_pwnity.run_command("parser update ip-finder-no-report add-rule ips")
        # The regex value should not be quoted in the command
        running_pwnity.run_command("parser update ip-finder-no-report ips regex (\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}\\.\\d{1,3})")
        running_pwnity.run_command("tool add echo")  # FIX: Use valid command
        running_pwnity.run_command("tool update echo command say")
        running_pwnity.run_command("tool update echo say param 1.2.3.4")  # Simplified param
        running_pwnity.run_command("tool load echo")
        pwn_output = running_pwnity.run_command("pwn say now")  # Erstellt Logbook-Eintrag

        # Extract log ID
        # The ID is now a UUID.
        match = re.search(r"Logbook ID\s+([0-9a-fA-F\-]+)", running_pwnity._strip_ansi(pwn_output))
        assert match, f"Konnte die Logbook-ID aus der 'pwn now' Ausgabe nicht extrahieren. Ausgabe war:\n{pwn_output}"
        log_id = match.group(1)

        # 2. Sicherstellen, dass kein Report geladen ist (Standardzustand)

        # 3. Parser anwenden und die Ausgabe überprüfen
        apply_output = running_pwnity.run_command(f"parser apply ip-finder-no-report {log_id}")
        clean_output = running_pwnity._strip_ansi(apply_output)

        assert "No report loaded. Findings were found but cannot be saved." in clean_output
        assert "Create and load a report to save findings" in clean_output
        assert "report add my-report" in clean_output

@pytest.mark.integration
class TestOverviewIntegration:
    """Gruppiert Integrationstests für den 'overview'-Befehl."""

    def test_overview_verbose_and_short(self, running_pwnity):
        """Testet die detaillierte und die kurze 'overview'-Ansicht."""
        # 1. Setup: Eine Session mit geladenen Entitäten erstellen
        running_pwnity.run_command("target add overview-target")
        running_pwnity.run_command("target update overview-target url http://overview.test/path")
        running_pwnity.run_command("tool add overview-tool")
        running_pwnity.run_command("tool update overview-tool command scan")
        running_pwnity.run_command("tool update overview-tool scan param -p-")
        running_pwnity.run_command("tool update overview-tool scan param $target.ip")
        running_pwnity.run_command("report add overview-report")
        running_pwnity.run_command("wordlist add overview-list")
        running_pwnity.run_command("wordlist update overview-list path /tmp/list.txt")

        running_pwnity.run_command("target load overview-target")
        running_pwnity.run_command("tool load overview-tool")
        running_pwnity.run_command("report load overview-report")
        running_pwnity.run_command("wordlist load overview-list")

        # Add a note now that the report is loaded
        running_pwnity.run_command("note add 'This is an overview note.'")

        # 2. Detaillierte Übersicht testen
        verbose_output = running_pwnity.run_command("overview")
        clean_verbose = running_pwnity._strip_ansi(verbose_output)

        assert "Session Overview: default" in clean_verbose
        # Verify details, not just names
        assert "Target: overview-target" in clean_verbose
        assert "url: http://overview.test/path" in clean_verbose
        assert "Tool: overview-tool" in clean_verbose
        assert "$target.ip" in clean_verbose # Check for tool parameter
        assert "Report Data: overview-report" in clean_verbose
        assert "This is an overview note." in clean_verbose # Check for report content
        assert "Wordlist: overview-list" in clean_verbose
        assert "/tmp/list.txt" in clean_verbose

        # 3. Kurze Übersicht testen
        short_output = running_pwnity.run_command("overview --short")
        clean_short = running_pwnity._strip_ansi(short_output)

        assert "overview-target" in clean_short
        assert "overview-tool" in clean_short
        assert "overview-report" in clean_short
        assert "overview-list" in clean_short

@pytest.mark.integration
class TestDispatchCommandIntegration:
    """
    Gruppiert Integrationstests, die speziell das Verhalten der
    zentralen `_dispatch_command`-Methode überprüfen.
    """

    def test_dispatch_standard_subcommand(self, running_pwnity):
        """Testet, ob ein Standard-Befehl (z.B. 'target list') korrekt weitergeleitet wird."""
        # 'target list' sollte die Liste der Targets anzeigen. In einem sauberen Zustand ist diese leer.
        output = running_pwnity.run_command("target list")
        clean_output = running_pwnity._strip_ansi(output)
        assert "No Targets found." in clean_output

    def test_dispatch_help_subcommand(self, running_pwnity):
        """Testet, ob 'target help' an den HelpManager weitergeleitet wird."""
        output = running_pwnity.run_command("target help")
        clean_output = running_pwnity._strip_ansi(output)
        assert "Help: `target`" in clean_output
        assert "Manages targets, which store all relevant information" in clean_output

    def test_dispatch_dash_h_flag(self, running_pwnity):
        """Testet, ob 'target -h' korrekt durch die RichCommandHelpAction behandelt wird."""
        output = running_pwnity.run_command("target -h")
        clean_output = running_pwnity._strip_ansi(output)
        assert "Help: `target`" in clean_output

    def test_dispatch_no_subcommand_shows_help(self, running_pwnity):
        """Testet, ob ein Befehl ohne Unterbefehl (z.B. 'target') die Hilfe anzeigt."""
        output = running_pwnity.run_command("target")
        clean_output = running_pwnity._strip_ansi(output)
        assert "Help: `target`" in clean_output

    def test_dispatch_special_case_revshell(self, running_pwnity):
        """Testet, ob der Sonderfall 'revshell' korrekt behandelt wird."""
        output = running_pwnity.run_command("revshell bash-tcp")
        clean_output = running_pwnity._strip_ansi(output)
        assert "/dev/tcp/" in clean_output
        assert "LHOST not set in profile, attempting to auto-detect..." in clean_output

@pytest.mark.integration
class TestLogbookIntegration:
    """Gruppiert Integrationstests für das 'logbook'-Modul."""

    def test_logbook_list_and_show(self, running_pwnity):
        """Testet das Auflisten von Log-Einträgen und das Anzeigen eines Eintrags."""
        # 1. Logbook-Eintrag erzeugen
        running_pwnity.run_command("tool add echo")
        running_pwnity.run_command("tool update echo command say")
        running_pwnity.run_command("tool update echo say param 'Hello Logbook'")
        running_pwnity.run_command("tool load echo")
        # Führe den Befehl aus, um einen Log-Eintrag zu erzeugen
        pwn_output = running_pwnity.run_command("pwn say now")
        
        # Extrahiere die Logbook-ID aus der Zusammenfassung
        # The ID is now a UUID.
        match = re.search(r"Logbook ID\s+([0-9a-fA-F\-]+)", running_pwnity._strip_ansi(pwn_output))
        assert match, "Konnte die Logbook-ID aus der 'pwn now' Ausgabe nicht extrahieren."
        log_id = match.group(1)

        # 2. 'logbook list' testen
        list_output = running_pwnity.run_command("logbook list")
        # The table truncates the UUID. We check that the start of the UUID is present.
        # Since the column width is 8, rich truncates to 7 chars + ellipsis. We check for the first 7 chars.
        log_id_prefix_visible = log_id[:7]
        assert log_id_prefix_visible in running_pwnity._strip_ansi(list_output)

        # 3. 'logbook show' testen
        # We can use the prefix for 'show' as the manager handles it.
        show_output = running_pwnity.run_command(f"logbook show {log_id_prefix_visible}")
        assert "Output of Logbook Entry #" in show_output
        assert "Hello Logbook" in show_output # The actual output of the echo command