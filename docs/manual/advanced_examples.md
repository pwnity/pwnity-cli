> Summary: Showcases advanced techniques and creative ways to use pwnity beyond the standard workflow.

[bold]Advanced Examples & Creative Uses[/bold]

This page showcases advanced techniques and creative ways to use `pwnity` beyond the standard workflow. These examples demonstrate how to leverage the framework's flexibility for complex automation and out-of-the-box tasks.

[cyan]▶ Using Standard Linux Commands as Tools[/cyan]
You can wrap any command-line utility, not just security tools. This is useful for quick diagnostics or integrating system commands into your workflow.

[dim]Example: Wrapping `ping` and `curl`[/dim]
[green]  # Create a simple 'ping' tool[/green]
[green]  tool add ping[/green]
[green]  tool update ping command check[/green]
[green]  tool update ping check param "-c 4 $target.ip"[/green]
[green]  # Run it[/green]
[green]  target load my-server[/green]
[green]  pwn check now[/green]

[green]  # Create a 'curl' tool to grab HTTP headers[/green]
[green]  tool add curl[/green]
[green]  tool update curl command get-headers[/green]
[green]  tool update curl get-headers param "-I -s $target.url"[/green]
[green]  # Run it[/green]
[green]  pwn get-headers now[/green]

[cyan]▶ Dynamic Wordlist Generation with `crunch`[/cyan]
A `wordlist` object doesn't have to point to a file. You can use it to store parameters for a wordlist generator like `crunch`.

[dim]Example: Generating an 8-digit numeric list[/dim]
[green]  # 1. Create a 'wordlist' to hold the parameters[/green]
[green]  wordlist add 8-digit-numeric[/green]
[green]  wordlist update 8-digit-numeric min 8[/green]
[green]  wordlist update 8-digit-numeric max 8[/green]
[green]  wordlist update 8-digit-numeric charset "0123456789"[/green]

[green]  # 2. Create a 'crunch' tool that uses these parameters[/green]
[green]  tool add crunch[/green]
[green]  tool update crunch command generate[/green]
[green]  tool update crunch generate param "$wordlist.min $wordlist.max $wordlist.charset"[/green]

[green]  # 3. Load the parameter-wordlist and run the generator[/green]
[green]  wordlist load 8-digit-numeric[/green]
[green]  tool load crunch[/green]
[green]  pwn generate now[/green] [dim]# This will run 'crunch 8 8 0123456789'[/dim]

[cyan]▶ Using `pwnity` as a Dynamic Checklist Manager[/cyan]
By wrapping the `echo` command, you can turn a tool into a dynamic checklist generator that uses placeholders from your target.

[dim]Example: A web-app recon checklist[/dim]
[green]  # Use /bin/echo as the tool's executable[/green]
[green]  tool add checklist[/green]
[green]  tool update checklist path /bin/echo[/green]

[green]  # Create a command with each step as a parameter[/green]
[green]  tool update checklist command web-recon[/green]
[green]  tool update checklist web-recon execute_per_param true[/green] [dim]# Set to run 'echo' for each param[/dim]
[green]  tool update checklist web-recon param "== Recon Checklist for $target.name =="[/green]
[green]  tool update checklist web-recon param "1. Check robots.txt -> $target.base_url/robots.txt"[/green]
[green]  tool update checklist web-recon param "2. Check for sitemap -> $target.base_url/sitemap.xml"[/green]
[green]  tool update checklist web-recon param "3. Review HTTP headers for $target.hostname"[/green]

[green]  # Load a target and run the 'pwn' command to display the checklist[/green]
[green]  target load my-webapp[/green]
[green]  tool load checklist[/green]
[green]  pwn web-recon now[/green]

[cyan]▶ API Integration via the Global Profile[/cyan]
The `profile` is perfect for storing API keys that can be used by tools.

[dim]Example: Integrating `whatweb` with an API key[/dim]
[green]  # 1. Store your API key in the global profile[/green]
[green]  profile update whatweb_apikey YOUR_API_KEY_HERE[/green]

[green]  # 2. Create a 'whatweb' tool that uses the key[/green]
[green]  tool add whatweb[/green]
[green]  tool update whatweb command deep-scan[/green]
[green]  tool update whatweb deep-scan param "-a 3"[/green]
[green]  tool update whatweb deep-scan param "--api-key=$profile.whatweb_apikey"[/green]
[green]  tool update whatweb deep-scan param "$target.url"[/green]

[green]  # 3. Run the scan[/green]
[green]  target load my-webapp[/green]
[green]  tool load whatweb[/green]
[green]  pwn deep-scan now[/green]

[cyan]▶ Chaining Tools for Automated Target Discovery[/cyan]
You can use one tool to discover assets and then pipe the results into `pwnity` to create new targets automatically.

[dim]Example: Using `subfinder` to create new targets[/dim]
[green]  # 1. In pwnity, configure a subfinder tool[/green]
[green]  tool add subfinder[/green]
[green]  tool update subfinder command find[/green]
[green]  tool update subfinder find param "-d $target.domain -o /tmp/subs.txt"[/green]
[green]  target load example.com[/green]
[green]  pwn find now[/green]

[green]  # 2. Use the built-in 'shell' command to process the output file without leaving pwnity[/green]
[dim]  # This command reads each subdomain from the file and creates a pwnity script.[/dim]
[green]  shell while read sub; do echo "target add $$sub; target update $$sub url https://$$sub"; done < /tmp/subs.txt > create_targets.pwn[/green]
[dim]  # Note: We use '$$sub' because '$' is a special character in cmd2. Doubling it escapes it for the shell.[/dim]

[green]  # 3. Back in pwnity, run the generated script[/green]
[green]  run_script create_targets.pwn[/green]
[green]  target list[/green] [dim]# You will now see all the discovered subdomains as new targets[/dim]

[cyan]▶ Using Placeholder Functions for Data Transformation[/cyan]
The placeholder system supports functions to encode, decode, or hash data on the fly. This is extremely powerful for preparing payloads.

[dim]Example: Base64-encoding a value for a `curl` header[/dim]
[green]  # Suppose a target requires a Base64-encoded 'Authorization' header.[/green]
[green]  # The value is composed of a username from the profile and a static string.[/green]
[green]  profile update username pentester[/green]

[green]  tool add curl[/green]
[green]  tool update curl command auth-test[/green]
[green]  tool update curl auth-test param "-H 'Authorization: Basic b64encode($profile.username:secret-token)'"[/green]
[green]  tool update curl auth-test param "$target.url"[/green]

[dim]  # The 'pwn' command will resolve this to:[/dim]
[dim]  # curl -H 'Authorization: Basic cGVudGVzdGVyOnNlY3JldC10b2tlbg==' http://...[/dim]

[dim]Example: Testing the functions with the `print` command[/dim]
[green]  print b64encode($target.name)[/green]
[green]  print md5('test-string')[/green]