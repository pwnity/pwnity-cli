> Summary: Define command templates that are dynamically filled with data from your current session.

[bold]The Placeholder System[/bold]

Placeholders are the core of `pwnity`'s flexibility. They allow you to define command templates that are dynamically filled with data from your current session at runtime.

[bold]Syntax[/bold]
`$entity.path.to.value`

[bold]Entities[/bold]
The available entities are:
[green]  •[/green] `target`: The currently loaded target.
[green]  •[/green] `tool`: The currently loaded tool.
[green]  •[/green] `wordlist`: The currently loaded wordlist.
[green]  •[/green] `profile`: Global key-value pairs you define.
[green]  •[/green] `proxy`: The current effective proxy configuration.

[bold]Path Navigation[/bold]
You can access nested data using dot notation.
[dim]Example:[/dim]
If a target has been updated with `target update my-server url "https://api.example.com/v1?user=test"`, you can access:
[green]  •[/green] `$target.ip` -> (the resolved IP of api.example.com)
[green]  •[/green] `$target.port` -> `443`
[green]  •[/green] `$target.query_values.user.0` -> `test`

[bold]Inspecting Placeholders[/bold]
Use the `placeholders` command to see all available placeholders and their current resolved values for the loaded entities.
[dim]Example:[/dim]
[green]  placeholders target[/green]
[green]  placeholders all[/green]