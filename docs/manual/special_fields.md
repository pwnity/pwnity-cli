> Summary: Learn about special fields like 'target.url' that trigger automatic actions and data parsing.

[bold]Special Fields & Magic Actions[/bold]

Certain fields, when used with the `update` command, trigger special actions or have unique behaviors beyond simply storing a value.

[cyan]▶ Target: The `url` Field[/cyan]
This is the most powerful special field. When you update a target's `url`, `pwnity` doesn't just store the string; it performs a comprehensive analysis:
[green]  •[/green] [bold]Resolution:[/bold] It resolves the hostname to an IP address.
[green]  •[/green] [bold]Parsing:[/bold] It breaks the URL into its components: `protocol`, `hostname`, `port`, `uri`, `query_params`, etc.
[green]  •[/green] [bold]Domain Analysis:[/bold] It uses `tldextract` to identify the `subdomains`, `domain`, and `tld`.
[green]  •[/green] [bold]Base URL:[/bold] It constructs a `base_url` (e.g., `https://example.com:8443`) for convenience.

[dim]Example:[/dim]
[green]  target update my-server url "https://api.example.com/v1?user=test"[/green]
This single command populates over a dozen fields, making a vast number of placeholders instantly available.

[cyan]▶ Tool: The `sudo` Field[/cyan]
Setting the `sudo` field to `true` marks a tool as requiring root privileges.
[dim]Example:[/dim]
[green]  tool update nmap sudo true[/green]
When you run this tool, `pwnity` will automatically prepend `sudo` to the command and handle the password prompt if necessary.

[cyan]▶ Proxy: The `wrapper_needs_sudo` Field[/cyan]
This is similar to the tool's `sudo` field but applies specifically to the proxy wrapper command (like `proxychains-ng`).
[dim]Example:[/dim]
[green]  proxy set wrapper_needs_sudo true[/green]
If the proxy is enabled and this flag is set, the entire command (including the wrapper) will be executed with `sudo`.

[cyan]▶ Tool: The `execute_per_param` Field[/cyan]
This boolean field, set on a tool's command, changes how the final command is built and run. By default (`false`), all parameters are joined into a single command line.

[dim]Value: `true`[/dim]
If you set `execute_per_param` to `true`, `pwnity` will execute the tool's command [underline]once for each parameter[/underline] in the list. This is perfect for creating dynamic checklists with `echo`.

[dim]Example:[/dim]
[green]  tool update checklist web-recon execute_per_param true[/green]
Now, when `pwn web-recon now` is run, it will execute `echo` for each line of the checklist, producing a clean, multi-line output.
