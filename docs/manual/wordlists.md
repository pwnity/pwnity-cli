> Summary: Manage named references to wordlist files for use in tool commands.

[bold]Managing Wordlists[/bold]

In pwnity, a wordlist is not the content of the list itself, but rather a named reference (or pointer) to a wordlist file on your system. This approach allows you to manage large lists efficiently without duplicating data.

The primary purpose is to make the file path available through the `$wordlist.path` placeholder, which can then be used in your tool configurations.

[bold]Core Concepts[/bold]
[green]  •[/green] [bold]Wordlist Object:[/bold] A simple JSON object with a `name` and a `path`.
[green]  •[/green] [bold]Session Loading:[/bold] Loading a wordlist into a session makes its path available to any tool run within that session.

[bold]Common Workflow[/bold]

[cyan]1. Create a Wordlist Reference[/cyan]
First, create a named entry for the wordlist you want to use.
[dim]Example:[/dim]
[green]  wordlist add common-directories[/green]

[cyan]2. Set the File Path[/cyan]
Next, tell `pwnity` where the actual file is located.
[dim]Example:[/dim]
[green]  wordlist update common-directories path /usr/share/wordlists/dirbuster/directory-list-2.3-medium.txt[/green]

[cyan]3. Use it in a Tool[/cyan]
Configure a tool (like `gobuster`) to use the `$wordlist.path` placeholder.
[dim]Example:[/dim]
[green]  tool update gobuster dir param "-w $wordlist.path"[/green]

[cyan]4. Load and Run[/cyan]
Load the wordlist into your session before running the tool.
[dim]Example:[/dim]
[green]  wordlist load common-directories[/green]
[green]  pwn dir now[/green]
[dim]  # pwnity resolves $wordlist.path to the full file path when executing the command.[/dim]

[bold]All Commands[/bold]
[dim]Commands:[/dim]
[green]  •[/green] `wordlist add <name>`: Creates a new, empty wordlist reference.
[green]  •[/green] `wordlist list`: Lists all available wordlists.
[green]  •[/green] `wordlist show <name>`: Displays the details (like the path) of a wordlist.
[green]  •[/green] `wordlist update <name> path <value>`: Sets the file path for the wordlist.
[green]  •[/green] `wordlist load <name>`: Loads the wordlist into the current session.
[green]  •[/green] `wordlist unload`: Unloads the wordlist from the current session.
[green]  •[/green] `wordlist rename <old_name> <new_name>`: Renames a wordlist reference.
[green]  •[/green] `wordlist destroy <name>`: Deletes a wordlist reference.
[green]  •[/green] `wordlist export <name>`: Generates the commands to recreate the wordlist reference.