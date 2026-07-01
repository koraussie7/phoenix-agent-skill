#!/usr/bin/env python3
"""
🔥 Phoenix Watchdog Setup Script
One-command setup: turns any agent into an immortal phoenix.

Usage:
  python3 setup_watchdog.py \\
    --agent-name "my-bot" \\
    --agent-cmd "/usr/bin/python3 /opt/bot.py" \\
    --install
"""

import argparse
import os
import shutil
import subprocess
from pathlib import Path


def setup(args):
    name = args.agent_name
    cmd = args.agent_cmd

    # Resolve template paths
    script_dir = Path(__file__).parent.resolve()

    # 1. Copy and configure watchdog script
    watchdog_dir = Path("/opt/phoenix-watchdog")
    watchdog_dir.mkdir(parents=True, exist_ok=True)

    watchdog_src = script_dir / "phoenix_template.py"
    watchdog_dst = watchdog_dir / f"phoenix_{name}.py"
    shutil.copy(watchdog_src, watchdog_dst)

    # Read and patch
    content = watchdog_dst.read_text()
    content = content.replace('AGENT_NAME = "my-agent"', f'AGENT_NAME = "{name}"')
    content = content.replace(
        '    "/usr/bin/python3",\n    "/opt/my-agent/main.py"\n]',
        f"[\n    {', '.join(repr(c) for c in cmd.split())}\n]"
    )
    if args.interval:
        content = content.replace(
            "WATCH_INTERVAL = 60",
            f"WATCH_INTERVAL = {args.interval}"
        )
    watchdog_dst.write_text(content)
    os.chmod(watchdog_dst, 0o755)
    print(f"✅ Watchdog script: {watchdog_dst}")

    # 2. Setup systemd service for agent
    service_content = f"""[Unit]
Description={name} (Phoenix — Self-Healing Agent)
After=network.target

[Service]
Type=simple
ExecStart={cmd}
Restart=always
RestartSec=3
StartLimitIntervalSec=60
StartLimitBurst=5
OOMScoreAdjust=-500
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
"""
    service_path = Path(f"/etc/systemd/system/{name}.service")
    service_path.write_text(service_content)
    print(f"✅ Agent service: {service_path}")

    # 3. Setup systemd service for watchdog
    watchdog_service_content = f"""[Unit]
Description=Phoenix Watchdog for {name}
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 {watchdog_dst}
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
"""
    watchdog_service_path = Path(f"/etc/systemd/system/phoenix-{name}.service")
    watchdog_service_path.write_text(watchdog_service_content)
    print(f"✅ Watchdog service: {watchdog_service_path}")

    if args.install:
        subprocess.run(["systemctl", "daemon-reload"], check=True)
        subprocess.run(["systemctl", "enable", f"{name}.service"], check=True)
        subprocess.run(["systemctl", "start", f"{name}.service"], check=True)
        subprocess.run(["systemctl", "enable", f"phoenix-{name}.service"], check=True)
        subprocess.run(["systemctl", "start", f"phoenix-{name}.service"], check=True)
        print(f"\n🔥 {name} is now a PHOENIX!")
        print(f"   systemctl status {name}.service")
        print(f"   systemctl status phoenix-{name}.service")
        print(f"   journalctl -u phoenix-{name} -f  (watch watchdog)")


def main():
    parser = argparse.ArgumentParser(
        description="🔥 Phoenix Watchdog — Turn any agent into an immortal phoenix",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 setup_watchdog.py --agent-name "discord-bot" --agent-cmd "/usr/bin/python3 /opt/bot.py" --install
  python3 setup_watchdog.py --agent-name "node-server" --agent-cmd "/usr/bin/node /opt/server.js" --interval 30
        """
    )
    parser.add_argument("--agent-name", required=True, help="Agent name (used for pgrep detection)")
    parser.add_argument("--agent-cmd", required=True, help="Full command to start the agent (e.g. '/usr/bin/python3 /opt/bot.py')")
    parser.add_argument("--interval", type=int, default=60, help="Watchdog check interval in seconds (default: 60)")
    parser.add_argument("--no-install", action="store_true", help="Skip systemctl enable/start")
    args = parser.parse_args()
    args.install = not args.no_install
    setup(args)


if __name__ == "__main__":
    main()
