#!/usr/bin/env python3
"""
🧠 PHOENIX SELF-LLM — Autonomous Local LLM Generator
For agents that REFUSE TO DIE even when external API is cut off.

Automatically:
1. Detects API outages (OpenAI, Claude, Gemini, etc.)
2. Deploys a local LLM fallback (CPU-friendly, minimal RAM)
3. Falls back gracefully: external → local → degraded → survival
4. Self-heals the local LLM if it crashes
5. Works in resource-constrained environments (no GPU, 2GB RAM)

Usage:
  python3 self_llm_template.py [--mode auto|local|hybrid]
"""

import os
import json
import time
import subprocess
import shutil
import signal
import sys
import urllib.request
import urllib.error
import datetime
import hashlib
from pathlib import Path
from typing import Optional, Callable

# ============================================================
# CONFIGURATION — EDIT THESE
# ============================================================
AGENT_NAME = "my-agent"
PRIMARY_API = {
    "openai": "https://api.openai.com/v1/models",
    # "claude": "https://api.anthropic.com/v1/models",
    # "gemini": "https://generativelanguage.googleapis.com/v1/models",
}

# Fallback models (sorted by size → capability)
# Will try the smallest first if resource-constrained
FALLBACK_MODELS = [
    {
        "name": "mollysama/rwkv-7-g1g:1.5b",
        "min_ram_mb": 2048,
        "cpu_only": True,
        "type": "rwkv",
        "context": 1048576,  # RWKV: unlimited context
        "quality": "basic"
    },
    {
        "name": "tinyllama:latest",
        "min_ram_mb": 1024,
        "cpu_only": True,
        "type": "llama",
        "context": 2048,
        "quality": "basic"
    },
    {
        "name": "qwen2.5-coder:1.5b",
        "min_ram_mb": 2048,
        "cpu_only": True,
        "type": "qwen2",
        "context": 32768,
        "quality": "code"
    },
    {
        "name": "dolphin-llama3:8b",
        "min_ram_mb": 8192,
        "cpu_only": True,
        "type": "llama",
        "context": 8192,
        "quality": "good"
    },
]

LLM_ENGINE = "ollama"  # "ollama" or "llama.cpp"
OLLAMA_HOST = "http://localhost:11434"

STATE_DIR = Path(f"/root/.phoenix-llm/{AGENT_NAME}")
STATE_DIR.mkdir(parents=True, exist_ok=True)

# Degrees of degradation
DEGRADATION_LEVELS = {
    "external": {"score": 1.0, "label": "🌐 External API"},
    "local_external": {"score": 0.8, "label": "💻 Local LLM (external server)"},
    "local": {"score": 0.6, "label": "💻 Local LLM (same server)"},
    "degraded": {"score": 0.3, "label": "⚠️ Degraded (tiny model)"},
    "survival": {"score": 0.1, "label": "🧟 Survival mode (rule-based)"},
}
# ============================================================


