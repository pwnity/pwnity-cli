> Summary: A common step-by-step workflow for using pwnity, from target creation to documenting findings.

[bold]Typical Workflow[/bold]

Here is a common step-by-step workflow for using `pwnity`.

[cyan]1. Create and Configure a Target[/cyan]
First, create a target and give it a URL. `pwnity` will automatically parse it.
[dim]Example:[/dim]
[green]  target add web-server[/green]
[green]  target update web-server url http://192.168.1.10/login[/green]

[cyan]2. Create and Configure a Tool[/cyan]
Next, set up the tool you want to use. Define its subcommands and parameters using placeholders.
[dim]Example for `gobuster`:[/dim]
[green]  tool add gobuster[/green]
[green]  tool update gobuster command dir[/green]
[green]  tool update gobuster dir param "-u $target.base_url -w $wordlist.path"[/green]

[cyan]3. Add a Wordlist[/cyan]
If your tool needs a wordlist, add a reference to it.
[dim]Example:[/dim]
[green]  wordlist add common-dirs[/green]
[green]  wordlist update common-dirs path /usr/share/wordlists/dirb/common.txt[/green]

[cyan]4. Create and Load a Report[/cyan]
Before you can save notes or loot, you need a report to store them in.
[dim]Example:[/dim]
[green]  report add web-server-report[/green]
[green]  report load web-server-report[/green]

[cyan]5. Load Everything into the Session[/cyan]
Load your created objects into the current session. The prompt will update to show the context.
[dim]Example:[/dim]
[green]  target load web-server[/green]
[green]  tool load gobuster[/green]
[green]  wordlist load common-dirs[/green]

[cyan]6. Run the Scan[/cyan]
Preview the command, then execute it in the foreground (`now`) or background (`bg`).
[dim]Example:[/dim]
[green]  pwn dir[/green]        (Preview the command)
[green]  pwn dir now[/green]      (Run it now)

[cyan]7. Document Findings[/cyan]
As you find things, add them to the loaded report.
[dim]Example:[/dim]
[green]  note add Found admin panel at /admin-portal[/green]
[green]  loot add credential admin:password123[/green]