#!/usr/bin/env python3
"""
SecureBot CLI - Terminal TUI chat interface
"""

import curses
import threading
import time
import os
import sys
import json
import logging
import traceback
import subprocess
import datetime
import shutil
import re
import textwrap

# ── stdlib HTTP ──────────────────────────────────────────────────────────────
import urllib.request
import urllib.parse
import urllib.error

# ── Config ───────────────────────────────────────────────────────────────────
GATEWAY_URL           = "http://localhost:8080"
VAULT_URL             = "http://localhost:8200"
RAG_URL               = "http://localhost:8400"
USER_ID               = "roland"
MEMORY_DIR            = os.path.expanduser("~/securebot/memory")
VAULT_SECRETS         = os.path.expanduser("~/securebot/vault/secrets/secrets.json")
PREFS_FILE            = os.path.expanduser("~/.securebot-cli-prefs.json")
RESPONSE_MODEL        = os.getenv("RESPONSE_MODEL", "llama3.2:3b")  # overridden below after .env loads
REFRESH_INTERVAL      = 3
MAX_CHAT_LINES        = 100
SYSTEM_PROMPT_REFRESH = 30

DRAW_LOG = "/tmp/securebot-draw.log"

# ── HMAC signing ──────────────────────────────────────────────────────────────
import hmac
import hashlib
import secrets as _secrets

def _load_service_secret() -> str:
    """Read SERVICE_SECRET from ~/securebot/.env"""
    env_path = os.path.expanduser("~/securebot/.env")
    try:
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line.startswith("SERVICE_SECRET="):
                    return line.split("=", 1)[1].strip()
    except Exception:
        pass
    return os.getenv("SERVICE_SECRET", "")

SERVICE_SECRET = _load_service_secret()
SERVICE_ID     = "gateway"  # CLI signs as gateway service


def _load_gateway_api_key() -> str:
    """Read GATEWAY_API_KEY from ~/securebot/.env"""
    env_path = os.path.expanduser("~/securebot/.env")
    try:
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line.startswith("GATEWAY_API_KEY="):
                    return line.split("=", 1)[1].strip()
    except Exception:
        pass
    return os.getenv("GATEWAY_API_KEY", "")


GATEWAY_API_KEY = _load_gateway_api_key()


def _load_response_model() -> str:
    """Read RESPONSE_MODEL from ~/securebot/.env, falling back to env var then default."""
    env_path = os.path.expanduser("~/securebot/.env")
    try:
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line.startswith("RESPONSE_MODEL="):
                    return line.split("=", 1)[1].strip()
    except Exception:
        pass
    return os.getenv("RESPONSE_MODEL", "llama3.2:3b")


RESPONSE_MODEL = _load_response_model()  # read dynamically from .env


def _sign_headers(method: str, path: str) -> dict:
    """Generate HMAC auth headers matching common/auth.py sign_request()"""
    if not SERVICE_SECRET:
        return {}
    timestamp = str(int(time.time()))
    nonce     = _secrets.token_hex(8)
    message   = f"{SERVICE_ID}:{timestamp}:{nonce}:{method.upper()}:{path}"
    signature = hmac.new(
        SERVICE_SECRET.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()
    return {
        "X-Service-ID": SERVICE_ID,
        "X-Timestamp":  timestamp,
        "X-Nonce":      nonce,
        "X-Signature":  f"sha256={signature}"
    }

def http_get(url: str, headers: dict = None, timeout: int = 5, signed: bool = False):
    """HTTP GET with optional HMAC signing. Returns parsed JSON or raises."""
    req_headers = {"Accept": "application/json"}
    if headers:
        req_headers.update(headers)
    if signed:
        path = urllib.parse.urlparse(url).path
        req_headers.update(_sign_headers("GET", path))
    req = urllib.request.Request(url, headers=req_headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())

def http_post(url: str, payload: dict, headers: dict = None, timeout: int = 30, signed: bool = False):
    """HTTP POST with optional HMAC signing. Returns parsed JSON or raises."""
    req_headers = {"Content-Type": "application/json"}
    if headers:
        req_headers.update(headers)
    if signed:
        path = urllib.parse.urlparse(url).path
        req_headers.update(_sign_headers("POST", path))
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers=req_headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    filename="/tmp/securebot-cli.log",
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(message)s",
)

