# tests/test_parser_factory.py
import pytest
import argparse
from modules.parser_factory import ParserFactory, ChoicesProvider

@pytest.fixture
def mock_managers(mocker):
    """Creates a dictionary of mocked managers."""
    manager_names = [
        'target_mgr', 'tool_mgr', 'wordlist_mgr', 'preset_mgr', 'session_mgr',
        'job_mgr', 'profile_mgr', 'help_mgr', 'manual_mgr', 'parser_mgr',
        'logbook_mgr', 'report_mgr', 'revshell_mgr', 'heartbeat_mgr',
        'library_mgr', 'workflow_mgr'
    ]
    managers = {}
    for name in manager_names:
        mock = mocker.MagicMock()
        # Ensure list methods exist and return empty lists for completers
        if hasattr(mock, 'list_all'):
            mock.list_all.return_value = []
        if hasattr(mock, 'list'):
            mock.list.return_value = []
        if hasattr(mock, 'list_jobs'):
            mock.list_jobs.return_value = []
        managers[name] = mock
    return managers

@pytest.fixture
def parser_factory(mock_managers):
    """Provides a ParserFactory instance with all dependencies mocked."""
    return ParserFactory(**mock_managers)

@pytest.fixture
def empty_parsers():
    """Provides a dictionary of empty ArgumentParser objects."""
    parser_names = [
        'target', 'tool', 'wordlist', 'preset', 'session', 'jobs', 'profile',
        'proxy', 'overview', 'note', 'loot', 'placeholders', 'config', 'manual',
        'parser', 'logbook', 'report', 'revshell', 'heartbeat', 'library',
        'workflow', 'pwn'
    ]
    return {name: argparse.ArgumentParser(prog=name) for name in parser_names}

def get_subparser(parser, name):
    """Helper to find a subparser by name."""
    subparsers_action = next((action for action in parser._actions if isinstance(action, argparse._SubParsersAction)), None)
    if subparsers_action:
        return subparsers_action.choices.get(name)
    return None

def test_populate_target_parser(parser_factory, empty_parsers):
    """
    Tests that the target parser is correctly populated with its subcommands.
    """
    parsers = {"target": empty_parsers["target"]}
    parser_factory.populate_all_parsers(parsers)
    
    target_parser = parsers["target"]
    
    # Check for common subcommands
    assert get_subparser(target_parser, "add") is not None
    assert get_subparser(target_parser, "list") is not None
    assert get_subparser(target_parser, "load") is not None
    
    # Check for target-specific subcommand
    assert get_subparser(target_parser, "gather") is not None
    
    # Check an argument on a subcommand
    add_parser = get_subparser(target_parser, "add")
    actions = [action.dest for action in add_parser._actions]
    assert "name" in actions

def test_populate_tool_parser(parser_factory, empty_parsers):
    """
    Tests that the tool parser is correctly populated.
    """
    parsers = {"tool": empty_parsers["tool"]}
    parser_factory.populate_all_parsers(parsers)
    tool_parser = parsers["tool"]

    # Check for tool-specific subcommand
    assert get_subparser(tool_parser, "reorder") is not None
    
    # Check arguments on the reorder subcommand
    reorder_parser = get_subparser(tool_parser, "reorder")
    actions = [action.dest for action in reorder_parser._actions]
    assert "old_index" in actions
    assert "new_index" in actions

def test_tool_parser_custom_help_examples(parser_factory, empty_parsers):
    """
    Tests that the custom help examples for 'tool update' and 'tool delete'
    are correctly set in the parser factory.
    """
    parsers = {"tool": empty_parsers["tool"]}
    parser_factory.populate_all_parsers(parsers)
    tool_parser = parsers["tool"]

    # 1. Check 'tool update' examples
    update_parser = get_subparser(tool_parser, "update")
    assert update_parser is not None
    update_examples = {example[0] for example in update_parser.examples} # Use a set for easy checking
    assert "tool update nmap sudo true" in update_examples
    assert "tool update nmap command stealth-scan" in update_examples
    assert "tool update nmap stealth-scan param '-p-'" in update_examples

    # 2. Check 'tool delete' examples
    delete_parser = get_subparser(tool_parser, "delete")
    assert delete_parser is not None
    delete_examples = {example[0] for example in delete_parser.examples}
    assert "tool delete nmap path" in delete_examples
    assert "tool delete nmap stealth-scan" in delete_examples # Shortcut
    assert "tool delete nmap command stealth-scan" in delete_examples # Explicit
    assert "tool delete nmap stealth-scan param 2" in delete_examples


