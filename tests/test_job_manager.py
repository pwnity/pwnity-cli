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

# tests/test_job_manager.py
import pytest
import time
import argparse
from modules.managers.job_manager import JobManager, strip_ansi

@pytest.fixture
def job_manager(mocker, monkeypatch):
    """
    Eine Pytest-Fixture, die einen sauberen JobManager für jeden Test bereitstellt.
    Abhängigkeiten wie cli, logbook_mgr und report_mgr werden gemockt.
    """
    # Mock-Objekte für die Abhängigkeiten erstellen
    mock_cli = mocker.MagicMock()
    mock_logbook_mgr = mocker.MagicMock()
    mock_report_mgr = mocker.MagicMock()

    # Wir mocken auch die `create_entry`-Methode, damit sie eine Fake-ID zurückgibt
    # und keine echten Log-Dateien schreibt.
    mock_logbook_mgr.create_entry.return_value = 123

    # Mock abhängiger Manager
    mock_cli.display_mgr = mocker.MagicMock()

    # --- FIX: Force INFO log level for tests by patching the config service ---
    # The logger reads its level from the config upon initialization.
    # We patch the config service to ensure that any module using the logger
    # during this test will get an instance configured with the INFO level.
    from modules.services import log
    from modules.services import config
    original_get_parameter = config.get_parameter
    monkeypatch.setattr(config, 'get_parameter', lambda section, key, fallback=None: "INFO" if key == "DEBUG_LEVEL" else original_get_parameter(section, key, fallback))

    # Den JobManager mit den Mocks instanziieren
    return JobManager(
        cli_instance=mock_cli,
        logbook_mgr=mock_logbook_mgr,
        report_mgr=mock_report_mgr
    )

@pytest.fixture
def mock_session(mocker):
    """Eine Fixture, die ein einfaches Mock-Session-Objekt bereitstellt."""
    session = mocker.MagicMock()
    session.name = "test-session"
    session.report = "test-report" # Wichtig für den ReportManager-Aufruf
    return session

def test_start_and_finish_successful_job(job_manager, mock_session):
    """
    Testet, ob ein einfacher, erfolgreicher Job korrekt ausgeführt wird und endet.
    """
    # 1. Job starten
    command = ["echo", "hello world"]
    job_id = job_manager.start_job(command, session_obj=mock_session)
    assert job_id is not None

    # 2. Warten, bis der Job fertig ist (echo ist sehr schnell)
    # Wir geben dem Thread eine kurze Chance zu laufen und den Status zu aktualisieren.
    time.sleep(0.2) 
    job = job_manager.get_job(job_id)
    assert job is not None

    # 3. Status und Ergebnis überprüfen
    # Der Job sollte 'finished' sein, da der Output-Reader-Thread den Status aktualisiert.
    assert job.status == "finished"
    assert job.return_code == 0
    # Wir müssen Zeilenumbrüche beachten, die von `echo` kommen.
    assert "hello world" in job.output

    # 4. Überprüfen, ob die Log-Methoden aufgerufen wurden
    job_manager.logbook_mgr.create_entry.assert_called_once()
    job_manager.report_mgr.add_history_entry.assert_called_once()

def test_start_and_finish_failed_job(job_manager, mock_session):
    """
    Testet, ob ein Job, der fehlschlägt, korrekt als 'failed' markiert wird.
    """
    # 1. Job starten, der garantiert fehlschlägt
    command = ["ls", "/nonexistent-directory-for-pwnity-testing"]
    job_id = job_manager.start_job(command, session_obj=mock_session)
    assert job_id is not None

    # 2. Warten, bis der Job fertig ist
    time.sleep(0.2)
    job = job_manager.get_job(job_id)
    assert job is not None

    # 3. Status und Ergebnis überprüfen
    assert job.status == "failed"
    assert job.return_code != 0
    assert "No such file or directory" in job.output

