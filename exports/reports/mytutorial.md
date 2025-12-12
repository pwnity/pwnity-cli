# pwnity Report: mytutorial
Generated on: 2025-12-11 23:54:26

## Notes

- **[2025-12-11 | Target: moonandhoney.de]** I found something cool on /foo.bar

## Loot

- **Type:** `credentials` | **Target:** `moonandhoney.de`
  - **Value:** `admin:password`
- **Type:** `flag` | **Target:** `moonandhoney.de`
  - **Value:** `^FLAG:1234`
- **Type:** `foofoo` | **Target:** `moonandhoney.de`
  - **Value:** `^FLAG:1234`
- **Type:** `^FLAG:1234` | **Target:** `moonandhoney.de`
  - **Value:** ``

## Parser Findings

- **Category:** `ipv4` | **Target:** `moonandhoney.de` | **Source:** `Log #ded0a599-2016-4537-83aa-b827a2c61884`
  - **Match:** `58.62.205.92`
- **Category:** `ipv4` | **Target:** `moonandhoney.de` | **Source:** `Log #ded0a599-2016-4537-83aa-b827a2c61884`
  - **Match:** `92.205.62.58`
- **Category:** `hostname` | **Target:** `moonandhoney.de` | **Source:** `Log #ded0a599-2016-4537-83aa-b827a2c61884`
  - **Match:** `58.62.205.92.host.secureserver.net`
- **Category:** `tcp_port` | **Target:** `moonandhoney.de` | **Source:** `Log #ded0a599-2016-4537-83aa-b827a2c61884`
  - **Match:** `135`
- **Category:** `tcp_port` | **Target:** `moonandhoney.de` | **Source:** `Log #ded0a599-2016-4537-83aa-b827a2c61884`
  - **Match:** `139`
- **Category:** `tcp_port` | **Target:** `moonandhoney.de` | **Source:** `Log #ded0a599-2016-4537-83aa-b827a2c61884`
  - **Match:** `22`
- **Category:** `tcp_port` | **Target:** `moonandhoney.de` | **Source:** `Log #ded0a599-2016-4537-83aa-b827a2c61884`
  - **Match:** `443`
- **Category:** `tcp_port` | **Target:** `moonandhoney.de` | **Source:** `Log #ded0a599-2016-4537-83aa-b827a2c61884`
  - **Match:** `445`
- **Category:** `tcp_port` | **Target:** `moonandhoney.de` | **Source:** `Log #ded0a599-2016-4537-83aa-b827a2c61884`
  - **Match:** `631`
- **Category:** `tcp_port` | **Target:** `moonandhoney.de` | **Source:** `Log #ded0a599-2016-4537-83aa-b827a2c61884`
  - **Match:** `80`
- **Category:** `service_name` | **Target:** `moonandhoney.de` | **Source:** `Log #ded0a599-2016-4537-83aa-b827a2c61884`
  - **Match:** `ssh`
- **Category:** `service_version` | **Target:** `moonandhoney.de` | **Source:** `Log #ded0a599-2016-4537-83aa-b827a2c61884`
  - **Match:** `445/tcp filtered microsoft-ds`
- **Category:** `service_version` | **Target:** `moonandhoney.de` | **Source:** `Log #ded0a599-2016-4537-83aa-b827a2c61884`
  - **Match:** `80/tcp  open     http`
