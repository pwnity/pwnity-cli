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

# modules/logger.py
from datetime import datetime
from collections import deque
import weakref

class Logger:

    '''
    Central logging class.
    '''
    COLORS = {}
    LEVEL = {"TRACE": 5, "DEBUG": 10, "INFO": 20, "SUCCESS": 25, "WARNING": 30, "ERROR": 40, "CRITICAL": 50, "PROMPT": 90, "HEADER": 95}
    SYMBOLS = {
        "SUCCESS": "+",
        "INFO": "*",
        "WARNING": "!",
        "ERROR": "-",
        "CRITICAL": "!",
        "DEBUG": "D",
        "TRACE": "T",
        "PROMPT": "?",
        "CUSTOM": "#",
        "CFG_ERROR": "X"
    }
    FALLBACK_LEVEL = "DEBUG"

    def __init__(self, config=None, cli_instance=None, timestamp=False):
        self.config = config
        self.COLORS = self.config.get_section("COLORS")
        self.RESET = self.COLORS["RESET"]
        self.history = deque(maxlen=10) # Stores the last 10 log messages
        self.timestamp = timestamp
        self.cli_instance = weakref.ref(cli_instance) if cli_instance else None

        level = self.config.get_parameter("GLOBAL","DEBUG_LEVEL",self.FALLBACK_LEVEL)
        if level not in self.LEVEL:
            msg = f"{level} not defined in configuration. Falling back to default {self.FALLBACK_LEVEL}"
            self._output(
                log_message=msg,
                log_level="CFG_ERROR",
                color="RED_BG",
                timestamp_enabled=self.timestamp
            )
            level = self.FALLBACK_LEVEL
        self.min_log_level = level
        self.log_value = self.LEVEL[self.min_log_level]

    def set_cli_instance(self, cli_instance):
        """Sets a weak reference to the cmd2 app instance to redirect output."""
        if cli_instance:
            self.cli_instance = weakref.ref(cli_instance)
            self.debug("Logger bound to cmd2 instance.")
        else:
            self.cli_instance = None

    def _log(self,log_message, log_level, log_color):
        level_value = self.LEVEL[log_level]
        if level_value >= self.log_value:
            self._output(log_message, log_level=log_level, color=log_color, timestamp_enabled=self.timestamp)

    def _output(self, log_message, log_level, color, timestamp_enabled):
        color_code = self.COLORS.get(color, "")
        timestamp = ""
        if timestamp_enabled:
            timestamp = self._set_timestamp()

        symbol = self.SYMBOLS.get(log_level, "*")

        # Special case for header
        if log_level == "HEADER":
            formatted_message = f"\n{color_code}--- {log_message} ---{self.RESET}"
        else:
            formatted_message = f"{timestamp}{color_code}[{symbol}]{self.RESET} {log_message}"
        self.history.append(f"[{symbol}] {log_message}") # Add uncolored message to history
        cli = self.cli_instance() if self.cli_instance else None
        if cli:
            cli.poutput(formatted_message)
        else:
            print(formatted_message)

    def _set_timestamp(self):
        now = datetime.now()
        timestamp_now = "[" + now.strftime("%Y-%m-%d %H:%M:%S.%f") + "] - "
        return timestamp_now

    def get_history(self):
        """Returns the stored log history."""
        return list(self.history)

    # ---- EXTERNAL FUNCTIONS BELOW ---- #

    def trace(self, log_message):
        self._log(log_message, "TRACE", "MAGENTA_BG")

    def info(self, log_message):
        self._log(log_message, "INFO", "GREY")

    def success(self, log_message):
        self._log(log_message, "SUCCESS", "GREEN")

    def prompt(self, log_message):
        self._log(log_message, "PROMPT", "CYAN")

    def header(self, log_message):
        self._log(log_message, "HEADER", "WHITE")

    def debug(self, log_message):
        self._log(log_message, "DEBUG", "BLUE")

    def warning(self, log_message):
        self._log(log_message, "WARNING", "YELLOW")

    def error(self, log_message):
        self._log(log_message, "ERROR", "RED")

    def critical(self, log_message):
        self._log(log_message, "CRITICAL", "RED_BG")

    def custom(self, log_message, log_level="CUSTOM", timestamp = None):
        if timestamp == None:
            timestamp = self.timestamp
        color = "CYAN"
        self._output(log_message=log_message, log_level=log_level, color=color, timestamp_enabled=timestamp)
