> Summary: Manage targets, the central objects for an engagement that hold all discovered information.

[bold]Managing Targets[/bold]
 
A Target is the central object for an engagement. It holds all the [underline]technical information[/underline] you discover about a specific asset (like an IP address or domain).
 
[dim]Note:[/dim] Analytical findings like your personal notes and discovered loot (credentials, flags) are stored in a separate `report` object, not in the target itself.

[bold]The Power of the `url` Field[/bold]
The most important command is `target update <name> url <url>`. When you provide a URL, `pwnity` automatically parses it and populates numerous fields for you:
[green]  •[/green] `ip`: Resolves the hostname to an IP address.
[green]  •[/green] `hostname`, `port`, `protocol`, `uri`: Basic URL components.
[green]  •[/green] `domain`, `tld`, `subdomains`: Detailed domain information.
[green]  •[/green] `query_params`, `query_values`: Parsed query string parameters.

This means you only need to set the URL, and dozens of useful placeholders become available instantly.

[bold]Active Information Gathering[/bold]
Beyond parsing, you can actively gather information with the `gather` command.
[dim]Example:[/dim]
[green]  target gather my-server dns[/green]   (Gets A, AAAA, CNAME, MX, NS, TXT records)
[green]  target gather my-server whois[/green]  (Performs a WHOIS lookup on the main domain)
[green]  target gather my-server http[/green]   (Retrieves HTTP headers and the SSL certificate)
[green]  target gather my-server geo[/green]    (Retrieves Geo-IP information for the target's IP)
[green]  target gather my-server all[/green]    (Does all of the above)