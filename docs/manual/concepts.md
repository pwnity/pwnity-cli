> Summary: An explanation of the core ideas behind pwnity: Targets, Tools, Wordlists, and Sessions.

[bold]Core Concepts[/bold]

`pwnity` is built around a few core ideas. Understanding them is key to using the tool effectively.

[cyan]▶ Targets: The "What"[/cyan]
A Target represents the entity you are testing (e.g., an IP address, a domain, a web application). It acts as a container for all related information:
[green]  •[/green] Network details (IP, hostname, port)
[green]  •[/green] Automatically gathered data (DNS, WHOIS, HTTP Headers)

[cyan]▶ Tools: The "How"[/cyan]
A Tool is a template for an external command-line program you want to run (e.g., `nmap`, `gobuster`). You define how the tool is called, including its subcommands and parameters. The real power comes from using placeholders in the parameters.

[cyan]▶ Reports: The "Findings"[/cyan]
A Report is the central container for all your analytical findings for an engagement. It stores:
[green]  •[/green] Your personal notes.
[green]  •[/green] Discovered credentials or flags (Loot).
[green]  •[/green] Structured findings extracted by Parsers.

[cyan]▶ Wordlists: The "With What"[/cyan]
A Wordlist is a simple reference to a file on your system containing a list of words, typically used for fuzzing, directory busting, or password cracking.

[cyan]▶ Sessions: The "Workspace"[/cyan]
A Session is your current working context. It "remembers" which Target, Tool, and Wordlist you have loaded. This allows you to switch between different projects without re-configuring everything. The prompt always shows you what's loaded in the active session.

[cyan]▶ Presets: The "Shortcut"[/cyan]
A Preset is a saved session. If you often use the same combination of a tool and wordlist for a certain type of target, you can save it as a preset and load it with a single command.