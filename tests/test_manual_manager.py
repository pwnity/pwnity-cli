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

# tests/test_manual_manager.py
import pytest
from modules.managers.manual_manager import ManualManager
from modules.services import config, log
from rich.panel import Panel

@pytest.fixture
def manual_manager(tmp_path, monkeypatch, mocker):
    """
    Stellt eine ManualManager-Instanz bereit, die für die Verwendung eines temporären
    Verzeichnisses für Handbücher konfiguriert ist.
    """
    manuals_dir = tmp_path / "manuals"
    manuals_dir.mkdir()

    # Mocke die Konfiguration, um auf das temporäre Verzeichnis zu verweisen
    original_get_parameter = config.get_parameter
    def mock_get_parameter(section, key, fallback=None):
        if section == "DIRS" and key == "MANUALS":
            return str(manuals_dir)
        return original_get_parameter(section, key, fallback)
    monkeypatch.setattr(config, 'get_parameter', mock_get_parameter)

    # Mocke die Konsole, die der Manager verwenden wird
    mock_console = mocker.MagicMock()

    # Logger stummschalten
    import logging
    monkeypatch.setattr(log, 'log_value', logging.CRITICAL + 1)

    # Instanziiere den Manager
    manager = ManualManager(console=mock_console)
    
    # Gib den Manager, die Mock-Konsole und das Verzeichnis für die Tests zurück
    return manager, mock_console, manuals_dir

def test_manager_handles_uncreatable_directory(monkeypatch, mocker):
    """
    Testet, ob der Manager den Fall handhabt, in dem das Handbuchverzeichnis
    nicht erstellt werden kann (z.B. wegen fehlender Berechtigungen).
    """
    # Mocke os.makedirs, um einen Fehler auszulösen
    mock_makedirs = mocker.patch("os.makedirs", side_effect=OSError("Permission denied"))
    mock_log_error = mocker.patch("modules.services.log.error")

    # Mocke die Konfiguration, um auf einen Pfad zu verweisen, der die Erstellung auslöst
    monkeypatch.setattr(config, 'get_parameter', lambda section, key, fallback=None: "/uncreatable/path" if key == "MANUALS" else fallback)

    # Die Instanziierung sollte den Fehler abfangen und protokollieren
    manager = ManualManager(console=mocker.MagicMock())

    mock_log_error.assert_any_call("Could not create manuals directory '/uncreatable/path': Permission denied")

    # Methoden sollten sich jetzt sicher verhalten
    assert manager.list_topics() == []
    manager.show_page("any_topic")
    mock_log_error.assert_any_call("Manual page for topic 'any_topic' not found.")

def test_list_topics(manual_manager):
    """
    Testet, ob list_topics die Namen von .md-Dateien korrekt findet und zurückgibt.
    """
    manager, _, manuals_dir = manual_manager

    # Erstelle einige Dummy-Handbuchdateien
    (manuals_dir / "topic_one.md").write_text("Content one")
    (manuals_dir / "topic_two.md").write_text("Content two")
    (manuals_dir / "not_a_manual.txt").touch() # Sollte ignoriert werden

    topics = manager.list_topics()

    assert "topic_one" in topics
    assert "topic_two" in topics
    assert "not_a_manual" not in topics
    assert len(topics) == 2

def test_list_topics_empty(manual_manager):
    """
    Testet, ob list_topics eine leere Liste zurückgibt, wenn keine Handbücher vorhanden sind.
    """
    manager, _, manuals_dir = manual_manager
    (manuals_dir / "not_a_manual.txt").touch()

    topics = manager.list_topics()
    assert topics == []

def test_show_page_found_and_cleaned(manual_manager):
    """
    Testet, ob eine Handbuchseite korrekt geladen, bereinigt (Titel, Zusammenfassung)
    und an die Konsole zum Anzeigen übergeben wird.
    """
    manager, mock_console, manuals_dir = manual_manager
    topic_name = "test_topic"
    
    # Erstelle eine Dummy-Datei mit Titel, Zusammenfassung und Inhalt
    content = """
    # Test Topic Title
    > Summary: This is the summary line.
    
    This is the actual content that should be displayed.
    Line two of the content.
    """
    (manuals_dir / f"{topic_name}.md").write_text(content)

    manager.show_page(topic_name)

    # Überprüfe, ob console.print mit einem Panel aufgerufen wurde
    mock_console.print.assert_called_once()
    # Hole das Argument, das an print übergeben wurde
    call_args, _ = mock_console.print.call_args
    printed_panel = call_args[0]

    assert isinstance(printed_panel, Panel)
    # Überprüfe, ob der Titel und die Zusammenfassung aus dem Inhalt entfernt wurden
    panel_content = printed_panel.renderable.markup
    assert "Test Topic Title" not in panel_content
    assert "This is the summary line" not in panel_content
    assert "This is the actual content" in panel_content

