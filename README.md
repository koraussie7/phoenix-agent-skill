# 🔥 Phoenix Agent Skill

Turn any agent, bot, or process into an **immortal phoenix** — a self-healing daemon with:

- **3-layer defense**: systemd (boot) → watchdog (alive check) → link (cross-server)
- **Adaptive anomaly detection**: learns normal behavior, adjusts thresholds
- **Self-improving memory**: tracks death causes, fix success rates
- **Automatic resurrection**: agent dies → watchdog detects → restarts in <30s

## Quick Start

```bash
# One command setup:
python3 templates/setup_watchdog.py \
  --agent-name "my-bot" \
  --agent-cmd "/usr/bin/python3 /opt/bot.py" \
  --install

# Or manual:
cp templates/phoenix_template.py /opt/phoenix_my-bot.py
# Edit AGENT_NAME and AGENT_CMD at the top of the file
systemctl daemon-reload && systemctl enable my-bot.service phoenix-my-bot.service --now
```

## What's Included

| File | Purpose |
|---|---|
| `SKILL.md` | Full OpenClaw skill documentation |
| `templates/phoenix_template.py` | Watchdog daemon template |
| `templates/link_template.py` | Cross-server resurrection |
| `templates/agent.service` | systemd unit for agent |
| `templates/watchdog.service` | systemd unit for watchdog |
| `templates/link.service` | systemd unit for cross-server link |
| `templates/setup_watchdog.py` | One-command setup tool |

## Origin

Inspired by the **Hermes Nexus** postmortem — a 348-line self-healing AI that kept Hermes alive through a 3-layer defense system with adaptive thresholds, trajectory prediction, and cross-server knowledge sharing.

## Related

- Obsidian vault: `nexus-ai-agent-skill-a2f2351a` (full source code)
- Obsidian vault: `hermes-phoenix-mechanism-2918dc24` (phoenix autopsy)

---

**License:** MIT