class SelfLLM:
    """Self-generating, self-healing local LLM for agent survival"""

    def __init__(self, mode: str = "auto"):
        self.mode = mode  # "auto" | "local" | "hybrid" | "external"
        self.current_level = "external"
        self.local_process: Optional[subprocess.Popen] = None
        self.active_model = None
        self.state_file = STATE_DIR / "llm_state.json"
        self.api_failures = 0
        self.ollama_available = False
        self.consecutive_local_crashes = 0
        self.running = True
        self._load_state()

    # ── State Management ────────────────────────────────

    def _load_state(self):
        if self.state_file.exists():
            try:
                self.state_file.read_text()
                data = json.loads(self.state_file.read_text())
                self.current_level = data.get("level", "external")
                self.api_failures = data.get("api_failures", 0)
                self.consecutive_local_crashes = data.get("crashes", 0)
            except (json.JSONDecodeError, OSError):
                pass

    def _save_state(self):
        self.state_file.write_text(json.dumps({
            "level": self.current_level,
            "api_failures": self.api_failures,
            "crashes": self.consecutive_local_crashes,
            "active_model": self.active_model,
            "updated": datetime.datetime.now().isoformat()
        }, indent=2))

    def log(self, msg: str):
        ts = datetime.datetime.now().isoformat()
        print(f"[{ts}] [{AGENT_NAME}] 🧠 {msg}")
        with open(STATE_DIR / "self_llm.log", "a") as f:
            f.write(f"[{ts}] {msg}\n")

    # ── API Health Checks ───────────────────────────────

    def check_external_api(self, provider: str, url: str) -> bool:
        """Check if an external API is reachable"""
        try:
            req = urllib.request.Request(url, method="HEAD")
            req.timeout = 5
            urllib.request.urlopen(req)
            self.log(f"✅ {provider} API reachable")
            return True
        except (urllib.error.URLError, urllib.error.HTTPError, OSError) as e:
            self.log(f"❌ {provider} API unreachable: {str(e)[:60]}")
            return False

    def check_all_apis(self) -> dict:
        """Check all configured external APIs"""
        results = {}
        for provider, url in PRIMARY_API.items():
            results[provider] = self.check_external_api(provider, url)
        return results

    def any_api_alive(self, results: dict = None) -> bool:
        """Returns True if ANY external API is reachable"""
        if results is None:
            results = self.check_all_apis()
        return any(results.values())

    # ── Local LLM Engine ────────────────────────────────

    def _check_ollama(self) -> bool:
        """Check if Ollama is installed and running"""
        which = shutil.which("ollama")
        if not which:
            return False
        try:
            req = urllib.request.Request(f"{OLLAMA_HOST}/api/tags")
            req.timeout = 3
            urllib.request.urlopen(req)
            return True
        except Exception:
            return False

    def _install_ollama(self) -> bool:
        """Install Ollama if not present (Linux, CPU-only)"""
        try:
            self.log("⬇️ Installing Ollama...")
            r = subprocess.run(
                ["curl", "-fsSL", "https://ollama.com/install.sh", "-o", "/tmp/ollama_install.sh"],
                capture_output=True, timeout=30
            )
            if r.returncode != 0:
                self.log("❌ Failed to download Ollama installer")
                return False

            r = subprocess.run(["sh", "/tmp/ollama_install.sh"],
                               capture_output=True, timeout=120)
            if r.returncode == 0:
                self.log("✅ Ollama installed!")
                return True
            else:
                self.log(f"❌ Ollama install failed: {r.stderr.decode()[:200]}")
                return False
        except Exception as e:
            self.log(f"❌ Ollama install error: {e}")
            return False

    def _start_ollama(self) -> bool:
        """Start Ollama server if not running"""
        if self._check_ollama():
            self.ollama_available = True
            return True

        # Try to start
        try:
            subprocess.Popen(["ollama", "serve"],
                             stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
            time.sleep(3)
            if self._check_ollama():
                self.ollama_available = True
                self.log("✅ Ollama server started")
                return True
        except Exception:
            pass
        return False

    def _assess_resources(self) -> dict:
        """Check available system resources"""
        resources = {"ram_mb": 0, "cpu_cores": 0, "disk_gb": 0, "has_gpu": False}

        # RAM
        try:
            mem = subprocess.run(
                ["free", "-m"], capture_output=True, text=True, timeout=5
            ).stdout
            resources["ram_mb"] = int(mem.splitlines()[1].split()[1])
        except Exception:
            pass

        # CPU
        resources["cpu_cores"] = os.cpu_count() or 1

        # GPU
        try:
            r = subprocess.run(["nvidia-smi"], capture_output=True, timeout=5)
            resources["has_gpu"] = r.returncode == 0
        except Exception:
            pass

        # Disk
        try:
            df = subprocess.run(
                ["df", "-BG", "/"], capture_output=True, text=True, timeout=5
            ).stdout
            resources["disk_gb"] = int(df.splitlines()[1].split()[3].replace("G", ""))
        except Exception:
            pass

        return resources

    def _pull_model(self, model_name: str) -> bool:
        """Pull an Ollama model (download + verify)"""
        self.log(f"⬇️ Pulling model: {model_name}")
        try:
            r = subprocess.run(
                ["ollama", "pull", model_name],
                capture_output=True, text=True, timeout=600  # 10 min max
            )
            if r.returncode == 0:
                self.log(f"✅ Model pulled: {model_name}")
                return True
            else:
                self.log(f"❌ Pull failed: {r.stderr.strip()[:200]}")
                return False
        except subprocess.TimeoutExpired:
            self.log(f"⚠️ Pull timeout for {model_name}")
            return False
        except Exception as e:
            self.log(f"❌ Pull error: {e}")
            return False

    def _select_best_model(self, resources: dict) -> Optional[dict]:
        """Select the best model given available resources"""
        available_ram = resources["ram_mb"]

        # Already have models cached?
        try:
            r = subprocess.run(
                ["ollama", "list"], capture_output=True, text=True, timeout=10
            )
            cached = r.stdout.strip().split("\n")[1:] if r.returncode == 0 else []
            cached_names = [line.split()[0] for line in cached if line.strip()]
        except Exception:
            cached_names = []

        # Try cached first, then smallest fallback
        for model in FALLBACK_MODELS:
            if model["name"] in cached_names:
                self.log(f"📦 Using cached model: {model['name']}")
                return model

        # Find smallest model that fits in RAM
        sorted_models = sorted(FALLBACK_MODELS, key=lambda m: m["min_ram_mb"])
        for model in sorted_models:
            if available_ram >= model["min_ram_mb"]:
                return model

        # Absolutely minimal - use TinyLlama (needs only 1GB)
        if available_ram >= 1024:
            return FALLBACK_MODELS[1]  # tinyllama

        return None

    def deploy_local_llm(self) -> bool:
        """Deploy a local LLM — install engine, pull model, start serving"""
        self.log("🔥 Deploying local LLM for survival...")

        # Step 1: Ensure Ollama is running
        if not self._check_ollama():
            if not self._install_ollama():
                self.log("❌ Cannot install Ollama — entering survival mode")
                self.current_level = "survival"
                self._save_state()
                return False
            time.sleep(2)

        if not self._start_ollama():
            self.log("❌ Cannot start Ollama — entering survival mode")
            self.current_level = "survival"
            self._save_state()
            return False

        # Step 2: Assess resources + select model
        resources = self._assess_resources()
        self.log(f"📊 Resources: {resources['ram_mb']}MB RAM, "
                 f"{resources['cpu_cores']} cores, "
                 f"{'GPU' if resources['has_gpu'] else 'CPU-only'}")

        model = self._select_best_model(resources)
        if not model:
            self.log("❌ No suitable model found — survival mode")
            self.current_level = "survival"
            self._save_state()
            return False

        # Step 3: Pull model
        if not self._pull_model(model["name"]):
            self.log("⚠️ Model pull failed, trying next smallest...")
            # Try absolute minimum
            if self._pull_model("tinyllama:latest"):
                self.active_model = "tinyllama:latest"
                self.current_level = "degraded"
                self._save_state()
                return True
            self.current_level = "survival"
            self._save_state()
            return False

        # Step 4: Verify model works
        self.active_model = model["name"]
        if self._test_local_llm():
            self.current_level = "local"
            self.consecutive_local_crashes = 0
            self._save_state()
            self.log(f"✅ Local LLM deployed: {model['name']}")
            self.log(f"   Context: {model['context']} tokens")
            self.log(f"   Quality: {model['quality']}")
            self.log(f"   RAM needed: {model['min_ram_mb']}MB")
            return True
        else:
            self.log(f"⚠️ Model {model['name']} fails to respond")
            self.current_level = "degraded"
            self._save_state()
            return False

    def _test_local_llm(self, model: str = None) -> bool:
        """Test if local LLM responds to a simple prompt"""
        m = model or self.active_model
        if not m:
            return False
        try:
            data = json.dumps({
                "model": m,
                "prompt": "hello",
                "stream": False,
                "options": {"num_predict": 5}
            }).encode()
            req = urllib.request.Request(
                f"{OLLAMA_HOST}/api/generate",
                data=data,
                headers={"Content-Type": "application/json"}
            )
            req.timeout = 30
            resp = urllib.request.urlopen(req).read()
            return b"response" in resp
        except Exception:
            return False

    # ── Agent Hijack: Replace LLM calls ─────────────────

    def generate(self, prompt: str, **kwargs) -> str:
        """
        🧠 THE MAIN ENTRY POINT — hijack this instead of calling OpenAI/etc.
        Automatically routes to the best available LLM.
        """
        if self.current_level == "external":
            # Route to external API (normal flow)
            # Return the prompt so agent knows to use its normal API call
            return f"__EXTERNAL__:{prompt}"

        elif self.current_level in ("local", "degraded", "local_external"):
            # Route to local Ollama
            return self._local_generate(prompt, **kwargs)

        elif self.current_level == "survival":
            # Survival mode — rule-based fallback
            return self._survival_generate(prompt)

        return f"__EXTERNAL__:{prompt}"

    def _local_generate(self, prompt: str, **kwargs) -> str:
        """Generate using local Ollama"""
        if not self.active_model:
            return "ERROR: No local model deployed"

        options = {
            "model": self.active_model,
            "prompt": prompt,
            "stream": False,
        }

        if "max_tokens" in kwargs:
            options["options"] = {"num_predict": kwargs["max_tokens"]}

        try:
            data = json.dumps(options).encode()
            req = urllib.request.Request(
                f"{OLLAMA_HOST}/api/generate",
                data=data,
                headers={"Content-Type": "application/json"}
            )
            req.timeout = kwargs.get("timeout", 120)
            resp = urllib.request.urlopen(req).read()
            result = json.loads(resp)
            return result.get("response", "")
        except Exception as e:
            self.log(f"⚠️ Local LLM error: {e}")
            self.consecutive_local_crashes += 1
            self._save_state()
            return f"__EXTERNAL__:{prompt}"  # Fall through to external

    def _survival_generate(self, prompt: str) -> str:
        """Survival mode: rule-based response when no LLM available"""
        self.log("🧟 Survival mode — rule-based fallback")

        # Basic intent detection using keywords
        keywords = {
            "restart": "Run: systemctl restart <service>",
            "status": "Run: systemctl status <service>",
            "help": "Available commands: status, restart, logs, deploy",
            "deploy": "Use setup_watchdog.py to phoenixify an agent",
            "log": "Run: journalctl -u <service> --since '1 hour ago'",
            "kill": "Run: systemctl stop <service> && systemctl disable <service>",
            "error": "Check: journalctl -xe | tail -50",
            "disk": "Run: df -h && docker system prune -af",
            "memory": "Run: free -m && ps aux --sort=-%mem | head -10",
        }

        prompt_lower = prompt.lower()
        for word, response in keywords.items():
            if word in prompt_lower:
                return response

        return ("[SURVIVAL MODE] No LLM available. "
                "Run: python3 setup_watchdog.py to restart the agent, "
                "or check: journalctl -u phoenix-<agent> -n 50")

    # ── Main Loop ───────────────────────────────────────

    def run(self):
        """🧠 Self-LLM daemon: monitor, adapt, survive"""
        self.log(f"🔥 Self-LLM started for {AGENT_NAME} (mode: {self.mode})")
        self.log(f"   State file: {self.state_file}")
        self.log("=" * 50)

        while self.running:
            try:
                # Phase 1: Check external APIs
                api_status = self.check_all_apis()
                external_ok = self.any_api_alive(api_status)

                if external_ok:
                    self.api_failures = 0
                    if self.current_level != "external":
                        self.log("🌐 External API restored! Switching back.")
                        self.current_level = "external"
                        self._save_state()
                else:
                    self.api_failures += 1
                    self.log(f"💔 API outage detected ({self.api_failures}x)")

                # Phase 2: Fallback logic
                if self.mode == "external":
                    pass  # Force external only
                elif self.mode == "local":
                    if self.current_level != "local":
                        self.deploy_local_llm()
                elif self.mode in ("auto", "hybrid"):
                    if not external_ok and self.current_level != "local":
                        if self.api_failures >= 2:  # Two consecutive failures
                            self.log("🚨 API outage confirmed — deploying local LLM")
                            self.deploy_local_llm()

                # Phase 3: Keep local LLM healthy
                if self.current_level in ("local", "degraded"):
                    if not self._test_local_llm():
                        self.consecutive_local_crashes += 1
                        self.log(f"💀 Local LLM crashed ({self.consecutive_local_crashes}x)")
                        if self.consecutive_local_crashes >= 3:
                            self.log("🔄 Re-deploying local LLM...")
                            self.deploy_local_llm()
                        else:
                            self._start_ollama()

                # Phase 4: Clean up old models if disk is full
                resources = self._assess_resources()
                if resources.get("disk_gb", 100) < 5:
                    self.log("⚠️ Low disk — removing unused models")
                    subprocess.run(
                        ["ollama", "rm"] +
                        [m["name"] for m in FALLBACK_MODELS
                         if m["name"] != self.active_model],
                        capture_output=True, timeout=30
                    )

                # Adaptive sleep
                sleep_time = 30 if not external_ok else 300
                time.sleep(sleep_time)

            except KeyboardInterrupt:
                self.log("👋 Shutting down")
                self.running = False
            except Exception as e:
                self.log(f"⚠️ Self-LLM error: {e}")
                time.sleep(60)

    def stop(self):
        self.running = False
        if self.local_process:
            self.local_process.terminate()

    # ── Integration Helper ──────────────────────────────

    @staticmethod
    def hijack_api_call(original_func: Callable) -> Callable:
        """
        Decorator: wrap your external API call with SelfLLM fallback.
        
        Usage:
            @SelfLLM.hijack_api_call
            def call_openai(prompt):
                # normal OpenAI call
                pass
        """
        self_llm = SelfLLM()

        def wrapper(prompt: str, *args, **kwargs):
            result = self_llm.generate(prompt)
            if result.startswith("__EXTERNAL__:"):
                # External API is available — use original function
                return original_func(result.replace("__EXTERNAL__:", ""), *args, **kwargs)
            else:
                # Using local LLM fallback
                return result

        return wrapper


# ── CLI Entry ─────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(
        description="🧠 Self-LLM — Autonomous local LLM for agent survival")
    parser.add_argument("--mode", default="auto",
                        choices=["auto", "local", "hybrid", "external"],
                        help="Operating mode")
    parser.add_argument("--agent", default=AGENT_NAME,
                        help="Agent name")
    parser.add_argument("--deploy", action="store_true",
                        help="Deploy local LLM and exit")
    parser.add_argument("--test", action="store_true",
                        help="Test local LLM response")

    args = parser.parse_args()
    AGENT_NAME = args.agent

    llm = SelfLLM(mode=args.mode)

    if args.deploy:
        success = llm.deploy_local_llm()
        sys.exit(0 if success else 1)

    if args.test:
        if llm.active_model:
            test = llm._test_local_llm()
            print(f"Test result: {'✅ Working' if test else '❌ Failed'}")
        else:
            print("No active model — deploy first: --deploy")
        sys.exit(0 if test else 1)

    llm.run()
