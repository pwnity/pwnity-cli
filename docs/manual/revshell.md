> Summary: Generate reverse shell one-liners for various languages.

[bold]Generating Reverse Shells[/bold]

The `revshell` command is a powerful utility that generates reverse shell one-liners for various languages. It helps you quickly create payloads for command execution vulnerabilities.

[bold]How It Works[/bold]
The command generates a clean, copy-pasteable payload string that you can use on a remote target.

[bold]Default IP and Port[/bold]
The command uses the following logic to determine the listener IP and port:
1.  It uses the IP and port if you provide them directly (e.g., `revshell php 10.0.0.1 9001`).
2.  If not provided, it looks for `$profile.lhost` and `$profile.lport` in your global profile.
3.  If `$profile.lhost` is not set, it will [bold]attempt to auto-detect your local IP address[/bold].
4.  If `$profile.lport` is not set, it will [bold]default to port 1337[/bold].

It is still highly recommended to set these in your global profile for consistency.

[dim]Example: Setting up your profile[/dim]
[green]  profile update lhost 192.168.49.128[/green]
[green]  profile update lport 4444[/green]

[bold]Core Commands[/bold]

[cyan]▶ Generating a Payload[/cyan]
Simply specify the language. The command will use your profile settings.
[dim]Example:[/dim]
[green]  revshell python3[/green]

[cyan]▶ Specifying IP and Port Manually[/cyan]
You can override the profile settings by providing the IP and port directly.
[dim]Example:[/dim]
[green]  revshell php 10.10.14.2 9001[/green]