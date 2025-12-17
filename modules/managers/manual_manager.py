#
# # Project: https://github.com/pwnity/pwnity-cli
# # Copyright 2025 pwnity
# #
# # Licensed under the Apache License, Version 2.0 (the "License");
# # you may not use this file except in compliance with the License.
# # You may obtain a copy of the License at
# #
# #     http://www.apache.org/licenses/LICENSE-2.0
# #
# # Unless required by applicable law or agreed to in writing, software
# # distributed under the License is distributed on an "AS IS" BASIS,
# # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# # See the License for the specific language governing permissions and
# # limitations under the License.#

# modules/managers/manual_manager.py
import os
from rich.panel import Panel
from rich.text import Text
from ..services import log, config
import re

class ManualManager:
    def __init__(self, console):
        self.console = console
        self.manual_dir = config.get_parameter("DIRS", "MANUALS", "docs/manual")
        # Ensure the directory exists, create it if it doesn't
        try:
            os.makedirs(self.manual_dir, exist_ok=True)
        except OSError as e:
            log.error(f"Could not create manuals directory '{self.manual_dir}': {e}")
            self.manual_dir = None

    def _load_content(self, topic: str) -> str | None:
        """Loads the content of a manual page from a file."""
        if not self.manual_dir:
            return None
        
        file_path = os.path.join(self.manual_dir, f"{topic}.md")
        if not os.path.exists(file_path):
            return None
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            log.error(f"Error reading manual file '{file_path}': {e}")
            return None

    def get_topic_summary(self, topic: str) -> str:
        """
        Loads a summary for a manual topic. It first looks for a line starting
        with '> Summary: '. If not found, it falls back to the first non-title line.
        """
        content = self._load_content(topic)
        if not content:
            return f"Documentation for '{topic.replace('_', ' ')}'."

        # First pass: look for an explicit summary
        summary_prefix = "> Summary:"
        for line in content.splitlines():
            # Strip the line first to handle leading whitespace
            if line.strip().startswith(summary_prefix): # Check against prefix without trailing space
                summary = line.strip()[len(summary_prefix):].strip()
                # If the summary line is present but empty, don't return it.
                # Let the logic fall through to the next non-title line.
                if summary:
                    return summary

        # Second pass (fallback): use the first non-title line
        for line in content.splitlines():
            line = line.strip()
            # Skip empty lines and markdown titles (which usually start with [bold] or #)
            # --- FIX: Also skip explicit summary lines in the fallback pass ---
            if line and not line.lower().startswith('[bold]') and not line.startswith('#') and not line.startswith(summary_prefix):
                # Clean up rich markup for a plain text summary
                clean_line = re.sub(r'\[/?.*?\]', '', line)
                # Truncate if too long
                return (clean_line[:77] + '...') if len(clean_line) > 80 else clean_line
        
        # Fallback if no suitable line is found
        return f"Documentation for '{topic.replace('_', ' ')}'."

    def show_page(self, topic: str):
        """Loads and displays a specific manual page."""
        content = self._load_content(topic)
        if content is None:
            log.error(f"Manual page for topic '{topic}' not found.")
            # To be helpful, we can list available topics.
            available_topics = self.list_topics()
            if available_topics:
                log.prompt(f"Available topics are: {', '.join(available_topics)}")
            return
        
        # Filter out the summary line before displaying
        summary_prefix = "> Summary: "
        lines_after_summary = [
            line for line in content.splitlines() 
            if not line.strip().startswith(summary_prefix)
        ]
        
        # Find the index of the first non-empty line (which is the title)
        first_content_line_index = -1
        for i, line in enumerate(lines_after_summary):
            if line.strip():
                first_content_line_index = i
                break
        
        # If a title line was found, slice the list to exclude it and any preceding empty lines.
        if first_content_line_index != -1:
            # We start from the line *after* the title.
            final_lines = lines_after_summary[first_content_line_index + 1:]
        else:
            final_lines = []

        cleaned_content = "\n".join(final_lines).lstrip()
        text_content = Text.from_markup(cleaned_content)
        title = topic.replace('_', ' ').title()
        panel = Panel(text_content, title=f"[bold white]Manual: {title}[/bold white]", border_style="white", padding=(1, 2))
        self.console.print(panel)

    def list_topics(self) -> list[str]:
        """Lists all available manual topics by scanning the directory."""
        if not self.manual_dir:
            return []
        try:
            return sorted([f.replace('.md', '') for f in os.listdir(self.manual_dir) if f.endswith('.md')])
        except OSError as e:
            log.error(f"Could not list manual topics in '{self.manual_dir}': {e}")
            return []