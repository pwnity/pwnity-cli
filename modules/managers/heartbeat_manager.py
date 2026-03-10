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

# modules/managers/heartbeat_manager.py

import os
import json
import time
import threading
import socket
import random
import hashlib
import http.client
from urllib.parse import urlparse
from datetime import datetime
from collections import Counter

# Optional import for SOCKS proxy support
try:
    import socks
    pysocks_available = True
except ImportError:
    pysocks_available = False

from .base_manager import BaseManager
from modules.services import log, config
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.console import Group
from rich.rule import Rule
from rich.live import Live # Keep this import for _cmd_show
from rich.columns import Columns

class HeartbeatManager(BaseManager):
    def __init__(self, target_mgr):
        self.target_mgr = target_mgr
        self.folder = self._get_config_dir("HEARTBEATS", "data/heartbeats")
        if not os.path.exists(self.folder):
            os.makedirs(self.folder)
        self.active_heartbeats = {} # { 'target_name': {'thread': <Thread>, 'stop_event': <Event>} }

    def dispatch(self, subcommand, args, cli):
        """Overrides BaseManager's dispatch to handle the case where no subcommand is given."""
        if not subcommand:
            cli.help_mgr.show_help_heartbeat()
            return True
        
        # Let the parent class handle the actual dispatch to _cmd_* methods
        return super().dispatch(subcommand, args, cli)

    def _cmd_destroy(self, args, cli):
        """Handles the 'destroy' subcommand by calling the manager's destroy logic."""
        self.destroy(args.name)

    def _get_entity_type(self):
        return "Heartbeat"

    def destroy(self, target_name):
        """Deletes the data file for a given heartbeat."""
        if target_name in self.active_heartbeats:
            log.error(f"Cannot delete data for a running heartbeat. Please stop '{target_name}' first.")
            return False
        
        path = self._get_heartbeat_path(target_name)
        if not os.path.exists(path):
            log.warning(f"No data file found for heartbeat '{target_name}'. Nothing to delete.")
            return True # It's already gone, so success.

        try:
            os.remove(path)
            log.success(f"Deleted heartbeat data for '{target_name}'.")
            return True
        except OSError as e:
            log.error(f"Failed to delete heartbeat data file '{path}': {e}")
            return False

    def list_all(self):
        """Lists all available heartbeats (running or stopped) for autocompletion."""
        all_files = {f.replace('.json', '') for f in os.listdir(self.folder) if f.endswith('.json')}
        return sorted(list(all_files | set(self.active_heartbeats.keys())))

    def _get_heartbeat_path(self, target_name):
        return os.path.join(self.folder, f"{target_name}.json")

    def _read_heartbeat_data(self, target_name):
        path = self._get_heartbeat_path(target_name)
        if not os.path.exists(path):
            return None
        try:
            with open(path, 'r') as f:
                return json.load(f)
        except (IOError, json.JSONDecodeError):
            return None

    def _write_heartbeat_data(self, target_name, data):
        path = self._get_heartbeat_path(target_name)
        temp_path = path + ".tmp"
        try:
            with open(temp_path, 'w') as f:
                json.dump(data, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp_path, path)
        except (IOError, OSError) as e:
            log.error(f"Failed to write heartbeat data for '{target_name}': {e}")
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def _cmd_start(self, args, cli):
        target_name = cli.session.target
        if not target_name:
            log.error("No target loaded in the current session. Please load a target first.")
            log.prompt("Example: target load my-target")
            return

        if target_name in self.active_heartbeats:
            log.error(f"A heartbeat is already running for target '{target_name}'.")
            return

        target_data = self.target_mgr.load(target_name)
        if not target_data:
            log.error(f"Target '{target_name}' not found.")
            return

        url = target_data.get('url')
        if not url:
            log.error(f"Target '{target_name}' has no URL defined.")
            return

        # Parse options from remainder
        options = {}
        try:
            it = iter(args.options)
            for key in it:
                options[key.lower()] = next(it)
        except StopIteration:
            log.error("Invalid options format. Expected key-value pairs (e.g., delaymin 5).")
            return

        try:
            min_delay = float(options.get('delaymin', config.get_parameter("HEARTBEAT", "MIN_DELAY_SECONDS", 5)))
            max_delay = float(options.get('delaymax', config.get_parameter("HEARTBEAT", "MAX_DELAY_SECONDS", 15)))
            timelimit = int(options.get('timelimit')) if 'timelimit' in options else None
        except (ValueError, TypeError):
            log.error("Invalid value for delay or timelimit. Delays must be numbers, timelimit must be an integer.")
            return

        if min_delay > max_delay:
            log.error("delaymin cannot be greater than delaymax.")
            return

        stop_event = threading.Event()
        proxy_config = cli.proxy_mgr.get_effective_config(cli.session)
        
        thread = threading.Thread(
            target=self._monitor_loop,
            args=(target_name, url, min_delay, max_delay, timelimit, stop_event, proxy_config),
            daemon=True
        )
        
        self.active_heartbeats[target_name] = {'thread': thread, 'stop_event': stop_event}
        thread.start()
        log.success(f"Heartbeat started for '{target_name}' with a random delay between {min_delay}-{max_delay}s.")
        if timelimit:
            log.info(f"Monitoring will stop automatically after {timelimit} seconds.")
        log.prompt(f"View live data with 'heartbeat show {target_name}' or stop with 'heartbeat stop {target_name}'.")

    def _monitor_loop(self, target_name, url, min_delay, max_delay, timelimit, stop_event, proxy_config, user_agent=None):
        heartbeat_data = {
            "target_name": target_name,
            "url": url,
            "min_delay_seconds": min_delay,
            "max_delay_seconds": max_delay,
            "timelimit_seconds": timelimit,
            "user_agent": user_agent,
            "status": "running",
            "data_points": []
        }
        self._write_heartbeat_data(target_name, heartbeat_data)

        start_loop_time = time.monotonic()

        while not stop_event.is_set():
            if timelimit and (time.monotonic() - start_loop_time) > timelimit:
                log.info(f"Heartbeat for '{target_name}' reached time limit of {timelimit}s. Stopping.")
                break

            parsed_url = urlparse(url)
            host = parsed_url.hostname

            port = parsed_url.port or (443 if parsed_url.scheme == 'https' else 80)
            path = parsed_url.path or "/"
            
            data_point = {"timestamp": datetime.now().isoformat()}
            start_time = time.monotonic()
            conn = None

            # --- Proxy Handling ---
            original_socket = socket.socket
            is_socks_patched = False

            try:
                if proxy_config:
                    if proxy_config.get('type', 'http').lower() == 'socks5':
                        if not pysocks_available:
                            raise ConnectionError("PySocks library not found. Install with `pip install PySocks` to use a SOCKS proxy.")
                        proxy_host = proxy_config.get('host')
                        proxy_port = int(proxy_config.get('port'))
                        socks.set_default_proxy(socks.SOCKS5, proxy_host, proxy_port)
                        socket.socket = socks.socksocket
                        is_socks_patched = True
                        data_point['resolved_ip'] = 'via SOCKS5 proxy'
                    else:  # HTTP Proxy
                        data_point['resolved_ip'] = 'via HTTP proxy'
                else:  # No proxy
                    data_point['resolved_ip'] = socket.gethostbyname(host)

                # --- Connection Logic ---
                if proxy_config and not is_socks_patched: # HTTP Proxy
                    proxy_host = proxy_config.get('host')
                    proxy_port = int(proxy_config.get('port'))
                    if parsed_url.scheme == 'https':
                        # For HTTPS over HTTP proxy, we must use HTTPSConnection to the proxy
                        # and then set up a tunnel. The library handles the upgrade to SSL.
                        # The correct way is to use HTTPConnection to the proxy.
                        conn = http.client.HTTPConnection(proxy_host, proxy_port, timeout=10)
                        conn.set_tunnel(host, port)
                    else:
                        # For HTTP over HTTP proxy, this is straightforward.
                        conn = http.client.HTTPConnection(proxy_host, proxy_port, timeout=10)
                else: # No Proxy or SOCKS Proxy (uses patched socket)
                    if parsed_url.scheme == 'https':
                        # Use an unverified context for monitoring to support self-signed certs
                        context = ssl._create_unverified_context()
                        conn = http.client.HTTPSConnection(host, port, timeout=10, context=context)
                    else:
                        conn = http.client.HTTPConnection(host, port, timeout=10)
                
                # Prepare headers with User-Agent
                # user_agent is already resolved by the caller (sockets.py)
                headers = {
                    'User-Agent': user_agent or 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': '*/*',
                    'Connection': 'close'
                }
                
                conn.request("GET", path, body=None, headers=headers)
                response = conn.getresponse()
                content = response.read()
                data_point['latency_ms'] = round((time.monotonic() - start_time) * 1000)
                data_point['status_code'] = response.status
                data_point['content_length'] = len(content)
                data_point['content_hash'] = f"md5:{hashlib.md5(content).hexdigest()}"
            except Exception as e:
                data_point['error'] = str(e)
            finally:
                if conn:
                    conn.close()
                # Restore original socket if it was patched
                if is_socks_patched:
                    socket.socket = original_socket
                    socks.set_default_proxy() # Reset to none

            current_data = self._read_heartbeat_data(target_name)
            if current_data:
                current_data['data_points'].append(data_point)
                self._write_heartbeat_data(target_name, current_data)

            sleep_duration = random.uniform(min_delay, max_delay)
            stop_event.wait(timeout=sleep_duration)

        final_data = self._read_heartbeat_data(target_name)
        if final_data:
            final_data['status'] = 'stopped'
            self._write_heartbeat_data(target_name, final_data)
        
        # Clean up from the active list if this thread is the one that should be there
        # This handles the case where the thread stops by itself (e.g. timelimit)
        if target_name in self.active_heartbeats and self.active_heartbeats[target_name]['thread'] is threading.current_thread():
            del self.active_heartbeats[target_name]

    def _cmd_stop(self, args, cli):
        target_name = args.name
        if not target_name:
            target_name = cli.session.target
            if not target_name:
                log.error("No target specified and no target loaded in the session.")
                return
            log.info(f"No target specified, attempting to stop heartbeat for loaded target: '{target_name}'")

        if target_name not in self.active_heartbeats:
            log.error(f"No active heartbeat found for target '{target_name}'.")
            data = self._read_heartbeat_data(target_name)
            if data and data.get('status') == 'stopped':
                log.info(f"A previous heartbeat for '{target_name}' exists but is already stopped.")
            return

        log.info(f"Stopping heartbeat for '{target_name}'...")
        # Atomically pop the heartbeat info to prevent race conditions
        heartbeat_info = self.active_heartbeats.pop(target_name, None)
        
        if not heartbeat_info:
            # This can happen if the thread stopped itself (e.g., via timelimit)
            # between the check above and this pop operation.
            log.warning(f"Heartbeat for '{target_name}' appears to have stopped on its own.")
            return

        heartbeat_info['stop_event'].set()
        heartbeat_info['thread'].join(timeout=5)
        log.success(f"Heartbeat for '{target_name}' stopped.")

        # If running in web UI mode, automatically clean up the data file
        # to treat it as a pure live-tool from the UI's perspective.
        if hasattr(cli, 'web_ui_mode') and cli.web_ui_mode:
            self.destroy(target_name)

    def _create_plot_renderable(self, data: list[int], min_val: int, max_val: int, width: int = 60, height: int = 5):
        """Creates a multi-line, text-based scatter plot for the latency data."""
        if not data:
            return Text("[dim]Waiting for data...[/dim]", justify="center")

        # Create a grid for the plot area
        grid = [[' ' for _ in range(width)] for _ in range(height)]
        val_range = max_val - min_val if max_val > min_val else 1

        # Quantize and place data points in the grid
        for x, d in enumerate(data):
            if x >= width: break
            level = 0
            if val_range > 0:
                # Calculate the y-coordinate on the grid
                level = int(((d - min_val) / val_range) * (height - 1))
            # Invert y-axis because terminal (0,0) is top-left
            grid[height - 1 - level][x] = '█'

        # Create a rich Table to handle alignment of Y-axis labels and plot
        plot_table = Table.grid(padding=0)
        plot_table.add_column(style="dim", justify="right", width=9)  # Y-axis labels
        plot_table.add_column()  # Plot area

        # Add plot rows with Y-axis labels
        for i in range(height):
            y_label_val = max_val - i * (val_range / (height - 1 if height > 1 else 1))
            y_label = f"{y_label_val: >4.0f}ms ┤"
            row_str = "".join(grid[i])
            plot_table.add_row(y_label, Text(row_str, style="green"))

        # Add X-axis line
        plot_table.add_row(" " * 9 + "└" + "─" * (width - 1))
        
        # Add time labels for X-axis
        time_label = Text(justify="space-between", end="")
        time_label.append(f"last ~{len(data)} probes")
        time_label.append("now")
        plot_table.add_row(" " * 10, time_label)

        return plot_table

    def _generate_show_panel(self, target_name, console):
        data = self._read_heartbeat_data(target_name)
        if not data:
            return Panel(f"[dim]No data found for heartbeat '{target_name}'.[/dim]", border_style="red")

        points = data.get('data_points', [])

        # --- Latency Plot Panel ---
        # Use all data points for a stable scale, but only draw the most recent ones.
        all_latencies = [dp.get('latency_ms', 0) for dp in points if 'error' not in dp]
        
        # Calculate available width for the plot, accounting for panel borders and labels
        # Main Panel (4) + Latency Panel (4) + Y-axis label (9) + some buffer (3) = 20
        plot_width = console.width - 20 if console.width > 40 else 20

        if not all_latencies:
            plot_renderable = self._create_plot_renderable([], 0, 0, width=plot_width)
            latency_stats = "[dim]Waiting for first data point...[/dim]"
        else:
            # Draw up to plot_width points to fill the available space
            latencies_to_draw = all_latencies[-plot_width:]
            min_latency = min(all_latencies)
            max_latency = max(all_latencies)
            avg_latency = sum(all_latencies) / len(all_latencies)
            plot_renderable = self._create_plot_renderable(latencies_to_draw, min_latency, max_latency, width=plot_width)
            latency_stats = f"Min: [bold blue]{min_latency:.0f}ms[/bold blue]  Avg: [bold green]{avg_latency:.0f}ms[/bold green]  Max: [bold red]{max_latency:.0f}ms[/bold red]"

        latency_group = Group(
            plot_renderable,
            Text(""), # Spacer
            Text.from_markup(latency_stats, justify="center")
        )
        latency_panel = Panel(latency_group, title="[b]Latency Plot[/b]", border_style="dim", expand=True)

        # Status Panel
        status_codes = [dp.get('status_code') for dp in points if 'status_code' in dp]
        status_counts = Counter(status_codes)
        status_table = Table(box=None, show_header=False, expand=True)
        status_table.add_column()
        status_table.add_column()
        for code, count in sorted(status_counts.items()):
            color = "green" if str(code).startswith('2') else "yellow" if str(code).startswith('3') else "red"
            status_table.add_row(f"[{color}]{code}[/{color}]", str(count))
        status_panel = Panel(status_table, title="[b]Status Codes[/b]", border_style="dim", expand=True)

        # IP Panel
        ips = {dp.get('resolved_ip') for dp in points if 'resolved_ip' in dp}
        ip_panel = Panel(Text("\n".join(sorted(ips))), title="[b]Resolved IPs[/b]", border_style="dim")

        # Content Hash Panel
        hashes = {dp.get('content_hash') for dp in points if 'content_hash' in dp}
        hash_panel = Panel(Text(f"{len(hashes)} unique version(s)"), title="[b]Content Hash[/b]", border_style="dim", expand=True)

        # Config Panel
        config_table = Table(box=None, show_header=False, expand=True)
        config_table.add_column(style="dim")
        config_table.add_column()
        config_table.add_row("Delay Range:", f"{data.get('min_delay_seconds', 'N/A')} - {data.get('max_delay_seconds', 'N/A')}s")
        if data.get('timelimit_seconds'):
            config_table.add_row("Time Limit:", f"{data.get('timelimit_seconds')}s")
        config_panel = Panel(config_table, title="[b]Configuration[/b]", border_style="dim", expand=True)

        # Main Layout
        bottom_cols = Columns([status_panel, ip_panel, hash_panel, config_panel], expand=True)
        
        status_color = "green" if data.get('status') == 'running' else "yellow"
        title_text = f":pulse: [bold]Heartbeat: {target_name}[/bold] ([{status_color}]{data.get('status')}[/{status_color}])"
        return Panel(Group(latency_panel, bottom_cols), title=Text.from_markup(title_text), border_style="blue", expand=True)

    def _cmd_show(self, args, cli):
        target_name_arg = args.name
        if not target_name_arg:
            target_name_arg = cli.session.target
            if not target_name_arg:
                log.error("No target specified and no target loaded in the session.")
                log.prompt("Use 'heartbeat show <name>' or load one with 'heartbeat start'.")
                return

        is_live = target_name_arg in self.active_heartbeats

        if is_live:
            try:
                with Live(self._generate_show_panel(target_name_arg, cli.console), console=cli.console, screen=True, auto_refresh=False) as live:
                    while target_name_arg in self.active_heartbeats:
                        live.update(self._generate_show_panel(target_name_arg, cli.console), refresh=True)
                        time.sleep(1)
            except KeyboardInterrupt:
                pass # Exit live view gracefully
        else:
            panel = self._generate_show_panel(target_name_arg, cli.console)
            cli.console.print(panel)

    def _cmd_list(self, args, cli):
        items = self.list_all()
        if not items:
            log.info("No Heartbeats found (running or stopped).")
            return

        table = Table(box=None, expand=True, show_header=True, header_style="bold blue", padding=(0, 2))
        table.add_column("Target", style="cyan")
        table.add_column("Status", style="green")
        table.add_column("Delay (s)")
        table.add_column("Data Points")

        all_files = {f.replace('.json', '') for f in os.listdir(self.folder) if f.endswith('.json')}
        all_targets = self.list_all()

        for target_name in all_targets:
            if target_name in self.active_heartbeats: # Running heartbeats
                data = self._read_heartbeat_data(target_name)
                status = "[bold green]Running[/bold green]"
                interval = f"{data.get('min_delay_seconds', 'N/A')}-{data.get('max_delay_seconds', 'N/A')}" if data else "N/A"
                points = str(len(data.get('data_points', []))) if data else "N/A"
                table.add_row(target_name, status, interval, points)
            else:
                data = self._read_heartbeat_data(target_name)
                if data: # Stopped heartbeats with data files
                    status = "[dim]Stopped[/dim]"
                    interval = f"{data.get('min_delay_seconds', 'N/A')}-{data.get('max_delay_seconds', 'N/A')}"
                    points = str(len(data.get('data_points', [])))
                    table.add_row(target_name, status, interval, points)
        
        panel = Panel(
            table,
            title="[bold]Heartbeat Status[/bold]",
            border_style="blue",
            expand=False,
            subtitle=f"{len(items)} Heartbeats total"
        )
        cli.console.print(panel)

    def shutdown(self):
        if not self.active_heartbeats:
            return
        log.info("Shutting down all active heartbeats...")
        for target_name in list(self.active_heartbeats.keys()):
            self._cmd_stop(type('Args', (), {'name': target_name})(), None)