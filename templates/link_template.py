#!/usr/bin/env python3
"""
🌐 PHOENIX LINK — Cross-server agent resurrection daemon

One server can revive the agent on another server if it dies.
Prevents total blackout when a single server goes down.

Usage:
  1. Edit REMOTE_HOST, REMOTE_AGENT, SSH_KEY
  2. Run: python3 link_template.py
  3. Requires passwordless SSH to remote server
"""

import subprocess
import time
import datetime
from pathlib import Path

# ============================================================
# CONFIGURATION
# ============================================================
LOCAL_NAME = "225-server"
REMOTE_HOST = "192.168.1.100"
REMOTE_PORT = 22
REMOTE_AGENT = "my-bot"
REMOTE_SERVICE = "my-bot.service"  # systemd service name (optional)
SSH_KEY = "/root/.ssh/id_ed25519"
SSH_USER = "root"
CHECK_INTERVAL = 300  # 5 minutes

LOG_DIR = Path("/var/log/phoenix-link")
LOG_DIR.mkdir(parents=True, exist_ok=True)
# ============================================================


class PhoenixLink:
    def __init__(self):
        self.log_file = LOG_DIR / f"link_{REMOTE_AGENT}.log"

    def log(self, msg: str):
        ts = datetime.datetime.now().isoformat()
        line = f"[{ts}] [{LOCAL_NAME}→{REMOTE_HOST}] {msg}"
        with open(self.log_file, "a") as f:
            f.write(line + "\n")
        print(line)

    def check_and_resurrect(self) -> bool:
        """Check remote agent and restart if dead"""
        try:
            # First check if agent process is alive
            check_cmd = [
                "ssh", "-i", SSH_KEY,
                "-o", "StrictHostKeyChecking=no",
                "-o", "ConnectTimeout=10",
                "-p", str(REMOTE_PORT),
                f"{SSH_USER}@{REMOTE_HOST}",
                f"pgrep -f {REMOTE_AGENT}"
            ]
            r = subprocess.run(check_cmd, capture_output=True, text=True, timeout=15)

            if r.returncode == 0 and r.stdout.strip():
                self.log(f"✅ {REMOTE_AGENT} is alive on remote")
                return True
            else:
                self.log(f"💀 {REMOTE_AGENT} is DEAD on remote — resurrecting...")

                # Try systemd first (cleaner)
                systemd_cmd = [
                    "ssh", "-i", SSH_KEY,
                    "-p", str(REMOTE_PORT),
                    f"{SSH_USER}@{REMOTE_HOST}",
                    f"systemctl start {REMOTE_SERVICE}"
                ]
                sd_r = subprocess.run(systemd_cmd, capture_output=True, text=True, timeout=15)

                if sd_r.returncode == 0:
                    time.sleep(3)
                    # Verify
                    v = subprocess.run([
                        "ssh", "-i", SSH_KEY,
                        "-p", str(REMOTE_PORT),
                        f"{SSH_USER}@{REMOTE_HOST}",
                        f"pgrep -f {REMOTE_AGENT}"
                    ], capture_output=True, text=True, timeout=10)
                    alive = v.returncode == 0 and bool(v.stdout.strip())
                    self.log(f"{'✅' if alive else '❌'} Remote resurrection "
                             f"{'succeeded' if alive else 'failed'}")
                    return alive
                else:
                    self.log(f"❌ systemctl failed: {sd_r.stderr.strip()[:200]}")
                    return False

        except subprocess.TimeoutExpired:
            self.log(f"⚠️ SSH timeout — remote unreachable")
            return False
        except Exception as e:
            self.log(f"⚠️ Error: {e}")
            return False

    def run(self):
        self.log(f"🌐 Phoenix Link started: {LOCAL_NAME} → {REMOTE_AGENT}@{REMOTE_HOST}")
        self.log(f"   Interval: {CHECK_INTERVAL}s")
        self.log(f"   SSH Key: {SSH_KEY}")
        self.log("=" * 50)

        while True:
            try:
                self.check_and_resurrect()
                time.sleep(CHECK_INTERVAL)
            except KeyboardInterrupt:
                self.log("👋 Shutting down")
                break
            except Exception as e:
                self.log(f"⚠️ Link error: {e}")
                time.sleep(60)


if __name__ == "__main__":
    link = PhoenixLink()
    link.run()
