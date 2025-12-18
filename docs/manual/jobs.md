> Summary: Run long-running scans in the background and manage them with the 'jobs' command.

[bold]Background Jobs[/bold]

Long-running scans or commands can be executed in the background, allowing you to continue using the `pwnity` shell without interruption.

[bold]Starting a Background Job[/bold]
To start a command as a background job, simply append `bg` to your `pwn` command instead of `now`.

[dim]Example:[/dim]
[green]  pwn full-scan bg[/green]

`pwnity` will immediately return the prompt to you, and the job will run in the background.

[bold]Managing Jobs[/bold]
You can manage your background jobs with the `jobs` command:
[green]  •[/green] `jobs list`: Shows a table of all running and finished jobs with their ID, status, and duration.
[green]  •[/green] `jobs show <id>`: Displays the complete output of a specific job.
[green]  •[/green] `jobs kill <id>`: Terminates a job that is currently running.
[green]  •[/green] `jobs clear`: Removes all finished, failed, or killed jobs from the list to keep it clean.

[bold]Completion Notifications[/bold]
When a background job finishes, fails, or is killed, a summary panel will automatically be displayed in the console, informing you of the outcome. This ensures you never miss when a long task is complete.