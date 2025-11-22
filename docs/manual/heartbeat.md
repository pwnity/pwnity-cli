> Summary: Monitor a target's health and responsiveness over time.

[bold]Monitoring with Heartbeat[/bold]

The `heartbeat` command is a powerful monitoring utility that continuously checks a target's "vital signs". It runs in the background, collecting data on latency, HTTP status codes, and content changes.

[bold]Use Cases[/bold]
[green]  •[/green] [bold]Establish a Baseline:[/bold] Run a heartbeat before a scan to understand the target's normal performance.
[green]  •[/green] [bold]Detect Impact:[/bold] Observe the heartbeat while running an aggressive scan to see if you are degrading the server's performance or triggering a WAF.
[green]  •[/green] [bold]Identify Dynamic Content:[/bold] See if the page content hash changes over time.
[green]  •[/green] [bold]Discover Load Balancing:[/bold] See if the resolved IP address changes between requests.

[bold]Core Commands[/bold]

[cyan]▶ Starting and Stopping[/cyan]
The heartbeat runs as a background thread within `pwnity` and automatically uses the currently loaded target.
[dim]Example:[/dim]
[green]  heartbeat start[/green]
[dim]  # Starts monitoring the loaded target with a default random delay.[/dim]
[green]  heartbeat start delaymin 1 delaymax 5 timelimit 300[/green]
[dim]  # Overrides defaults: uses a 1-5s delay and stops after 5 minutes.[/dim]
[green]  heartbeat stop [target_name][/green]
[dim]  # Stops the heartbeat for the specified or loaded target.[/dim]

[cyan]▶ Viewing Data[/cyan]
The `show` command provides a dashboard view. If the heartbeat is running, the dashboard will update live.
[dim]Example:[/dim]
[green]  heartbeat show my-webapp[/green]

[cyan]▶ Listing Heartbeats[/cyan]
You can see all running and previously saved heartbeats.
[dim]Example:[/dim]
[green]  heartbeat list[/green]