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

# modules/placeholders.py
import re
import os
from modules.services import log
from .functions import FUNCTION_REGISTRY
import argparse # Import argparse for type checking

# Global registry for managers
_manager_registry = {}
import xml.etree.ElementTree as ET
import json

# Pattern for the innermost function call, e.g., func(arg) where arg has no parentheses
FUNC_PATTERN = re.compile(r'(\w+)\(([^()]*)\)')

# Matches: {{ key }} or ${ key }
BRACED_PLACEHOLDER_PATTERN = re.compile(r"(?:\{\{\s*(.*?)\s*\}\})|(?:\$\{\s*(.*?)\s*\})")

# --- FIX: Allow hyphens in attribute paths ---
# The character set for the attribute path was missing the hyphen '-'.
# This prevented placeholders like '$target.http_headers.Cache-Control' from being resolved.
SIMPLE_PLACEHOLDER_PATTERN = re.compile(r"\$((?:[a-zA-Z_][a-zA-Z0-9_]*\.[a-zA-Z_][a-zA-Z0-9_]*\([^)]*\))|[a-zA-Z_][a-zA-Z0-9_]*)(\.([a-zA-Z0-9_@.#\[\]\-]+))?")

def xml_to_dict(element):
    """
    Converts an xml.etree.ElementTree.Element into a dictionary.
    This is a helper function now at the module level.
    """
    d = {}
    # Add attributes as normal keys
    d.update(element.attrib)
    # Add text content if it exists
    if element.text and element.text.strip():
        d['#text'] = element.text.strip()

    children = list(element)
    if children:
        for child in children:
            child_dict = xml_to_dict(child)
            tag = child.tag
            if tag not in d:
                d[tag] = []
            d[tag].append(child_dict)
    return d

def get_parsed_report_file_data(report_mgr, report_name: str) -> dict:
    """
    Scans a report's directory, parses supported files (JSON, XML),
    and returns them as a structured dictionary. This is the centralized
    logic for both CLI and Web UI placeholder generation.
    """
    if not report_name or not report_mgr:
        return {}

    files = report_mgr.list_files_details(report_name) # This method exists in report_manager.py now
    if not files:
        return {}

    file_data = {}
    for file_info in files:
        file_name = file_info['name']
        file_path = os.path.join(report_mgr.folder, report_name, file_name)
        if not os.path.isfile(file_path):
            continue

        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            sanitized_name = file_name.replace('.', '_')
            if file_name.lower().endswith('.json'):
                file_data[sanitized_name] = json.loads(content)
            elif file_name.lower().endswith('.xml'):
                root = ET.fromstring(content)
                file_data[sanitized_name] = xml_to_dict(root)
        except Exception as e:
            log.debug(f"Skipping file '{file_name}' during parsing for placeholders: {e}")
    return file_data

def resolve_placeholders(text: str, session=None, tool_name: str = None, command_name: str = None, strict: bool = False) -> str:
    """
    Resolves both simple placeholders ($entity.key) and function-based placeholders (func(...))
    in a given string. Works from the inside out to handle nesting.
    
    If strict=True, it will raise a ValueError if any placeholder cannot be resolved.
    """
    if not isinstance(text, str) or not session:
        return text

    current_text = text
    # --- FINAL FIX for deeply nested placeholders ---
    # This loop ensures that the entire string is repeatedly processed until no more
    # placeholders (neither functions nor simple $entity.key) can be resolved.
    # This correctly handles cases like $tool.input -> $target.auth_b64 -> b64encode($target.username:$target.password) -> final_string
    while True:
        # First, resolve all simple placeholders ($entity.key)
        resolved_simple = _resolve_simple_placeholders(current_text, session, tool_name, command_name, strict=strict)
        # Then, resolve any function calls that might have been exposed
        resolved_functions = _resolve_functions(resolved_simple, session, tool_name, command_name)
        if resolved_functions == current_text:
            # If the text is stable (no more changes), we are done.
            break
        current_text = resolved_functions
    return current_text

def register_manager(key, manager):
    """Registers a manager with a given prefix for placeholder resolution."""
    _manager_registry[key.upper()] = manager