def test_kill_running_job(job_manager, mock_session):
    """
    Testet, ob ein laufender Job korrekt beendet werden kann.
    """
    # 1. Einen langlebigen Job starten
    command = ["sleep", "5"]
    job_id = job_manager.start_job(command, session_obj=mock_session)
    job = job_manager.get_job(job_id)
    
    # 2. Direkt nach dem Start den Status überprüfen
    assert job.status == "running"

    # 3. Den Job beenden
    kill_success = job_manager.kill_job(job_id)
    assert kill_success is True

    # 4. Warten, bis der Kill-Prozess abgeschlossen ist
    time.sleep(0.2)

    # 5. Endgültigen Status überprüfen
    assert job.status == "killed"
    # Der Return-Code eines beendeten Prozesses ist typischerweise negativ oder > 128
    assert job.return_code is not None
    assert job.return_code != 0

def test_kill_non_running_job(job_manager, mock_session):
    """Testet, dass der Versuch, einen nicht laufenden Job zu beenden, fehlschlägt."""
    job_id = job_manager.start_job(["echo", "test"], session_obj=mock_session)
    time.sleep(0.2) # Warten, bis der Job beendet ist

    job = job_manager.get_job(job_id)
    assert job.status == "finished"

    # Der Versuch, den beendeten Job zu beenden, sollte False zurückgeben
    kill_success = job_manager.kill_job(job_id)
    assert kill_success is False

def test_send_input_to_finished_job(job_manager, mock_session):
    """Testet, dass keine Eingabe an einen beendeten Job gesendet werden kann."""
    job_id = job_manager.start_job(["echo", "test"], session_obj=mock_session)
    time.sleep(0.2) # Warten, bis der Job beendet ist

    send_success = job_manager.send_input(job_id, "this should fail")
    assert send_success is False

def test_start_job_with_nonexistent_command(job_manager, mock_session, mocker):
    """
    Tests that attempting to start a non-existent command creates a job that immediately fails.
    """
    command = ["nonexistentcommand12345"]
    
    # Act: Start the job that is expected to fail immediately.
    job_id = job_manager.start_job(command, session_obj=mock_session)
    
    # Assert 1: The manager should return a valid job ID even for a failed job.
    assert job_id is not None
    
    # Assert 2: The job object should exist in the manager.
    job = job_manager.get_job(job_id)
    assert job is not None

    # Assert 3: The job should be in the 'failed' state immediately.
    # The new pipe-based error reporting in start_job makes this synchronous,
    # so no polling or sleeping is needed.
    assert job.status == "failed"
    assert "pwnity: command not found: nonexistentcommand12345" in job.output, \
        f"Expected error message not found in job output: {job.output}"

def test_send_input_to_job(job_manager, mock_session):
    """
    Testet, ob Input korrekt an einen laufenden Job gesendet werden kann.
    """
    # 1. Starte einen Job, der auf stdin wartet (cat ist dafür perfekt)
    command = ["cat"]
    job_id = job_manager.start_job(command, session_obj=mock_session)
    job = job_manager.get_job(job_id)
    
    # Gib dem Prozess einen Moment zum Starten
    time.sleep(0.1)
    assert job.status == "running"

    # 2. Sende eine Zeile Text an den Job
    input_text = "hello from the test"
    send_success = job_manager.send_input(job_id, input_text)
    assert send_success is True

    # 3. Warte kurz, damit der Output-Reader-Thread den Output erfassen kann
    time.sleep(0.1)

    # 4. Überprüfe, ob der gesendete Text im Output des Jobs erscheint
    with job.lock:
        assert input_text in job.output

    # 5. Aufräumen: Beende den Job
    job_manager.kill_job(job_id)

def test_clear_finished_jobs(job_manager, mock_session):
    """
    Testet, ob beendete Jobs korrekt aus der Liste entfernt werden,
    während laufende Jobs erhalten bleiben.
    """
    # 1. Einen erfolgreichen und einen fehlgeschlagenen Job starten
    job_id_success = job_manager.start_job(["echo", "success"], session_obj=mock_session)
    job_id_fail = job_manager.start_job(["ls", "/nonexistent-dir"], session_obj=mock_session)

    # 2. Warten, bis beide fertig sind
    time.sleep(0.2)
    assert job_manager.get_job(job_id_success).status == "finished"
    assert job_manager.get_job(job_id_fail).status == "failed"
    assert len(job_manager.list_jobs()) == 2

    # 3. Einen laufenden Job starten, der nicht entfernt werden sollte
    job_id_running = job_manager.start_job(["sleep", "2"], session_obj=mock_session)
    assert job_manager.get_job(job_id_running).status == "running"
    assert len(job_manager.list_jobs()) == 3

    # 4. Aufräumen
    job_manager.clear_finished_jobs()

    # 5. Überprüfen
    remaining_jobs = job_manager.list_jobs()
    assert len(remaining_jobs) == 1
    assert remaining_jobs[0].id == job_id_running
    assert remaining_jobs[0].status == "running"

    # Aufräumen des letzten Jobs
    job_manager.kill_job(job_id_running)

