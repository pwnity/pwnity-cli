# pwnity

> A flexible and session-based wrapper for orchestrating command-line tools for pentesting and CTFs.

`pwnity` is a framework designed to streamline the repetitive process of tool configuration and execution during a penetration test. It features a powerful interactive command-line interface (CLI) and a modern, reactive Web UI. Instead of manually assembling long commands over and over, you define how a tool (e.g., `nmap`, `gobuster`) is used once, and then you can quickly apply it to different targets.

## Table of Contents

- Features
- The Web UI
- Core Concepts
- Prerequisites
- Installation
- Configuration
- Quick Start: A Simple Workflow
- Key Concepts in Detail
  - Placeholders
  - Proxy Integration & Sudo
- Command Reference
  - target
  - tool
  - wordlist
  - revshell
  - heartbeat
  - parser
  - library
  - session
  - preset
  - proxy
  - pwn / run
  - jobs
  - note & loot
  - overview
  - placeholders
  - identify
  - config
  - profile
- License

## Features

*   **Modular Management:** Manage `Targets`, `Tools`, and `Wordlists` as reusable JSON objects.
*   **Session-Based Workflow:** Keep your workspace clean by loading objects into sessions. Seamlessly switch between different projects.
*   **Dynamic Placeholders:** Build commands with dynamic placeholders like `$target.ip` or `$wordlist.path` that are resolved at runtime.
*   **Intelligent URL Parsing:** Automatically extract hostname, IP, port, domain, and query parameters when you set a target's URL.
*   **Presets:** Save and load complete setups (Target + Tool + Wordlist + Proxy Settings) for recurring scans.
*   **Information Gathering:** Automatically collect DNS, WHOIS, and HTTP information for your targets (`target gather`).
*   **Notes & Loot:** Record your findings directly with the target (`note add`, `loot add`).
*   **Centralized Reporting:** Collect notes, loot, and parser findings from multiple targets into a single, flexible report object.
*   **Proxy Integration:** Route tool execution through a proxy (e.g., `proxychains-ng`) on a per-session basis.
*   **Robust Sudo Handling:** The tool automatically prompts for `sudo` credentials when needed, even for background jobs.
*   **Background Jobs:** Run long-lasting commands in the background and get notified upon completion.
*   **Interactive Shell:** Benefit from autocompletion, command history, and a clear, modern UI thanks to `cmd2` and `rich`.
*   **Web Interface:** A rich, single-page web application for a visual and interactive workflow, featuring a live terminal, drag-and-drop, and real-time updates.
*   **Reference Library:** Manage a personal library of useful links and resources, complete with automatic URL status checking.
*   **Export & Import:** Easily reconstruct your objects elsewhere with the `export` commands.

## Core Concepts

*   **Targets:** The **What**. A target represents the goal of your engagement (e.g., an IP address, a domain). It stores all related information like URL, ports, and gathered data.
*   **Tools:** The **How**. A tool is a template for an external command-line program. You define its subcommands (e.g., `dir` for `gobuster`) and its parameters.
*   **Wordlists:** The **With What**. A simple reference to a text file used for activities like brute-forcing or fuzzing.
*   **Reports:** The **Dossier**. A report is the central data container for an engagement. You load a report into your session, and all subsequent notes, loot, and parser findings are automatically saved to it. This allows you to collect data from multiple targets into one report.
*   **Sessions:** Your current **Workspace**. A session "remembers" which target, tool, wordlist, and proxy settings you have currently loaded. The prompt always shows you the current status.
*   **Revshells:** The **Callback**. A utility to quickly generate reverse shell one-liners for various languages.
*   **Heartbeat:** The **Monitor**. A utility to continuously check a target's health (latency, status code, etc.) over time.
*   **Presets:** A **saved session**. If you often use the same combination of target type, tool, and wordlist, you can save it as a preset and load it with a single command.
*   **Parsers:** The **Eyes**. A parser is a collection of regex rules used to extract structured information (like IPs, emails, hostnames) from unstructured text output.
*   **Library:** Your personal **Knowledge Base**. A collection of reference links, categorized and with automatic status checks to identify dead links.