# ── psutil ensure ─────────────────────────────────────────────────────────────
def _ensure_psutil():
    global psutil
    try:
        import psutil as _p
        psutil = _p
    except ImportError:
        logging.warning("psutil not found, installing...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "psutil", "-q"])
        import psutil as _p
        psutil = _p

_ensure_psutil()

# ── Color pair IDs ────────────────────────────────────────────────────────────
C_HEADER  = 1
C_USER    = 2
C_BOT     = 3
C_DIM     = 4
C_GREEN   = 5
C_YELLOW  = 6
C_RED     = 7
C_CYAN    = 8
C_MAGENTA = 9
C_BOLD    = 10

# ── Tuning descriptions ───────────────────────────────────────────────────────
TONE_DESCRIPTIONS = {
    1: "Use formal, precise language. No contractions or colloquialisms.",
    2: "Be helpful and professional but approachable. Natural tone.",
    3: "Be friendly and conversational. Contractions fine, relaxed tone.",
}
VERBOSITY_DESCRIPTIONS = {
    1: "1-3 sentences maximum. Just the answer, no explanation.",
    2: "Answer directly with minimal elaboration. Skip preamble.",
    3: "Complete answers with necessary context. No padding.",
    4: "Thorough with examples and context. Anticipate follow-ups.",
    5: "Comprehensive and conversational. Elaborate freely.",
}

SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

# ── ChatBuffer ────────────────────────────────────────────────────────────────
class ChatBuffer:
    def __init__(self):
        self._lines = []
        self._lock  = threading.Lock()

    def add(self, text: str, color: int = 0):
        with self._lock:
            self._lines.append((text, color))
            if len(self._lines) > MAX_CHAT_LINES:
                self._lines = self._lines[-MAX_CHAT_LINES:]

    def get_lines(self):
        with self._lock:
            return list(self._lines)

    def clear(self):
        with self._lock:
            self._lines.clear()

# ── Prefs ─────────────────────────────────────────────────────────────────────
class Prefs:
    def __init__(self):
        self.tone      = 2
        self.verbosity = 3
        self._load()

    def _load(self):
        try:
            if os.path.exists(PREFS_FILE):
                with open(PREFS_FILE) as f:
                    d = json.load(f)
                self.tone      = d.get("tone", 2)
                self.verbosity = d.get("verbosity", 3)
        except Exception as e:
            logging.warning(f"Prefs load error: {e}")

    def save(self):
        try:
            with open(PREFS_FILE, "w") as f:
                json.dump({"tone": self.tone, "verbosity": self.verbosity}, f)
        except Exception as e:
            logging.warning(f"Prefs save error: {e}")

# ── ResourceMonitor ───────────────────────────────────────────────────────────
class ResourceMonitor:
    def __init__(self, redraw_event: threading.Event):
        self._event    = redraw_event
        self._lock     = threading.Lock()
        self._snapshot = {}
        self._thread   = threading.Thread(target=self._run, daemon=True)
        self._running  = True

    def start(self):
        # Prime cpu_percent so first sample isn't 0
        psutil.cpu_percent(interval=None)
        self._thread.start()

    def stop(self):
        self._running = False

    def snapshot(self):
        with self._lock:
            return dict(self._snapshot)

    def _run(self):
        time.sleep(0.5)  # allow cpu_percent prime to settle
        while self._running:
            data = {}
            try:
                data["cpu"]  = psutil.cpu_percent(interval=1)
                vm            = psutil.virtual_memory()
                data["ram"]  = vm.percent
                try:
                    data["disk_home"] = psutil.disk_usage(
                        os.path.expanduser("~")).percent
                except Exception:
                    data["disk_home"] = None
                try:
                    data["disk_root"] = psutil.disk_usage("/").percent
                except Exception:
                    data["disk_root"] = None

                # GPU via nvidia-smi
                try:
                    result = subprocess.run(
                        ["nvidia-smi",
                         "--query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu",
                         "--format=csv,noheader,nounits"],
                        capture_output=True, text=True, timeout=3
                    )
                    if result.returncode == 0:
                        fields = [x.strip() for x in result.stdout.strip().split(",")]
                        gpu_pct  = float(fields[0])
                        vram_used= float(fields[1])
                        vram_tot = float(fields[2])
                        gpu_temp = float(fields[3])
                        data["gpu_available"] = True
                        data["gpu"]      = gpu_pct
                        data["vram"]     = (vram_used / vram_tot * 100) if vram_tot else 0
                        data["gpu_temp"] = gpu_temp
                    else:
                        data["gpu_available"] = False
                except Exception:
                    data["gpu_available"] = False

                # Processes
                procs = []
                for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
                    try:
                        procs.append(p.info)
                    except Exception:
                        pass
                procs.sort(key=lambda x: x.get("cpu_percent") or 0, reverse=True)
                data["procs"] = procs[:2]

            except Exception as e:
                logging.error(f"Monitor error: {e}")

            with self._lock:
                self._snapshot = data
            self._event.set()
            time.sleep(max(0, REFRESH_INTERVAL - 1))  # -1 for the cpu_percent(interval=1) block

# ── SystemPromptBuilder ───────────────────────────────────────────────────────
class SystemPromptBuilder:
    def __init__(self, prefs: Prefs):
        self._prefs  = prefs
        self._lock   = threading.Lock()
        self._prompt = ""
        self._skills = []
        self._tasks  = {}

    def build(self, last_user_msg: str = "hello") -> str:
        """Build and cache the system prompt. Safe to call from any thread (file I/O only)."""
        def read_file(path, label):
            try:
                with open(path) as f:
                    return f.read()
            except FileNotFoundError:
                logging.warning(f"Memory file missing: {path}")
                return ""
            except Exception as e:
                logging.warning(f"Error reading {label}: {e}")
                return ""

        soul    = read_file(os.path.join(MEMORY_DIR, "soul.md"),    "soul.md")
        user    = read_file(os.path.join(MEMORY_DIR, "user.md"),    "user.md")
        session = read_file(os.path.join(MEMORY_DIR, "session.md"), "session.md")

        # RAG context
        rag_context = ""
        try:
            query = urllib.parse.quote(last_user_msg[:200])
            url   = f"{RAG_URL}/context?query={query}&max_tokens=300"
            data  = http_get(url, timeout=5, signed=True)
            rag_context = data.get("context") or data.get("text") or ""
        except Exception as e:
            logging.warning(f"RAG unreachable: {e}")

        # Skills
        skills_text = self._load_skills_text()

        # Tasks
        tasks_text = self._load_tasks_text()

        # Tone / verbosity
        tone_inst = TONE_DESCRIPTIONS.get(self._prefs.tone, TONE_DESCRIPTIONS[2])
        verb_inst = VERBOSITY_DESCRIPTIONS.get(self._prefs.verbosity, VERBOSITY_DESCRIPTIONS[3])

        parts = [
            "Answer only what is asked. Do not invent session IDs, timestamps,\n"
            "privacy policies, or procedures not mentioned in the context.\n"
            "Be direct and natural.\n\n"
            "You are SecureBot, a personal AI assistant helping Roland with IT\n"
            "automation, AI engineering, and system administration tasks.\n"
            "Use the context below to give personalized, relevant answers.",
        ]

        if soul:
            parts.append(f"\n--- IDENTITY ---\n{soul}\n--- END IDENTITY ---")
        if user:
            parts.append(f"\n--- USER PROFILE ---\n{user}\n--- END USER PROFILE ---")
        if session:
            parts.append(f"\n--- CURRENT SESSION ---\n{session}\n--- END SESSION ---")
        if rag_context:
            parts.append(f"\n--- RELEVANT CONTEXT ---\n{rag_context}\n--- END CONTEXT ---")
        if skills_text:
            parts.append(
                f"\n--- AVAILABLE SKILLS ---\n"
                f"You have these automation skills. Use them when a request matches.\n"
                f"If no skill matches, say so clearly - do not pretend to execute\n"
                f"skills you do not have.\n{skills_text}\n--- END SKILLS ---"
            )
        if tasks_text:
            parts.append(f"\n--- TASKS ---\n{tasks_text}\n--- END TASKS ---")

        parts.append(f"\n--- RESPONSE STYLE ---\n{tone_inst}\n{verb_inst}\n--- END STYLE ---")

        prompt = "\n".join(parts)
        with self._lock:
            self._prompt = prompt
        return prompt

    def get_cached(self) -> str:
        with self._lock:
            return self._prompt

    def _load_skills_text(self) -> str:
        skills_dir = os.path.join(os.path.dirname(MEMORY_DIR), "skills")
        lines = []
        try:
            for name in sorted(os.listdir(skills_dir)):
                skill_path = os.path.join(skills_dir, name, "skill.json")
                md_path    = os.path.join(skills_dir, name, "SKILL.md")
                desc = ""
                if os.path.exists(skill_path):
                    try:
                        with open(skill_path) as f:
                            d = json.load(f)
                        desc = d.get("description", "")
                    except Exception:
                        pass
                elif os.path.exists(md_path):
                    try:
                        with open(md_path) as f:
                            first = f.readline().strip()
                        desc = first.lstrip("# ").strip()
                    except Exception:
                        pass
                if desc:
                    lines.append(f"- {name}: {desc}")
                else:
                    lines.append(f"- {name}")
        except Exception as e:
            logging.warning(f"Skills load error: {e}")
        return "\n".join(lines)

    def _load_tasks_text(self) -> str:
        tasks_path = os.path.join(MEMORY_DIR, "tasks.json")
        try:
            with open(tasks_path) as f:
                d = json.load(f)
            lines = []
            active = d.get("active_task")
            if active:
                lines.append(f"Active: {active.get('title','?')} ({active.get('status','?')})")
            todo = d.get("todo", [])
            if todo:
                lines.append("Pending: " + ", ".join(
                    f"{t.get('title','?')} (p:{t.get('priority','?')})" for t in todo
                ))
            return "\n".join(lines)
        except Exception as e:
            logging.warning(f"Tasks load error: {e}")
            return ""

# ── SecureBotApp ──────────────────────────────────────────────────────────────
class SecureBotApp:
    def __init__(self, stdscr):
        self.stdscr = stdscr
        self.chat   = ChatBuffer()
        self.prefs  = Prefs()
        self._redraw_needed = threading.Event()
        self._running       = True
        self._thinking      = False
        self._spinner_idx   = 0
        self._last_draw     = 0.0
        self._worker_thread = None

        self.input_buf  = ""
        self.cursor_pos = 0
        self.scroll_offset = 0

        self.monitor   = ResourceMonitor(self._redraw_needed)
        self.sp_builder = SystemPromptBuilder(self.prefs)

    # ── Setup ─────────────────────────────────────────────────────────────────
    def setup(self):
        curses.cbreak()
        curses.noecho()
        self.stdscr.keypad(True)
        self.stdscr.nodelay(True)
        # Try highest visibility first; fall back gracefully
        for _vis in (2, 1):
            try:
                curses.curs_set(_vis)
                break
            except curses.error:
                pass

        curses.use_default_colors()
        curses.init_pair(C_HEADER,  curses.COLOR_WHITE,  curses.COLOR_BLUE)
        curses.init_pair(C_USER,    curses.COLOR_WHITE,  -1)
        curses.init_pair(C_BOT,     curses.COLOR_CYAN,   -1)
        curses.init_pair(C_DIM,     curses.COLOR_WHITE,  -1)
        curses.init_pair(C_GREEN,   curses.COLOR_GREEN,  -1)
        curses.init_pair(C_YELLOW,  curses.COLOR_YELLOW, -1)
        curses.init_pair(C_RED,     curses.COLOR_RED,    -1)
        curses.init_pair(C_CYAN,    curses.COLOR_CYAN,   -1)
        curses.init_pair(C_MAGENTA, curses.COLOR_MAGENTA,-1)
        curses.init_pair(C_BOLD,    curses.COLOR_WHITE,  -1)

    # ── Main loop ─────────────────────────────────────────────────────────────
    def run(self):
        self.setup()
        self.monitor.start()

        # Startup in daemon thread
        t = threading.Thread(target=self._startup, daemon=True)
        t.start()

        self.stdscr.nodelay(True)
        while self._running:
            time.sleep(0.02)
            ch = self.stdscr.getch()
            if ch == -1:
                if self._redraw_needed.is_set():
                    self._redraw_needed.clear()
                    self.redraw()
                elif time.time() - self._last_draw > 0.3:
                    self.redraw()
                    self._last_draw = time.time()
                # advance spinner if thinking
                if self._thinking:
                    self._spinner_idx = (self._spinner_idx + 1) % len(SPINNER_FRAMES)
                continue
            self.handle_key(ch)
            self.redraw()

        self.monitor.stop()
        curses.curs_set(0)

    # ── Startup ───────────────────────────────────────────────────────────────
    def _ollama_warmup(self):
        """Send a tiny request to force model load before first user message."""
        try:
            payload = json.dumps({
                "model": RESPONSE_MODEL,
                "prompt": "hi",
                "stream": False,
                "options": {"num_predict": 1}
            }).encode()
            req = urllib.request.Request(
                "http://localhost:11434/api/generate",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            urllib.request.urlopen(req, timeout=60)
            self.chat.add("Model warmed up.", curses.color_pair(C_DIM))
        except Exception as e:
            self.chat.add(f"Warmup warning: {e}", curses.color_pair(C_YELLOW))
        finally:
            self._redraw_needed.set()

    def _startup(self):
        self.chat.add("SecureBot CLI v1.0 — /help for commands", curses.color_pair(C_DIM))
        self._redraw_needed.set()

        # RAG warmup with retry loop
        def rag_warmup_with_retry(max_attempts=5, delay=3):
            for attempt in range(max_attempts):
                try:
                    result = http_get(
                        f"{RAG_URL}/context?query=hello&max_tokens=10",
                        signed=True,
                        timeout=5
                    )
                    if result is not None:
                        return True
                except Exception:
                    pass
                if attempt < max_attempts - 1:
                    self.chat.add(
                        f"RAG not ready, retrying ({attempt+1}/{max_attempts})...",
                        curses.color_pair(C_YELLOW)
                    )
                    self._redraw_needed.set()
                    time.sleep(delay)
            return False

        rag_ok = rag_warmup_with_retry()
        if rag_ok:
            self.chat.add("RAG ready.", curses.color_pair(C_GREEN))
        else:
            self.chat.add("[warning] RAG not reachable — check /status", curses.color_pair(C_YELLOW))
        self._redraw_needed.set()

        # Build system prompt
        try:
            self.sp_builder.build()
        except Exception as e:
            logging.error(f"Startup sp build error: {e}")

        # Ollama warmup — loads model into VRAM before first user message
        self.chat.add("Warming up model...", curses.color_pair(C_DIM))
        self._redraw_needed.set()
        self._ollama_warmup()

        self.chat.add("Ready.", curses.color_pair(C_DIM))
        self._redraw_needed.set()

    # ── Key handler ───────────────────────────────────────────────────────────
    def handle_key(self, ch: int):
        if ch in (10, 13):  # Enter
            self._submit()
        elif ch == 3:  # Ctrl-C
            self._running = False
        elif ch in (curses.KEY_BACKSPACE, 127, 8):
            if self.cursor_pos > 0:
                self.input_buf  = self.input_buf[:self.cursor_pos-1] + self.input_buf[self.cursor_pos:]
                self.cursor_pos -= 1
        elif ch == curses.KEY_DC:
            if self.cursor_pos < len(self.input_buf):
                self.input_buf = self.input_buf[:self.cursor_pos] + self.input_buf[self.cursor_pos+1:]
        elif ch == curses.KEY_LEFT:
            self.cursor_pos = max(0, self.cursor_pos - 1)
        elif ch == curses.KEY_RIGHT:
            self.cursor_pos = min(len(self.input_buf), self.cursor_pos + 1)
        elif ch in (curses.KEY_HOME, 1):  # Home / Ctrl-A
            self.cursor_pos = 0
        elif ch in (curses.KEY_END, 5):  # End / Ctrl-E
            self.cursor_pos = len(self.input_buf)
        elif ch == 21:  # Ctrl-U
            self.input_buf  = ""
            self.cursor_pos = 0
        elif ch == 11:  # Ctrl-K
            self.input_buf  = self.input_buf[:self.cursor_pos]
        elif ch == curses.KEY_UP:
            self.scroll_offset += 1
        elif ch == curses.KEY_DOWN:
            self.scroll_offset = max(0, self.scroll_offset - 1)
        elif ch == curses.KEY_PPAGE:
            self.scroll_offset += 5
        elif ch == curses.KEY_NPAGE:
            self.scroll_offset = max(0, self.scroll_offset - 5)
        elif 32 <= ch <= 126:
            self.input_buf = self.input_buf[:self.cursor_pos] + chr(ch) + self.input_buf[self.cursor_pos:]
            self.cursor_pos += 1

    # ── Submit ────────────────────────────────────────────────────────────────
    def _submit(self):
        text = self.input_buf.strip()
        if not text:
            return
        self.input_buf  = ""
        self.cursor_pos = 0
        self.scroll_offset = 0

        if text.startswith("/"):
            self.chat.add(f"You: {text}", curses.color_pair(C_USER))
            self._run_command(text)
        else:
            self.chat.add(f"You: {text}", curses.color_pair(C_USER))
            self._send_message(text)

    # ── Commands ──────────────────────────────────────────────────────────────
    def _run_command(self, text: str):
        parts = text.split(None, 1)
        cmd   = parts[0].lower()
        arg   = parts[1] if len(parts) > 1 else ""

        if cmd == "/memory":
            self._cmd_memory()
        elif cmd == "/edit":
            self._cmd_edit(arg)
        elif cmd == "/session":
            self._cmd_session(arg)
        elif cmd == "/reload":
            self._cmd_reload()
        elif cmd == "/tasks":
            self._cmd_tasks()
        elif cmd == "/task":
            self._cmd_add_task(arg)
        elif cmd in ("/tone", "/t"):
            self._cmd_tone(arg)
        elif cmd in ("/verbosity", "/v"):
            self._cmd_verbosity(arg)
        elif cmd == "/prefs":
            self._cmd_prefs()
        elif cmd == "/skills":
            self._cmd_skills()
        elif cmd == "/status":
            self._cmd_status()
        elif cmd == "/clear":
            self.chat.clear()
        elif cmd == "/help":
            self._cmd_help()
        elif cmd in ("/quit", "/exit"):
            self._running = False
        elif cmd == "/cc":
            self._cmd_cc(arg)
        elif cmd == "/haiku":
            self._cmd_haiku(arg)
        else:
            self.chat.add(f"Unknown command: {cmd}  (type /help)", curses.color_pair(C_RED))

    def _cmd_memory(self):
        for fname in ("soul.md", "user.md"):
            path = os.path.join(MEMORY_DIR, fname)
            self.chat.add(f"── {fname} ──", curses.color_pair(C_YELLOW))
            try:
                with open(path) as f:
                    for line in f.read().splitlines():
                        self.chat.add(line, curses.color_pair(C_DIM))
            except Exception as e:
                self.chat.add(f"Error reading {fname}: {e}", curses.color_pair(C_RED))
        self._redraw_needed.set()

    def _cmd_edit(self, which: str):
        which = which.strip().lower()
        if which not in ("soul", "user", "session"):
            self.chat.add("Usage: /edit <soul|user|session>", curses.color_pair(C_YELLOW))
            return
        path   = os.path.join(MEMORY_DIR, f"{which}.md")
        editor = os.getenv("EDITOR", "nano")
        curses.endwin()
        try:
            subprocess.call([editor, path])
        except Exception as e:
            pass
        # Restore curses
        self.stdscr.keypad(True)
        curses.cbreak()
        curses.noecho()
        self.stdscr.clear()
        self.stdscr.refresh()
        self.sp_builder.build()
        self.chat.add(f"Edited {which}.md and rebuilt system prompt.", curses.color_pair(C_GREEN))
        self._redraw_needed.set()

    def _cmd_session(self, note: str):
        if not note:
            self.chat.add("Usage: /session <note>", curses.color_pair(C_YELLOW))
            return
        path = os.path.join(MEMORY_DIR, "session.md")
        ts   = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        try:
            with open(path, "a") as f:
                f.write(f"\n## {ts}\n{note}\n")
            self.chat.add(f"Session note saved.", curses.color_pair(C_GREEN))
        except Exception as e:
            self.chat.add(f"Error saving session: {e}", curses.color_pair(C_RED))

    def _cmd_reload(self):
        try:
            self.sp_builder.build()
            self.chat.add("Memory files reloaded and system prompt rebuilt.", curses.color_pair(C_GREEN))
        except Exception as e:
            self.chat.add(f"Reload error: {e}", curses.color_pair(C_RED))
        self._redraw_needed.set()

    def _cmd_tasks(self):
        path = os.path.join(MEMORY_DIR, "tasks.json")
        try:
            with open(path) as f:
                d = json.load(f)
            active = d.get("active_task")
            if active:
                self.chat.add(
                    f"Active: [{active.get('priority','?').upper()}] {active.get('title','?')} — {active.get('status','?')}",
                    curses.color_pair(C_GREEN)
                )
            todo = d.get("todo", [])
            if todo:
                self.chat.add("── TODO ──", curses.color_pair(C_YELLOW))
                for t in todo:
                    self.chat.add(
                        f"  [{t.get('priority','?').upper()}] {t.get('title','?')}",
                        curses.color_pair(C_USER)
                    )
            done = d.get("completed", [])
            if done:
                self.chat.add("── DONE ──", curses.color_pair(C_DIM))
                for t in done:
                    self.chat.add(f"  ✓ {t.get('title','?')}", curses.color_pair(C_DIM))
        except Exception as e:
            self.chat.add(f"Error reading tasks: {e}", curses.color_pair(C_RED))
        self._redraw_needed.set()

    def _cmd_add_task(self, desc: str):
        if not desc:
            self.chat.add("Usage: /task <description>", curses.color_pair(C_YELLOW))
            return
        path = os.path.join(MEMORY_DIR, "tasks.json")
        try:
            with open(path) as f:
                d = json.load(f)
        except Exception:
            d = {"active_task": None, "todo": [], "completed": []}
        ts = int(time.time())
        new_task = {
            "id":       f"task_{ts}",
            "title":    desc,
            "priority": "medium",
            "status":   "pending",
        }
        d.setdefault("todo", []).append(new_task)
        try:
            with open(path, "w") as f:
                json.dump(d, f, indent=2)
            self.chat.add(f"✅ Task added: {desc}", curses.color_pair(C_GREEN))
        except Exception as e:
            self.chat.add(f"Error saving task: {e}", curses.color_pair(C_RED))

    def _cmd_tone(self, arg: str):
        try:
            val = int(arg)
            assert 1 <= val <= 3
        except Exception:
            self.chat.add("Usage: /tone <1-3>", curses.color_pair(C_YELLOW))
            return
        self.prefs.tone = val
        self.prefs.save()
        self.sp_builder.build()
        self.chat.add(f"Tone set to {val}: {TONE_DESCRIPTIONS[val]}", curses.color_pair(C_GREEN))
        self._redraw_needed.set()

    def _cmd_verbosity(self, arg: str):
        try:
            val = int(arg)
            assert 1 <= val <= 5
        except Exception:
            self.chat.add("Usage: /verbosity <1-5>", curses.color_pair(C_YELLOW))
            return
        self.prefs.verbosity = val
        self.prefs.save()
        self.sp_builder.build()
        self.chat.add(f"Verbosity set to {val}: {VERBOSITY_DESCRIPTIONS[val]}", curses.color_pair(C_GREEN))
        self._redraw_needed.set()

    def _cmd_prefs(self):
        t = self.prefs.tone
        v = self.prefs.verbosity
        self.chat.add(f"Tone {t}: {TONE_DESCRIPTIONS.get(t,'?')}", curses.color_pair(C_USER))
        self.chat.add(f"Verbosity {v}: {VERBOSITY_DESCRIPTIONS.get(v,'?')}", curses.color_pair(C_USER))
        self._redraw_needed.set()

    def _cmd_skills(self):
        def _do():
            try:
                url = f"{GATEWAY_URL}/health"
                with urllib.request.urlopen(url, timeout=5) as resp:
                    data = json.loads(resp.read())
                skills = data.get("skills", [])
                if skills:
                    self.chat.add("── Skills ──", curses.color_pair(C_YELLOW))
                    for s in skills:
                        name = s if isinstance(s, str) else s.get("name", str(s))
                        self.chat.add(f"  - {name}", curses.color_pair(C_USER))
                else:
                    self.chat.add("No skills returned from gateway.", curses.color_pair(C_DIM))
            except Exception as e:
                self.chat.add(f"Gateway unreachable: {e}", curses.color_pair(C_RED))
            self._redraw_needed.set()
        threading.Thread(target=_do, daemon=True).start()

    def _cmd_status(self):
        def _do():
            checks = [
                ("Gateway",  f"{GATEWAY_URL}/health",           False),
                ("Vault",    f"{VAULT_URL}/health",             False),
                ("Memory",   "http://localhost:8300/health",    False),
                ("RAG",      f"{RAG_URL}/health",               True),
                ("Ollama",   "http://localhost:11434/api/tags",  False),
            ]
            self.chat.add("── Status ──", curses.color_pair(C_YELLOW))
            for name, url, signed in checks:
                try:
                    if signed:
                        http_get(url, timeout=3, signed=True)
                    else:
                        with urllib.request.urlopen(url, timeout=3):
                            pass
                    self.chat.add(f"  ✓ {name}", curses.color_pair(C_GREEN))
                except Exception:
                    self.chat.add(f"  ✗ {name}", curses.color_pair(C_RED))
            self._redraw_needed.set()
        threading.Thread(target=_do, daemon=True).start()

    def _cmd_help(self):
        lines = [
            "── Help ──",
            "/memory            Show soul.md + user.md",
            "/edit <soul|user|session>  Open file in editor",
            "/session <note>    Append note to session.md",
            "/reload            Reload memory files",
            "/tasks             Show tasks",
            "/task <desc>       Add a task",
            "/tone /t <1-3>     Set tone (1=formal 3=casual)",
            "/verbosity /v <1-5> Set verbosity",
            "/prefs             Show current preferences",
            "/skills            List gateway skills",
            "/status            Health check all services",
            "/clear             Clear chat",
            "/cc <prompt>       Delegate to Claude Code",
            "/haiku <prompt>    Ask Claude Haiku directly",
            "/quit /exit        Exit",
            "PgUp/PgDn ↑↓      Scroll chat",
            "Ctrl-A/E           Cursor home/end",
            "Ctrl-U             Clear input",
            "Ctrl-K             Kill to end",
        ]
        for line in lines:
            attr = curses.color_pair(C_YELLOW) if line.startswith("──") else curses.color_pair(C_USER)
            self.chat.add(line, attr)
        self._redraw_needed.set()

    def _cmd_cc(self, prompt: str):
        if not prompt:
            self.chat.add("Usage: /cc <prompt>", curses.color_pair(C_YELLOW))
            return
        if not shutil.which("claude"):
            self.chat.add("Error: claude not found. Install: npm install -g @anthropic-ai/claude-code",
                          curses.color_pair(C_RED))
            return

        def _do():
            try:
                proc = subprocess.Popen(
                    ["claude", "-p", "--dangerously-skip-permissions", prompt],
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
                )
                for line in proc.stdout:
                    line = line.rstrip("\n")
                    self.chat.add(f"[Claude Code] {line}", curses.color_pair(C_YELLOW))
                    self._redraw_needed.set()
                proc.wait()
            except Exception as e:
                self.chat.add(f"[Claude Code] Error: {e}", curses.color_pair(C_RED))
                self._redraw_needed.set()

        threading.Thread(target=_do, daemon=True).start()

    def _cmd_haiku(self, prompt: str):
        if not prompt:
            self.chat.add("Usage: /haiku <prompt>", curses.color_pair(C_YELLOW))
            return

        def _do():
            api_key = None
            # Try vault first
            try:
                url = f"{VAULT_URL}/v1/secret/data/anthropic"
                with urllib.request.urlopen(url, timeout=5) as resp:
                    data = json.loads(resp.read())
                api_key = (data.get("data", {}).get("data", {}).get("anthropic_api_key")
                           or data.get("data", {}).get("anthropic_api_key"))
            except Exception:
                pass

            # Fallback to direct file read
            if not api_key:
                try:
                    with open(VAULT_SECRETS) as f:
                        secrets = json.load(f)
                    api_key = secrets.get("anthropic_api_key")
                except Exception as e:
                    self.chat.add(f"Error: cannot read API key: {e}", curses.color_pair(C_RED))
                    self._redraw_needed.set()
                    return

            if not api_key:
                self.chat.add("Error: anthropic_api_key not found.", curses.color_pair(C_RED))
                self._redraw_needed.set()
                return

            try:
                payload = json.dumps({
                    "model":      "claude-haiku-4-5-20251001",
                    "max_tokens": 1000,
                    "messages":   [{"role": "user", "content": prompt}],
                }).encode()
                req = urllib.request.Request(
                    "https://api.anthropic.com/v1/messages",
                    data=payload,
                    headers={
                        "Content-Type":      "application/json",
                        "x-api-key":         api_key,
                        "anthropic-version": "2023-06-01",
                    },
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=30) as resp:
                    data = json.loads(resp.read())
                text = data["content"][0]["text"]
                self.chat.add(f"[Haiku] {text}", curses.color_pair(C_MAGENTA))
            except Exception as e:
                self.chat.add(f"[Haiku] Error: {e}", curses.color_pair(C_RED))
            self._redraw_needed.set()

        threading.Thread(target=_do, daemon=True).start()

    # ── Send message to gateway ───────────────────────────────────────────────
    def _send_message(self, text: str):
        if self._thinking:
            self.chat.add("Still waiting for response...", curses.color_pair(C_YELLOW))
            return
        self._thinking    = True
        self._spinner_idx = 0

        def _worker():
            try:
                system_prompt = self.sp_builder.build(text)
                payload = json.dumps({
                    "channel":     "cli",
                    "user_id":     USER_ID,
                    "text":        text,
                    "system":      system_prompt,
                    "temperature": 0.7,
                }).encode()
                gw_headers = {"Content-Type": "application/json"}
                if GATEWAY_API_KEY:
                    gw_headers["X-API-Key"] = GATEWAY_API_KEY
                req = urllib.request.Request(
                    f"{GATEWAY_URL}/message",
                    data=payload,
                    headers=gw_headers,
                    method="POST",
                )
                t0 = time.time()
                with urllib.request.urlopen(req, timeout=120) as resp:
                    data = json.loads(resp.read())
                elapsed = time.time() - t0
                bot_text = data.get("response") or data.get("text") or data.get("message") or ""
                meta     = data.get("metadata", {})
                method   = (meta.get("method") if isinstance(meta, dict) else None) or data.get("method", "gateway")
                if not bot_text or not bot_text.strip():
                    self.chat.add(
                        f"[No response — method: {method}. Try rephrasing.]",
                        curses.color_pair(C_YELLOW)
                    )
                elif bot_text.startswith("{") and "status" in bot_text:
                    self.chat.add("[Gateway error — raw response received]", curses.color_pair(C_RED))
                else:
                    self.chat.add(f"🤖 Bot: {bot_text}", curses.color_pair(C_BOT))
                self.chat.add(f"   [{method} | {elapsed:.1f}s]", curses.color_pair(C_DIM))
            except urllib.error.URLError as e:
                self.chat.add(f"Error: Gateway unreachable — {e.reason}", curses.color_pair(C_RED))
            except Exception as e:
                self.chat.add(f"Error: {e}", curses.color_pair(C_RED))
                logging.error(f"Worker error: {traceback.format_exc()}")
            finally:
                self._thinking = False
                self._redraw_needed.set()

        self._worker_thread = threading.Thread(target=_worker, daemon=True)
        self._worker_thread.start()

    # ── Drawing ───────────────────────────────────────────────────────────────
    def redraw(self):
        try:
            self._do_redraw()
            self._last_draw = time.time()
        except Exception as e:
            try:
                with open(DRAW_LOG, "a") as f:
                    f.write(f"{datetime.datetime.now()}: {traceback.format_exc()}\n")
            except Exception:
                pass

    def _do_redraw(self):
        h, w = self.stdscr.getmaxyx()
        self.stdscr.erase()
        snap = self.monitor.snapshot()

        row = 0

        # ── Header ────────────────────────────────────────────────────────────
        machine   = snap.get("machine", "local")
        hostname  = os.uname().nodename if hasattr(os, "uname") else "local"
        header = (f" SecureBot CLI | {RESPONSE_MODEL} | {hostname} | "
                  f"tone:{self.prefs.tone}|v:{self.prefs.verbosity}")
        self._safe_addstr(row, 0, header[:w].ljust(w), curses.color_pair(C_HEADER) | curses.A_BOLD)
        row += 1

        if h < 20:
            # Minimal layout: skip process panel
            chat_top = row
        else:
            # ── Resource panel ─────────────────────────────────────────────────
            gpu_avail = snap.get("gpu_available", False)
            mid       = w // 2

            if gpu_avail:
                left_w  = mid
                right_w = w - mid
            else:
                left_w  = w
                right_w = 0

            # CPU / RAM / DISK
            cpu  = snap.get("cpu", 0)
            ram  = snap.get("ram", 0)
            disk_home = snap.get("disk_home")
            disk_root = snap.get("disk_root")

            cpu_bar  = self._bar(cpu,  left_w - 16)
            ram_bar  = self._bar(ram,  left_w - 16)
            disk_str = ""
            if disk_home is not None and disk_root is not None:
                disk_str = f"DISK /home {disk_home:.0f}% / {disk_root:.0f}%"
            elif disk_home is not None:
                disk_str = f"DISK /home {disk_home:.0f}%"
            elif disk_root is not None:
                disk_str = f"DISK / {disk_root:.0f}%"

            if row < h:
                line = f" CPU  {cpu_bar} {cpu:4.0f}%"
                self._safe_addstr(row, 0, line[:left_w], self._bar_color(cpu))
                if gpu_avail and right_w > 0:
                    gpu  = snap.get("gpu",  0)
                    gpu_bar = self._bar(gpu, right_w - 17)
                    line2 = f" GPU  {gpu_bar} {gpu:4.0f}%"
                    self._safe_addstr(row, mid, line2[:right_w], curses.color_pair(C_CYAN))
                row += 1

            if row < h:
                line = f" RAM  {ram_bar} {ram:4.0f}%"
                self._safe_addstr(row, 0, line[:left_w], self._bar_color(ram))
                if gpu_avail and right_w > 0:
                    vram = snap.get("vram", 0)
                    vram_bar = self._bar(vram, right_w - 17)
                    line2 = f" VRAM {vram_bar} {vram:4.0f}%"
                    self._safe_addstr(row, mid, line2[:right_w], curses.color_pair(C_CYAN))
                row += 1

            if row < h:
                line = f" {disk_str}"
                self._safe_addstr(row, 0, line[:left_w], curses.color_pair(C_GREEN))
                if gpu_avail and right_w > 0:
                    temp = snap.get("gpu_temp", 0)
                    line2 = f" GPU Temp: {temp:.0f}°C"
                    self._safe_addstr(row, mid, line2[:right_w], curses.color_pair(C_CYAN))
                row += 1

            # ── Separator ─────────────────────────────────────────────────────
            if row < h:
                self._safe_addstr(row, 0, "─" * w, curses.color_pair(C_DIM))
                row += 1

            # ── Process table ─────────────────────────────────────────────────
            if row < h:
                hdr = f" {'PID':>6}  {'CPU%':>5}  {'MEM%':>5}  PROCESS"
                self._safe_addstr(row, 0, hdr[:w], curses.color_pair(C_YELLOW))
                row += 1
            procs = snap.get("procs", [])
            for proc in procs[:2]:
                if row >= h:
                    break
                pid   = proc.get("pid", "?")
                cpu_p = proc.get("cpu_percent") or 0
                mem_p = proc.get("memory_percent") or 0
                name  = (proc.get("name") or "")[:max(1, w - 25)]
                line  = f" {pid:>6}  {cpu_p:>5.1f}  {mem_p:>5.1f}  {name}"
                self._safe_addstr(row, 0, line[:w], curses.color_pair(C_USER))
                row += 1

            # Pad process section to at least 2 rows after header
            while row < h and row < (h - 10):
                if snap.get("procs") is None:
                    break
                break  # only pad if we had fewer than 2 procs
            chat_top = row

        # ── Separator before chat ─────────────────────────────────────────────
        if chat_top < h:
            self._safe_addstr(chat_top, 0, "─" * w, curses.color_pair(C_DIM))
            chat_top += 1

        # ── Input line position ───────────────────────────────────────────────
        input_row  = max(chat_top, h - 2)
        status_row = h - 1
        chat_h     = max(0, input_row - chat_top)

        # ── Chat area ─────────────────────────────────────────────────────────
        raw_lines = self.chat.get_lines()
        # Word-wrap each line
        wrapped = []
        for (text, attr) in raw_lines:
            wrapped.extend(self._wrap(text, w, attr))

        # Scroll clamp
        max_scroll = max(0, len(wrapped) - chat_h)
        self.scroll_offset = min(self.scroll_offset, max_scroll)
        self.scroll_offset = max(0, self.scroll_offset)

        # Visible slice (pin to bottom unless scrolled)
        if self.scroll_offset == 0:
            visible = wrapped[-chat_h:] if chat_h > 0 else []
        else:
            end_idx = max(0, len(wrapped) - self.scroll_offset)
            start_idx = max(0, end_idx - chat_h)
            visible = wrapped[start_idx:end_idx]

        for i, (line, attr) in enumerate(visible):
            if chat_top + i >= input_row:
                break
            self._safe_addstr(chat_top + i, 0, line[:w].ljust(w), attr)

        # ── Input line ────────────────────────────────────────────────────────
        _final_cursor = None
        if input_row < h:
            prefix = f"[tone:{self.prefs.tone}|v:{self.prefs.verbosity}] "
            if self._thinking:
                sp = SPINNER_FRAMES[self._spinner_idx % len(SPINNER_FRAMES)]
                prefix_shown = f"{sp} "
            else:
                prefix_shown = prefix

            avail     = max(0, w - len(prefix_shown) - 1)
            buf       = self.input_buf
            # Pan if cursor out of view
            view_start = 0
            if self.cursor_pos >= avail:
                view_start = self.cursor_pos - avail + 1
            view_buf   = buf[view_start:view_start + avail]
            cursor_col = len(prefix_shown) + (self.cursor_pos - view_start)

            input_line = prefix_shown + view_buf
            self._safe_addstr(input_row, 0, input_line[:w].ljust(w), curses.color_pair(C_USER))
            cursor_col = min(cursor_col, w - 1)
            # Save position; move AFTER refresh so it is not overwritten
            _final_cursor = (input_row, cursor_col)

        # ── Status row ────────────────────────────────────────────────────────
        if status_row < h and status_row != input_row:
            if self._thinking:
                status = " ⏳ Waiting for response..."
                self._safe_addstr(status_row, 0, status[:w].ljust(w), curses.color_pair(C_DIM))
            else:
                self._safe_addstr(status_row, 0, " " * w, curses.color_pair(C_DIM))

        self.stdscr.refresh()
        # Place cursor AFTER refresh to ensure correct terminal position
        if _final_cursor:
            try:
                self.stdscr.move(*_final_cursor)
            except curses.error:
                pass

    # ── Drawing helpers ───────────────────────────────────────────────────────
    def _safe_addstr(self, row: int, col: int, text: str, attr: int = 0):
        h, w = self.stdscr.getmaxyx()
        if row < 0 or row >= h or col < 0 or col >= w:
            return
        try:
            self.stdscr.addstr(row, col, text, attr)
        except curses.error:
            pass

    def _bar(self, pct: float, width: int) -> str:
        width = max(1, width)
        filled = int(pct / 100 * width)
        filled = min(filled, width)
        return "█" * filled + "░" * (width - filled)

    def _bar_color(self, pct: float) -> int:
        if pct > 90:
            return curses.color_pair(C_RED)
        elif pct > 80:
            return curses.color_pair(C_YELLOW)
        else:
            return curses.color_pair(C_GREEN)

    def _wrap(self, text: str, width: int, attr: int):
        """Word-wrap text with smart paragraph handling for multi-line bot responses."""
        if width <= 0:
            return [(text, attr)]
        result = []
        # Split on blank lines to get paragraphs
        paragraphs = re.split(r'\n\s*\n', text)
        for p_idx, para in enumerate(paragraphs):
            lines = para.split('\n')
            # Detect structured content: bullets, code fences, headers
            is_structured = any(
                l.strip().startswith(('- ', '* ', '• ', '```', '# '))
                for l in lines if l.strip()
            )
            if is_structured:
                # Preserve structure; word-wrap each line individually
                for line in lines:
                    if not line.strip():
                        result.append(('', attr))
                    else:
                        for wl in (textwrap.wrap(line, width) or [line]):
                            result.append((wl, attr))
            else:
                # Prose: join continuation lines, then rewrap as single paragraph
                joined = ' '.join(l.strip() for l in lines if l.strip())
                if joined:
                    for wl in (textwrap.wrap(joined, width) or [joined]):
                        result.append((wl, attr))
                else:
                    result.append(('', attr))
            # Blank separator between paragraphs (not after the last one)
            if p_idx < len(paragraphs) - 1:
                result.append(('', attr))
        return result or [('', attr)]


# ── Entry point ───────────────────────────────────────────────────────────────
def main(stdscr):
    app = SecureBotApp(stdscr)
    app.run()


if __name__ == "__main__":
    try:
        curses.wrapper(main)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        # Last-resort: print to stderr so user sees it
        print(f"Fatal error: {e}", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)
