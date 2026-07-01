---
name: phoenix-agent-skill
description: "🔥 Phoenix Agent — Turn any agent/process into an immortal self-healing daemon with 3-layer defense, ML-based anomaly detection, and cross-server resurrection."
metadata:
  openclaw:
    emoji: "🔥"
    requires:
      bins: ["python3", "systemctl"]
    install:
      - id: git
        kind: git
        repo: "https://github.com/yangon/phoenix-agent-skill"
        bins: ["python3"]
        label: "Clone Phoenix Agent Skill"
---

# 🔥 Phoenix Agent Skill

Turn any agent, bot, or process into an **immortal phoenix** — a self-healing daemon with 3-layer defense, adaptive threshold learning, and optional cross-server resurrection.

Inspired by the **Hermes Nexus** autopsies (see `hermes-phoenix-mechanism` in Obsidian vault).

---

## 📐 Architecture

```
┌───────────────────────────────────────────┐
│         PHOENIX AGENT SYSTEM              │
│                                           │
│  Layer 3: Cross-Server Link (optional)    │
│  ┌─────────────────────────────────────┐  │
│  │ link_<agent>.py   ──  SSH tunnel    │  │
│  │ Sync: 5min intervals                │  │
│  └──────────┬──────────────────────────┘  │
│             │                              │
│  Layer 2: Phoenix Watchdog (daemon)       │
│  ┌──────────▼──────────────────────────┐  │
│  │ phoenix_<agent>.py                  │  │
│  │ - Sense: every 30-120s              │  │
│  │ - Think: adaptive thresholds        │  │
│  │ - Act: auto-restart + cleanup       │  │
│  │ - Learn: success rate tracking      │  │
│  └──────────┬──────────────────────────┘  │
│             │                              │
│  Layer 1: systemd (foundation)             │
│  ┌──────────▼──────────────────────────┐  │
│  │ <agent>.service                     │  │
│  │ - Restart=always                    │  │
│  │ - RestartSec=3                      │  │
│  │ - OOMScoreAdjust=-500               │  │
│  └─────────────────────────────────────┘  │
└───────────────────────────────────────────┘
```

## 🧩 Components

| Layer | Component | File | Purpose |
|---|---|---|---|
| 1 | systemd Service | `<agent>.service` | Boot-time auto-start, Restart=always |
| 2 | Phoenix Watchdog | `phoenix_<agent>.py` | Alive check, auto-restart, adaptive thresholds |
| 3 | Cross-server Link | `link_<agent>.py` | Multi-server resurrection (optional) |
| - | Memory Core | `PhoenixMemory` class | JSON-based persistent learning |
| - | Template | `phoenix_template.py` | Ready-to-edit watchdog stub |

## 🚀 Quick Start

### Step 1: Apply Phoenix to any agent

```bash
# Copy the template
cp templates/phoenix_template.py /opt/my-agent/phoenix_my_agent.py

# Edit: change AGENT_NAME and AGENT_CMD
sed -i 's/AGENT_NAME = "my-agent"/AGENT_NAME = "my-bot"/' /opt/my-agent/phoenix_my_agent.py
sed -i 's|AGENT_CMD = \["\/usr\/bin\/python3", "\/opt\/my-agent\/main.py"\]|AGENT_CMD = ["\/usr\/bin\/node", "\/opt\/my-bot\/index.js"]|' /opt/my-agent/phoenix_my_agent.py

# Register systemd service
cp templates/agent.service.template /etc/systemd/system/my-bot.service
sed -i 's|AGENT_NAME|my-bot|g' /etc/systemd/system/my-bot.service
sed -i 's|AGENT_CMD|/usr/bin/node /opt/my-bot/index.js|g' /etc/systemd/system/my-bot.service

systemctl daemon-reload
systemctl enable my-bot.service --now

# Register watchdog
cp templates/watchdog.service.template /etc/systemd/system/phoenix-my-bot.service
systemctl enable phoenix-my-bot.service --now
```

### Step 2: One-liner for quick setup

```bash
# For Python agents
phoenixify() {
  local name=$1 cmd=$2
  cat > /etc/systemd/system/$name.service << EOF
[Unit]
Description=$name (Phoenix)
After=network.target

[Service]
Type=simple
ExecStart=$cmd
Restart=always
RestartSec=3
OOMScoreAdjust=-500
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF
  systemctl daemon-reload && systemctl enable $name.service --now
  echo "🔥 $name is now a phoenix"
}

# Usage:
# phoenixify "my-bot" "/usr/bin/python3 /opt/bot.py"
# phoenixify "my-node" "/usr/bin/node /opt/server.js"
```

### Step 3: Add watchdog (recommended for critical agents)

```bash
python3 templates/setup_watchdog.py \
  --agent-name "my-bot" \
  --agent-cmd "/usr/bin/python3 /opt/bot.py" \
  --interval 60 \
  --install
```

