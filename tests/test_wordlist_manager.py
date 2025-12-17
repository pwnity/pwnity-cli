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

# tests/test_wordlist_manager.py
import pytest
import os
from modules.managers.wordlist_manager import WordlistManager
from modules.services import config, log

@pytest.fixture
def wordlist_manager(tmp_path, monkeypatch):
    """
    Stellt einen sauberen WordlistManager bereit, der in ein temporäres Verzeichnis schreibt.
    """
    wordlists_dir = tmp_path / "wordlists"
    wordlists_dir.mkdir()

    # Leite den Manager auf das temporäre Verzeichnis um
    original_get_parameter = config.get_parameter
    def mock_get_parameter(section, key, fallback=None):
        if section == "DIRS" and key == "WORDLISTS":
            return str(wordlists_dir)
        return original_get_parameter(section, key, fallback)
    monkeypatch.setattr(config, 'get_parameter', mock_get_parameter)

    # Logger stummschalten
    import logging
    monkeypatch.setattr(log, 'log_value', logging.CRITICAL + 1)

    return WordlistManager()

def test_wordlist_create_and_exists(wordlist_manager):
    """
    Testet, ob eine Wordlist korrekt erstellt wird, existiert und das 'path'-Feld hat.
    """
    name = "rockyou"
    assert wordlist_manager.exists(name) is False

    # Simuliere den Aufruf von `wordlist add rockyou`
    args = type('Args', (), {'name': name})()
    wordlist_manager._cmd_add(args, cli=None)

    assert wordlist_manager.exists(name) is True
    data = wordlist_manager.load(name)
    assert data is not None
    assert data.get("name") == name
    # Die überschriebene _cmd_add Methode sollte ein leeres 'path'-Feld erstellen
    assert "path" in data
    assert data["path"] == ""

def test_wordlist_update(wordlist_manager):
    """
    Testet das Aktualisieren von Feldern einer Wordlist.
    """
    name = "common"
    wordlist_manager.create(name)

    # Aktualisiere den Pfad
    path_value = "/usr/share/wordlists/dirb/common.txt"
    wordlist_manager.update(name, "path", path_value)

    # Aktualisiere eine Beschreibung
    desc_value = "Common web directories"
    wordlist_manager.update(name, "description", desc_value)

    data = wordlist_manager.load(name)
    assert data.get("path") == path_value
    assert data.get("description") == desc_value

def test_wordlist_destroy(wordlist_manager, tmp_path):
    """
    Testet, ob eine Wordlist und ihre Datei korrekt gelöscht werden.
    """
    name = "to-be-deleted"
    wordlist_manager.create(name)
    assert wordlist_manager.exists(name) is True

    # Physische Datei sollte existieren
    file_path = tmp_path / "wordlists" / f"{name}.json"
    assert file_path.is_file()

    # Löschen
    wordlist_manager.destroy(name)

    assert wordlist_manager.exists(name) is False
    assert not file_path.exists()

def test_wordlist_list_all(wordlist_manager):
    """
    Testet, ob `list_all` alle erstellten Wordlists zurückgibt.
    """
    names = ["list1", "list2", "list3"]
    for name in names:
        wordlist_manager.create(name)

    listed_names = wordlist_manager.list_all()
    assert sorted(listed_names) == sorted(names)

@pytest.mark.parametrize("path_value, description_value", [
    ("/usr/share/wordlists/rockyou.txt", "Standard rockyou list"),
    ("/path/with spaces/my list.txt", "A list with spaces in path and description")
])
def test_wordlist_export(wordlist_manager, mocker, path_value, description_value):
    """
    Testet, ob die Export-Funktion die korrekten Rekonstruktions-Befehle generiert.
    Prüft sowohl Pfade ohne als auch mit Leerzeichen.
    """
    import shlex
    name = "seclists-common"
    wordlist_manager.create(name)
    wordlist_manager.update(name, "path", path_value)
    wordlist_manager.update(name, "description", description_value)

    # Mocke das cli-Objekt und seine poutput-Methode, um die Ausgabe abzufangen
    mock_cli = mocker.MagicMock()
    captured_output = []
    mock_cli.poutput.side_effect = lambda x: captured_output.append(x)

    # Führe die Export-Methode aus
    args = type('Args', (), {'name': name})()
    wordlist_manager._cmd_export(args, mock_cli)

    full_output = "\n".join(captured_output)
    # Wir verwenden shlex.quote auch im Test, um den erwarteten Output zu generieren.
    expected_path_str = f"wordlist update {name} path {shlex.quote(path_value)}"
    expected_desc_str = f"wordlist update {name} description {shlex.quote(description_value)}"

    assert f"wordlist add {name}" in full_output
    assert expected_path_str in full_output
    assert expected_desc_str in full_output