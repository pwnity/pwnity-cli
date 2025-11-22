# tests/test_library_manager.py
import os
import pytest
from modules.managers.library_manager import LibraryManager
# Wir importieren das `config`-Objekt direkt, um es patchen zu können.
from modules.services import config

@pytest.fixture
def library_manager(tmp_path, monkeypatch):
    """
    Eine Pytest-Fixture, die einen sauberen LibraryManager für jeden Test bereitstellt.
    Der Manager wird so konfiguriert, dass er in ein temporäres Verzeichnis schreibt.
    """
    # Erstelle ein temporäres Verzeichnis für die Bibliotheksdaten
    library_dir = tmp_path

    # Definiere eine neue Funktion, die die originale ersetzt
    def mock_get_parameter(section, key, fallback=None):
        if section == "DIRS" and key == "LIBRARY":
            return str(library_dir)
        # Fallback auf einen leeren Wert, um externe Abhängigkeiten zu vermeiden
        return fallback

    monkeypatch.setattr(config, 'get_parameter', mock_get_parameter)

    # Instanziiere den Manager. Er wird jetzt in `tmp_path/library` schreiben.
    # Dieser Manager wird an jeden Test übergeben, der die Fixture anfordert.
    return LibraryManager()

@pytest.fixture
def mock_cli_for_library(mocker):
    """Provides a mock CLI instance for library tests."""
    cli = mocker.MagicMock()
    cli.session = mocker.MagicMock()
    cli.help_mgr = mocker.MagicMock()
    cli.console = mocker.MagicMock()
    return cli

def test_library_create_and_exists(library_manager, tmp_path):
    """
    Testet, ob ein Library-Eintrag korrekt erstellt wird und existiert.
    """
    # Die Fixture `library_manager` hat den Manager bereits für uns konfiguriert.
    lib_manager = library_manager

    # --- Testfall 1: Erstellen eines neuen Eintrags ---
    entry_name = "My Test Entry"
    sanitized_name = "My_Test_Entry"
    
    assert lib_manager.exists(entry_name) is False
    
    # Führe die zu testende Funktion aus
    result = lib_manager.create(entry_name, category="Testing")
    print(f"\n[DEBUG] Created entry '{entry_name}', checking file existence...")
    
    # Überprüfe die Ergebnisse
    assert result is True
    assert lib_manager.exists(entry_name) is True
    
    # Überprüfe, ob die Datei physisch existiert und den korrekten Inhalt hat
    # Wir müssen den Pfad hier neu konstruieren, da die Fixture ihn nicht direkt zurückgibt.
    expected_file = tmp_path / f"{sanitized_name}.json"
    assert expected_file.is_file()
    
    # Lade die Daten direkt, um den Inhalt zu verifizieren
    data = lib_manager.load(entry_name)
    assert data is not None
    assert data.get("name") == entry_name # Der interne Name sollte der Originalname sein
    assert data.get("category") == "Testing"

    # --- Testfall 2: Versuch, einen existierenden Eintrag erneut zu erstellen ---
    result_fail = lib_manager.create(entry_name)
    assert result_fail is False

def test_library_url_check_logic(library_manager, monkeypatch):
    """
    Testet die Logik für den URL-Check, indem `requests` gemockt wird.
    """
    # Die Fixture `library_manager` hat den Manager bereits für uns konfiguriert.
    lib_manager = library_manager

    # Mock für die `requests`-Bibliothek
    class MockResponse:
        def __init__(self, status_code):
            self.status_code = status_code
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

    # Erstelle einen Test-Eintrag mit einer URL
    entry_name = "Test URL"
    lib_manager.create(entry_name)
    lib_manager.update(entry_name, "url", "http://fake-url.com")

    # --- Testfall 1: Erfolgreicher Check (Status 200) ---
    # `monkeypatch.setattr` ersetzt `requests.get` durch unsere Mock-Funktion
    monkeypatch.setattr("modules.managers.library_manager.requests.get", lambda *args, **kwargs: MockResponse(200))
    
    lib_manager._check_url(entry_name)
    
    data = lib_manager.load(entry_name)
    assert data["url_status_code"] == 200
    assert "url_last_checked" in data

    # --- Testfall 2: Fehlgeschlagener Check (Request-Exception) ---
    def raise_exception(*args, **kwargs):
        # Wir importieren `requests` hier lokal, nur um die Exception zu haben
        import requests
        raise requests.exceptions.RequestException("Connection failed")

    monkeypatch.setattr("modules.managers.library_manager.requests.get", raise_exception)

    lib_manager._check_url(entry_name)

    data = lib_manager.load(entry_name)
    assert data["url_status_code"] == "Error"

def test_library_rename(library_manager, tmp_path):
    """
    Testet das Umbenennen eines Eintrags, inklusive der Dateinamen-Sanitisierung.
    """
    lib_manager = library_manager
    old_name = "Old Entry Name"
    new_name = "New Entry Name"
    sanitized_old_name = "Old_Entry_Name"
    sanitized_new_name = "New_Entry_Name"

    # 1. Eintrag erstellen
    lib_manager.create(old_name)
    assert lib_manager.exists(old_name) is True
    assert not lib_manager.exists(new_name)

    # 2. Umbenennen
    result = lib_manager.rename(old_name, new_name)
    assert result is True

    # 3. Überprüfen
    assert lib_manager.exists(old_name) is False
    assert lib_manager.exists(new_name) is True

    # Überprüfe die physischen Dateien
    old_file = tmp_path / f"{sanitized_old_name}.json"
    new_file = tmp_path / f"{sanitized_new_name}.json"
    assert not old_file.exists()
    assert new_file.is_file()

    # Überprüfe den internen Namen in der neuen Datei
    data = lib_manager.load(new_name)
    assert data is not None
    assert data.get("name") == new_name

