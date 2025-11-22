# tests/test_placeholders.py
import pytest
from modules import placeholders
from modules.cli_sessions import CLISession
import os

@pytest.fixture
def placeholder_test_setup(mocker):
    """
    A comprehensive fixture to set up a complete mock environment for placeholder testing.
    It creates mock managers, populates them with data, registers them, and creates a mock session.
    """
    # 1. Create mock managers
    mock_target_mgr = mocker.MagicMock()
    mock_tool_mgr = mocker.MagicMock()
    mock_profile_mgr = mocker.MagicMock()
    mock_report_mgr = mocker.MagicMock()
    mock_logbook_mgr = mocker.MagicMock()

    # 2. Define mock data
    target_data = {
        "name": "test-server.com",
        "ip": "192.168.1.101",
        "hostname": "test-server.com",
        "port": "443",
        "subdomains": ["www", "api"],
        "data": {"nested_key": "nested_value"}
    }
    tool_data = {"name": "nmap"}
    profile_data = {"lhost": "10.10.14.5"}
    report_data = {"name": "test-report"}
    logbook_data = {"id": 123, "command": "nmap -sV localhost"}

    # 3. Configure mock managers to return the data
    mock_target_mgr.load.return_value = target_data
    mock_tool_mgr.load.return_value = tool_data
    mock_profile_mgr.load.return_value = profile_data
    mock_report_mgr.load.return_value = report_data
    mock_logbook_mgr.load.return_value = logbook_data

    # 4. Register mock managers with the placeholder module
    placeholders.register_manager("TARGET", mock_target_mgr)
    placeholders.register_manager("TOOL", mock_tool_mgr)
    placeholders.register_manager("PROFILE", mock_profile_mgr)
    placeholders.register_manager("REPORT", mock_report_mgr)
    placeholders.register_manager("LOGBOOK", mock_logbook_mgr)

    # 5. Create a mock session and "load" the entities
    session = CLISession("test-session")
    session.target = "test-server.com"
    session.tool = "nmap"
    session.report = "test-report"

    return {
        "session": session,
        "target_mgr": mock_target_mgr,
        "tool_mgr": mock_tool_mgr,
        "profile_mgr": mock_profile_mgr,
        "report_mgr": mock_report_mgr,
        "logbook_mgr": mock_logbook_mgr,
    }

@pytest.mark.parametrize("input_str, expected_output", [
    # Simple placeholders
    ("Target IP is $target.ip", "Target IP is 192.168.1.101"),
    ("Tool name is $tool.name", "Tool name is nmap"),
    ("LHOST is $profile.lhost", "LHOST is 10.10.14.5"),
    ("Report name is $report.name", "Report name is test-report"),
    
    # Default placeholders
    ("Default for target is $target", "Default for target is test-server.com"),
    
    # Nested access
    ("Nested value: $target.data.nested_key", "Nested value: nested_value"),
    
    # List/index access
    ("First subdomain: $target.subdomains.0", "First subdomain: www"),
    ("Second subdomain: $target.subdomains.1", "Second subdomain: api"),
    
    # Unresolved placeholders
    ("Non-existent field: $target.nonexistent", "Non-existent field: $target.nonexistent"),
    ("Unloaded entity: $wordlist.path", "Unloaded entity: $wordlist.path"),
    
    # No placeholders
    ("Just a regular string", "Just a regular string"),
    ("String with a dollar sign $ but no placeholder", "String with a dollar sign $ but no placeholder"),
])
def test_simple_placeholder_resolution(placeholder_test_setup, input_str, expected_output):
    """Tests the resolution of simple $entity.key placeholders."""
    session = placeholder_test_setup["session"]
    resolved_text = placeholders.resolve_placeholders(input_str, session)
    assert resolved_text == expected_output

@pytest.mark.parametrize("input_str, expected_output", [
    # Single function
    ("b64encode($target.name)", "dGVzdC1zZXJ2ZXIuY29t"),
    ("hexencode($profile.lhost)", "31302e31302e31342e35"),
    
    # Nested functions (resolved from inside out)
    ("hexencode(b64encode($target.name))", "6447567a6443317a5a584a325a58497559323974"),
    
    # Function with plain text argument
    ("md5(fixed_string)", "8475fa7d3a2fa0616d91bd7542199c7f"),
    
    # Function with mixed content
    ("urlencode(path/$target.name)", "path%2Ftest-server.com"),
])
def test_function_placeholder_resolution(placeholder_test_setup, input_str, expected_output):
    """Tests the resolution of function-based placeholders like func($entity.key)."""
    session = placeholder_test_setup["session"]
    resolved_text = placeholders.resolve_placeholders(input_str, session)
    assert resolved_text == expected_output

def test_workflow_placeholder_resolution(placeholder_test_setup):
    """
    Tests placeholder resolution in a workflow context, where the 'session'
    is a dictionary of override values, not a CLISession object.
    """
    # In workflows, the frontend provides a flat dictionary of placeholder values.
    workflow_data = {
        "target.ip": "10.20.30.40", # This value should override the one from the mock manager
        "profile.lhost": "192.168.254.254",
        "custom_key": "custom_value"
    }

    input_str = "Attack from $profile.lhost to $target.ip with value $custom_key"
    expected_output = "Attack from 192.168.254.254 to 10.20.30.40 with value custom_value"

    # The `resolve_placeholders` function should detect that the session is a dict
    # and use it as a direct key-value mapping.
    resolved_text = placeholders.resolve_placeholders(input_str, session=workflow_data)
    assert resolved_text == expected_output

def test_report_file_placeholder_resolution(placeholder_test_setup, tmp_path):
    """Tests the dynamic parsing of report files via placeholders like $report.file.*."""
    report_mgr = placeholder_test_setup["report_mgr"]
    session = placeholder_test_setup["session"]

    # Create a dummy report directory and a JSON file inside it
    report_dir = tmp_path / "reports" / "test-report"
    report_dir.mkdir(parents=True)
    scan_results_file = report_dir / "nmap_scan.json"
    scan_results_file.write_text('{"host": {"status": {"state": "up"}}}')

    # Configure the mock report manager to use this temporary directory
    report_mgr.folder = str(tmp_path / "reports")

    input_str = "Host status is: $report.file.nmap_scan_json.host.status.state"
    expected_output = "Host status is: up"

    resolved_text = placeholders.resolve_placeholders(input_str, session)
    assert resolved_text == expected_output

def test_special_placeholder_types(placeholder_test_setup, tmp_path):
    """
    Tests special placeholder types like $report.path and $logbook.<id>.*
    which have their own dedicated logic paths.
    """
    session = placeholder_test_setup["session"]
    report_mgr = placeholder_test_setup["report_mgr"]
    
    # --- Test 1: $report.path ---
    # Configure the mock report manager to use a temporary directory
    report_mgr.folder = str(tmp_path / "reports")
    expected_report_path = str(tmp_path / "reports" / "test-report")

    resolved_path = placeholders.resolve_placeholders("$report.path", session)
    assert resolved_path == expected_report_path
    assert os.path.isdir(resolved_path) # Check that the directory was created

    # --- Test 2: $logbook.<id>.* ---
    resolved_log_cmd = placeholders.resolve_placeholders("$logbook.123.command", session)
    assert resolved_log_cmd == "nmap -sV localhost"

    # --- Test 3: Default $report placeholder ---
    # This should resolve to a generated file path based on tool and command context.
    expected_default_report_file = os.path.join(expected_report_path, "nmap-scan.txt")
    resolved_default_report = placeholders.resolve_placeholders("$report", session, tool_name="nmap", command_name="scan")
    assert resolved_default_report == expected_default_report_file