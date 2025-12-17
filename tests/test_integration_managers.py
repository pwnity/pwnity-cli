import pytest
import os
import json

# Tests for TargetManager

@pytest.mark.integration
def test_target_copy_command(pwnity_app):
    """Test the 'target copy' command."""
    # 1. Setup: Create a source target with some data
    source_name = "copy_source_target"
    dest_name = "copy_dest_target"
    pwnity_app.onecmd_plus_hooks(f"target add {source_name}")
    pwnity_app.onecmd_plus_hooks(f"target update {source_name} url http://source.com")
    pwnity_app.onecmd_plus_hooks(f"target update {source_name} custom_field 'custom_value'")

    # 2. Action: Run the copy command
    pwnity_app.onecmd_plus_hooks(f"target copy {source_name} {dest_name}")

    # 3. Assertions
    target_mgr = pwnity_app.target_mgr
    assert target_mgr.exists(source_name), "Source target should still exist after copy."
    assert target_mgr.exists(dest_name), "Destination target should be created."

    source_data = target_mgr.load(source_name)
    dest_data = target_mgr.load(dest_name)

    assert dest_data is not None, "Destination data should not be None."
    assert dest_data.get('name') == dest_name, "Destination target's internal name should be updated."
    assert dest_data.get('url') == source_data.get('url'), "URL should be copied."
    assert dest_data.get('hostname') == source_data.get('hostname'), "Hostname should be copied."
    assert dest_data.get('custom_field') == source_data.get('custom_field'), "Custom fields should be copied."

@pytest.mark.integration
def test_target_export_command(pwnity_app, capsys):
    """Test the 'target export' command for correct command generation."""
    # 1. Setup: Create a target with various data types
    target_name = "export_target"
    pwnity_app.onecmd_plus_hooks(f"target add {target_name}")
    pwnity_app.onecmd_plus_hooks(f"target update {target_name} url http://export.test")
    pwnity_app.onecmd_plus_hooks(f"target update {target_name} whois_info '{{'some':'whois'}}'") # JSON as string
    pwnity_app.onecmd_plus_hooks(f"target update {target_name} geo_intel '{{'some':'geo'}}'")
    pwnity_app.onecmd_plus_hooks(f"target update {target_name} custom_field 'custom_value'")

    # 2. Action: Run the export command
    pwnity_app.onecmd_plus_hooks(f"target export {target_name}")
    captured = capsys.readouterr()
    output = captured.out

    # 3. Assertions: Check if the output contains the expected commands
    assert f"target add {target_name}" in output
    assert f"target update {target_name} url 'http://export.test'" in output
    # Check for gather commands, which are semantically correct
    assert f"target gather {target_name} whois" in output
    assert f"target gather {target_name} geo" in output
    # Check for custom fields
    assert f"target update {target_name} custom_field 'custom_value'" in output
    # Check that derived fields are NOT exported redundantly
    assert "target update export_target hostname" not in output
    assert "target update export_target ip" not in output


# Tests for ToolManager

@pytest.mark.integration
def test_tool_copy_command(pwnity_app):
    """Test the 'tool copy' command."""
    # 1. Setup: Create a source tool with some data
    source_name = "copy_source_tool"
    dest_name = "copy_dest_tool"
    pwnity_app.onecmd_plus_hooks(f"tool add {source_name}")
    pwnity_app.onecmd_plus_hooks(f"tool update {source_name} path /usr/bin/test")
    pwnity_app.onecmd_plus_hooks(f"tool update {source_name} description 'A test tool'")
    pwnity_app.onecmd_plus_hooks(f"tool update {source_name} command mycmd")
    pwnity_app.onecmd_plus_hooks(f"tool update {source_name} mycmd param '-p $target.port'")

    # 2. Action: Run the copy command
    pwnity_app.onecmd_plus_hooks(f"tool copy {source_name} {dest_name}")

    # 3. Assertions
    tool_mgr = pwnity_app.tool_mgr
    assert tool_mgr.exists(source_name), "Source tool should still exist after copy."
    assert tool_mgr.exists(dest_name), "Destination tool should be created."

    source_data = tool_mgr.load(source_name)
    dest_data = tool_mgr.load(dest_name)

    assert dest_data is not None, "Destination data should not be None."
    assert dest_data.get('name') == dest_name, "Destination tool's internal name should be updated."
    assert dest_data.get('path') == source_data.get('path'), "Path should be copied."
    assert dest_data.get('description') == source_data.get('description'), "Custom fields should be copied."
    assert len(dest_data.get('commands', [])) == 1, "Commands should be copied."
    assert dest_data['commands'][0]['name'] == 'mycmd'
    assert dest_data['commands'][0]['params'][0] == '-p $target.port'

@pytest.mark.integration
def test_tool_export_command(pwnity_app, capsys):
    """Test the 'tool export' command for correct command generation."""
    # 1. Setup: Create a tool with various data types
    tool_name = "export_tool"
    pwnity_app.onecmd_plus_hooks(f"tool add {tool_name}")
    pwnity_app.onecmd_plus_hooks(f"tool update {tool_name} path /usr/bin/export")
    pwnity_app.onecmd_plus_hooks(f"tool update {tool_name} sudo true")
    pwnity_app.onecmd_plus_hooks(f"tool update {tool_name} description 'A test tool'")
    pwnity_app.onecmd_plus_hooks(f"tool update {tool_name} command mycmd")
    pwnity_app.onecmd_plus_hooks(f"tool update {tool_name} mycmd param '-p $target.port'")
    pwnity_app.onecmd_plus_hooks(f"tool update {tool_name} mycmd description 'A test command'")

    # 2. Action: Run the export command
    pwnity_app.onecmd_plus_hooks(f"tool export {tool_name}")
    captured = capsys.readouterr()
    output = captured.out

    # 3. Assertions: Check if the output contains the expected commands
    assert f"tool add {tool_name}" in output
    assert f"tool update {tool_name} path '/usr/bin/export'" in output
    assert f"tool update {tool_name} sudo true" in output
    assert f"tool update {tool_name} description 'A test tool'" in output
    assert f"tool update {tool_name} command mycmd" in output
    assert f"tool update {tool_name} mycmd description 'A test command'" in output
    assert f"tool update {tool_name} mycmd param '-p $target.port'" in output