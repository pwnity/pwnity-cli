> Summary: Document findings using notes for general observations and loot for structured data like credentials or flags.

[bold]Documenting Findings: Notes & Loot[/bold]
 
A crucial part of any engagement is documenting your findings. `pwnity` provides two mechanisms for this, both of which are stored in the currently loaded `report`.
 
[yellow]Important:[/yellow] You must create and load a `report` before you can add notes or loot.

[bold]Notes: General Observations[/bold]
Notes are for general-purpose, timestamped observations. They are perfect for keeping a running log of your thoughts, actions, and discoveries.

[dim]Commands:[/dim]
[green]  •[/green] `note add <text...>`: Adds a new note.
[green]  •[/green] `note list`: Displays all notes for the current target.
[green]  •[/green] `note delete <index>`: Deletes a note by its number from the list.

[dim]Example:[/dim]
[green]  report load my-project-report[/green]
[green]  note add Found a potential XSS vulnerability on the login page.[/green]
[green]  note add The server seems to be running an outdated version of Apache.[/green]

[bold]Loot: Structured Findings[/bold]
Loot is for structured, high-value findings like credentials, API keys, or flags. Each loot item has a `type` and a `value`. The available types are defined as a comma-separated list in the `LOOT_TYPES` key under the `[GLOBAL]` section of your `etc/config.ini` file. This allows for consistent and easy data entry with autocompletion.

[dim]Commands:[/dim]
[green]  •[/green] `loot add <type> <value...>`: Adds a new loot item using one of the predefined types.
[green]  •[/green] `loot list`: Displays all loot for the current target.
[green]  •[/green] `loot delete <index>`: Deletes a loot item by its number from the list.

[dim]Example:[/dim]
[green]  report load my-project-report[/green]
[green]  loot add credential admin:password123[/green]
[green]  loot add key A_VERY_SECRET_API_KEY_XYZ[/green]
[green]  loot add flag THM{y0u_f0und_m3}[/green]

By storing notes and loot in a report, all your findings for an engagement are kept organized in one place.