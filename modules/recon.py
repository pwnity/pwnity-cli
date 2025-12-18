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

# modules/recon.py
from modules.services import log
import socket
import ssl
import http.client, json, re
from datetime import datetime

try:
    import whois
    import dns.resolver
except ImportError:
    whois = None
    dns = None
    log.error("Dependencies 'python-whois' and/or 'dnspython' not found. 'gather' command is disabled.")
    log.error("Please install with 'pip install python-whois dnspython'.")

class ReconService:
    """Gathers information about a given target."""

    def __init__(self, target_data):
        if not whois or not dns:
            raise ImportError("Dependencies for ReconService not installed.")
        self.target = target_data
        self.hostname = self.target.get('hostname')
        self.ip = self.target.get('ip')
        # Newly added fields for smarter queries
        self.domain = self.target.get('domain')

    def _get_ip_intel(self, ip_address=""):
        """Fetches geolocation and ISP/Org info for an IP address from ip-api.com."""
        conn = None
        try:
            conn = http.client.HTTPConnection("ip-api.com", timeout=5)
            fields = "status,message,country,city,lat,lon,query,isp,org,as"
            conn.request("GET", f"/json/{ip_address}?fields={fields}")
            response = conn.getresponse()
            if response.status == 200:
                data = json.loads(response.read().decode())
                if data.get('status') == 'success':
                    result = {
                        "ip": data.get('query'),
                        "lat": data.get('lat'),
                        "lon": data.get('lon'),
                        "city": data.get('city'),
                        "country": data.get('country'),
                        "isp": data.get('isp'),
                        "org": data.get('org'),
                        "as": data.get('as'),
                    }
                    return result
            return None
        except Exception as e:
            log.error(f"  -> Error during Geo-IP query: {e}")
            return None
        finally:
            if conn:
                conn.close()

    def _get_mx_records(self, query_name: str) -> dict:
        """
        Private helper to query MX records for a given hostname.
        Returns a dictionary with the 'mx_records' key on success.
        """
        if not query_name:
            return {}
        
        try:
            mx_records = dns.resolver.resolve(query_name, 'MX')
            mx_data = sorted([f"{record.preference} {record.exchange}" for record in mx_records])
            log.success(f"  -> {len(mx_data)} MX record(s) found for '{query_name}'.")
            return {'mx_records': mx_data}
        except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN):
            log.info(f"  -> No MX records found for '{query_name}'.")
        except Exception as e:
            log.warning(f"  -> Error during MX query for '{query_name}': {e}")
        return {}

    def gather_all(self):
        """Executes all gather methods and returns the collected data."""
        all_updates = {}
        dns_updates = self.gather_dns()
        all_updates.update(dns_updates)
        self.target.update(dns_updates) # Update IP for subsequent scans

        all_updates.update(self.gather_http())
        all_updates.update(self.gather_whois())
        all_updates.update(self.gather_geo())
        return all_updates

    def gather_dns(self):
        log.info(f"Gathering DNS information for {self.hostname or self.ip}...")
        updates = {}
        # The name used for most queries. Starts with the hostname.
        query_name = self.hostname

        # Step 1: Forward lookups (based on hostname)
        if self.hostname:
            # CNAME resolution to find the "real" name for further queries
            try:
                cname_answer = dns.resolver.resolve(self.hostname, 'CNAME')
                cname_targets = [str(r.target).rstrip('.') for r in cname_answer]
                updates['cname_records'] = cname_targets
                if cname_targets:
                    query_name = cname_targets[0]
                    log.success(f"  -> '{self.hostname}' is a CNAME for '{query_name}'. Performing further queries for '{query_name}'.")
            except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN):
                log.info(f"  -> No CNAME record found for '{self.hostname}'.")
            except Exception as e:
                log.warning(f"  -> Error during CNAME query: {e}")

            # A-Record (IPv4)
            try:
                ip = socket.gethostbyname(query_name)
                updates['ip'] = ip
                self.ip = ip  # Update instance IP for PTR lookup
                log.success(f"  -> IP address (A) for '{query_name}' found/updated: {ip}")
            except socket.gaierror:
                log.warning(f"  -> Could not resolve hostname '{query_name}' to an IPv4 address.")

            # AAAA-Record (IPv6)
            try:
                aaaa_records = dns.resolver.resolve(query_name, 'AAAA')
                updates['ipv6_addresses'] = [record.to_text() for record in aaaa_records]
                log.success(f"  -> {len(updates['ipv6_addresses'])} AAAA record(s) (IPv6) found for '{query_name}'.")
            except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN):
                log.info(f"  -> No AAAA records found for '{query_name}'.")
            except Exception as e:
                log.warning(f"  -> Error during AAAA query: {e}")

            # TXT-Records
            try:
                txt_records = dns.resolver.resolve(query_name, 'TXT')
                updates['txt_records'] = [record.to_text().strip('"') for record in txt_records]
                log.success(f"  -> {len(updates['txt_records'])} TXT record(s) found for '{query_name}'.")
            except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN):
                log.info(f"  -> No TXT records found for '{query_name}'.")
            except Exception as e:
                log.warning(f"  -> Error during TXT query: {e}")

            # NS-Records
            try:
                ns_records = dns.resolver.resolve(query_name, 'NS')
                updates['name_servers'] = sorted([str(record.target) for record in ns_records])
                log.success(f"  -> {len(updates['name_servers'])} NS record(s) found for '{query_name}'.")
            except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN):
                log.info(f"  -> No NS records found for '{query_name}'.")
            except Exception as e:
                log.warning(f"  -> Error during NS query: {e}")

            # MX-Records
            log.info(f"  -> Querying MX records for '{query_name}'...")
            updates.update(self._get_mx_records(query_name))

        # Step 2: Reverse lookup (based on IP)
        # This is executed if we have an IP, either from the start or from the A-record lookup.
        if self.ip:
            try:
                ptr_record, _, _ = socket.gethostbyaddr(self.ip)
                updates['ptr_record'] = ptr_record
                log.success(f"  -> Reverse DNS (PTR) for '{self.ip}' found: {ptr_record}")
            except socket.herror:
                log.info(f"  -> No Reverse DNS (PTR) record found for '{self.ip}'.")

        return updates

    def gather_mx(self):
        """Gathers only MX records for the target."""
        # MX queries are based on the hostname or domain.
        query_name = self.hostname
        if not query_name:
            log.warning("  -> Skipping MX query: No hostname available for the target.")
            return {}

        log.info(f"Gathering MX records for {query_name}...")
        # The helper function does the actual work and logging.
        return self._get_mx_records(query_name)

    def gather_whois(self):
        # WHOIS queries are most useful for the registered domain (e.g., google.com),
        # not for a specific subdomain (e.g., www.google.com).
        query_target = self.domain or self.hostname or self.ip
        if not query_target:
            log.warning("  -> Skipping WHOIS query: No hostname, domain, or IP available for the target.")
            return {}

        log.info(f"Gathering WHOIS information for {query_target}...")
        try:
            w = whois.whois(query_target)
            def serialize_value(value):
                if isinstance(value, datetime): return value.isoformat()
                if isinstance(value, list): return [item.isoformat() if isinstance(item, datetime) else item for item in value]
                return value
            whois_data = {k: serialize_value(v) for k, v in w.items() if v and not k.startswith('_')}
            log.success(f"  -> WHOIS data saved.")
            return {'whois_info': whois_data}
        except Exception as e:
            log.error(f"  -> Error during WHOIS query: {e}")
        return {}

    def gather_geo(self):
        """Gathers Geo-IP information for the target's IP."""
        if not self.ip:
            log.warning("  -> Skipping Geo-IP query: No IP address available for the target.")
            return {}
        
        log.info(f"Gathering Geo-IP information for {self.ip}...")
        geo_data = self._get_ip_intel(self.ip)
        if geo_data:
            log.success("  -> Geo-IP data saved.")
            return {'geo_intel': geo_data}
        else:
            log.info("  -> No Geo-IP information found.")
        return {}

    def gather_http(self):
        port = self.target.get('port', 443)
        protocol = self.target.get('protocol', 'https')
        updates = {}
        log.info(f"Gathering HTTP information for {self.hostname}:{port}...")

        if protocol == 'https':
            try:
                context = ssl.create_default_context()
                with socket.create_connection((self.hostname, port), timeout=5) as sock:
                    with context.wrap_socket(sock, server_hostname=self.hostname) as ssock:
                        cert = ssock.getpeercert()
                        cert_info = {
                            'subject': dict(x[0] for x in cert.get('subject', [])),
                            'issuer': dict(x[0] for x in cert.get('issuer', [])),
                            'valid_from': cert.get('notBefore'),
                            'valid_to': cert.get('notAfter'),
                            'sans': [x[1] for x in cert.get('subjectAltName', [])]
                        }
                        updates['ssl_info'] = cert_info
                        log.success("  -> SSL certificate successfully analyzed.")
            except Exception as e:
                log.warning(f"  -> Error retrieving SSL certificate: {e}")

        try:
            conn_class = http.client.HTTPSConnection if protocol == 'https' else http.client.HTTPConnection
            conn = conn_class(self.hostname, port, timeout=5)
            conn.request("GET", self.target.get('uri', '/'))
            response = conn.getresponse()
            headers = dict(response.getheaders())
            updates['http_headers'] = headers
            log.success(f"  -> HTTP headers successfully retrieved (Status: {response.status}).")
            conn.close()
        except Exception as e:
            log.warning(f"  -> Error retrieving HTTP headers: {e}")
        return updates