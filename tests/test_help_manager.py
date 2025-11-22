# tests/test_help_manager.py
import pytest
import argparse
from modules.help_manager import HelpManager
from rich.console import Console
from rich.console import Group
from rich.panel import Panel
from rich.table import Table
import os

@pytest.fixture
def mock_console(mocker):
    """Stellt eine gemockte rich Console bereit, um die Ausgabe abzufangen."""
    mock = mocker.MagicMock(spec=Console)
    # Wir verwenden eine echte Konsole, die ins Nichts schreibt, um die Render-Fähigkeiten zu nutzen
    real_console = Console(file=open(os.devnull, 'w'), force_terminal=True, width=120)
    mock.render = real_console.render
    return mock

@pytest.fixture
def mock_cli(mocker):
    """
    Stellt eine gemockte CLI-Instanz mit den für den HelpManager notwendigen Attributen bereit.
    Dies beinhaltet eine simulierte argparse-Struktur.
    """
    cli = mocker.MagicMock()
    cli.get_all_commands.return_value = ['target', 'tool', 'pwn', 'help']

    # Mocke die docstrings, die für die Befehlsübersicht verwendet werden
    cli.do_target.__doc__ = "Manages targets for scans."
    cli.do_tool.__doc__ = "Configures external tools."
    cli.do_pwn.__doc__ = "Executes the loaded tool."
    cli.do_help.__doc__ = "Shows help."

    # --- Mocke die argparse-Struktur für den 'target'-Befehl ---
    # Dies ist entscheidend für den Test von show_subcommand_help
    target_parser = argparse.ArgumentParser(prog="target")
    target_subparsers = target_parser.add_subparsers(dest="subcommand")

    # Mock 'target add'
    add_parser = target_subparsers.add_parser(
        "add",
        help="Create a new target.",
        description="Creates a new, empty target."
    )
    add_parser.add_argument("name", help="A unique name for the new target.")
    add_parser.add_argument("-c", "--category", help="Assign a category to the target.")
    add_parser.examples = [("target add my-server", "Creates a new target named 'my-server'.")]

    # Mock 'target list'
    list_parser = target_subparsers.add_parser("list", help="List all targets.")
    list_parser.aliases = ['ls'] # Add an alias for testing

    # Weise den gemockten Parser dem CLI-Objekt zu
    cli.target_parser = target_parser

    return cli

@pytest.fixture
def help_manager(mock_console, mock_cli, mocker):
    """Stellt eine HelpManager-Instanz mit gemockten Abhängigkeiten bereit."""
    manager = HelpManager(console=mock_console, cli_instance=mock_cli)
    # Mocke den manual_mgr, der für die dynamische Hilfe benötigt wird
    mock_manual_mgr = mocker.MagicMock()
    mock_manual_mgr.list_topics.return_value = ['concepts', 'workflow']
    # FIX: Mocke auch den Rückgabewert für get_topic_summary, um den NotRenderableError zu vermeiden.
    mock_manual_mgr.get_topic_summary.return_value = "A summary for the topic."
    mock_cli.manual_mgr = mock_manual_mgr
    return manager

def test_show_command_overview(help_manager, mock_console):
    """
    Testet, ob die Haupt-Hilfeübersicht korrekt als Panel mit einer Tabelle angezeigt wird.
    """
    help_manager.show_command_overview()

    # Überprüfe, ob console.print mit einem Panel aufgerufen wurde
    mock_console.print.assert_called()
    # Der vorletzte Aufruf ist der relevante (der letzte ist ein Newline)
    printed_panel = mock_console.print.call_args_list[-2][0][0]

    assert isinstance(printed_panel, Panel)
    assert "Available Commands" in printed_panel.title
    assert isinstance(printed_panel.renderable, Table)

def test_show_subcommand_help(help_manager, mock_console):
    """
    Testet, ob die Hilfe für einen spezifischen Unterbefehl (z.B. 'target add')
    korrekt gerendert wird, inklusive Beschreibung, Argumenten und Beispielen.
    """
    was_handled = help_manager.show_subcommand_help("target", "add")

    assert was_handled is True
    mock_console.print.assert_called_once()
    printed_panel = mock_console.print.call_args[0][0]

    assert isinstance(printed_panel, Panel)
    assert "Help: `target add`" in printed_panel.title

    # Wir können nicht einfach den gerenderten Text prüfen, aber wir können
    # die Struktur des Inhalts (ein Table-Objekt) untersuchen.
    # Wir wandeln das renderable in einen String um, um nach Schlüsselwörtern zu suchen.
    # Wir müssen das Objekt rendern, um seinen Textinhalt zu erhalten.
    rendered_segments = mock_console.render(printed_panel.renderable)
    rendered_text = "".join(segment.text for segment in rendered_segments)

    assert "Usage: target add" in rendered_text
    assert "Creates a new, empty target." in rendered_text # Description
    assert "Positional Arguments" in rendered_text
    assert "Options" in rendered_text
    assert "Common Examples" in rendered_text
    assert "target add my-server" in rendered_text # Example command