def test_populate_jobs_parser(parser_factory, empty_parsers):
    """
    Tests that the jobs parser is correctly populated.
    """
    parsers = {"jobs": empty_parsers["jobs"]}
    parser_factory.populate_all_parsers(parsers)
    jobs_parser = parsers["jobs"]

    assert get_subparser(jobs_parser, "list") is not None
    assert get_subparser(jobs_parser, "show") is not None
    assert get_subparser(jobs_parser, "kill") is not None
    assert get_subparser(jobs_parser, "clear") is not None

    show_parser = get_subparser(jobs_parser, "show")
    actions = [action.dest for action in show_parser._actions]
    assert "id" in actions

def test_choices_provider(mocker):
    """
    Tests the ChoicesProvider helper class to ensure it calls the correct manager method.
    """
    mock_mgr = mocker.MagicMock()
    mock_mgr.list_all.return_value = ["item1", "item2"]

    provider = ChoicesProvider(mock_mgr, method_name='list_all')
    
    # The provider instance should be callable
    result = provider()

    mock_mgr.list_all.assert_called_once()
    assert result == ["item1", "item2"]

def test_populate_pwn_parser(parser_factory, empty_parsers):
    """
    Tests that the pwn parser is correctly populated with its 'REMAINDER' argument.
    """
    parsers = {"pwn": empty_parsers["pwn"]}
    parser_factory.populate_all_parsers(parsers)
    
    pwn_parser = parsers["pwn"]
    
    # The pwn parser should have one main argument that captures all following text.
    actions = [action.dest for action in pwn_parser._actions]
    assert "pwn_args" in actions
    assert len(actions) == 2 # One for pwn_args, one for help

def test_populate_proxy_parser(parser_factory, empty_parsers):
    """
    Tests that the proxy parser is correctly populated with its subcommands.
    """
    parsers = {"proxy": empty_parsers["proxy"]}
    parser_factory.populate_all_parsers(parsers)
    
    proxy_parser = parsers["proxy"]
    
    # Check for simple subcommands without arguments
    assert get_subparser(proxy_parser, "on") is not None
    assert get_subparser(proxy_parser, "off") is not None
    assert get_subparser(proxy_parser, "show") is not None
    
    # Check a subcommand with arguments
    set_parser = get_subparser(proxy_parser, "set")
    assert set_parser is not None
    actions = [action.dest for action in set_parser._actions]
    assert "set_args" in actions

def test_populate_config_parser(parser_factory, empty_parsers):
    """
    Tests that the config parser is correctly populated.
    """
    parsers = {"config": empty_parsers["config"]}
    parser_factory.populate_all_parsers(parsers)
    config_parser = parsers["config"]

    assert get_subparser(config_parser, "list") is not None
    
    get_parser = get_subparser(config_parser, "get")
    assert get_parser is not None
    assert "key" in [action.dest for action in get_parser._actions]

    set_parser = get_subparser(config_parser, "set")
    assert set_parser is not None
    actions = [action.dest for action in set_parser._actions]
    assert "key" in actions
    assert "value" in actions

def test_populate_session_parser(parser_factory, empty_parsers):
    """
    Tests that the session parser is correctly populated.
    """
    parsers = {"session": empty_parsers["session"]}
    parser_factory.populate_all_parsers(parsers)
    session_parser = parsers["session"]

    assert get_subparser(session_parser, "new") is not None
    assert get_subparser(session_parser, "switch") is not None
    assert get_subparser(session_parser, "list") is not None
    assert get_subparser(session_parser, "destroy") is not None
    assert get_subparser(session_parser, "show") is not None

def test_populate_revshell_parser(parser_factory, empty_parsers):
    """
    Tests that the revshell parser is correctly populated with its optional arguments.
    """
    parsers = {"revshell": empty_parsers["revshell"]}
    parser_factory.populate_all_parsers(parsers)
    revshell_parser = parsers["revshell"]

    actions = [action.dest for action in revshell_parser._actions]
    assert "language" in actions
    assert "ip" in actions
    assert "port" in actions

def test_populate_report_parser(parser_factory, empty_parsers):
    """
    Tests that the report parser is correctly populated with its mix of
    common and custom subcommands.
    """
    parsers = {"report": empty_parsers["report"]}
    parser_factory.populate_all_parsers(parsers)
    report_parser = parsers["report"]

    # Common commands
    assert get_subparser(report_parser, "add") is not None
    assert get_subparser(report_parser, "load") is not None
    # Custom commands
    assert get_subparser(report_parser, "render") is not None
    assert get_subparser(report_parser, "view") is not None
    assert get_subparser(report_parser, "unload") is not None