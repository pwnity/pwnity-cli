# **Pwnity – Command Automation for Pentesters**  
**Stop typing. Start pwning.**

Pwnity is a flexible, session-based tool designed for pentesters, bug bounty hunters, and CTF players. It automates repetitive CLI tasks: define your targets, tools, and wordlists once, and Pwnity handles the execution. Keep your workspace clean, focus on the hunt, and leave the command chaos behind.




## Table of Contents

- Features
- Prerequisites
- Installation
- Quick Start
- Configuration
- Core Concepts
- The Web UI
- Command Reference
- License


## Features

### Modular by Design
- Manage **Targets**, **Tools**, **Wordlists** and **Reports** as reusable JSON objects.
- Build clean, repeatable workflows without rewriting commands.

### Smart CLI Automation
- Use **dynamic placeholders** like `$target.ip`, `$target.url.host`, `$wordlist.path` etc., resolved at runtime.
- Automatic URL parsing: hostname, IP, port, protocol, path, query parameters — all available as variables.
- Create **presets** to store complete setups for recurring tasks or scans.

### Session-Based Workflow
- Keep your workspace organized with isolated sessions.
- Switch between projects instantly without losing context.

### Built‑in Recon & Intelligence
- `target gather`: DNS, WHOIS, HTTP metadata, service detection and more.
- Centralized reporting: collect findings across tools and sessions.
- **Notes & loot system**: attach comments, credentials, artifacts or links directly to your report entries.

### Seamless Tool Execution
- Per-session **proxy support** (e.g., proxychains-ng).
- **sudo handling** with smart prompts.
- **Background jobs** for long-running scans.
- Full interactive shell with autocompletion & rich terminal output.

### Bring Your Own Tools
- Run **any script or binary** directly through Pwnity.  
- Full paths or simple executable names — Pwnity automatically detects and integrates them.


### Reference Library
- Store useful links, snippets, cheat sheets or external resources.
- Automatic health/status checking for all entries.

### Import & Export
- Convert your Pwnlabs objects back into raw commands for portability.
- Export or sync your JSON objects with any backup tool — no database, no dumps, no pain.

### Optional Web UI
- A powerful WebUI is in active development — stay tuned.



## Prerequisites

Before installing Pwnity, make sure your system meets the following requirements:

- **Python 3.x**  
- **pip** for installing Python packages  
- Any external tools you plan to use (e.g., `nmap`, `gobuster`, `whatweb`).  
  You can provide either the full path to the binary or just the executable name.  
  If no full path is given, Pwnity will automatically search for the tool in your system’s `PATH`.

## Installation

Getting started with Pwnity is straightforward.  
Clone the repository, create your virtual environment, install the dependencies — done.

```bash
git clone git@github.com:pwnity/pwnity-cli.git
cd pwnity-cli

# Create and activate a virtual environment
python -m venv venv
source venv/bin/activate

# Install required packages
pip install -r requirements.txt

# Make the CLI executable
chmod +x pwnity

# Start Pwnity
./pwnity
```



## Quickstart Guide

Pwnity ships with example configurations to help you get started quickly.  
Just add a target, load your tools, and launch your first scan:

1. **Start the interactive shell**
    ```bash
    python3 pwnity.py
    ```

2. **Add your target**
    ```bash
    target add example.com
    target update example.com url https://www.example.com
    ```

3. **Load your target and tool**
    ```bash
    target load example.com
    tool load nmap
    ```

4. **Run your scan**
    ```bash
    pwn quick now
    ```

That's it — you’ve executed your first workflow with Pwnity.

## Configuration

Pwnity’s configuration is stored in `etc/config.json`.  
Below is a description of all configuration sections and their parameters.

---

### GLOBAL
General application settings.

- **DEBUG_LEVEL**  
  Log verbosity level.

- **HISTORY_FILE**  
  Path to the shell history file.

- **ALIASES_FILE**  
  Path to the aliases definition file.

- **LOOT_TYPES**  
  List of allowed loot categories.

---

### LIBRARY
Settings for the reference library.

- **CATEGORIES**  
  Comma‑separated list of library categories.

- **URL_CHECK_REFRESH_DAYS**  
  Number of days before a library URL is revalidated.

---

### DIRS
Directory structure for all stored objects.