def _resolve_simple_placeholders(text: str, session=None, tool_name: str = None, command_name: str = None, strict: bool = False) -> str:
    """Resolves only the simple $entity.key placeholders."""
    if not isinstance(text, str) or not session:
        return text

    # --- FIX for nested placeholders ---
    # Loop to resolve nested simple placeholders, e.g., $target.auth_b64 which contains "$target.username:$target.password".
    # The previous implementation would only perform one pass.
    current_text = text
    while True:
        # 1. Resolve braced patterns {{}} and ${}
        text_with_braced = BRACED_PLACEHOLDER_PATTERN.sub(lambda m: _resolve_braced_match(m, session, tool_name, command_name, strict=strict), current_text)
        
        # 2. Resolve $ patterns using existing logic
        resolved_text = SIMPLE_PLACEHOLDER_PATTERN.sub(lambda m: _resolve_match(m, session, tool_name, command_name, strict=strict), text_with_braced)
        
        if resolved_text == current_text: # No more placeholders were found and replaced
            return resolved_text
        current_text = resolved_text

def _resolve_functions(text: str, session=None, tool_name: str = None, command_name: str = None) -> str:
    """Resolves only the function-based placeholders, e.g., func(...)"""
    current_text = text
    # Loop to resolve nested functions, e.g., b64encode(urlencode(...))
    while True:
        match = FUNC_PATTERN.search(current_text)
        if not match:
            break # No more function calls found

        func_name, arg_str = match.groups()

        if func_name in FUNCTION_REGISTRY:
            # The argument string is already resolved from the main loop, so we can call the function directly.
            try:
                result = FUNCTION_REGISTRY[func_name](arg_str)
                # Replace the entire function call with its result
                current_text = current_text[:match.start()] + str(result) + current_text[match.end():]
            except Exception as e:
                log.error(f"Error executing placeholder function '{func_name}': {e}")
                break # Stop processing to avoid further errors
        else:
            # If the name is not a registered function, stop to avoid infinite loops
            # on strings that look like functions but aren't (e.g., "some_command(foo)").
            break
    return current_text


def _resolve_braced_match(match, session, tool_name: str = None, command_name: str = None, strict: bool = False) -> str:
    """Callback for braced placeholders like {{target.ip}} or ${target.ip}."""
    original_placeholder = match.group(0)
    # Group 1 is {{...}}, Group 2 is ${...}
    content = match.group(1) or match.group(2)
    
    if not content:
        return original_placeholder
        
    content = content.strip()
    
    # Split content into entity and attribute path
    if '.' in content:
        parts = content.split('.', 1)
        entity_type = parts[0]
        attr_path = parts[1]
    else:
        entity_type = content
        attr_path = None
        
    return _resolve_from_parts(entity_type, attr_path, original_placeholder, session, tool_name, command_name, strict=strict)

def _resolve_match(match, session, tool_name: str = None, command_name: str = None, strict: bool = False) -> str:
    """Callback function for re.sub to resolve a single placeholder match."""
    original_placeholder = match.group(0) # e.g. $target.ip

    # The new regex has 3 groups. e.g., for '$target.ip', groups are ('target', '.ip', 'ip')
    # For '$target', groups are ('target', None, None)
    entity_type, _, attr_path = match.groups()
    
    return _resolve_from_parts(entity_type, attr_path, original_placeholder, session, tool_name, command_name, strict=strict)

