> Summary: Generate pwnity commands to back up, share, or version-control your configurations.

[bold]Exporting Objects[/bold]

The `export` command (aliased as `reverse`) is a powerful feature for backing up, sharing, or version-controlling your configurations. It generates a series of `pwnity` commands that can be used to perfectly reconstruct an object.

[bold]Use Cases[/bold]
[green]  •[/green] [bold]Backup:[/bold] Save the output to a script file for easy restoration.
[green]  •[/green] [bold]Sharing:[/bold] Send the output to a teammate so they can quickly replicate your setup.
[green]  •[/green] [bold]Version Control:[/bold] Commit the exported scripts to a Git repository to track changes to your tools and targets over time.

[bold]How it Works[/bold]
The `export` command is context-aware and intelligent. For a `target`, it will prioritize using the `url` and `gather` commands to reconstruct derived data, rather than setting each field manually.

[dim]Available on:[/dim]
[green]  •[/green] `target` (exports technical data like IP, domain, etc.)
[green]  •[/green] `tool`
[green]  •[/green] `wordlist`
[green]  •[/green] `preset`
[green]  •[/green] `report`
[green]  •[/green] `session`

[dim]Example:[/dim]
[green]  target export my-server[/green]
[dim]  # The commands to recreate the target will be printed to the console.[/dim]
[dim]  # You can copy this output and save it to a file (e.g., 'my-backup.pwn').[/dim]
You can then run this script in a new `pwnity` instance to recreate the `my-server` target.
[green]  run_script my-backup.pwn[/green]