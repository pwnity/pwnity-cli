# pwnity Workflow Nodes Documentation

This document provides a detailed overview of all available nodes in the pwnity workflow editor.

*Last Updated: 2025-10-10*

## Node Categories

- [General Nodes](#general-nodes)
- [Control Flow Nodes](#control-flow-nodes)
- [Data Manipulation Nodes](#data-manipulation-nodes)
- [Viewers](#viewers)
- [Data Sources & Sinks](#data-sources--sinks)

---

## General Nodes

### Start
- **Purpose**: The entry point for a workflow. The `Run` button in the UI triggers all `Start` nodes on the canvas.
- **Outputs**:
  - `start` (EVENT): Triggers the next node.

### Output (Debug)
- **Purpose**: Displays any incoming data for debugging purposes.
- **Features**:
  - Can have multiple inputs. Use the `Add Input` and `Remove Last` buttons.
  - Each input is passed through to a corresponding output.
- **Inputs**:
  - `trigger` (ACTION): Updates the display with the current values.
  - `in_*` (*): The data to be displayed.
- **Outputs**:
  - `on_finish` (EVENT): Triggers after the display is updated.
  - `out_*` (*): The data passed through from the corresponding input.

### String / Integer / Boolean Input
- **Purpose**: Provides a static, typed value to the workflow. This is useful for setting default values or constants.
- **Features**:
  - The value can be changed directly in the node's properties.
  - The output is always available and updates as you type.
- **Outputs**:
  - `out` (string|number|boolean): The configured value.

### Group
- **Purpose**: Visually groups multiple nodes on the canvas.
- **Features**:
  - Can be resized and colored to organize the workflow.
  - Moving the group moves all nodes contained within it.
  - `on_finish` (EVENT): Triggers after the display is updated.
  - `out_*` (*): The data passed through from the corresponding input.

### Comment
- **Purpose**: A simple text box for adding notes and comments directly to the workflow canvas. It has no functional effect on the workflow.

---

## Control Flow Nodes

### If Condition
- **Purpose**: The core node for conditional logic. It evaluates a condition between inputs `A` and `B` (and potentially more) and triggers either the `true` or `false` event path.
- **Inputs**:
  - `trigger` (ACTION): Starts the evaluation.
  - `A`, `B`, `C`, ... (*): The values to be compared. Can be connected or set as static values in the node's properties.
- **Outputs**:
  - `true` (EVENT): Triggered if the condition is met.
  - `false` (EVENT): Triggered if the condition is not met.
  - `result` (boolean): The raw boolean result (`true` or `false`) of the evaluation.
  - `result_inv` (boolean): The inverted boolean result.

#### If-Node Operators

| Operator                | Description                                                                                             | Example (A, B) -> Result                               |
| ----------------------- | ------------------------------------------------------------------------------------------------------- | ------------------------------------------------------ |
| `==`                    | Checks for loose equality.                                                                              | `5`, `"5"` -> `true`                                   |
| `!=`                    | Checks for loose inequality.                                                                            | `5`, `6` -> `true`                                     |
| `>`, `<`, `>=`, `<=`    | Performs a numerical comparison.                                                                        | `10`, `5` -> `true` (for `>`)                          |
| `contains`              | Checks if string `A` contains string `B`.                                                               | `"hello world"`, `"world"` -> `true`                   |
| `matches regex`         | Checks if string `A` matches the regular expression in `B`.                                             | `"test@test.com"`, `^\S+@\S+$` -> `true`                |
| `is in`                 | Checks if value `A` is an element of array `B`.                                                         | `"443"`, `["80", "443"]` -> `true`                     |
| `is not in`             | Checks if value `A` is **not** an element of array `B`.                                                 | `"8080"`, `["80", "443"]` -> `true`                     |
| `intersects`            | Checks if array `A` and array `B` have at least one common element. `B` can be a comma-separated string. | `["80", "22"]`, `["443", "80"]` -> `true`              |
| `any in array contains` | Checks if **any** element in array `A` contains the string `B`.                                         | `["http-proxy", "ssh"]`, `"http"` -> `true`            |
| `all in array contain`  | Checks if **all** elements in array `A` contain the string `B`.                                         | `["http-proxy", "http-alt"]`, `"http"` -> `true`       |
| `is true` / `is false`  | Checks if `A` is truthy (e.g., not `null`, `undefined`, `0`, `false`, `""`) or falsy.                     | `true` -> `true` (for `is true`)                       |
| `is empty`              | Checks if `A` is `null`, `undefined`, an empty string `""`, or an empty array `[]`.                       | `[]` -> `true`                                         |
| `is not empty`          | The opposite of `is empty`.                                                                             | `[1]` -> `true`                                        |
| `AND` / `OR` / `XOR`    | Performs a logical operation on all inputs (`A`, `B`, `C`, ...).                                        | `true`, `false` -> `false` (for `AND`)                 |

### Loop (For Each)
- **Purpose**: Iterates over a collection (array or object).
- **Inputs**:
  - `start` (ACTION): Begins the loop with the provided collection.
  - `next` (ACTION): Manually triggers the next iteration.
  - `collection` (*): The array or object to loop over.
- **Outputs**:
  - `on_iteration` (EVENT): Triggered for each item in the collection.
  - `item` (*): The value of the current item.
  - `key_or_index` (*): The index (for an array) or key (for an object) of the current item.
  - `on_finish` (EVENT): Triggered after the last iteration.

### Wait (Join)
- **Purpose**: Waits for multiple, parallel execution paths to complete before triggering a single follow-up action.
- **Features**:
  - Starts with two inputs, more can be added.
  - It will only fire its output once all of its inputs have been triggered at least once.
  - After firing, it resets itself for the next run.
- **Inputs**:
  - `in_*` (ACTION): A trigger from a preceding path.
- **Outputs**:
  - `on_all_finished` (EVENT): Triggered when all inputs have been received.

### Switch
- **Purpose**: Directs the execution flow to one of several event outputs based on the input value.
- **Features**:
  - The possible cases are defined as a comma-separated string in the node's properties.
- **Inputs**:
  - `trigger` (ACTION): Starts the evaluation.
  - `in` (*): The value to be checked.
- **Outputs**:
  - `default` (EVENT): Triggered if the input value does not match any of the defined cases.
  - `caseName` (EVENT): A dynamic output for each defined case.

### Delay
- **Purpose**: Pauses the execution flow for a specified amount of time.
- **Inputs**:
  - `trigger` (ACTION): Starts the delay timer.
- **Outputs**:
  - `on_finish` (EVENT): Triggered after the delay has passed.
- **Properties**:
  - `Seconds`: The duration of the delay in seconds.

### Gate
- **Purpose**: A dynamic switch to enable or disable one or more execution paths.
- **Features**:
  - You can add multiple named gates.
  - Each gate has a toggle in the node's properties to enable or disable it.
  - A disabled gate will not pass through any trigger events.

### Relay
- **Purpose**: A dynamic passthrough node that helps organize complex graphs by routing connections without adding logic.
- **Features**:
  - Starts with one empty `trigger` and one empty `data` input.
  - When an input is connected, it and its corresponding output adopt the name of the source node's output.
  - A new, empty input of the same type (`trigger` or `data`) is automatically created.
  - When a connection is removed, the now-unused input/output pair is automatically deleted, keeping the graph clean.
  - It always maintains at least one empty input of each type, ready for new connections.
- **Inputs**:
  - Dynamic (ACTION or *): Accepts any connection.
- **Outputs**:
  - Dynamic (EVENT or *): Passes the input through to the corresponding output.
---

## Data Manipulation Nodes

### JSON
- **Purpose**: Converts data between object/array and a JSON string.
- **Modes**:
  - `Parse (String to Object)`: Converts a JSON string into a structured object or array.
  - `Stringify (Object to String)`: Converts an object or array into a JSON string. Can be "pretty printed".

### Get Property
- **Purpose**: Safely extracts a nested value from an object or array using a path.
- **Properties**:
  - `Path`: The path to the value, e.g., `data.user.name` or `results[0].ip`.
  - `Default Value`: The value to output if the path is not found or the input is `undefined`.

### Set Property
- **Purpose**: Sets or adds a property at a nested path within an object. It outputs a new object and does not modify the original.

### Concat / Collect
- **Purpose**: Collects multiple items into a single array. Useful for gathering results from a loop.
- **Inputs**:
  - `append` (ACTION): Adds the data from the `in` slot to the internal collection.
  - `clear` (ACTION): Empties the collection.
  - `in` (*): The data to add.
- **Outputs**:
  - `out` (array): The current array of all collected items.

### Merge
- **Purpose**: Combines multiple inputs into a single string or array.
- **Features**:
  - Can have multiple inputs.
  - Can output either a single array containing all items or a single string joined by a delimiter.

### Encoder
- **Purpose**: Performs various encoding, decoding, and hashing operations on the input data.
- **Modes**:
  - `Join Array`: Converts an array into a string, joined by a delimiter.
  - `Base64 Encode / Decode`
  - `URL Encode / Decode`
  - `MD5`, `SHA-1`, `SHA-256`, `SHA-512`: Hashes the input string.

### Filter
- **Purpose**: Filters an array of strings (or a multi-line string) based on a regular expression.
- **Properties**:
  - `Regex`: The regex pattern to match against each item.
  - `Invert (Remove)`: If enabled, items that match the regex are removed; otherwise, only matching items are kept.

### Regex Extract
- **Purpose**: A powerful node to extract specific parts of a string using a regular expression with capture groups.
- **Inputs**:
  - `trigger` (ACTION): Starts the extraction.
  - `text_in` (string): The text to search within.
- **Outputs**:
  - `on_finish` (EVENT): Triggered after extraction.
  - `full_matches` (array): An array of all full matches found (e.g., `["port 80", "port 443"]`).
  - `groups` (array): An array of arrays, where each inner array contains the capture groups for a match (e.g., `[["80"], ["443"]]`).
  - `first_match` (string): Only the first full match found.
  - `first_groups` (array): Only the capture groups from the first match.

### Wordlist Processor
- **Purpose**: A utility node for cleaning and manipulating wordlists. It takes file paths as input and outputs a path to a new, temporary file.
- **Properties**:
  - `Sort`: Sorts the combined wordlist alphabetically.
  - `Reverse Sort`: Sorts in reverse order (only if `Sort` is enabled).
  - `Unique`: Removes duplicate lines.
  - `Start Line` / `End Line`: Slices the wordlist, keeping only the lines within the specified range.

---

## Viewers

### HTML Viewer
- **Purpose**: Displays HTML content in a modal window.
- **Features**:
  - Can automatically resolve relative links (e.g., for images) if a `base_url` is provided.
  - Can be set to open automatically on trigger or manually via a button.

### CMD Viewer
- **Purpose**: Displays raw text output (e.g., from a tool) in a proper, read-only terminal view inside a modal window.
- **Features**:
  - Preserves colors and formatting from the original command output.
  - Can be set to open automatically on trigger or manually via a button.

---

## Data Sources & Sinks

### Target / Wordlist / etc.
- **Purpose**: Loads a specific item (like a Target or Tool) from the pwnity database and exposes all of its properties as data outputs.
- **Outputs**:
  - `on_finish` (EVENT): Triggered after the data has been loaded.
  - `item.property...` (*): Various outputs corresponding to the item's data structure (e.g., `target.ip`).

### Tool
- **Purpose**: Executes a pre-defined command from a Tool definition.
- **Features**:
  - Dynamically creates input slots based on the placeholders (e.g., `$target.ip`) in the selected command.
  - The execution is handled by the job manager, and the node polls for the result.
- **Outputs**:
  - `on_finish` (EVENT): Triggered when the tool command has finished executing.
  - `stdout` (string): The standard output of the command.
  - `status` (string): The final status of the job (e.g., `finished`, `failed`).
  - `return_code` (number): The command's exit code.

### Parser
- **Purpose**: Applies a set of regular expressions to a text input to extract structured data.
- **Features**:
  - Dynamically creates an output slot for each rule defined in the parser file.
- **Inputs**:
  - `trigger` (ACTION): Starts the parsing process.
  - `text_input` (string): The text to be parsed (e.g., from a Tool's `stdout`).
- **Outputs**:
  - `on_finish` (EVENT): Triggered after parsing is complete.
  - `found_rules` (array): A debug output containing the names of all rules that found at least one match.
  - `rule_name` (array): An array of all unique matches found for that specific rule.

### File Reader
- **Purpose**: Reads a file from the server's filesystem line by line. Ideal for processing large files without loading them entirely into memory.
- **Inputs**:
  - `start_reading` (ACTION): Opens the file specified in the `path` input.
  - `next_line` (ACTION): Reads the next line from the open file.
  - `close` (ACTION): Closes the file handle.
  - `path` (string): The absolute path to the file on the server.
- **Outputs**:
  - `on_ready` (EVENT): Triggered when the file is successfully opened.
  - `on_iteration` (EVENT): Triggered for each line that is read.
  - `on_finish` (EVENT): Triggered when the end of the file is reached.
  - `line` (string): The content of the currently read line.
