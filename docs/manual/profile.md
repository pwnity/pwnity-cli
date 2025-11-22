> Summary: Use a global, persistent key-value store for data available across all sessions, like API keys or a User-Agent.

[bold]The Global Profile[/bold]

The Profile is a global, persistent key-value store for data that you want to be available across all your sessions and targets. It's perfect for information that doesn't belong to a specific target.

[bold]Use Cases[/bold]
[green]  •[/green] Storing a custom User-Agent string.
[green]  •[/green] Keeping a global session cookie for a web application.
[green]  •[/green] Storing API keys for services like Shodan or Hunter.io.
[green]  •[/green] Defining your name or handle for report templates.

[bold]Managing the Profile[/bold]
[dim]Commands:[/dim]
[green]  •[/green] `profile update <key> <value...>`: Adds or updates a setting.
[green]  •[/green] `profile show`: Displays all settings in the profile.
[green]  •[/green] `profile delete <key>`: Removes a setting.

[dim]Example:[/dim]
[green]  profile update user_agent "MyCustomPentestBrowser/1.0"[/green]
[green]  profile update cookie "session=a1b2c3d4e5f6; tracking=false"[/green]

[bold]Using Profile Placeholders[/bold]
You can access profile data in your tool commands using the `$profile` placeholder.

[dim]Example with `curl`:[/dim]
[green]  tool add curl[/green]
[green]  tool update curl command get[/green]
[green]  tool update curl get param "-H 'User-Agent: $profile.user_agent'"[/green]
[green]  tool update curl get param "-H 'Cookie: $profile.cookie'"[/green]
[green]  tool update curl get param "$target.url"[/green]