# pwnity Report: pwnity_report
Generated on: 2026-02-10 01:16:49

## Involved Targets

- `Automation`
- `acme-search.local`
- `google`
- `pwnity`
- `{'name': 'pwnity', 'protocol': 'http', 'hostname': 'pwnity.local', 'ip': '192.168.178.76', 'domain': '', 'domain_name': 'local', 'tld': '', 'subdomains': ['pwnity'], 'port': '80', 'base_url': 'http://pwnity.local', 'uri': '/', 'url': 'http://pwnity.local'}`

## Command History

| Timestamp | Tool | Command | Log ID |
|---|---|---|---|
| 2026-02-03 13:13 | `nmap` | `/usr/bin/nmap -T4 -F 192.168.178.76` | `394b3a71-5404-4a3e-a050-32d07949e168` |
| 2026-02-03 13:14 | `gobuster` | `/usr/bin/gobuster dir -w /usr/share/wordlists/dirb/common.txt -u http://pwnity.local -t 50` | `57506566-6f8a-45eb-b120-f58dfc192919` |
| 2026-02-06 16:23 | `gobuster` | `/usr/bin/gobuster dir -w /usr/share/wordlists/dirb/common.txt -u http://pwnity.local -t 50` | `bb73b74c-55aa-40de-97e5-3c0e8f1f2ec2` |
| 2026-02-07 23:10 | `Faketest` | `sudo /home/kali/fake_test.sh 20` | `939a6e5e-0c51-4050-bb75-5696324cd7df` |
| 2026-02-07 23:12 | `Faketest` | `sudo /home/kali/fake_test.sh 20` | `fe908a54-fffc-46ab-9b8f-1c6429483389` |
| 2026-02-07 23:13 | `Faketest` | `sudo /home/kali/fake_test.sh 20` | `ad4130b8-ee6a-4ca0-bbd1-276cf8563cd3` |
| 2026-02-07 23:15 | `Faketest` | `sudo /home/kali/fake_test.sh 20` | `9e694580-42b2-48f2-87d0-f0fff1d35960` |
| 2026-02-07 23:27 | `Faketest` | `sudo /home/kali/fake_test.sh 20` | `ae881950-012b-4de2-9a63-6ef56c535049` |
| 2026-02-07 23:28 | `Faketest` | `sudo /home/kali/fake_test.sh 20` | `3786aaa0-c467-494a-bf7d-e0bcc4a731c8` |

## Notes

| Timestamp | Target | Note |
|---|---|---|
| 2026-02-05 | `acme-search.local` | Oh, this seems to be a note? Yeah, sure! |
| 2026-02-09 | `Automation` | test |

## Loot

- **Type:** `credential` | **Target:** `acme-search.local`
  - **Value:** `admin:pass`
- **Type:** `flag` | **Target:** `acme-search.local`
  - **Value:** `$FLAG{ABC}`
- **Type:** `text` | **Target:** `Automation`
  - **Value:** `test`
- **Type:** `text` | **Target:** `Automation`
  - **Value:** `test`
- **Type:** `text` | **Target:** `{'name': 'pwnity', 'protocol': 'http', 'hostname': 'pwnity.local', 'ip': '192.168.178.76', 'domain': '', 'domain_name': 'local', 'tld': '', 'subdomains': ['pwnity'], 'port': '80', 'base_url': 'http://pwnity.local', 'uri': '/', 'url': 'http://pwnity.local'}`
  - **Value:** `test`
### Loot Type: `credential`

| Target | Value |
|---|---|
| `acme-search.local` | `admin:pass` |

### Loot Type: `flag`

| Target | Value |
|---|---|
| `acme-search.local` | `$FLAG{ABC}` |

### Loot Type: `text`

| Target | Value |
|---|---|
| `Automation` | `test` |
| `Automation` | `test` |
| `{'name': 'pwnity', 'protocol': 'http', 'hostname': 'pwnity.local', 'ip': '192.168.178.76', 'domain': '', 'domain_name': 'local', 'tld': '', 'subdomains': ['pwnity'], 'port': '80', 'base_url': 'http://pwnity.local', 'uri': '/', 'url': 'http://pwnity.local'}` | `test` |


## Parser Findings

- **Category:** `ipv4` | **Target:** `pwnity` | **Source:** `Log #394b3a71-5404-4a3e-a050-32d07949e168`
  - **Match:** `192.168.178.76`
- **Category:** `tcp_port` | **Target:** `pwnity` | **Source:** `Log #394b3a71-5404-4a3e-a050-32d07949e168`
  - **Match:** `80`
- **Category:** `ipv4` | **Target:** `google` | **Source:** `Log #eee99320-27b9-4963-a0d1-65b5ca3d7e8c`
  - **Match:** `192.168.178.76`
- **Category:** `tcp_port` | **Target:** `google` | **Source:** `Log #eee99320-27b9-4963-a0d1-65b5ca3d7e8c`
  - **Match:** `631`
- **Category:** `tcp_port` | **Target:** `google` | **Source:** `Log #eee99320-27b9-4963-a0d1-65b5ca3d7e8c`
  - **Match:** `80`
### Finding Category: `ipv4`

| Target | Match | Source Log |
|---|---|---|
| `pwnity` | `192.168.178.76` | `Log #394b3a71-5404-4a3e-a050-32d07949e168` |
| `google` | `192.168.178.76` | `Log #eee99320-27b9-4963-a0d1-65b5ca3d7e8c` |

### Finding Category: `tcp_port`

| Target | Match | Source Log |
|---|---|---|
| `pwnity` | `80` | `Log #394b3a71-5404-4a3e-a050-32d07949e168` |
| `google` | `631` | `Log #eee99320-27b9-4963-a0d1-65b5ca3d7e8c` |
| `google` | `80` | `Log #eee99320-27b9-4963-a0d1-65b5ca3d7e8c` |

