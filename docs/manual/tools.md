> Summary: Define reusable templates for external command-line tools like nmap or gobuster.

[bold]Configuring Tools[/bold]

A Tool is a reusable template for an external command. This is where you define how to use programs like `nmap` or `ffuf`.

[bold]Commands and Parameters[/bold]
A tool can have multiple "commands". Each command is just a label for a specific set of parameters. The key to flexibility is to [underline]add each parameter individually[/underline].

[dim]Example for `nmap`:[/dim]
[cyan]1. Create the tool:[/cyan]
[green]  tool add nmap[/green]

[cyan]2. Add a 'quick-scan' command:[/cyan]
[green]  tool update nmap command quick-scan[/green]

[cyan]3. Add parameters individually:[/cyan]
[green]  tool update nmap quick-scan param "-sV"[/green]
[green]  tool update nmap quick-scan param "-T4"[/green]
[green]  tool update nmap quick-scan param "$target.ip"[/green]

This creates a command that will be assembled as `nmap -sV -T4 192.168.1.1`.

[bold]Parameter & Value Separation[/bold]
For tools where a parameter and its value are separate (e.g., `gobuster dir -u <url>`), you should add them as separate parameters in `pwnity`. This makes the tool configuration even more modular.

[dim]Example for `gobuster`:[/dim]
[green]  tool add gobuster[/green]
[green]  tool update gobuster command dir[/green]
[green]  tool update gobuster dir param "-u"[/green]
[green]  tool update gobuster dir param "$target.base_url"[/green]
[green]  tool update gobuster dir param "-w"[/green]
[green]  tool update gobuster dir param "$wordlist.path"[/green]

This approach is more flexible than `param "-u $target.base_url"`.

[bold]Reordering Parameters[/bold]
Because parameters are stored as a list, you can change their order. This is useful if a tool requires a specific argument sequence.
[dim]Example:[/dim]
Let's say we want `$target.ip` to be the first parameter for our `nmap` quick-scan.
[green]  tool reorder nmap quick-scan 3 1[/green]
This moves the 3rd parameter (`$target.ip`) to the 1st position. The new command would be `nmap $target.ip -sV -T4`.

[bold]Sudo Handling[/bold]
If a tool requires root privileges, you can mark it once. `pwnity` will then automatically handle the `sudo` prompt when you run it.
[dim]Example:[/dim]
[green]  tool update nmap sudo true[/green]