> Summary: A utility to quickly determine the possible type of a given cryptographic hash string.

[bold]The `identify` Command[/bold]

The `identify` command is a utility to quickly determine the possible type of a given cryptographic hash string. It analyzes the string's length and character set to match it against common hash formats.

[bold]Supported Formats[/bold]
The command can identify a variety of common hash types, including:
[green]  •[/green] Standard hashes like MD5, NTLM, SHA1, SHA256, and SHA512.
[green]  •[/green] Common Linux password hashes like bcrypt, md5crypt, sha256crypt, and sha512crypt.
[green]  •[/green] Hashes from specific applications like MySQL5.

[bold]Core Use Cases[/bold]
[green]  •[/green] [bold]Hash Identification:[/bold] Quickly check if a found string is a known hash type like MD5, SHA1, or SHA256.
[green]  •[/green] [bold]Placeholder Integration:[/bold] Directly identify hashes stored as loot or in notes without copy-pasting.

[bold]Syntax[/bold]
[green]  identify <hash_string_or_placeholder>[/green]

[dim]Examples:[/dim]
[green]  # Identify a raw hash string[/green]
[green]  identify 5f4dcc3b5aa765d61d8327deb882cf99[/green]

[green]  # Identify a hash that was previously saved as loot[/green]
[green]  loot add hash 5f4dcc3b5aa765d61d8327deb882cf99[/green]
[green]  identify $loot.0.value[/green]