def _resolve_from_parts(entity_type, attr_path, original_placeholder, session, tool_name=None, command_name=None, strict: bool = False) -> str:
    """Shared logic for resolving placeholders given parsed components."""
    
    # --- FINAL, ROBUST FIX ---
    # Handle special cases for '$report' keys first (or report.file...)
    # We check if the KEY indicates a report file access.
    # Construct a key to check against 'report.file.'
    full_key = f"{entity_type}.{attr_path}" if attr_path else entity_type
    
    if full_key.lower().startswith('report.file.'):
        # Manually parse: report.file.<sanitized_filename>.<rest.of.path>
        path_parts = full_key.split('.')[2:]
        if not path_parts:
            return original_placeholder

        file_name_sanitized = path_parts[0]
        # Correctly desanitize the filename.
        if '_' in file_name_sanitized:
            parts = file_name_sanitized.rsplit('_', 1)
            file_name = '.'.join(parts)
        else:
            file_name = file_name_sanitized
        remaining_path = ".".join(path_parts[1:])

        report_mgr = _manager_registry.get('REPORT')
        report_name = getattr(session, 'report', None)
        if not report_name or not report_mgr:
            log.warning(f"Cannot resolve '{original_placeholder}': No report is loaded.")
            return original_placeholder
        
        file_path = os.path.join(report_mgr.folder, report_name, file_name)
        if not os.path.isfile(file_path):
            log.warning(f"Cannot resolve '{original_placeholder}': File '{file_name}' not found in report '{report_name}'.")
            return original_placeholder
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

            if file_name.lower().endswith('.json'):
                parsed_data = json.loads(content)
            elif file_name.lower().endswith('.xml'):
                parsed_data = xml_to_dict(ET.fromstring(content))
            else:
                return original_placeholder

            return _traverse_object(parsed_data, remaining_path, original_placeholder, f"File '{file_name}'", strict=strict)
        except Exception as e:
            if strict: raise
            log.error(f"Error parsing or traversing file for placeholder '{original_placeholder}': {e}")
            return original_placeholder
    # --- End of report.file.* special handling ---

    # The new regex has 3 groups. e.g., for '$target.ip', groups are ('target', '.ip', 'ip')
    # For '$target', groups are ('target', None, None)
    # entity_type, _, attr_path = match.groups() # This is now passed in

    # Case 1: Handle dictionaries (e.g., from workflow overrides or simple dicts)
    if isinstance(session, dict):
        # Check for a full key match first (e.g., "target.ip").
        full_key = f"{entity_type}.{attr_path}" if attr_path else entity_type
        if full_key in session:
            val = session[full_key]
            return json.dumps(val, indent=2) if isinstance(val, (dict, list)) else str(val)

        # Handle nested traversal for entities provided as dicts
        if entity_type in session:
            obj = session[entity_type]
            if attr_path:
                return _traverse_object(obj, attr_path, original_placeholder, f"Workflow Data '{entity_type}'")
            return json.dumps(obj, indent=2) if isinstance(obj, (dict, list)) else str(obj)

        if strict:
            raise ValueError(f"Required placeholder '{original_placeholder}' not found.")
        log.warning(f"Workflow placeholder '{original_placeholder}' not found in provided data.")
        return original_placeholder

    # Case 2: Handle WorkflowContext objects from the automation engine.
    # We check the class name as a string to avoid circular imports.
    if session.__class__.__name__ == 'WorkflowContext':
        path_parts = [entity_type] + (attr_path.split('.') if attr_path else [])
        current_obj = session
        for part in path_parts:
            if hasattr(current_obj, part):
                current_obj = getattr(current_obj, part)
            else:
                if strict:
                    raise ValueError(f"Required placeholder '{original_placeholder}' not found in WorkflowContext at path '{part}'.")
                log.debug(f"Placeholder '{original_placeholder}' not found in WorkflowContext at path '{part}'.")
                return original_placeholder
        
        return str(current_obj)

    # Case 3: Handle standard CLISession objects from the interactive shell.

    log.debug(f"Attempting to resolve placeholder: {original_placeholder}")
    
    manager_key = entity_type.upper()
    
    # --- NEW: Special handling for $report.path ---
    if entity_type == 'report' and attr_path == 'path':
        report_mgr = _manager_registry.get('REPORT')
        report_name = getattr(session, 'report', None)
        if not report_name or not report_mgr:
            log.warning(f"Cannot resolve '{original_placeholder}': No report is loaded.")
            return original_placeholder
        
        # Construct the path to the report's data directory
        report_dir = os.path.join(report_mgr.folder, report_name)
        os.makedirs(report_dir, exist_ok=True) # Ensure the directory exists
        log.debug(f"Placeholder '{original_placeholder}' replaced with: '{report_dir}'")
        return report_dir
    
    # --- Default placeholder logic (e.g., $target, $report) ---
    if not attr_path:
        # For most entities, the default is the loaded name.
        if hasattr(session, entity_type):
            value = getattr(session, entity_type)
            if value:
                # For '$report', the default is a generated output file path.
                if entity_type == 'report':
                    return _resolve_report_default_path(session, tool_name, command_name)
                return str(value)
        if strict:
            raise ValueError(f"Required placeholder '{original_placeholder}' not found.")
        return original_placeholder # If no default can be determined

    # --- Standard entity.attribute resolution ---
    manager_key = entity_type.upper()
    
    # Special case for '$report' default placeholder, which resolves to a file path
    if entity_type == 'report' and not attr_path:
        # Special case for '$report' which resolves to a file path
        if not tool_name or not command_name:
            log.warning(f"Cannot resolve '{original_placeholder}': tool/command context is required but not provided.")
            return original_placeholder
        
        report_mgr = _manager_registry.get('REPORT')
        report_name = getattr(session, 'report', None)
        if not report_name or not report_mgr:
            log.warning(f"Cannot resolve '{original_placeholder}': No report is loaded.")
            return original_placeholder
        
        report_dir = os.path.join(report_mgr.folder, report_name)
        os.makedirs(report_dir, exist_ok=True)
        filename = f"{tool_name}-{command_name}.txt"
        return os.path.join(report_dir, filename)
    else:
        # --- Handle 'session' as a special case ---
        if entity_type == 'session':
            if hasattr(session, 'name'): # It's a session object
                obj = {
                    'name': session.name,
                    'target': session.target,
                    'tool': session.tool,
                    'wordlist': session.wordlist,
                    'report': session.report
                }
                obj_name_for_log = session.name
            else: # It's a dictionary (from a workflow)
                obj = session
                obj_name_for_log = "Workflow Data"
        else:
            mgr = _manager_registry.get(manager_key.upper())

            if not mgr:
                log.warning(f"No manager registered for '{manager_key}'. Placeholder '{original_placeholder}' will not be replaced.")
                return original_placeholder

            # 'profile' is global and not bound to the session.
            if entity_type == 'profile':
                obj = mgr.load()
                obj_name_for_log = "Profile"
            elif entity_type == 'proxy':
                obj = mgr.get_placeholder_config(session)
                obj_name_for_log = "Proxy"
            elif entity_type == 'logbook':
                path_parts = attr_path.split('.')
                log_id = path_parts.pop(0)
                attr_path = ".".join(path_parts)
                obj = mgr.load(log_id)
                obj_name_for_log = f"Logbook Entry #{log_id}"
                if not obj:
                    log.warning(f"Logbook entry with ID '{log_id}' not found.")
                    return original_placeholder
            elif entity_type in ['note', 'loot']:
                if not session.report:
                    log.warning(f"Cannot resolve ${entity_type} placeholder: No report loaded.")
                    return original_placeholder
                report_data = _manager_registry.get('REPORT').load(session.report)
                if not report_data:
                    log.warning(f"Cannot resolve ${entity_type} placeholder: Could not load report '{session.report}'.")
                    return original_placeholder
                data_key = 'notes' if entity_type == 'note' else 'loot'
                obj = report_data.get(data_key, [])
                obj_name_for_log = f"Report '{session.report}'"
            else:
                obj_name = getattr(session, entity_type, None)
                obj_name_for_log = obj_name
                if not obj_name or not isinstance(obj_name, str):
                    log.warning(f"No object for '{entity_type}' loaded in session. Placeholder '{original_placeholder}' will not be replaced.")
                    return original_placeholder
                log.debug(f"Loading object '{obj_name}' from manager '{manager_key}'...")
                obj = mgr.load(obj_name)

    if not obj:
        log.error(f"Could not load object '{obj_name_for_log}'. Placeholder '{original_placeholder}' will not be replaced.")
        return original_placeholder

    # --- Logic for nested access ---
    path_parts = attr_path.split('.')
    current_value = obj

    for i, part in enumerate(path_parts):
        current_path_str = ".".join(path_parts[:i+1])
        if isinstance(current_value, dict):
            if part in current_value:
                current_value = current_value[part]
            else:
                log.debug(f"Sub-path '{current_path_str}' not found in object '{obj_name_for_log}' (key '{part}' is missing). Placeholder '{original_placeholder}' will not be replaced.")
                return original_placeholder
        elif isinstance(current_value, list):
            try:
                # Use 'part' as a 0-based index, consistent with documentation.
                index = int(part)
                current_value = current_value[index]
            except (ValueError, IndexError):
                log.debug(f"Invalid or out-of-bounds index '{part}' for sub-path '{current_path_str}' in placeholder '{original_placeholder}'.")
                return original_placeholder
        else:
            # We cannot go deeper if it's not a dict or a list
            log.debug(f"Cannot fully resolve attribute path '{attr_path}'. '{current_path_str}' is not an object or list. Placeholder '{original_placeholder}' will not be replaced.")

    resolved_value = current_value
    # --- FIX: Correctly handle None values ---
    # The previous logic returned the original placeholder if the resolved value was None.
    # The correct behavior is to return the string representation of the resolved value.
    log.debug(f"Placeholder '{original_placeholder}' replaced with: '{resolved_value}' of type {type(resolved_value)}")
    # If the final resolved value is a complex type, format it as JSON for readability.
    if isinstance(resolved_value, (dict, list)):
        return json.dumps(resolved_value, indent=2)
    
    if resolved_value is None and strict:
         raise ValueError(f"Resolved value for '{original_placeholder}' is None.")

    # This will correctly convert None to "None", "" to "", etc.
    return str(resolved_value)

