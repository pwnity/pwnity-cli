> Summary: Create and manage custom shortcuts for longer pwnity commands.

[bold]Using Aliases[/bold]

Aliases are custom shortcuts for longer `pwnity` commands. They are useful for frequently used command sequences.

[bold]Creating an Alias[/bold]
You can create an alias using the `alias create` command. The value of the alias must be enclosed in single or double quotes.

[dim]Example:[/dim]
[green]  alias create nmap-full 'pwn full-scan now'[/green]
[green]  alias create show-target 'target show $target.name'[/green]

Now, you can simply type `nmap-full` to execute the full nmap scan.

[bold]Managing Aliases[/bold]
[green]  •[/green] `alias list`: Shows all currently defined aliases.
[green]  •[/green] `alias delete <name>`: Deletes a specific alias.

[bold]Automatic Saving[/bold]
Aliases are automatically saved to the file specified in `etc/config.ini` (by default, `etc/aliases.txt`) whenever you create, update, or delete one. They are loaded automatically when `pwnity` starts.