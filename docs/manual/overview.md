> Summary: Use the 'overview' command to display a comprehensive dashboard of your current session's state.

[bold]The Overview Command[/bold]

The `overview` command provides a comprehensive dashboard of your current session's state. It is one of the most useful commands for quickly understanding your current context.

[bold]What it Shows[/bold]
The overview displays several panels:
[green]  •[/green] [bold]Target:[/bold] Shows all data for the loaded target, with placeholders resolved to their current values.
[green]  •[/green] [bold]Report:[/bold] If a report is loaded, this shows its contents, including notes, loot, and other findings.
[green]  •[/green] [bold]Tool:[/bold] Displays the configuration of the loaded tool, with placeholders resolved.
[green]  •[/green] [bold]Wordlist:[/bold] Shows the path of the loaded wordlist.
[green]  •[/green] [bold]Profile:[/bold] Lists your global profile settings.
[green]  •[/green] [bold]Proxy:[/bold] Shows the current status and configuration of the proxy.
[green]  •[/green] [bold]Recent Activity:[/bold] A log of the most recent commands and messages.

This is the best way to see how your placeholders (`$target.ip`, etc.) will be resolved before you run a command.

[bold]Compact View[/bold]
For a less detailed, more compact summary, you can use the `--short` flag.

[dim]Example:[/dim]
[green]  overview --short[/green]

This is useful for getting a quick glance at what's loaded without filling the screen.