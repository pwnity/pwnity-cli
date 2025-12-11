> Summary: Manage and apply regex-based parsers to extract structured information from tool output.

[bold]Using Parsers[/bold]

The `parser` command manages and applies regex-based parsers to extract structured information (called "findings") from unstructured text, such as the output of a tool. These findings are then saved to the currently loaded `report`.

[bold]Core Concepts[/bold]
[green]  •[/green] [bold]Parser:[/bold] A collection of rules stored in a JSON file (e.g., `data/parsers/common.json`).
[green]  •[/green] [bold]Rule:[/bold] A single regex pattern within a parser, identified by a name (e.g., `ipv4_address`).
[green]  •[/green] [bold]Logbook Entry:[/bold] The source of the text to be parsed. Every command run via `pwn ... now` or `pwn ... bg` creates a logbook entry with a unique ID.
[green]  •[/green] [bold]Finding:[/bold] A piece of information (a match) extracted by a rule, which is then stored in the loaded report.

[bold]Common Workflow[/bold]

[cyan]1. Run a tool and generate output[/cyan]
The output of every command is automatically saved to the logbook.
[dim]Example:[/dim]
[green]  pwn web-scan now[/green]
[dim]  # Let's assume this produced a Logbook Entry with ID 3a8f...[/dim]

[cyan]2. Apply a parser to the output[/cyan]
Use `parser apply` with the name of the parser and the ID of the logbook entry.
[dim]Example:[/dim]
[green]  report load my-project-report[/green]
[green]  parser apply common 3a8f[/green]

`pwnity` will then run all regex rules from the `common` parser against the output of log entry `3a8f...`.

[cyan]3. Review and Save Findings[/cyan]
If matches are found, you will be presented with an interactive checklist allowing you to select which findings to save to the currently loaded report.

[cyan]4. View the Report[/cyan]
The new findings will now appear in the "Parser Findings" section of your report.
[dim]Example:[/dim]
[green]  report show[/green]

[bold]Managing Parsers[/bold]
[dim]Commands:[/dim]
[green]  •[/green] `parser list`: Shows all available parsers.
[green]  •[/green] `parser show <name>`: Displays the rules for a specific parser.
[green]  •[/green] `parser add <name>`: Creates a new, empty parser file.
[green]  •[/green] `parser update <name> ...`: Adds or modifies rules and their regex patterns.
[green]  •[/green] `parser destroy <name>`: Deletes a parser file.

[bold]Defining a Custom Parser[/bold]

While `pwnity` comes with some common parsers, the real power lies in creating your own. Here’s how to create a simple parser to extract IP addresses.

[cyan]1. Create the Parser[/cyan]
This creates the JSON file in `data/parsers/`.
[dim]Example:[/dim]
[green]  parser add custom-ips[/green]

[cyan]2. Add a Rule[/cyan]
A parser is a collection of rules. Let's add one called `ipv4`.
[dim]Example:[/dim]
[green]  parser update custom-ips add-rule ipv4[/green]

[cyan]3. Define the Regex Pattern[/cyan]
Now, assign the regular expression that will find the data.
[dim]Example:[/dim]
[green]  parser update custom-ips ipv4 regex "\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"[/green]

[cyan]4. (Optional) Add Exclusion Patterns[/cyan]
You can add patterns to exclude certain matches. For example, to ignore the loopback address.
[dim]Example:[/dim]
[green]  parser update custom-ips ipv4 exclude "^127\.0\.0\.1$"[/green]

[cyan]5. View Your Parser[/cyan]
Use `parser show` to see the complete result.
[dim]Example:[/dim]
[green]  parser show custom-ips[/green]