def test_shutdown_kills_running_jobs(job_manager, mock_session):
    """Testet, ob die shutdown-Methode alle laufenden Jobs beendet."""
    job_id = job_manager.start_job(["sleep", "5"], session_obj=mock_session)
    assert job_manager.get_job(job_id).status == "running"

    job_manager.shutdown()
    time.sleep(0.2) # Gib dem Kill-Prozess Zeit

    assert job_manager.get_job(job_id).status == "killed"

@pytest.mark.parametrize("input_text, expected_output", [
    ("Just plain text", "Just plain text"),
    ("\x1b[31mRed text\x1b[0m", "Red text"),
    ("Progress: 10%\rProgress: 50%\rProgress: 100%", "Progress: 100%"),
    ("Line 1\r\nLine 2", "Line 1\nLine 2"),
    ("Mixed \x1b[32mcontent\x1b[0m with\rOverwrite", "Overwrite"),
])
def test_strip_ansi_function(input_text, expected_output):
    """
    Testet die `strip_ansi`-Funktion isoliert, um sicherzustellen, dass sie
    sowohl ANSI-Farbcodes als auch Wagenrückläufe korrekt entfernt.
    """
    # Die Logik für den Wagenrücklauf wurde vereinfacht, um nur den letzten Teil zu behalten.
    # Wir passen den Test an, um dieses Verhalten zu reflektieren.
    # Der Test `test_start_and_finish_failed_job` deckt bereits den Fall ab, dass die Ausgabe "No such file or directory" enthält.
    assert strip_ansi(input_text) == expected_output.replace('\r', '')

# --- New tests for _cmd_* methods ---

def test_cmd_list(job_manager, mock_session, mocker):
    """Tests the _cmd_list handler."""
    mock_cli = job_manager.cli
    job_manager.start_job(["echo", "test"], mock_session)
    job_manager._cmd_list(args=None, cli=mock_cli)
    mock_cli.display_mgr.display_jobs_list.assert_called_once()

def test_cmd_show_with_logbook(job_manager, mock_session, mocker):
    """Tests _cmd_show when the job has a logbook entry."""
    mock_cli = job_manager.cli
    job_id = job_manager.start_job(["echo", "test"], mock_session)
    time.sleep(0.2) # Let job finish
    job = job_manager.get_job(job_id)
    job.logbook_id = 123 # Manually set for the test

    args = type('Args', (), {'id': job_id})()
    job_manager._cmd_show(args, mock_cli)
    
    # It should dispatch to the logbook manager
    mock_cli.logbook_mgr.dispatch.assert_called_once_with("show", mocker.ANY, mock_cli)

def test_cmd_show_without_logbook(job_manager, mock_session):
    """Tests _cmd_show when the job has no logbook entry (e.g., still running)."""
    mock_cli = job_manager.cli
    job_id = job_manager.start_job(["sleep", "1"], mock_session)
    
    args = type('Args', (), {'id': job_id})()
    job_manager._cmd_show(args, mock_cli)

    # It should fall back to displaying raw job output
    mock_cli.display_mgr.display_job_output.assert_called_once()

def test_cmd_kill(job_manager, mock_session, mocker):
    """Tests the _cmd_kill handler."""
    mocker.patch.object(job_manager, 'kill_job')
    # The parser now provides a string, so we simulate that.
    args = type('Args', (), {'id': '1'})()
    job_manager._cmd_kill(args, cli=None)
    job_manager.kill_job.assert_called_once_with('1')
