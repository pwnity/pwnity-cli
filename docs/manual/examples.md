> Summary: A cookbook of common command patterns for various tasks in pwnity.

[bold]Command Examples Cookbook[/bold]

This page provides a quick reference and "cookbook" of common command patterns for various tasks in `pwnity`.

[cyan]▶ Setting up a simple Web Target[/cyan]
[green]  target add my-webapp[/green]
[green]  target update my-webapp url https://example.com/login.php[/green]
[green]  target gather my-webapp http[/green]
[green]  target show my-webapp[/green]

[cyan]▶ Configuring a simple Tool (nmap)[/cyan]
[green]  tool add nmap[/green]
[green]  tool update nmap command quick[/green] [dim]# Add a command named 'quick'[/dim]
[green]  tool update nmap quick param "-sV"[/green] [dim]# Add parameters individually for more flexibility[/dim]
[green]  tool update nmap quick param "-T4"[/green]
[green]  tool update nmap quick param "$target.ip"[/green]
[green]  tool update nmap sudo true[/green]

[cyan]▶ Configuring a Tool with Placeholders (gobuster)[/cyan]
[green]  tool add gobuster[/green]
[green]  tool update gobuster command vhost[/green]
[green]  tool update gobuster vhost param "vhost"[/green]
[green]  tool update gobuster vhost param "-u $target.base_url"[/green]
[green]  tool update gobuster vhost param "-w $wordlist.path"[/green]
[green]  tool update gobuster vhost param "--append-domain -d $target.domain"[/green]

[cyan]▶ Running a Scan[/cyan]
[green]  target load my-webapp[/green]
[green]  tool load nmap[/green]
[green]  pwn quick[/green]         (Preview the command)
[green]  pwn quick now[/green]     (Run in foreground)
[green]  pwn quick bg[/green]      (Run in background)

[cyan]▶ Reordering Tool Parameters[/cyan]
[dim]  # The nmap 'quick' command now has params: 1="-sV", 2="-T4", 3="$target.ip"[/dim]
[dim]  # Let's move the IP address to the front.[/dim]
[green]  tool reorder nmap quick 3 1[/green]
[dim]  # The command will now be assembled as 'nmap $target.ip -sV -T4'[/dim]

[cyan]▶ Documenting Findings[/cyan]
[green]  report add my-webapp-report[/green]
[green]  report load my-webapp-report[/green]
[green]  note add "The login page seems to have a default password policy."[/green]
[green]  loot add credential admin:admin[/green]
[green]  loot add flag FLAG{...}[/green]

[cyan]▶ Using the Proxy with Placeholders[/cyan]
[green]  proxy set host 127.0.0.1[/green]
[green]  proxy set port 8080[/green]
[green]  proxy on[/green]
[green]  tool update ffuf fuzz param "--proxy http://$proxy.host:$proxy.port"[/green]

[cyan]▶ Backing up a Target[/cyan]
[green]  target export my-webapp[/green]

[cyan]▶ Using a Preset for Repetitive Tasks[/cyan]
[green]  tool load gobuster[/green]
[green]  wordlist load directory-list-2.3-medium[/green]
[green]  preset save gobuster-medium[/green]
[dim]  # Later, in a new shell...[/dim]
[green]  preset load gobuster-medium[/green]
[dim]  # This creates a new session with the tool and wordlist pre-loaded.[/dim]