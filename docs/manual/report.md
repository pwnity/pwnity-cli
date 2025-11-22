> Summary: Manage reports, the central containers for all collected data like notes, loot, and parser findings.

[bold]Managing Reports[/bold]

A `report` is the central container for all your analytical findings for an engagement. It is designed to store everything you discover, keeping your notes, credentials, and automated parser results organized in one place.

[yellow]Important:[/yellow] You must create and load a report before you can use the `note`, `loot`, or `parser apply` commands.

[bold]What a Report Stores[/bold]
[green]  •[/green] [bold]Notes:[/bold] Your timestamped, free-form observations.
[green]  •[/green] [bold]Loot:[/bold] Structured findings like credentials, keys, and flags.
[green]  •[/green] [bold]Parser Findings:[/bold] Structured data extracted from tool output by the `parser` command.

[bold]Core Commands[/bold]

[cyan]▶ Creating and Loading[/cyan]
You start by creating a report for your project and then loading it into your session.
[dim]Example:[/dim]
[green]  report add my-project-report[/green]
[green]  report load my-project-report[/green]
[dim]  # The prompt will now show '[my-project-report]' to indicate it's loaded.[/dim]

[cyan]▶ Viewing a Report[/cyan]
You can view the contents of any report, or the currently loaded one.
[dim]Example:[/dim]
[green]  report show my-project-report[/green]
[green]  report show[/green] [dim]# Shows the currently loaded report[/dim]

[cyan]▶ Listing and Unloading[/cyan]
[dim]Example:[/dim]
[green]  report list[/green] [dim]# Shows all available reports[/dim]
[green]  report unload[/green] [dim]# Unloads the report from the current session[/dim]

[cyan]▶ Renaming and Deleting[/cyan]
[dim]Example:[/dim]
[green]  report rename my-project-report new-name[/green]
[green]  report destroy new-name[/green] [dim]# This permanently deletes the report file[/dim]

[cyan]▶ Exporting a Report[/cyan]
To back up, share, or version-control a report, use the `export` command. It generates a script of `pwnity` commands that can perfectly reconstruct the report, including all notes and loot.
[dim]Example:[/dim]
[green]  report export my-project-report[/green]
[dim]  # This will print the commands to the console. You can copy this output[/dim]
[dim]  # and save it to a file (e.g., 'my-backup.pwn') to be run with 'run_script'.[/dim]

[cyan]▶ Rendering a Report to a File[/cyan]
To create a clean, human-readable summary of a report for documentation or sharing, use the `render` command. It saves the output as a Markdown file.
[dim]Example:[/dim]
[green]  report render my-project-report[/green]
[dim]  # Saves a summary to 'exports/reports/my-project-report.md'[/dim]
[green]  report render my-project-report final_summary.md[/green]
[dim]  # Saves the summary to 'exports/reports/final_summary.md'[/dim]