## The Web UI

While `pwnity` is a fully-featured CLI application, it also includes a powerful web interface that provides a more visual and interactive way to manage your workflow.

**To start the Web UI:**
```bash
python3 web_ui/app.py
```
Then open `http://127.0.0.1:5001` in your browser.

**Web UI Features:**
*   **Live Terminal:** An integrated `xterm.js` terminal that is fully synced with the backend `pwnity` shell.
*   **Real-time Updates:** All views update in real-time as you execute commands in the terminal or interact with the UI.
*   **Visual Management:** Manage all your Targets, Tools, Wordlists, and Library items through an intuitive card-based interface.
*   **Drag-and-Drop:** Re-categorize library items or delete objects by dragging them to a drop zone.
*   **Quick Actions Panel:** Quickly add loot/notes, generate reverse shells, or encode/decode data without leaving your current view.
*   **Live System Stats:** Keep an eye on your system's CPU, Memory, and GPU usage.

## Prerequisites

*   Python 3.x
*   `pip` for installing packages
*   The external tools you want to use (e.g., `nmap`, `gobuster`, `whatweb`) must be installed and available in the system's `PATH`.
*   **Python Libraries:** `cmd2`, `rich`, `dnspython`, `python-whois`, `tldextract`, `rich-argparse`, `questionary`, `flask`, `flask-socketio`, `ptyprocess`, `requests`, `psutil`, `nvidia-ml-py`.

## Configuration

The main configuration is located in `etc/config.json`. You can either edit this file directly or use the `config` command within the shell. It allows you to customize:

*   **DIRS**: The directories where the JSON configurations for targets, tools, etc., are stored.
*   **GLOBAL**: Global settings like the `DEBUG_LEVEL` or the path to the history file.
*   **PROXY**: Global default settings for the proxy wrapper.
*   **LIBRARY**: Settings for the reference library, such as URL check frequency.

## Quick Start: A Simple Workflow

1.  **Start the shell:**
    ```bash
    python3 pwnity.py
    ```

2.  **Create and load a report:** This will be our central data store.
    ```
    (default)> report add project-x
    (default)> report load project-x
    ```

3.  **Create and configure a target:**
    ```
    (default)> target add web-server
    (default)> target update web-server url http://192.168.1.10
    ```
    *This automatically extracts the IP, port, hostname, etc.*

3.  **Create and configure a tool (e.g., `gobuster`):**
    ```
    (default | project-x)> tool add gobuster
    (default)> tool update gobuster command dir
    (default)> tool update gobuster dir param "dir"
    (default)> tool update gobuster dir param "-u $target.base_url"
    (default)> tool update gobuster dir param "-w $wordlist.path"
    (default)> tool update gobuster dir param "-t 50"
    (default)> tool update gobuster dir param "-o $report.path/gobuster.txt"
    ```
    *Note: Each parameter is added individually. `pwnity` is smart about where to place new parameters.*

4.  **Add a wordlist:**
    ```
    (default)> wordlist add common
    (default)> wordlist update common path /usr/share/wordlists/dirbuster/directory-list-2.3-medium.txt
    ```

5.  **Load everything into the session:**
    ```
    (default | project-x)> target load web-server
    (web-server | project-x)> tool load gobuster
    (web-server | gobuster | project-x)> wordlist load common
    (web-server | gobuster | common | project-x)>
    ```
    *The prompt always shows you what is currently loaded.*

6.  **Run the scan:**
    ```
    # Show a preview of the command that will be executed
    (web-server | gobuster | common)> pwn dir

    # Execute the command in the foreground now
    (web-server | gobuster | common)> pwn dir now

    # Or run it in the background
    (web-server | gobuster | common)> pwn dir bg
    ```