def test_library_list_all_desanitizes_names(library_manager):
    """
    Testet, ob `list_all` die korrekten Anzeigenamen (mit Leerzeichen) zurückgibt.
    """
    lib_manager = library_manager
    names = ["Test One", "Test Two", "Another Name"]
    for name in names:
        lib_manager.create(name)

    # list_all sollte die "schönen" Namen zurückgeben, nicht die Dateinamen
    listed_names = lib_manager.list_all()
    
    # Wir sortieren beide Listen, um einen stabilen Vergleich zu gewährleisten
    assert sorted(listed_names) == sorted(names)

def test_library_destroy(library_manager, tmp_path):
    """
    Testet, ob ein Eintrag und seine zugehörige Datei korrekt gelöscht werden.
    """
    lib_manager = library_manager
    entry_name = "Entry To Delete"
    sanitized_name = "Entry_To_Delete"

    # 1. Eintrag erstellen und Existenz bestätigen
    lib_manager.create(entry_name)
    assert lib_manager.exists(entry_name) is True
    file_path = tmp_path / f"{sanitized_name}.json"
    assert file_path.is_file()

    # 2. Eintrag löschen
    result = lib_manager.destroy(entry_name)
    assert result is True

    # 3. Überprüfen, ob der Eintrag und die Datei verschwunden sind
    assert lib_manager.exists(entry_name) is False
    assert not file_path.exists()

def test_check_all_entries_logic(library_manager, monkeypatch):
    """
    Testet die Logik von `check_all_entries_on_startup`, um sicherzustellen,
    dass nur die korrekten Einträge (veraltet, Fehler, neu) überprüft werden.
    """
    from datetime import datetime, timedelta, timezone
    lib_manager = library_manager

    # Mocken die `_check_url` Methode, um nur ihre Aufrufe zu verfolgen
    checked_entries = []
    def mock_check_url(name):
        checked_entries.append(name)

    monkeypatch.setattr(lib_manager, '_check_url', mock_check_url)

    # --- Testdaten erstellen ---
    # 1. Ein frischer Eintrag, der nicht geprüft werden sollte
    lib_manager.create("Fresh Entry")
    lib_manager.update("Fresh Entry", "url", "http://fresh.com")
    lib_manager.update("Fresh Entry", "url_last_checked", datetime.now(timezone.utc).isoformat())

    # 2. Ein veralteter Eintrag, der geprüft werden sollte
    stale_date = (datetime.now(timezone.utc) - timedelta(days=lib_manager.url_check_refresh_days + 1)).isoformat()
    lib_manager.create("Stale Entry")
    lib_manager.update("Stale Entry", "url", "http://stale.com")
    lib_manager.update("Stale Entry", "url_last_checked", stale_date)

    # 3. Ein Eintrag mit Fehler, der geprüft werden sollte
    lib_manager.create("Error Entry")
    lib_manager.update("Error Entry", "url", "http://error.com")
    lib_manager.update("Error Entry", "url_status_code", "Error")

    # 4. Ein Eintrag, der noch nie geprüft wurde und geprüft werden sollte
    lib_manager.create("New Entry")
    lib_manager.update("New Entry", "url", "http://new.com")

    # --- Test ausführen ---
    lib_manager.check_all_entries_on_startup()

    # --- Ergebnisse überprüfen ---
    # Es sollten genau die 3 erwarteten Einträge zur Prüfung ausgewählt worden sein
    assert len(checked_entries) == 3
    assert "Stale Entry" in checked_entries
    assert "Error Entry" in checked_entries
    assert "New Entry" in checked_entries
    assert "Fresh Entry" not in checked_entries

def test_check_url_fails_if_requests_missing(library_manager, monkeypatch, mocker):
    """
    Testet, ob _check_url eine Fehlermeldung loggt, wenn 'requests' nicht installiert ist.
    """
    # Simuliere, dass 'requests' nicht importiert werden konnte
    monkeypatch.setattr("modules.managers.library_manager.requests", None)
    
    entry_name = "No Requests Entry"
    library_manager.create(entry_name)
    library_manager.update(entry_name, "url", "http://example.com")

    # Mocke den Logger, um die Ausgabe zu überprüfen
    mock_log_error = mocker.patch("modules.services.log.error")

    assert library_manager._check_url(entry_name) is False
    mock_log_error.assert_called_with("The 'requests' library is not installed. Cannot check URL.")

def test_dispatch_shows_help_if_no_subcommand(library_manager, mock_cli_for_library):
    """
    Tests that the dispatch method calls the help manager if no subcommand is provided.
    """
    library_manager.dispatch(subcommand=None, args=None, cli_instance=mock_cli_for_library)
    mock_cli_for_library.help_mgr.show_help_library.assert_called_once()


def test_open_fails_for_entry_without_url(library_manager, mocker):
    """Testet, ob der 'open'-Befehl fehlschlägt, wenn ein Eintrag keine URL hat."""
    library_manager.create("No URL Entry")
    mock_log_error = mocker.patch("modules.services.log.error")
    library_manager._cmd_open(type('Args', (), {'name': "No URL Entry"})(), cli_instance=None)
    mock_log_error.assert_called_with("Library entry 'No URL Entry' does not have a URL defined.")
