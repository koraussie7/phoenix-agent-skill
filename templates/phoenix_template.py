#!/usr/bin/env python3
"""
🔥 PHOENIX WATCHDOG — Agent Self-Healing Engine
Inspired by Hermes Nexus (https://github.com/yangon/phoenix-agent-skill)

Usage:
  1. Edit AGENT_NAME and AGENT_CMD below
  2. Run: python3 phoenix_template.py
  3. Or register as systemd service (see SKILL.md)

The watchdog runs in a loop, checks if the agent is alive,
and restarts it if dead. Learns from failures over time.
"""

import os
import json
import time
import subprocess
import datetime
import sys
from pathlib import Path

# ============================================================
# CONFIGURATION — EDIT THESE
# ============================================================
AGENT_NAME = "my-agent"           # Used for pgrep detection
AGENT_CMD = [                     # Command to start the agent
    "/usr/bin/python3",
    "/opt/my-agent/main.py"
]
WATCH_INTERVAL = 60               # Normal check interval (seconds)
INCIDENT_INTERVAL = 30            # Check faster during incidents (seconds)
ESCALATION_THRESHOLD = 3          # Consecutive deaths before alert
# ============================================================

BASE = Path("/root/.phoenix-watchdog")
BASE.mkdir(parents=True, exist_ok=True)
MEMORY_DIR = Path("/root/.phoenix-memory")
MEMORY_DIR.mkdir(parents=True, exist_ok=True)


class PhoenixMemory:
    """Persistent learning from agent failures"""

    def __init__(self, agent_name: str):
        self.path = MEMORY_DIR / f"{agent_name}.json"
        self.data = {
            "agent": agent_name,
            "restarts": 0,
            "last_death": None,
            "last_restart": None,
            "common_causes": {},
            "fix_track": {},
            "consecutive_failures": 0,
            "learned_check_interval": WATCH_INTERVAL,
        }
        self.load()

    def load(self):
        if self.path.exists():
            try:
                self.data.update(json.loads(self.path.read_text()))
            except (json.JSONDecodeError, OSError):
                pass

    def save(self):
        self.path.write_text(json.dumps(self.data, indent=2, default=str))

    def record_death(self, cause: str = "unknown"):
        now = datetime.datetime.now().isoformat()
        self.data["last_death"] = now
        self.data["common_causes"][cause] = self.data["common_causes"].get(cause, 0) + 1
        self.data["consecutive_failures"] += 1
        self.save()

    def record_restart(self, success: bool = True):
        now = datetime.datetime.now().isoformat()
        self.data["restarts"] += 1
        self.data["last_restart"] = now
        if success:
            self.data["consecutive_failures"] = 0
        self.save()

    def should_escalate(self) -> bool:
        """Returns True if too many consecutive failures"""
        return self.data["consecutive_failures"] >= ESCALATION_THRESHOLD


class PhoenixWatchdog:
    """Self-healing watchdog daemon"""

    def __init__(self, name: str, cmd: list, interval: int = WATCH_INTERVAL):
        self.name = name
        self.cmd = cmd
        self.interval = interval
        self.memory = PhoenixMemory(name)
        self.running = True

    def log(self, msg: str):
        ts = datetime.datetime.now().isoformat()
        line = f"[{ts}] {msg}"
        with open(BASE / "watchdog.log", "a") as f:
            f.write(line + "\n")
        print(line)

    def is_alive(self) -> bool:
        """Check if agent process is running via pgrep"""
        try:
            r = subprocess.run(
                ["pgrep", "-f", self.name],
                capture_output=True, text=True, timeout=5
            )
            return bool(r.stdout.strip())
        except subprocess.TimeoutExpired:
            return False

    def restart(self) -> bool:
        """Restart the agent process"""
        try:
            subprocess.Popen(
                self.cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            time.sleep(2)
            alive = self.is_alive()
            self.memory.record_restart(success=alive)
            if alive:
                self.log(f"✅ {self.name} restarted successfully")
            else:
                self.log(f"⚠️ {self.name} restart may have failed")
            return alive
        except Exception as e:
            self.log(f"❌ Failed to restart {self.name}: {e}")
            self.memory.record_restart(success=False)
            return False

    def investigate(self):
        """Try to determine why the agent died"""
        causes = []
        # Check OOM
        try:
            r = subprocess.run(
                ["dmesg", "--level=err,warn", "--since", "5 minutes ago"],
                capture_output=True, text=True, timeout=5
            )
            if "Out of memory" in r.stdout or "oom" in r.stdout.lower():
                causes.append("oom_kill")
        except Exception:
            pass
        # Check systemd
        try:
            r = subprocess.run(
                ["journalctl", "-u", f"{self.name}.service", "-n", "10",
                 "--no-pager", "--since", "5 minutes ago"],
                capture_output=True, text=True, timeout=5
            )
            if "Exit" in r.stdout:
                import re
                exit_codes = re.findall(r"Exit code=(\d+)", r.stdout)
                if exit_codes:
                    causes.append(f"exit_code_{exit_codes[-1]}")
        except Exception:
            pass
        cause = causes[-1] if causes else "unknown"
        self.memory.record_death(cause)
        return cause

    def run(self):
        self.log(f"🔥 Phoenix Watchdog started for {self.name}")
        self.log(f"   Cmd: {' '.join(self.cmd)}")
        self.log(f"   Interval: {self.interval}s")
        self.log(f"   Memory: {self.memory.path}")
        self.log("=" * 50)

        while self.running:
            try:
                if not self.is_alive():
                    self.log(f"💀 {self.name} is DEAD — investigating...")
                    cause = self.investigate()
                    self.log(f"   Cause: {cause}")
                    self.restart()
                    if self.memory.should_escalate():
                        self.log(f"🚨 {self.name} crashed {ESCALATION_THRESHOLD}+ times!"
                                 " Manual intervention needed!")

                sleep_time = (INCIDENT_INTERVAL if not self.is_alive()
                              else self.interval)
                time.sleep(sleep_time)

            except KeyboardInterrupt:
                self.log(f"👋 Phoenix Watchdog for {self.name} shutting down")
                self.running = False
            except Exception as e:
                self.log(f"⚠️ Watchdog error: {e}")
                time.sleep(self.interval)

    def stop(self):
        self.running = False


if __name__ == "__main__":
    watchdog = PhoenixWatchdog(AGENT_NAME, AGENT_CMD)
    watchdog.run()