7.  **Document your findings:**
    ```
    (web-server | gobuster | common | project-x)> note add Found admin panel at /admin
    (web-server | gobuster | common | project-x)> loot add credential admin:admin
    ```

8.  **Get an overview:**
    ```
    (web-server | gobuster | common)> overview
    ```

## Key Concepts in Detail

### Placeholders

Placeholders are the core of `pwnity`'s flexibility. They allow you to define command templates that are dynamically filled with data from your current session at runtime.

#### Simple Placeholders
*   **Syntax:** `$entity.path.to.value`
*   **Examples:**
    *   `$target.ip`: The IP address of the loaded target.
    *   `$target.base_url`: The URL without path or query (`https://example.com:8080`).
    *   `$target.query_values.id.0`: The first value of the 'id' query parameter.
    *   `$wordlist.path`: The file path of the loaded wordlist.
    *   `$profile.useragent`: A globally defined User-Agent string from your profile.
    *   `$proxy.host`: The host of the currently configured proxy.
    *   `$profile.lhost`: Your local listener IP (used by `revshell`).
    *   `$profile.lport`: Your local listener port (used by `revshell`).
    *   `$report.path`: The absolute path to the data directory of the loaded report (e.g., `/path/to/pwnity/data/reports/project-x`).
*   `$report.name`: The name of the currently loaded report.

#### Function-based Placeholders
You can chain placeholders with functions to manipulate data on the fly.
*   **Syntax:** `function(placeholder)` or `function "value with $placeholder"`
*   **Examples:**
    *   `b64encode($target.name)`: Base64-encodes the target's name.
    *   `print urlencode "some text with spaces"`: URL-encodes a static string.
    *   `b64encode(urlencode($target.name))`: Nested functions are resolved from the inside out.

Use the `placeholders functions` command to see a list of all available functions.

Use the `placeholders <entity>` command to see all available placeholders for the loaded objects.

### Proxy Integration & Sudo

`pwnity` allows you to route tool execution through a proxy. These settings are **session-specific**, allowing you to work on different projects with different network configurations without conflict.

1.  **Enable the proxy for the current session:**
    ```
    (default)> proxy on
    ```
    The prompt will now show a green `㉿` separator.

2.  **Configure the proxy (optional, overrides `config.json`):**
    ```
    (default)> proxy set type socks5
    (default)> proxy set host 127.0.0.1
    (default)> proxy set port 9050
    ```

3.  **Sudo-Handling:**
    Some tools, or the proxy wrapper itself (`proxychains-ng`), require root privileges. `pwnity` handles this automatically.
    *   To mark a tool to always run with `sudo`, use:
        `tool update <tool_name> sudo true`
    *   If the proxy wrapper needs `sudo` (default for `proxychains`), it will be applied automatically when the proxy is on.
    *   If `sudo` is required, you will be prompted for your password interactively. This works for both foreground (`now`) and background (`bg`) jobs.

## Command Reference

The following list provides an overview of the most important commands. Use `<command> -h` in the shell for detailed information.

### target
Manages targets.
*   `target add <name>`: Creates a new target.
*   `target update <name> url <url>`: Sets the URL and automatically parses hostname, IP, port, etc.
*   `target update <name> <field> <value>`: Sets any other field on the target object.
*   `target gather <name> <type>`: Gathers info. `<type>` can be `dns`, `mx`, `whois`, `http`, or `all`.
*   `target fork-domain <name>`: Creates a new target from the main domain of a subdomain target.
*   `target load <name>`: Loads the target into the session.
*   `target list`: Lists all available targets.
*   `target show <name>`: Displays all collected information for a target.
*   `target rename <old> <new>`: Renames a target.
*   `target delete <name> [field]`: Deletes a field or the entire target object (but not the file).
*   `target destroy <name>`: Deletes the target and its file permanently.
*   `target export <name>`: Outputs the commands to reconstruct the target and its gathered data.

