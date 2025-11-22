> Summary: Organize your work with sessions (workspaces) and presets (saved session templates).

[bold]Sessions & Presets[/bold]

`pwnity` uses Sessions and Presets to help you organize your work and automate repetitive setups.

[bold]Sessions: Your Workspace[/bold]
A Session is your current, live workspace. It "remembers" which `target`, `tool`, and `wordlist` you have loaded, as well as any session-specific `proxy` settings.

The prompt always shows you the name of the active session, e.g., `(project-x)`.

[dim]Commands:[/dim]
[green]  •[/green] `session new <name>`: Creates a new, empty session and switches to it.
[green]  •[/green] `session switch <name>`: Switches to an existing session, restoring its context.
[green]  •[/green] `session list`: Shows all available sessions.
[green]  •[/green] `session show`: Displays what is currently loaded in the active session.
[green]  •[/green] `session destroy <name>`: Deletes a session (but not the targets or tools themselves).

[bold]Presets: Your Templates[/bold]
A Preset is a [underline]saved session configuration[/underline]. It's a template for a common task.

[dim]Use Case:[/dim]
Imagine you always use `gobuster` with the `directory-list-2.3-medium.txt` wordlist to scan web servers. You can save this combination as a preset.

[dim]Commands:[/dim]
[green]  •[/green] `preset save <name>`: Saves the currently loaded items as a preset.
[green]  •[/green] `preset load <name>`: Loads a preset. This creates a new session with the same name as the preset and loads all the saved items into it.
[green]  •[/green] `preset list`: Shows all available presets.
[green]  •[/green] `preset show <name>`: Displays the configuration of a preset.

[dim]Example:[/dim]
[green]  tool load gobuster[/green]
[green]  wordlist load common-dirs[/green]
[green]  preset save gobuster-common[/green]

Later, in a new `pwnity` instance:
[green]  preset load gobuster-common[/green]
This will create a new session named `gobuster-common` and automatically load the `gobuster` tool and `common-dirs` wordlist.