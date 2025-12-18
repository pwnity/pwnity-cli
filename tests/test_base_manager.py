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

# tests/test_base_manager.py
import pytest
import os
import json
from modules.managers.base_manager import JSONManager
from modules.services import config, log

# 1. Erstelle eine konkrete Implementierung des JSONManager nur für diesen Test
class ConcreteManager(JSONManager):
    def __init__(self, folder):
        self.dispatch_called_with = None
        # Rufe den Konstruktor der Elternklasse mit dem Ordnerpfad auf
        super().__init__(folder)

    def _get_entity_type(self):
        return "TestEntity"
    
    def _cmd_test_dispatch(self, args, cli):
        """Eine Dummy-Methode, um den Dispatch-Mechanismus zu testen."""
        self.dispatch_called_with = (args, cli)

@pytest.fixture
def test_manager(tmp_path, monkeypatch):
    """
    Stellt eine Instanz unseres ConcreteManager bereit, die in einem temporären
    Verzeichnis arbeitet.
    """
    # Logger stummschalten
    import logging
    monkeypatch.setattr(log, 'log_value', logging.CRITICAL + 1)
    
    # Der Manager wird direkt mit dem Pfad initialisiert, kein config-Patch nötig.
    return ConcreteManager(folder=str(tmp_path))

def test_create_and_exists(test_manager, tmp_path):
    """
    Testet, ob eine Entität korrekt erstellt wird, existiert und nicht
    erneut erstellt werden kann.
    """
    entity_name = "my-test-entity"
    
    # Am Anfang sollte die Entität nicht existieren
    assert test_manager.exists(entity_name) is False

    # Erstellen
    assert test_manager.create(entity_name) is True

    # Jetzt sollte sie existieren
    assert test_manager.exists(entity_name) is True

    # Überprüfe, ob die Datei physisch auf der Festplatte erstellt wurde
    expected_file = tmp_path / f"{entity_name}.json"
    assert expected_file.is_file()

    # Überprüfe den Inhalt der Datei
    with open(expected_file, 'r') as f:
        data = json.load(f)
    assert data == {"name": entity_name}

    # Der Versuch, sie erneut zu erstellen, sollte fehlschlagen
    assert test_manager.create(entity_name) is False

def test_load_and_list(test_manager):
    """
    Testet das Laden und Auflisten von Entitäten.
    """
    names = ["entity1", "entity2", "entity3"]
    for name in names:
        test_manager.create(name)

    # Teste list_all
    assert sorted(test_manager.list_all()) == sorted(names)

    # Teste das Laden einer existierenden Entität
    data = test_manager.load("entity2")
    assert data is not None
    assert data["name"] == "entity2"

    # Teste das Laden einer nicht existierenden Entität
    assert test_manager.load("non-existent") is None

def test_update_and_delete_key(test_manager):
    """
    Testet das Aktualisieren und Löschen eines Schlüssels innerhalb einer Entität.
    """
    name = "update-test"
    test_manager.create(name)

    # 1. Feld hinzufügen/aktualisieren
    test_manager.update(name, "status", "active")
    data = test_manager.load(name)
    assert data["status"] == "active"

    # 2. Feld löschen
    test_manager.delete(name, "status")
    data = test_manager.load(name)
    assert "status" not in data

def test_destroy(test_manager, tmp_path):
    """
    Testet das vollständige Löschen einer Entität und ihrer Datei.
    """
    name = "to-be-destroyed"
    test_manager.create(name)
    assert test_manager.exists(name) is True

    # Löschen
    assert test_manager.destroy(name) is True

    # Überprüfen
    assert test_manager.exists(name) is False
    expected_file = tmp_path / f"{name}.json"
    assert not expected_file.exists()

def test_rename(test_manager, tmp_path):
    """
    Testet das Umbenennen einer Entität, inklusive der Datei und des internen Namens.
    """
    old_name = "old-name"
    new_name = "new-name"
    test_manager.create(old_name)

    # Umbenennen
    assert test_manager.rename(old_name, new_name) is True

    # Überprüfen
    assert test_manager.exists(old_name) is False
    assert test_manager.exists(new_name) is True

    # Überprüfe die physischen Dateien
    assert not (tmp_path / f"{old_name}.json").exists()
    assert (tmp_path / f"{new_name}.json").is_file()

    # Überprüfe den Inhalt der neuen Datei
    data = test_manager.load(new_name)
    assert data["name"] == new_name

def test_filename_sanitization(test_manager, tmp_path):
    """Testet, ob ungültige Zeichen in Dateinamen korrekt ersetzt werden."""
    invalid_name = "my/invalid:name"
    sanitized_name = "my_invalid_name"
    
    test_manager.create(invalid_name)
    
    # Die Datei sollte unter dem bereinigten Namen existieren
    expected_file = tmp_path / f"{sanitized_name}.json"
    assert expected_file.is_file()
    
    # Der Manager sollte die Entität unter ihrem Originalnamen finden
    assert test_manager.exists(invalid_name) is True
    
    # Der interne Name in der Datei sollte der Originalname sein
    data = test_manager.load(invalid_name)
    assert data["name"] == invalid_name

def test_dispatch_method(test_manager, mocker):
    """
    Testet, ob die dispatch-Methode einen Sub-Befehl korrekt an die
    entsprechende _cmd_*-Methode weiterleitet.
    """
    # Erstelle Mock-Argumente und ein Mock-CLI-Objekt
    mock_args = mocker.MagicMock()
    mock_cli = mocker.MagicMock()

    # Rufe dispatch für unseren Test-Befehl auf
    was_handled = test_manager.dispatch("test_dispatch", mock_args, mock_cli)

    # Überprüfe die Ergebnisse
    assert was_handled is True
    assert test_manager.dispatch_called_with is not None
    assert test_manager.dispatch_called_with == (mock_args, mock_cli)