### tool
Manages tool configurations.
*   `tool add <name>`: Creates a new tool, attempting to find its path automatically.
*   `tool update <name> path </path/to/tool>`: Manually sets the path to the executable.
*   `tool update <name> sudo <true|false>`: Marks if the tool requires root privileges.
*   `tool update <name> command <cmd_name>`: Adds a new subcommand to the tool.
*   `tool update <name> <cmd_name> param "<param>"`: Adds a parameter to a command. Use quotes for parameters with spaces.
*   `tool reorder <name> <cmd_name> <old> <new>`: Changes the position of a parameter.
*   `tool delete <name> <args...>`: Deletes a field, a command, or a parameter. Use `tool delete -h` for syntax.
*   `tool load <name>`: Loads the tool into the session.
*   `tool list`: Lists all tools.
*   `tool show <name>`: Displays the tool's configuration.
*   `tool rename <old> <new>`: Renames a tool.
*   `tool destroy <name>`: Deletes the tool and its file permanently.
*   `tool export <name>`: Outputs the commands to reconstruct the tool.

### wordlist
Manages wordlist references.
*   `wordlist add <name>`: Creates a new wordlist.
*   `wordlist update <name> path </path/to/list.txt>`: Sets the file path.
*   `wordlist load <name>`: Loads the wordlist into the session.
*   `wordlist list`: Lists all wordlists.
*   `wordlist show <name>`: Displays wordlist details.
*   `wordlist export <name>`: Outputs the commands to reconstruct the wordlist.

### library
Manages your personal reference library.
*   `library add <name>`: Creates a new library entry.
*   `library update <name> <field> <value>`: Sets the URL, comment, or category.
*   `library check <name|all>`: Manually checks the status of a URL.
*   `library open <name>`: Opens the entry's URL in a browser.
*   `library list`: Lists all entries, grouped by category.
*   `library show <name>`: Displays details for an entry.
*   `library rename <old> <new>`: Renames an entry.
*   `library destroy <name>`: Deletes an entry permanently.
*   `library export <name>`: Outputs the commands to reconstruct the entry.

### session
Manages workspaces.
*   `session new <name>`: Creates a new, empty session and switches to it.
*   `session switch <name>`: Switches to an existing session.
*   `session list`: Shows all sessions.
*   `session show`: Shows the content of the current session.
*   `session destroy <name>`: Deletes a session.
*   `session export`: Outputs the `load` commands to restore the current session.

### preset
Manages saved session configurations.
*   `preset save <name>`: Saves the current session (target, tool, wordlist, proxy settings) as a preset.
*   `preset load <name>`: Loads a preset, creating and switching to a new session with its contents.
*   `preset list`: Lists all presets.
*   `preset show <name>`: Displays the configuration of a preset.
*   `preset destroy <name>`: Deletes a preset.
*   `preset export <name>`: Outputs the commands stored in the preset.

### logbook
Manages the immutable logs of previous command executions.
*   `logbook list`: Shows a list of the most recent execution logs.
*   `logbook show <id>`: Displays the full, raw output for a specific log entry.

### parser
Manages and applies regex-based parsers to extract information.
*   `parser list`: Lists all available parsers.
*   `parser show <name>`: Displays the regex rules for a specific parser.
*   `parser apply <parser> <logbook_id>`: Parses a logbook entry and adds all findings to the currently loaded report.
*   `parser destroy <name>`: Deletes a custom parser file.

### report
Manages reports, the central containers for all collected data.
*   `report add <name>`: Creates a new, empty report.
*   `report load <name>`: Loads a report into the session. All subsequent notes, loot, and findings will be saved here.
*   `report unload`: Unloads the current report from the session.
*   `report show [name]`: Shows the contents of the specified report, or the loaded one if no name is given.
*   `report list`: Lists all available reports.
*   `report destroy <name>`: Deletes a report and its file.
*   `report export <name>`: Outputs the commands to reconstruct the report.
*   `report render <name> [filename]`: Saves a human-readable summary of the report to a file (default: `exports/reports/<name>.md`).

