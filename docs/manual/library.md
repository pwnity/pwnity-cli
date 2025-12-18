# Manual: The `library` Command

The `library` command is used to manage a personal collection of useful links and resources, like cheat sheets, online tools, or documentation pages. It acts as a simple bookmark manager within pwnity.

## Concepts

- **Library Entry**: A single item in your library, identified by a unique name (e.g., `gtfobins`).
- **URL**: The web address for the resource.
- **Fields**: Each entry is a collection of key-value pairs. The `url` field is special, but you can add any other fields you find useful, such as `comment`, `tags`, etc.

## Common Workflow

1.  **Add a new entry**:
    ```
    pwnity> library add gtfobins
    ```

2.  **Add a URL and other details**:
    ```
    pwnity> library update gtfobins url https://gtfobins.github.io/
    pwnity> library update gtfobins comment "Curated list of Unix binaries for living off the land."
    ```

3.  **List all entries**:
    ```
    pwnity> library list
    ```

4.  **View details of an entry**:
    ```
    pwnity> library show gtfobins
    ```

5.  **Open the URL in a browser**:
    ```
    pwnity> library open gtfobins
    ```

## Subcommands

- `add <name>`: Creates a new, empty library entry.
- `list`: Lists the names of all saved library entries.
- `show <name>`: Displays all details for a specific entry.
- `update <name> <field> <value>`: Adds or changes a field for an entry.
- `open <name>`: Opens the entry's URL in your default web browser.
- `rename <old_name> <new_name>`: Renames an entry.
- `delete <name> [field]`: Deletes a specific field from an entry. If no field is given, it deletes the entire entry (same as `destroy`).
- `destroy <name>`: Permanently deletes an entry and its file.
- `export <name>`: Generates the `library` commands needed to recreate an entry.
