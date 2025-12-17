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

# tests/test_command_executor.py
import pytest
from modules.managers.command_executor import CommandExecutor

@pytest.fixture
def mock_managers(mocker):
    """Provides a dictionary of mocked managers required by the CommandExecutor."""
    return {
        "job_mgr": mocker.MagicMock(),
        "logbook_mgr": mocker.MagicMock(),
        "report_mgr": mocker.MagicMock(),
        "display_mgr": mocker.MagicMock(),
    }

@pytest.fixture
def executor(mock_managers):
    """Provides a CommandExecutor instance with mocked dependencies."""
    return CommandExecutor(
        job_mgr=mock_managers["job_mgr"],
        logbook_mgr=mock_managers["logbook_mgr"],
        report_mgr=mock_managers["report_mgr"],
        display_mgr=mock_managers["display_mgr"],
    )

@pytest.fixture
def mock_session(mocker):
    """Provides a mock session object."""
    session = mocker.MagicMock()
    session.name = "test-session"
    session.report = "test-report"
    return session

def test_execute_background_job(executor, mock_managers, mock_session):
    """
    Tests that executing with `run_bg=True` correctly calls the JobManager.
    """
    command_list = ["nmap", "-sV", "localhost"]

    # Configure the mock to return a realistic job ID
    mock_managers["job_mgr"].start_job.return_value = 1
    
    executor.execute(
        command_lists=[command_list],
        session_obj=mock_session,
        tool_name="nmap",
        tool_command_name="scan",
        run_now=False,
        run_bg=True
    )

    # Verify that the job manager was called to start the job
    mock_managers["job_mgr"].start_job.assert_called_once_with(
        command_list,
        session_obj=mock_session,
        tool_name="nmap",
        tool_command_name="scan"
    )

def test_execute_foreground_job_success(executor, mock_managers, mock_session, mocker):
    """
    Tests a successful foreground execution, verifying that output is processed
    and the correct managers are called for logging and display.
    """
    # Mock subprocess.Popen
    mock_process = mocker.MagicMock()
    mock_process.returncode = 0
    # Simulate stdout providing some bytes
    mock_process.stdout.read.side_effect = [b"Port 80 is open\n", b""]
    mocker.patch("subprocess.Popen", return_value=mock_process)

    command_list = ["nmap", "-sV", "localhost"]
    executor.execute(
        command_lists=[command_list],
        session_obj=mock_session,
        tool_name="nmap",
        tool_command_name="scan",
        run_now=True,
        run_bg=False
    )

    # Verify that a logbook entry was created
    mock_managers["logbook_mgr"].create_entry.assert_called_once()
    # Verify that the execution summary was displayed with a "Success" status
    mock_managers["display_mgr"].display_execution_summary.assert_called_once()
    call_kwargs = mock_managers["display_mgr"].display_execution_summary.call_args.kwargs
    assert call_kwargs["status_text"] == "Success"
    assert call_kwargs["return_code"] == 0

def test_execute_foreground_job_failure(executor, mock_managers, mock_session, mocker):
    """
    Tests a failed foreground execution.
    """
    mock_process = mocker.MagicMock()
    mock_process.returncode = 1
    mock_process.stdout.read.side_effect = [b"Error: Host not found\n", b""]
    mocker.patch("subprocess.Popen", return_value=mock_process)

    command_list = ["nmap", "nonexistent.host"]
    executor.execute(
        command_lists=[command_list],
        session_obj=mock_session,
        tool_name="nmap",
        tool_command_name="scan",
        run_now=True,
        run_bg=False
    )

    mock_managers["logbook_mgr"].create_entry.assert_called_once()
    mock_managers["display_mgr"].display_execution_summary.assert_called_once()
    call_kwargs = mock_managers["display_mgr"].display_execution_summary.call_args.kwargs
    assert call_kwargs["status_text"] == "Failed"
    assert call_kwargs["return_code"] == 1

def test_execute_command_not_found(executor, mock_managers, mock_session, mocker):
    """Tests that a FileNotFoundError is handled gracefully."""
    mocker.patch("subprocess.Popen", side_effect=FileNotFoundError)
    
    # The execute method should catch the error and not crash.
    # It should return -1 to indicate the failure.
    return_code = executor._run_foreground(["nonexistent_command"], mock_session, "test", "test")
    assert return_code == -1
    # No logbook entry or summary should be created for a command that never ran.
    mock_managers["logbook_mgr"].create_entry.assert_not_called()
    mock_managers["display_mgr"].display_execution_summary.assert_not_called()

def test_execute_multiple_commands_with_suppressed_summary(executor, mock_managers, mock_session, mocker):
    """
    Tests that when multiple commands are run with `suppress_individual_summaries=True`,
    only one final summary is displayed.
    """
    # Mock subprocess.Popen to simulate successful execution for all commands
    mock_process = mocker.MagicMock()
    mock_process.returncode = 0
    # Provide enough side effects for two separate Popen calls
    mock_process.stdout.read.side_effect = [b"output 1\n", b"", b"output 2\n", b""]
    mocker.patch("subprocess.Popen", return_value=mock_process)

    command_lists = [
        ["echo", "check 1"],
        ["echo", "check 2"]
    ]
    
    executor.execute(
        command_lists=command_lists,
        session_obj=mock_session,
        tool_name="test-tool",
        tool_command_name="checklist",
        run_now=True,
        run_bg=False,
        suppress_individual_summaries=True # The key flag to test
    )

    # Logbook should be called for each command
    assert mock_managers["logbook_mgr"].create_entry.call_count == 2
    
    # Display manager should be called only ONCE for the overall summary
    mock_managers["display_mgr"].display_execution_summary.assert_called_once()
    call_kwargs = mock_managers["display_mgr"].display_execution_summary.call_args.kwargs
    assert call_kwargs["title"] == "[bold]Overall Summary[/bold]"

def test_execute_foreground_job_interrupted(executor, mock_managers, mock_session, mocker):
    """
    Tests that a KeyboardInterrupt during a foreground job is handled gracefully,
    terminating the process and showing the correct summary.
    """
    # Mock subprocess.Popen
    mock_process = mocker.MagicMock()
    # Simulate that the process is still running when the interrupt happens
    mock_process.poll.return_value = None
    # Raise KeyboardInterrupt when stdout is read, simulating Ctrl+C
    mock_process.stdout.read.side_effect = KeyboardInterrupt
    mocker.patch("subprocess.Popen", return_value=mock_process)

    command_list = ["sleep", "10"]
    executor.execute(
        command_lists=[command_list],
        session_obj=mock_session,
        tool_name="sleep",
        tool_command_name="wait",
        run_now=True,
        run_bg=False
    )

    # Verify that the process was terminated
    mock_process.terminate.assert_called_once()
    # Verify that the summary was displayed with an "Interrupted" status
    mock_managers["display_mgr"].display_execution_summary.assert_called_once()
    call_kwargs = mock_managers["display_mgr"].display_execution_summary.call_args.kwargs
    assert call_kwargs["status_text"] == "Interrupted"
    assert call_kwargs["return_code"] == 130 # Standard exit code for Ctrl+C