### proxy
Manages proxy settings for the current session.
*   `proxy on` / `off`: Enables or disables the proxy wrapper.
*   `proxy set <key> <value>`: Configures a proxy setting (e.g., `host`, `port`, `type`).
*   `proxy reset [key|all]`: Resets a session-specific setting to its global default.
*   `proxy show`: Displays the current proxy status and configuration.

### pwn / run
Builds and executes the command of the loaded tool.
*   `pwn <command> [extra_params...]`: Shows a preview of the command to be executed.
*   `pwn <command> [extra_params...] now`: Executes the command in the foreground.
*   `pwn <command> [extra_params...] bg`: Executes the command in the background.

### jobs
Manages background jobs.
*   `jobs list`: Shows all running and finished jobs.
*   `jobs show <id>`: Displays the output of a specific job.
*   `jobs kill <id>`: Terminates a running job.
*   `jobs clear`: Removes all finished jobs from the list.

### heartbeat
Monitors a target's health and responsiveness.
*   `heartbeat start [delaymin <sec>] [delaymax <sec>] [timelimit <sec>]`: Starts monitoring the loaded target.
*   `heartbeat show <target_name>`: Displays a live dashboard of the monitoring data.
*   `heartbeat stop [target_name]`: Stops the monitoring process for the specified or loaded target.
*   `heartbeat list`: Lists all running and saved heartbeats.
*   `heartbeat destroy <target_name>`: Deletes the saved data for a heartbeat.

### revshell
Generates reverse shell payloads.
*   `revshell <language> [ip] [port]`: Generates a copy-pasteable payload string. Defaults to using `$profile.lhost` and `$profile.lport`.

### note & loot
Manage findings for the loaded **report**.
*   `note add <text...>`: Adds a timestamped note to the loaded report.
*   `note list`: Shows all notes in the loaded report.
*   `note delete <index>`: Deletes a note from the loaded report.
*   `loot add <type> <value...>`: Adds a loot item. The available types are defined in `etc/config.json` and support autocompletion.
*   `loot list`: Shows all loot items in the loaded report.
*   `loot delete <index>`: Deletes a loot item from the loaded report.

### overview
*   `overview`: Shows a detailed dashboard view of the current session, including resolved placeholders.
*   `overview --short`: Shows a compact summary.

### identify
*   `identify <hash_string>`: Analyzes a string to determine its possible hash type (e.g., MD5, SHA1).
    *   Example: `identify 5f4dcc3b5aa765d61d8327deb882cf99`
    *   Example: `identify $loot.0.value`

### config
*   `config list`: Displays the entire application configuration.
*   `config get <SECTION.KEY>`: Shows the value of a specific configuration key.
*   `config set <SECTION.KEY> <value>`: Sets a new value for a configuration key.
    *   Example: `config set PROXY.HOST 127.0.0.1`

### print
*   `print <text...>`: Resolves placeholders and functions in a string and prints the result. Useful for testing and transforming values.
    *   Example: `print b64encode($target.name)` or `print b64encode "some text"`

### placeholders
Inspect available placeholders.
*   `placeholders all`: Show all available placeholders from all loaded objects.
*   `placeholders <entity>`: Show placeholders for a specific entity (`target`, `tool`, `wordlist`, `profile`, `proxy`, `report`, etc.).
*   `placeholders functions`: Show available placeholder functions (e.g., `b64encode`).

### profile
Manage global key-value settings.
*   `profile show`: Shows all configured values.
*   `profile update <key> <value...>`: Sets a global value (e.g., `user_agent`, `cookie`).
*   `profile delete <key>`: Deletes a setting.

## License

This project is licensed under the MIT License. See the `LICENSE` file for more information.