def _traverse_object(obj, path_str, original_placeholder, obj_name_for_log, strict: bool = False):
    """Helper to traverse a nested object (dict/list) using a dot-separated path."""
    if not path_str:
        return json.dumps(obj, indent=2) if isinstance(obj, (dict, list)) else str(obj)

    path_parts = path_str.split('.')
    current_value = obj

    for i, part in enumerate(path_parts):
        current_path_str = ".".join(path_parts[:i+1])
        if isinstance(current_value, dict):
            if part in current_value:
                current_value = current_value[part]
            else:
                log.warning(f"Sub-path '{current_path_str}' not found in {obj_name_for_log} (key '{part}' is missing). Placeholder '{original_placeholder}' will not be replaced.")
                return original_placeholder
        elif isinstance(current_value, list):
            try:
                index = int(part)
                current_value = current_value[index]
            except (ValueError, IndexError):
                log.warning(f"Invalid or out-of-bounds index '{part}' for sub-path '{current_path_str}' in placeholder '{original_placeholder}'.")
                return original_placeholder
        else:
            if strict:
                raise ValueError(f"Cannot fully resolve attribute path '{path_str}'. '{current_path_str}' is not an object or list.")
            log.warning(f"Cannot fully resolve attribute path '{path_str}'. '{current_path_str}' is not an object or list. Placeholder '{original_placeholder}' will not be replaced.")
            return original_placeholder
    
    resolved_value = current_value
    if resolved_value is not None:
        # --- FINAL FIX for wrapped workflow data ---
        # If the resolved value is our special wrapped data object from the frontend,
        # we must extract the actual value from it before returning.
        if isinstance(resolved_value, dict) and '_path' in resolved_value and '_value' in resolved_value:
            resolved_value = resolved_value['_value']

        log.debug(f"Placeholder '{original_placeholder}' replaced with: '{resolved_value}'")
        # If the final resolved value is a complex type, format it as JSON for readability.
        if isinstance(resolved_value, (dict, list)):
            return json.dumps(resolved_value, indent=2)
        return str(resolved_value)

