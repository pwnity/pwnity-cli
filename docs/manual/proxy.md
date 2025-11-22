> Summary: Route tool commands through a proxy using either a wrapper command or tool-specific placeholders.

[bold]Proxy Integration[/bold]

`pwnity` can route tool commands through a proxy. There are two main methods to achieve this. Proxy settings are [underline]session-specific[/underline], meaning you can have different proxy configurations for different projects.

[bold]Method 1: Wrapper Command (e.g., `proxychains-ng`)[/bold]
This method forces [underline]all[/underline] network traffic from a tool through the proxy. When the proxy is enabled, `pwnity` prepends a "wrapper command" (defined in `etc/config.ini`) to your tool command. The default is `proxychains-ng`.

[bold]Method 2: Placeholders for Tool-Specific Flags[/bold]
Many tools (like `curl`, `sqlmap`, `ffuf`) have their own flags to specify a proxy (e.g., `--proxy`). This is the most flexible method. You can use `$proxy` placeholders in your tool definition.

[dim]Example: Configuring `ffuf` to use the proxy[/dim]
[green]  tool update ffuf fuzz param "--proxy $proxy.type://$proxy.username:$proxy.password@$proxy.host:$proxy.port"[/green]

When you run `ffuf`, `pwnity` will substitute the placeholders with the currently active proxy settings.
[dim]Note:[/dim] If `username` or `password` are not set, they will be replaced with an empty string. Most tools handle URLs like `http://:@host:port` correctly, but some may not.

[bold]Enabling and Disabling the Proxy[/bold]
[green]  •[/green] `proxy on`: Enables the proxy for the current session.
[green]  •[/green] `proxy off`: Disables the proxy for the current session.

[underline]When the proxy is on, the `㉿` symbol in your prompt will turn green.[/underline]

[bold]Configuration[/bold]
You can set global defaults in `etc/config.ini`. To override these for the current session, use the `proxy set` command.

[dim]Example: Setting up a Burp Suite proxy[/dim]
[green]  proxy set host 127.0.0.1[/green]
[green]  proxy set port 8080[/green]
[green]  proxy on[/green]

After this, you can use Method 1 (if `proxychains-ng` is configured for Burp) or Method 2 with placeholders like `$proxy.host`.

[bold]Resetting Configuration[/bold]
To revert a session-specific setting back to the global default, use `proxy reset`.
[dim]Example:[/dim]
[green]  proxy reset host[/green]
[green]  proxy reset all[/green]

[bold]Sudo and Proxy Wrappers[/bold]
If your wrapper command (Method 1) needs root privileges, set `wrapper_needs_sudo` to `true`. `pwnity` will handle the `sudo` prompt automatically.
[dim]Example:[/dim]
[green]  proxy set wrapper_needs_sudo true[/green]