def test_show_page_with_empty_content(manual_manager):
    """
    Testet, ob eine Seite, die nur einen Titel und eine Zusammenfassung hat,
    korrekt mit leerem Inhalt angezeigt wird.
    """
    manager, mock_console, manuals_dir = manual_manager
    topic_name = "empty_content_topic"
    
    content = """
    # Empty Content Title
    > Summary: This is a summary with no content following.
    """
    (manuals_dir / f"{topic_name}.md").write_text(content)

    manager.show_page(topic_name)

    mock_console.print.assert_called_once()
    call_args, _ = mock_console.print.call_args
    printed_panel = call_args[0]

    panel_content = printed_panel.renderable.markup.strip()
    assert panel_content == ""

def test_show_page_handles_no_title(manual_manager):
    """
    Testet, ob eine Seite ohne expliziten Titel (keine '#'-Zeile) korrekt
    verarbeitet wird, indem die erste Zeile als impliziter Titel behandelt wird.
    """
    manager, mock_console, manuals_dir = manual_manager
    topic_name = "no_title_topic"
    
    # Inhalt ohne '#'-Titelzeile
    content = """
This is the implicit title.
This is the actual content.
    """
    (manuals_dir / f"{topic_name}.md").write_text(content.strip())

    manager.show_page(topic_name)

    mock_console.print.assert_called_once()
    call_args, _ = mock_console.print.call_args
    printed_panel = call_args[0]

    panel_content = printed_panel.renderable.markup
    assert "This is the implicit title." not in panel_content
    assert "This is the actual content." in panel_content.strip()

def test_show_page_not_found(manual_manager, mocker):
    """
    Testet, ob eine Fehlermeldung geloggt wird, wenn ein Thema nicht existiert.
    """
    manager, _, manuals_dir = manual_manager
    mock_log_error = mocker.patch("modules.services.log.error")
    mock_log_prompt = mocker.patch("modules.services.log.prompt")

    manager.show_page("non_existent_topic")

    mock_log_error.assert_called_with("Manual page for topic 'non_existent_topic' not found.")

def test_get_topic_summary_scenarios(manual_manager, mocker):
    """
    Testet verschiedene Szenarien für get_topic_summary.
    """
    manager, _, manuals_dir = manual_manager

    # Fall 1: Explizite Zusammenfassung
    (manuals_dir / "explicit.md").write_text("> Summary: This is an explicit summary.")
    summary1 = manager.get_topic_summary("explicit")
    assert summary1 == "This is an explicit summary."

    # Fall 2: Fallback auf die erste Inhaltszeile
    (manuals_dir / "fallback.md").write_text("# Title\n\nThis is the fallback summary line.")
    summary2 = manager.get_topic_summary("fallback")
    assert summary2 == "This is the fallback summary line."

    # Fall 3: Datei existiert nicht
    summary3 = manager.get_topic_summary("non_existent")
    assert "Documentation for 'non existent'" in summary3

    # Fall 4: Datei ist leer
    (manuals_dir / "empty.md").write_text("")
    summary4 = manager.get_topic_summary("empty")
    assert "Documentation for 'empty'" in summary4

    # Fall 5: Leere explizite Zusammenfassung, sollte auf nächste Zeile zurückfallen
    (manuals_dir / "empty_summary.md").write_text("> Summary: \nThis is the real summary.")
    summary5 = manager.get_topic_summary("empty_summary")
    assert summary5 == "This is the real summary."

    # Fall 6: Datei enthält nur einen Titel, sollte auf Standard zurückfallen
    (manuals_dir / "title_only.md").write_text("# Just a Title")
    summary6 = manager.get_topic_summary("title_only")
    assert "Documentation for 'title only'" in summary6

def test_list_topics_handles_read_error(manual_manager, mocker):
    """Testet, ob list_topics einen OSError (z.B. fehlende Berechtigung) abfängt."""
    manager, _, _ = manual_manager
    mocker.patch("os.listdir", side_effect=OSError("Permission denied"))
    assert manager.list_topics() == []

def test_load_content_handles_read_error(manual_manager, mocker):
    """
    Testet, ob ein Lesefehler (z.B. Berechtigungsproblem) beim Öffnen
    einer Handbuchdatei korrekt abgefangen wird.
    """
    manager, _, manuals_dir = manual_manager
    topic_name = "unreadable_topic"
    (manuals_dir / f"{topic_name}.md").touch()

    # Mocke die `open`-Funktion, damit sie einen IOError auslöst
    mock_open = mocker.patch("builtins.open", side_effect=IOError("Permission denied"))
    mock_log_error = mocker.patch("modules.services.log.error")

    # Die `show_page`-Methode ruft intern `_load_content` auf
    manager.show_page(topic_name)

    # Überprüfe, ob der Fehler geloggt wurde
    mock_log_error.assert_any_call(f"Error reading manual file '{manuals_dir / topic_name}.md': Permission denied")