## 📁 File Reference

### `phoenix_template.py`

Core watchdog daemon. Edit `AGENT_NAME` and `AGENT_CMD` at the top:

```python
#!/usr/bin/env python3
"""
🔥 PHOENIX WATCHDOG — Agent Self-Healing Engine
Inspired by Hermes Nexus (https://github.com/yangon/phoenix-agent-skill)
"""

import os, json, time, subprocess, datetime
from pathlib import Path

BASE = Path("/root/.phoenix-watchdog")
BASE.mkdir(parents=True, exist_ok=True)

AGENT_NAME = "my-agent"           # ← CHANGE THIS
AGENT_CMD = [                     # ← CHANGE THIS
    "/usr/bin/python3",
    "/opt/my-agent/main.py"
]
WATCH_INTERVAL = 60               # seconds between checks
ESCLATION_THRESHOLD = 3           # consecutive deaths before alert
```

Full features:
- **Alive check** via `pgrep -f <agent_name>`
- **Adaptive sleep**: 30s during incidents, 120s when stable
- **Incident memory**: JSON log of all deaths/causes
- **Escalation**: alert after 3+ consecutive failures
- **Learned thresholds**: adjusts check frequency based on stability

### `link_template.py`

Cross-server resurrection daemon. One server can revive the other:

```python
#!/usr/bin/env python3
"""
🌐 PHOENIX LINK — Cross-server agent resurrection
"""
import subprocess, time

REMOTE_HOST = "192.168.1.100"
REMOTE_AGENT = "my-bot"
REMOTE_PORT = 22
SSH_KEY = "/root/.ssh/id_ed25519"

def check_and_resurrect():
    cmd = [
        "ssh", "-i", SSH_KEY,
        f"root@{REMOTE_HOST}",
        f"pgrep -f {REMOTE_AGENT} || systemctl restart {REMOTE_AGENT}"
    ]
    subprocess.run(cmd, capture_output=True, timeout=10)

while True:
    check_and_resurrect()
    time.sleep(300)  # 5 min
```

### `PhoenixMemory` class (for advanced users)

```python
class PhoenixMemory:
    """Persistent learning from agent failures"""
    def __init__(self, agent_name):
        self.path = Path(f"/root/.phoenix-memory/{agent_name}.json")
        self.data = {
            "restarts": 0,
            "last_death": None,
            "common_causes": {},
            "fix_success_rates": {},
            "learned_check_interval": 60
        }
        self.load()
    
    def record_death(self, cause="unknown"):
        self.data["restarts"] += 1
        self.data["last_death"] = datetime.datetime.now().isoformat()
        self.data["common_causes"][cause] = self.data["common_causes"].get(cause, 0) + 1
        self.save()
        return self.data["restarts"] >= ESCLATION_THRESHOLD  # → escalate
```

## 🔧 Templates

### `agent.service.template`

```ini
[Unit]
Description=AGENT_NAME (Phoenix)
After=network.target

[Service]
Type=simple
ExecStart=AGENT_CMD
Restart=always
RestartSec=3
OOMScoreAdjust=-500
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

### `watchdog.service.template`

```ini
[Unit]
Description=Phoenix Watchdog for AGENT_NAME
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 /opt/phoenix-watchdog/phoenix_AGENT_NAME.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### `link.service.template`

```ini
[Unit]
Description=Phoenix Link for AGENT_NAME
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 /opt/phoenix-link/link_AGENT_NAME.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

## 🧪 CLI Usage

```bash
# List all phoenix agents
systemctl list-units --type=service --state=running | grep -i phoenix

# Check watchdog log
journalctl -u phoenix-my-bot --since "1 hour ago"

# Force restart an agent
systemctl restart my-bot

# Check resurrection history
cat /root/.phoenix-memory/my-bot.json

# Remove phoenix (disable)
systemctl disable my-bot.service --now
systemctl disable phoenix-my-bot.service --now
rm /etc/systemd/system/{my-bot,phoenix-my-bot}.service
systemctl daemon-reload
```

## 📚 Related Obsidian Notes

- `nexus-ai-agent-skill-a2f2351a` — Full Nexus AI source code + architecture
- `hermes-phoenix-mechanism-2918dc24` — Hermes autopsy: 3-layer defense analysis

## ⚠️ Notes

- **Restart=always loop protection**: Add `StartLimitIntervalSec=60` and `StartLimitBurst=3` to service file if agent crashes repeatedly
- **Cross-server loop prevention**: Set `max_restarts` per agent; alert human after threshold
- **Log management**: Watchdog logs at `/root/.phoenix-watchdog/watchdog.log` — set up logrotate
- **OOM**: `OOMScoreAdjust=-500` reduces OOM killer priority; pair with `MemoryMax=` in systemd