def _resolve_report_default_path(session, tool_name, command_name):
    """
    Helper function to resolve the default '$report' placeholder to a file path.
    e.g., 'reports/my-report/nmap-scan.txt'
    """
    if not tool_name or not command_name:
        log.warning("Cannot resolve '$report': tool/command context is required but not provided.")
        return '$report'

    report_mgr = _manager_registry.get('REPORT')
    report_name = getattr(session, 'report', None)
    if not report_name or not report_mgr:
        log.warning("Cannot resolve '$report': No report is loaded.")
        return '$report'

    report_dir = os.path.join(report_mgr.folder, report_name)
    os.makedirs(report_dir, exist_ok=True)
    filename = f"{tool_name}-{command_name}.txt"
    return os.path.join(report_dir, filename)

def get_entity_data(entity, session):
    """
    Retrieves the full data dictionary for a specific entity type, 
    matching the logic used in the REST API.
    """
    if not session:
        return {}
    data = None
    manager_key = entity.upper()
    mgr = _manager_registry.get(manager_key)

    if mgr and entity != 'proxy':
        # Use a safe fallback for items that aren't stored as direct attributes in the session
        # (e.g., 'profile' is global)
        item_name = None
        if entity in ['target', 'tool', 'wordlist', 'report']:
            item_name = getattr(session, entity, None)
        
        data = mgr.load(item_name)
    elif entity == 'proxy':
        proxy_mgr = _manager_registry.get('PROXY')
        if proxy_mgr:
            data = proxy_mgr.get_placeholder_config(session)
    
    # Manually add $report.path if a report is loaded and the entity is 'report'
    if entity == 'report' and getattr(session, 'report', None) and data:
        data['path'] = resolve_placeholders('$report.path', session)

        # Dynamically add placeholders from files within the report
        try:
            report_mgr = _manager_registry.get('REPORT')
            file_data_for_placeholders = get_parsed_report_file_data(
                report_mgr, session.report
            )
            if file_data_for_placeholders:
                data['file'] = file_data_for_placeholders
        except Exception as e:
            log.error(f"Failed to parse report files for autocomplete: {e}")

    return data if data is not None else {}
