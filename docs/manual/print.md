> Summary: A utility for testing and debugging placeholders and functions.

[bold]The `print` Command[/bold]

The `print` command is a simple yet powerful utility for testing and debugging placeholders and functions. It takes a string, resolves any placeholders or functions within it, and prints the final result to the console.

[bold]Core Use Cases[/bold]
[green]  •[/green] [bold]Testing Placeholders:[/bold] Quickly check the value of a placeholder before using it in a complex tool command.
[green]  •[/green] [bold]Transforming Data:[/bold] Use placeholder functions to encode, decode, or hash data on the fly.
[green]  •[/green] [bold]Debugging:[/bold] Verify that complex, nested placeholders are being resolved as you expect.

[bold]Syntax[/bold]
The `print` command supports two main syntaxes:

[cyan]1. Simple Function Syntax[/cyan]
This is the most common and readable way to use functions.
[dim]Example:[/dim]
[green]  print b64encode "some text to encode"[/green]
[green]  print md5 $target.name[/green]

[cyan]2. Bracket and Placeholder Syntax[/cyan]
This syntax is used for resolving complex strings containing multiple placeholders or nested functions.
[dim]Example:[/dim]
[green]  print "The target is $target.name at $target.ip"[/green]
[green]  print b64encode(urlencode($target.name))[/green]
[green]  print $logbook.1[/green] [dim]# Prints the entire logbook entry as JSON[/dim]