def test_show_custom_command_help(help_manager, mock_console):
    """
    Testet, ob eine der benutzerdefinierten Hilfeseiten (z.B. für 'target')
    korrekt angezeigt wird.
    """
    help_manager.show_help_target()

    mock_console.print.assert_called_once()
    printed_panel = mock_console.print.call_args[0][0]

    assert isinstance(printed_panel, Panel)
    assert "Help: `target`" in printed_panel.title

    # Um den Textinhalt eines Group-Objekts zu erhalten, müssen wir es rendern.
    # Die mock_console ist so konfiguriert, dass sie eine echte Render-Engine verwendet.
    rendered_segments = mock_console.render(printed_panel.renderable)
    rendered_text = "".join(segment.text for segment in rendered_segments)

    # Der HelpManager verwendet eine eigene, detailliertere Beschreibung.
    assert "Manages targets, which store all relevant information" in rendered_text # Description
    assert "Available Actions" in rendered_text # Subcommands panel
    assert "Common Examples" in rendered_text # Examples panel

def test_show_subcommand_help_with_alias(help_manager, mock_console):
    """
    Testet, dass die Hilfe für einen Alias (z.B. 'target ls') korrekt auf den
    ursprünglichen Befehl ('target list') verweist.
    """
    was_handled = help_manager.show_subcommand_help("target", "ls") # 'ls' ist der Alias für 'list'

    assert was_handled is True
    mock_console.print.assert_called_once()
    printed_panel = mock_console.print.call_args[0][0]

    assert isinstance(printed_panel, Panel)
    # Der Titel sollte den echten Befehlsnamen 'list' enthalten, nicht den Alias 'ls'.
    assert "Help: `target list`" in printed_panel.title

def test_show_subcommand_help_nonexistent(help_manager, mock_console):
    """
    Testet, dass für einen nicht existierenden Befehl keine Hilfe angezeigt wird
    und die Methode False zurückgibt.
    """
    # Test für einen nicht existierenden Hauptbefehl
    was_handled_main = help_manager.show_subcommand_help("nonexistent", "command")
    assert was_handled_main is False

    # Test für einen existierenden Hauptbefehl, aber nicht existierenden Unterbefehl
    was_handled_sub = help_manager.show_subcommand_help("target", "nonexistent")
    assert was_handled_sub is False

    # In beiden Fällen sollte nichts an die Konsole gedruckt werden.
    mock_console.print.assert_not_called()

def test_show_dynamic_manual_help(help_manager, mock_console):
    """
    Testet, ob die Hilfe für den 'manual'-Befehl dynamisch die verfügbaren
    Themen aus dem ManualManager als Beispiele anzeigt.
    """
    help_manager.show_help_manual()

    mock_console.print.assert_called_once()
    printed_panel = mock_console.print.call_args[0][0]
    rendered_segments = mock_console.render(printed_panel.renderable)
    rendered_text = "".join(segment.text for segment in rendered_segments)

    # Überprüfe, ob die gemockten Themen aus der Fixture in den Beispielen erscheinen
    assert "A summary for the topic." in rendered_text
    assert "manual concepts" in rendered_text
    assert "manual workflow" in rendered_text

def test_show_subcommand_help_for_simple_command(help_manager, mock_console):
    """
    Testet, ob die Hilfe für einen einfachen Unterbefehl (ohne Argumente oder Beispiele)
    korrekt und ohne leere Abschnitte gerendert wird.
    """
    # 'list' wurde in der Fixture ohne Argumente oder Beispiele definiert
    was_handled = help_manager.show_subcommand_help("target", "list")

    assert was_handled is True
    mock_console.print.assert_called_once()
    printed_panel = mock_console.print.call_args[0][0]

    assert isinstance(printed_panel, Panel)
    assert "Help: `target list`" in printed_panel.title

    rendered_segments = mock_console.render(printed_panel.renderable)
    rendered_text = "".join(segment.text for segment in rendered_segments)

    assert "Usage: target list" in rendered_text
    # Diese Abschnitte sollten NICHT vorhanden sein, da der Befehl keine Argumente/Beispiele hat.
    assert "Positional Arguments" not in rendered_text
    assert "Options" not in rendered_text
    assert "Common Examples" not in rendered_text

def test_show_command_overview_with_dynamic_command(help_manager, mock_cli, mock_console, mocker):
    """
    Testet, dass ein dynamisch zur Hilfe hinzugefügter Befehl korrekt in der
    Kommandoübersicht angezeigt wird.
    """
    # 1. Arrange: Füge einen neuen Befehl dynamisch hinzu
    dynamic_cmd_name = "my_workflow"
    dynamic_cmd_desc = "Runs the custom 'my_workflow'."
    dynamic_cmd_category = "Workflows"  # Eine neue Kategorie

    # Mocke die notwendigen Teile auf dem cli-Objekt
    mock_cli.get_all_commands.return_value.append(dynamic_cmd_name)
    # Dynamisch ein __doc__-Attribut zu einem Mock-Objekt hinzufügen
    setattr(mock_cli, f"do_{dynamic_cmd_name}", mocker.MagicMock(__doc__=dynamic_cmd_desc))

    help_manager.add_command_to_category(dynamic_cmd_name, dynamic_cmd_category, dynamic_cmd_desc)

    # 2. Act: Zeige die Übersicht an
    help_manager.show_command_overview()

    # 3. Assert: Überprüfe, ob der neue Befehl und die Kategorie im Output sind
    printed_panel = mock_console.print.call_args_list[-2][0][0]
    rendered_text = "".join(segment.text for segment in mock_console.render(printed_panel.renderable))

    assert dynamic_cmd_category in rendered_text
    assert dynamic_cmd_name in rendered_text
    assert dynamic_cmd_desc in rendered_text