- **PRESETS** — Directory for presets  
- **TARGETS** — Directory for target objects  
- **WORDLISTS** — Directory for wordlists  
- **TOOLS** — Directory for tool definitions  
- **LIBRARY** — Directory for library entries  
- **LOGBOOK** — Directory for logbook entries  
- **REPORTS** — Directory for reports  
- **WORKFLOWS** — Directory for workflow definitions  
- **PARSERS** — Directory for parser definitions  
- **HEARTBEATS** — Directory for heartbeat logs  
- **REVSHELLS** — Path to the reverse shell template file  
- **EXPORTS** — Directory for exported objects  
- **MANUALS** — Directory for manuals  
- **PROFILE_FILE** — Path to the user profile file  

---

### HEARTBEAT
Controls the timing for job noise and stability checks.

- **MIN_DELAY_SECONDS**  
  Minimum interval between heartbeat checks.

- **MAX_DELAY_SECONDS**  
  Maximum interval between heartbeat checks.

---

### PROXY
Default proxy wrapper configuration.

- **ENABLED**  
  Enables or disables proxy usage.

- **TYPE**  
  Proxy type (e.g., `socks5`).

- **HOST**  
  Proxy host.

- **PORT**  
  Proxy port.

- **USERNAME**  
  Proxy username.

- **PASSWORD**  
  Proxy password.

- **WRAPPER_COMMAND**  
  The proxy wrapper binary (e.g., `proxychains`).

- **WRAPPER_OPTIONS**  
  Additional options passed to the wrapper.

- **WRAPPER_NEEDS_SUDO**  
  Whether the wrapper requires `sudo`.

---

### COLORS
ANSI color definitions used in the CLI.

Each entry defines a foreground or background color code.


# Core Concept Summary

At its core, **pwnity** is a flexible, session-based CLI framework designed to structure, automate, and accelerate the penetration testing workflow.  
It does **not replace tools** like Nmap or Gobuster — it intelligently orchestrates them.

## The Core Idea

pwnity centralizes everything that is typically scattered across multiple terminal windows, text files, and browser tabs into a single, consistent system:

- Targets  
- Tools  
- Wordlists  
- Reports  
- Automation  
- Parsing  
- Workflows  

Everything is contained within a well-defined working context: **the Session**.

## Sessions: Your Workspace

A session stores what is currently active:

- **Target** – the entity under assessment (IP, domain, URL, metadata)  
- **Tool** – the defined template for a CLI program  
- **Wordlist** – e.g., for fuzzing or brute-forcing  
- **Report** – central storage for all your findings  
- **Proxy configuration** – optionally active  

The prompt always reflects the current session state.  
You can switch seamlessly between sessions or projects without losing context.

## Dynamic Command Generation

The core of pwnity:

Commands contain **placeholders** such as:

´´´
$target.ip
$target.url.hostname
$wordlist.path
$profile.lhost
[...] (You define your placeholders :))
´´´

When executed, pwnity dynamically replaces them with real values from your current session and constructs the complete command automatically.  

Define once — reuse reliably — every command runs correctly without copy-paste.

## Centralized Data Collection & Analysis

Everything you do during an engagement is automatically stored in one place.

### Logbook
Each execution is immutably recorded:

- Timestamp  
- Final command  
- Full command output  

### Parsers
Parsers (regex rules) can be applied to logbook entries to automatically extract structured findings:

- IP addresses  
- Domains  
- URLs  
- Credentials  
- Flags  
- Error patterns  
- Custom data structures  

### Reports
All notes, loot, and automatically extracted data are stored in the active report — organized per target but centrally accessible.



# The Web UI

The Web UI is an actively developed, premium extension designed to provide a graphical management layer for all pwnity features.  
It introduces several UI‑exclusive capabilities that go beyond what the CLI offers, while still relying on the CLI as its underlying execution engine.

## Key Features

### Workflow Editor
A node-based visual workflow builder that allows users to design complex, multi-step attack chains.  
Each node represents a tool, parser, or action, and the data flow between them mirrors how commands are executed step by step.

### Graphical Regex Builder
A powerful interactive interface for crafting and testing regex-based parsers.  
This makes it significantly easier to build reliable extraction rules for command output without trial-and-error in the terminal.

### Full CLI Integration
The Web UI does not replace the CLI — it orchestrates it.  
Almost every action performed in the UI is translated directly into CLI operations behind the scenes.  
This ensures:

- Full compatibility  
- Transparent execution  
- Reproducible results  

You can also trigger CLI commands directly from within the Web UI, making it a seamless hybrid environment.

---

The Web UI is evolving rapidly and will continue to expand with new visualization tools, workflow features, and automation capabilities.  
Stay tuned!


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

This project is licensed under Apache-2.0. See the `LICENSE` file for more information.