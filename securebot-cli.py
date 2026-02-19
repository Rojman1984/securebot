#!/usr/bin/env python3
"""
SecureBot CLI - Terminal TUI chat interface
Single-file, SSH-compatible, curses-based
"""

import curses
import json
import os
import shlex
import subprocess
import sys
import threading
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Optional

# ═══════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════
GATEWAY_URL = "http://localhost:8080"
VAULT_URL   = "http://localhost:8200"
RAG_URL     = "http://localhost:8400"
USER_ID     = "roland"
MEMORY_DIR  = os.path.expanduser("~/securebot/memory")
VAULT_SECRETS = os.path.expanduser("~/securebot/vault/secrets/secrets.json")
PREFS_FILE  = os.path.expanduser("~/.securebot-cli-prefs.json")
REFRESH_INTERVAL      = 3
MAX_CHAT_HISTORY      = 100
SYSTEM_PROMPT_REFRESH = 30

# ═══════════════════════════════════════
# TONE / VERBOSITY SCALES
# ═══════════════════════════════════════
TONE_DESCRIPTIONS = {
    1: ("Formal",
        "You are a professional, precise assistant. Use formal language. "
        "Avoid contractions, colloquialisms, and casual phrasing."),
    2: ("Balanced",
        "You are helpful and professional but approachable. "
        "Natural conversational tone without being overly casual."),
    3: ("Casual",
        "You are a friendly, casual assistant. Use conversational "
        "language, contractions are fine, be relaxed and personable."),
}

VERBOSITY_DESCRIPTIONS = {
    1: ("Curt",
        "Be extremely concise. One to three sentences maximum. "
        "No explanations unless asked. Just the answer."),
    2: ("Brief",
        "Be concise. Answer directly, minimal elaboration. "
        "Skip preamble and summary."),
    3: ("Balanced",
        "Provide complete answers with necessary context. "
        "Avoid padding but don't truncate important details."),
    4: ("Detailed",
        "Be thorough. Include examples, context, and explanation. "
        "Anticipate follow-up questions."),
    5: ("Chatty",
        "Be comprehensive and conversational. Elaborate freely, "
        "include related insights, think out loud."),
}

# ═══════════════════════════════════════
# COLOR PAIR IDs
# ═══════════════════════════════════════
C_HEADER    = 1   # blue bg, white fg
C_BOT       = 2   # cyan
C_USER      = 3   # white
C_DIM       = 4   # gray / dim
C_GREEN     = 5   # success / bars
C_YELLOW    = 6   # warning / claude output
C_RED       = 7   # error
C_CYAN_BAR  = 8   # GPU bar
C_MAGENTA   = 9   # haiku output
C_GRAY_FILL = 10  # empty bar
C_BOLD_W    = 11  # input prompt (white bold via attr)


# ═══════════════════════════════════════
# PREFS
# ═══════════════════════════════════════
def load_prefs() -> dict:
    defaults = {"tone": 2, "verbosity": 3}
    try:
        if os.path.exists(PREFS_FILE):
            with open(PREFS_FILE) as f:
                defaults.update(json.load(f))
    except Exception:
        pass
    return defaults


def save_prefs(prefs: dict):
    try:
        with open(PREFS_FILE, "w") as f:
            json.dump(prefs, f, indent=2)
    except Exception:
        pass


# ═══════════════════════════════════════
# MEMORY / FILE HELPERS
# ═══════════════════════════════════════
def read_file_safe(path: str) -> str:
    try:
        with open(path) as f:
            return f.read().strip()
    except Exception:
        return ""


def read_tasks() -> dict:
    path = os.path.join(MEMORY_DIR, "tasks.json")
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return {"active_task": None, "todo": [], "completed": []}


def append_task(desc: str) -> bool:
    path = os.path.join(MEMORY_DIR, "tasks.json")
    try:
        tasks = read_tasks()
        tasks.setdefault("todo", []).append({
            "id": f"task_{int(time.time())}",
            "title": desc,
            "priority": "medium",
            "status": "pending",
        })
        with open(path, "w") as f:
            json.dump(tasks, f, indent=2)
        return True
    except Exception:
        return False


def append_session_note(note: str) -> bool:
    path = os.path.join(MEMORY_DIR, "session.md")
    try:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(path, "a") as f:
            f.write(f"\n## Note [{ts}]\n{note}\n")
        return True
    except Exception:
        return False


# ═══════════════════════════════════════
# HTTP HELPERS
# ═══════════════════════════════════════
def http_get(url: str, timeout: int = 5) -> Optional[dict]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except Exception:
        return None


def http_post(url: str, data: dict, timeout: int = 60) -> Optional[dict]:
    try:
        body = json.dumps(data).encode()
        req = urllib.request.Request(
            url, data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except Exception:
        return None


def get_anthropic_key() -> Optional[str]:
    """Try vault API first, then direct secrets file."""
    resp = http_get(f"{VAULT_URL}/secrets/anthropic_api_key", timeout=3)
    if resp and resp.get("value"):
        return resp["value"]
    try:
        with open(VAULT_SECRETS) as f:
            return json.load(f).get("anthropic_api_key")
    except Exception:
        return None


# ═══════════════════════════════════════
# SKILLS / GATEWAY
# ═══════════════════════════════════════
def fetch_skills() -> list:
    resp = http_get(f"{GATEWAY_URL}/health", timeout=5)
    if not resp:
        return []
    result = []
    for s in resp.get("skills", []):
        if isinstance(s, dict):
            result.append({"name": s.get("name", ""), "description": s.get("description", "")})
        elif isinstance(s, str):
            result.append({"name": s, "description": ""})
    return result


# ═══════════════════════════════════════
# RAG / CHROMADB
# ═══════════════════════════════════════
def rag_get_context(query: str, max_tokens: int = 200, collection: str = "") -> Optional[str]:
    url = (f"{RAG_URL}/context"
           f"?query={urllib.parse.quote(query)}&max_tokens={max_tokens}")
    if collection:
        url += f"&collection={urllib.parse.quote(collection)}"
    resp = http_get(url, timeout=3)
    if resp:
        return resp.get("context") or resp.get("text") or ""
    return None


def rag_get_skills(query: str, k: int = 2) -> list:
    url = f"{RAG_URL}/classify/examples?query={urllib.parse.quote(query)}&k={k}"
    resp = http_get(url, timeout=3)
    if resp:
        return resp.get("results") or resp.get("examples") or []
    return []


def rag_get_history_context(query: str, max_tokens: int = 120) -> Optional[str]:
    return rag_get_context(query, max_tokens=max_tokens, collection="cli_history")


def _safe_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def rag_store_exchange(user_msg: str, bot_msg: str, meta: dict):
    try:
        http_post(f"{RAG_URL}/embed/conversation",
                  {"user": user_msg, "bot": bot_msg, "metadata": meta},
                  timeout=3)
    except Exception:
        pass


def rag_warmup():
    http_get(f"{RAG_URL}/context?query=hello&max_tokens=10", timeout=5)


# ═══════════════════════════════════════
# SYSTEM PROMPT BUILDER
# ═══════════════════════════════════════
class SystemPromptBuilder:
    def __init__(self, prefs: dict):
        self.prefs = prefs
        self._lock = threading.Lock()
        self._cached = ""
        self._last_built = 0.0
        self._skills: list = []
        self._rag_ok = True

    def get_token_estimate(self, text: str) -> int:
        """Estimate token count as word count * 1.3."""
        return int(len(text.split()) * 1.3)

    def _first_paragraph(self, text: str) -> str:
        parts = [p.strip() for p in text.split("\n\n") if p.strip()]
        return parts[0] if parts else ""

    def build(self, user_query: str = "") -> str:
        tasks = read_tasks()

        tone_val  = self.prefs.get("tone", 2)
        verb_val  = self.prefs.get("verbosity", 3)
        tone_desc = TONE_DESCRIPTIONS.get(tone_val, TONE_DESCRIPTIONS[2])[1]
        verb_desc = VERBOSITY_DESCRIPTIONS.get(verb_val, VERBOSITY_DESCRIPTIONS[3])[1]

        parts = []

        # 1) identity
        soul_content = read_file_safe(os.path.join(MEMORY_DIR, "soul.md"))
        if soul_content:
            parts.append(self._first_paragraph(soul_content))

        # 2/3) user + session (full on fallback or empty query)
        user_content = read_file_safe(os.path.join(MEMORY_DIR, "user.md"))
        session_content = read_file_safe(os.path.join(MEMORY_DIR, "session.md"))

        # 4) relevant memory from RAG + conversation context
        rag_ctx = ""
        hist_ctx = ""
        if user_query and self._rag_ok:
            try:
                rag_ctx = rag_get_context(user_query, max_tokens=200) or ""
                hist_ctx = rag_get_history_context(user_query, max_tokens=120) or ""
            except Exception:
                self._rag_ok = False

        if rag_ctx:
            parts.append(f"RELEVANT MEMORY CONTEXT:\n{rag_ctx}")
        if hist_ctx:
            parts.append(f"RELEVANT PAST CONTEXT:\n{hist_ctx}")

        # fallback to file injection if no semantic context available
        if not user_query or (user_query and not rag_ctx):
            if user_content:
                parts.append(f"USER PROFILE:\n{user_content}")
            if session_content:
                parts.append(f"CURRENT SESSION:\n{session_content}")

        # 5) skills relevant to query (semantic)
        relevant_skills = []
        if user_query and self._rag_ok:
            try:
                raw_skills = rag_get_skills(user_query, k=3)
            except Exception:
                raw_skills = []
            for item in raw_skills:
                if not isinstance(item, dict):
                    continue
                sim = _safe_float(item.get("similarity", item.get("score", 0.0)), 0.0)
                if sim < 0.5:
                    continue
                relevant_skills.append((item.get("name", "unknown"), item.get("description", ""), sim))

        if relevant_skills:
            parts.append("RELEVANT SKILLS FOR THIS QUERY:")
            for n, d, sim in relevant_skills:
                parts.append(f"- {n}: {d} (similarity: {sim:.2f})")
        else:
            parts.append("RELEVANT SKILLS FOR THIS QUERY:\nNo existing skills match this query. A new skill can be created.")

        # 6) tasks (compact)
        active = tasks.get("active_task")
        todo = tasks.get("todo", [])
        task_lines = []
        if active:
            task_lines.append(f"Active: {active.get('title', '')} - {active.get('status', '')}")
        if todo:
            task_lines.append("Pending:")
            for t in todo[:3]:
                title = t.get("title", "")
                if title:
                    task_lines.append(f"- {title}")
        if task_lines:
            parts.append("CURRENT TASKS:\n" + "\n".join(task_lines))

        # 7) style controls
        parts.append(f"TONE: {tone_desc}")
        parts.append(f"VERBOSITY: {verb_desc}")

        prompt = "\n\n".join([x for x in parts if x]).strip()

        with self._lock:
            self._cached = prompt
            self._last_built = time.time()
        return prompt

    def get_cached(self) -> str:
        with self._lock:
            return self._cached

    def refresh_skills(self):
        self._skills = fetch_skills()

    def needs_rebuild(self) -> bool:
        return (time.time() - self._last_built) > SYSTEM_PROMPT_REFRESH


# ═══════════════════════════════════════
# RESOURCE MONITOR
# ═══════════════════════════════════════
class ResourceMonitor:
    def __init__(self):
        self._lock = threading.Lock()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._psutil_ok = False
        self.cpu_pct    = 0.0
        self.ram_pct    = 0.0
        self.disk_info  = []          # list of (mountpoint, pct)
        self.gpu_pct    = 0.0
        self.vram_pct   = 0.0
        self.gpu_temp   = 0
        self.gpu_available = True
        self.processes  = []          # list of (cpu%, mem%, pid, name)
        self._try_import()

    def _try_import(self):
        try:
            import psutil  # noqa
            self._psutil_ok = True
        except ImportError:
            self._psutil_ok = False

    def _collect(self):
        if not self._psutil_ok:
            return
        import psutil

        cpu = psutil.cpu_percent(interval=1)   # blocking 1 s sample for accuracy
        ram = psutil.virtual_memory().percent

        # Disk: home + root
        disks = []
        seen = set()
        for mnt in [os.path.expanduser("~"), "/home", "/"]:
            if mnt in seen:
                continue
            try:
                u = psutil.disk_usage(mnt)
                disks.append((mnt if mnt != os.path.expanduser("~") else "/home",
                               u.percent))
                seen.add(mnt)
            except Exception:
                pass

        # Processes top 10 CPU
        procs = []
        try:
            raw = []
            for p in psutil.process_iter(["pid", "name", "cpu_percent",
                                          "memory_percent", "cmdline"]):
                try:
                    info = p.info
                    cp = info.get("cpu_percent") or 0.0
                    mp = info.get("memory_percent") or 0.0
                    cmd = info.get("cmdline") or []
                    name = info.get("name", "")
                    pid  = info.get("pid", 0)
                    if cmd:
                        parts = [os.path.basename(cmd[0])]
                        parts += [c for c in cmd[1:3]
                                  if c and not c.startswith("-")]
                        display = " ".join(parts)[:30]
                    else:
                        display = name
                    raw.append((cp, mp, pid, display))
                except Exception:
                    pass
            raw.sort(reverse=True)
            procs = raw[:10]
        except Exception:
            pass

        # GPU
        gpu_pct, vram_pct, gpu_temp, gpu_ok = 0.0, 0.0, 0, self.gpu_available

        def _query_nvidia_smi():
            res = subprocess.run(
                ["nvidia-smi",
                 "--query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=3,
            )
            if res.returncode != 0:
                return None
            parts = res.stdout.strip().split(",")
            if len(parts) < 4:
                return None
            return parts

        try:
            fields = _query_nvidia_smi()
            if fields is not None:
                gpu_pct    = float(fields[0].strip())
                vram_used  = float(fields[1].strip())
                vram_total = float(fields[2].strip())
                gpu_temp   = int(float(fields[3].strip()))
                vram_pct   = (vram_used / vram_total * 100) if vram_total else 0
                gpu_ok     = True
                # Retry once if temp reads as 0 (common on first nvidia-smi call)
                if gpu_temp == 0:
                    time.sleep(0.1)
                    fields2 = _query_nvidia_smi()
                    if fields2 is not None:
                        gpu_temp = int(float(fields2[3].strip()))
            else:
                gpu_ok = False
        except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
            gpu_ok = False

        with self._lock:
            self.cpu_pct    = cpu
            self.ram_pct    = ram
            self.disk_info  = disks[:3]
            self.gpu_pct    = gpu_pct
            self.vram_pct   = vram_pct
            self.gpu_temp   = gpu_temp
            self.gpu_available = gpu_ok
            self.processes  = procs

    def start(self):
        self._running = True
        # Prime the CPU counter; first call always returns 0.0
        if self._psutil_ok:
            import psutil
            psutil.cpu_percent(interval=None)   # throwaway
            time.sleep(0.5)
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False

    def _loop(self):
        while self._running:
            try:
                self._collect()
            except Exception:
                pass
            time.sleep(REFRESH_INTERVAL)

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "cpu":          self.cpu_pct,
                "ram":          self.ram_pct,
                "disk":         list(self.disk_info),
                "gpu":          self.gpu_pct,
                "vram":         self.vram_pct,
                "gpu_temp":     self.gpu_temp,
                "gpu_available": self.gpu_available,
                "processes":    list(self.processes),
            }


# ═══════════════════════════════════════
# CHAT HISTORY
# ═══════════════════════════════════════
class ChatHistory:
    def __init__(self, max_len=MAX_CHAT_HISTORY):
        self.max_len = max_len
        self._lock = threading.Lock()
        self.lines: list = []       # (text, color_id, bold)
        self.exchanges: list = []   # (user_msg, bot_msg) last 10

    def add(self, text: str, color: int = C_USER, bold: bool = False):
        with self._lock:
            self.lines.append((text, color, bold))
            if len(self.lines) > self.max_len:
                self.lines = self.lines[-self.max_len:]

    def add_exchange(self, user_msg: str, bot_msg: str):
        self.exchanges.append((user_msg, bot_msg))
        if len(self.exchanges) > 10:
            self.exchanges = self.exchanges[-10:]

    def get_lines(self) -> list:
        with self._lock:
            return list(self.lines)

    def get_history_payload(self) -> list:
        result = []
        for u, b in self.exchanges[-10:]:
            result.append({"role": "user",      "content": u})
            result.append({"role": "assistant",  "content": b})
        return result

    def clear(self):
        with self._lock:
            self.lines.clear()


# ═══════════════════════════════════════
# HAIKU
# ═══════════════════════════════════════
def call_haiku(prompt: str) -> tuple:
    """Returns (text, error_str)."""
    key = get_anthropic_key()
    if not key:
        return "", "Anthropic API key not found in vault or secrets file"
    try:
        body = json.dumps({
            "model": "claude-haiku-4-5-20251001",
            "max_tokens": 1000,
            "messages": [{"role": "user", "content": prompt}],
        }).encode()
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=body,
            headers={
                "Content-Type": "application/json",
                "x-api-key": key,
                "anthropic-version": "2023-06-01",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            resp = json.loads(r.read().decode())
        text = resp.get("content", [{}])[0].get("text", "")
        return text, ""
    except Exception as exc:
        return "", str(exc)


# ═══════════════════════════════════════
# MAIN TUI
# ═══════════════════════════════════════
class SecureBotCLI:

    SPINNER = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"

    def __init__(self, stdscr):
        self.stdscr      = stdscr
        self.prefs       = load_prefs()
        self.chat        = ChatHistory()
        self.monitor     = ResourceMonitor()
        self.sp_builder  = SystemPromptBuilder(self.prefs)
        self.input_buf   = ""
        self.cursor_pos  = 0
        self.scroll_off  = 0
        self._running    = True
        self._thinking   = False
        self._spin_idx   = 0
        self._status_msg = ""
        self._draw_lock  = threading.Lock()
        self._redraw_needed = threading.Event()

    # ── INIT ──────────────────────────
    def init_colors(self):
        curses.start_color()
        curses.use_default_colors()
        gray = 8 if curses.COLORS >= 16 else curses.COLOR_WHITE
        curses.init_pair(C_HEADER,   curses.COLOR_WHITE,   curses.COLOR_BLUE)
        curses.init_pair(C_BOT,      curses.COLOR_CYAN,    -1)
        curses.init_pair(C_USER,     curses.COLOR_WHITE,   -1)
        curses.init_pair(C_DIM,      gray,                 -1)
        curses.init_pair(C_GREEN,    curses.COLOR_GREEN,   -1)
        curses.init_pair(C_YELLOW,   curses.COLOR_YELLOW,  -1)
        curses.init_pair(C_RED,      curses.COLOR_RED,     -1)
        curses.init_pair(C_CYAN_BAR, curses.COLOR_CYAN,    -1)
        curses.init_pair(C_MAGENTA,  curses.COLOR_MAGENTA, -1)
        curses.init_pair(C_GRAY_FILL,gray,                 -1)
        curses.init_pair(C_BOLD_W,   curses.COLOR_WHITE,   -1)

    def setup(self):
        self.init_colors()
        curses.curs_set(1)
        self.stdscr.timeout(100)
        self.stdscr.keypad(True)
        curses.cbreak()
        curses.noecho()
        # Ensure terminal size is fully initialized before first draw
        curses.resizeterm(*self.stdscr.getmaxyx())
        self.stdscr.clear()
        self.stdscr.refresh()
        time.sleep(0.1)

    # ── SAFE DRAW ─────────────────────
    def _put(self, row: int, col: int, text: str, attr: int = 0):
        h, w = self.stdscr.getmaxyx()
        if row < 0 or row >= h or col < 0 or col >= w:
            return
        max_len = w - col - 1
        if max_len <= 0:
            return
        try:
            self.stdscr.addstr(row, col, text[:max_len], attr)
        except curses.error:
            pass

    def _hline(self, row: int, w: int, char: str = "─"):
        try:
            self.stdscr.addstr(row, 0, char * (w - 1),
                               curses.color_pair(C_DIM))
        except curses.error:
            pass

    def _bar(self, row: int, col: int, width: int, pct: float,
             color_fill: int, warn: int = 80, crit: int = 90):
        h, w = self.stdscr.getmaxyx()
        if row >= h:
            return
        filled = int(width * min(100.0, pct) / 100)
        if pct >= crit:
            fa = curses.color_pair(C_RED)    | curses.A_BOLD
        elif pct >= warn:
            fa = curses.color_pair(C_YELLOW)
        else:
            fa = curses.color_pair(color_fill)
        ea = curses.color_pair(C_GRAY_FILL) | curses.A_DIM
        for i in range(width):
            c = col + i
            if c >= w - 1:
                break
            try:
                self.stdscr.addstr(row, c, "█" if i < filled else "░",
                                   fa if i < filled else ea)
            except curses.error:
                pass

    # ── LAYOUT ────────────────────────
    def _layout(self, h: int, w: int) -> dict:
        # Fixed row assignments:
        # 0        header
        # 1-3      resources (cpu/gpu, ram/vram, disk/temp) → row 4 = hline
        # 4        hline between resources and procs
        # 5        proc header
        # 6-7      proc rows (2 processes)
        # 8        hline between procs and chat
        # 9..h-3   chat area
        # h-2      input
        # h-1      status bar
        return {
            "header":     0,
            "res_rows":  (1, 3),       # inclusive
            "hline1":     4,
            "proc_hdr":   5,
            "proc_rows": (6, 7),       # inclusive
            "hline2":     8,
            "chat_top":   9,
            "chat_bot":   h - 3,       # inclusive
            "input_row":  h - 2,
            "status_row": h - 1,
            "h": h, "w": w,
        }

    # ── SECTION DRAWERS ───────────────
    def _draw_header(self, row: int, w: int):
        t = self.prefs.get("tone", 2)
        v = self.prefs.get("verbosity", 3)
        left  = f" SecureBot CLI | phi4-mini | local | p{t}"
        right = f" tone:{t}|v:{v} "
        pad   = max(0, w - len(left) - len(right) - 1)
        line  = left + " " * pad + right
        try:
            self.stdscr.addstr(row, 0, line[:w-1],
                               curses.color_pair(C_HEADER) | curses.A_BOLD)
        except curses.error:
            pass

    def _draw_resources(self, lyt: dict, snap: dict):
        w       = lyt["w"]
        half    = w // 2
        has_gpu = snap["gpu_available"]
        bar_w   = 10
        r0      = lyt["res_rows"][0]
        ua      = curses.color_pair(C_USER)
        dim     = curses.color_pair(C_DIM)

        # Row 0: CPU | GPU
        self._put(r0, 0, " CPU  ", ua)
        self._bar(r0, 6, bar_w, snap["cpu"], C_GREEN)
        self._put(r0, 6 + bar_w, f" {snap['cpu']:4.0f}%", ua)
        if has_gpu:
            self._put(r0, half, "│", dim)
            self._put(r0, half + 2, " GPU  ", ua)
            self._bar(r0, half + 8, bar_w, snap["gpu"], C_CYAN_BAR)
            self._put(r0, half + 8 + bar_w, f" {snap['gpu']:4.0f}%", ua)

        # Row 1: RAM | VRAM
        r1 = r0 + 1
        self._put(r1, 0, " RAM  ", ua)
        self._bar(r1, 6, bar_w, snap["ram"], C_GREEN)
        self._put(r1, 6 + bar_w, f" {snap['ram']:4.0f}%", ua)
        if has_gpu:
            self._put(r1, half, "│", dim)
            self._put(r1, half + 2, " VRAM ", ua)
            self._bar(r1, half + 8, bar_w, snap["vram"], C_CYAN_BAR)
            self._put(r1, half + 8 + bar_w, f" {snap['vram']:4.0f}%", ua)

        # Row 2: DISK | GPU Temp
        r2 = r0 + 2
        disk_str = " DISK"
        for mnt, pct in snap["disk"][:2]:
            short = "/home" if "/home" in mnt else mnt
            disk_str += f" {short} {pct:.0f}%"
        self._put(r2, 0, disk_str[:half - 1], ua)
        if has_gpu:
            temp  = snap["gpu_temp"]
            tc    = C_RED if temp >= 85 else C_YELLOW if temp >= 75 else C_GREEN
            self._put(r2, half, "│", dim)
            self._put(r2, half + 2, f"GPU Temp: {temp}°C",
                      curses.color_pair(tc))

    def _draw_processes(self, lyt: dict, snap: dict):
        w     = lyt["w"]
        r_hdr = lyt["proc_hdr"]
        r0, r1 = lyt["proc_rows"]
        procs = snap["processes"]
        da    = curses.color_pair(C_DIM) | curses.A_BOLD
        ua    = curses.color_pair(C_USER)

        self._put(r_hdr, 0,
                  f" {'PID':>6}  {'CPU%':>5}  {'MEM%':>5}  PROCESS"[:w-1], da)
        for i, row in enumerate(range(r0, r1 + 1)):
            if i < len(procs):
                cp, mp, pid, name = procs[i]
                line = f" {pid:>6}  {cp:>5.1f}  {mp:>5.1f}  {name}"
                self._put(row, 0, line[:w-1], ua)

    def _draw_chat(self, lyt: dict):
        w         = lyt["w"]
        chat_top  = lyt["chat_top"]
        chat_bot  = lyt["chat_bot"]
        vis_rows  = max(1, chat_bot - chat_top + 1)

        raw_lines = self.chat.get_lines()

        # Word-wrap
        wrapped = []
        for text, color, bold in raw_lines:
            while len(text) > w - 2:
                wrapped.append((text[:w-2], color, bold))
                text = "  " + text[w-2:]
            wrapped.append((text, color, bold))

        total = len(wrapped)
        start = max(0, total - vis_rows - self.scroll_off)

        for i in range(vis_rows):
            draw_row = chat_top + i
            if draw_row > chat_bot or draw_row >= lyt["h"] - 2:
                break
            li = start + i
            if li < total:
                text, color, bold = wrapped[li]
                attr = curses.color_pair(color)
                if bold:
                    attr |= curses.A_BOLD
                self._put(draw_row, 0, " " + text[:w-2], attr)
                # pad to clear stale chars
                rest = w - len(text) - 2
                if rest > 0:
                    self._put(draw_row, len(text) + 1, " " * rest, 0)
            else:
                self._put(draw_row, 0, " " * (w - 1), 0)

    def _draw_input(self, lyt: dict):
        w   = lyt["w"]
        row = lyt["input_row"]
        h   = lyt["h"]
        if row >= h - 1:
            return

        if self._thinking:
            sp  = self.SPINNER[self._spin_idx % len(self.SPINNER)]
            txt = f" {sp} Thinking..."
            self._put(row, 0, txt + " " * max(0, w - len(txt) - 1),
                      curses.color_pair(C_YELLOW) | curses.A_BOLD)
        else:
            t   = self.prefs.get("tone", 2)
            v   = self.prefs.get("verbosity", 3)
            pre = f" [tone:{t}|v:{v}] > "
            avail = max(1, w - len(pre) - 2)
            buf   = self.input_buf
            # scroll buffer so cursor is visible
            if len(buf) > avail:
                # show window ending at cursor
                end   = min(len(buf), self.cursor_pos + avail // 2)
                start = max(0, end - avail)
                buf   = buf[start:start + avail]
            line  = pre + buf
            self._put(row, 0, line + " " * max(0, w - len(line) - 1),
                      curses.color_pair(C_BOLD_W) | curses.A_BOLD)

        # Status bar
        sr = lyt["status_row"]
        if sr < h:
            msg = (" " + self._status_msg) if self._status_msg else ""
            self._put(sr, 0, msg + " " * max(0, w - len(msg) - 1),
                      curses.color_pair(C_DIM))

    def _place_cursor(self, lyt: dict):
        if self._thinking:
            return
        row = lyt["input_row"]
        h, w = self.stdscr.getmaxyx()
        if row >= h - 1:
            return
        t   = self.prefs.get("tone", 2)
        v   = self.prefs.get("verbosity", 3)
        pre = f" [tone:{t}|v:{v}] > "
        avail = max(1, w - len(pre) - 2)
        buf   = self.input_buf
        cx    = self.cursor_pos
        if len(buf) > avail:
            end   = min(len(buf), cx + avail // 2)
            start = max(0, end - avail)
            cx    = cx - start
        cx = len(pre) + max(0, min(cx, avail))
        if cx < w - 1:
            try:
                self.stdscr.move(row, cx)
            except curses.error:
                pass

    # ── FULL REDRAW ───────────────────
    def redraw(self):
        with self._draw_lock:
            try:
                snap = self.monitor.snapshot()
                h, w = self.stdscr.getmaxyx()
                if h < 12 or w < 40:
                    return
                lyt = self._layout(h, w)

                self.stdscr.erase()
                self._draw_header(lyt["header"], w)
                self._draw_resources(lyt, snap)
                self._hline(lyt["hline1"], w)
                self._draw_processes(lyt, snap)
                self._hline(lyt["hline2"], w)
                self._draw_chat(lyt)
                self._draw_input(lyt)
                self._place_cursor(lyt)
                self.stdscr.refresh()
            except Exception as _draw_exc:
                open("/tmp/securebot-draw-error.log", "a").write(
                    f"{__import__('time').time()}: {_draw_exc}\n"
                    + __import__('traceback').format_exc()
                )

    # ── GATEWAY ───────────────────────
    def _send_message(self, user_msg: str):
        """Fire-and-forget in background thread."""
        self._thinking = True
        self._spin_idx = 0
        self.chat.add(f"You: {user_msg}", C_USER)
        self.redraw()

        def _worker():
            try:
                sys_prompt = self.sp_builder.build(user_msg)
                payload = {
                    "channel":     "cli",
                    "user_id":     USER_ID,
                    "text":        user_msg,
                    "system":      sys_prompt,
                    "history":     self.chat.get_history_payload(),
                    "temperature": 0.7,
                }
                t0   = time.time()
                resp = http_post(f"{GATEWAY_URL}/message", payload, timeout=60)
                elapsed = time.time() - t0

                if resp is None:
                    self.chat.add("Error: Gateway unreachable", C_RED)
                else:
                    bot = (resp.get("response") or resp.get("text") or
                           resp.get("message") or str(resp))
                    method = resp.get("method", "gateway")
                    self.chat.add(f"Bot: {bot}", C_BOT)
                    self.chat.add(f"  [{method} | {elapsed:.1f}s]", C_DIM)
                    self.chat.add_exchange(user_msg, bot)
                    # Store in RAG asynchronously
                    threading.Thread(
                        target=rag_store_exchange,
                        args=(user_msg, bot, {
                            "timestamp":  time.time(),
                            "method":     method,
                            "tone":       self.prefs.get("tone"),
                            "verbosity":  self.prefs.get("verbosity"),
                        }),
                        daemon=True,
                    ).start()
            except Exception as exc:
                self.chat.add(f"Error: {exc}", C_RED)
            finally:
                self._thinking = False
                self._redraw_needed.set()

        threading.Thread(target=_worker, daemon=True).start()

    def _open_editor(self, path: str, editor: str, fname: str):
        """Suspend curses, run $EDITOR, then restore terminal state safely."""
        try:
            curses.def_prog_mode()
            curses.endwin()
            print("Opening editor... (save and exit to return to SecureBot CLI)")
            cmd = shlex.split(editor) if editor else ["nano"]
            subprocess.call(cmd + [path])
        except Exception as exc:
            self.chat.add(f"Editor error: {exc}", C_RED)
        finally:
            try:
                curses.reset_prog_mode()
                self.stdscr.keypad(True)
                curses.cbreak()
                curses.noecho()
                self.stdscr.nodelay(True)
                curses.flushinp()
                self.stdscr.clear()
                self.stdscr.refresh()
            except Exception:
                pass

        # Rebuild system prompt so edits take effect immediately
        try:
            self.sp_builder.build()
            self.chat.add(f"{fname} saved. System prompt reloaded.", C_GREEN)
        except Exception as exc:
            self.chat.add(f"Prompt rebuild error: {exc}", C_YELLOW)
        self._redraw_needed.set()

    # ── SLASH COMMANDS ────────────────
    def _slash(self, raw: str):
        """Handle /command [args].  raw includes the leading slash."""
        if raw.startswith("/"):
            raw = raw[1:]
        parts = raw.strip().split(None, 1)
        if not parts:
            return
        verb = "/" + parts[0].lower()
        arg  = parts[1] if len(parts) > 1 else ""

        # ── TUNING ──────────────────────
        if verb in ("/tone", "/t"):
            try:
                v = int(arg)
                assert v in TONE_DESCRIPTIONS
                self.prefs["tone"] = v
                save_prefs(self.prefs)
                self.chat.add(f"Tone set to {v} ({TONE_DESCRIPTIONS[v][0]})", C_GREEN)
                self.sp_builder.build()
            except Exception:
                self.chat.add("Usage: /tone <1-3>", C_RED)
            return

        if verb in ("/verbosity", "/v"):
            try:
                v = int(arg)
                assert v in VERBOSITY_DESCRIPTIONS
                self.prefs["verbosity"] = v
                save_prefs(self.prefs)
                self.chat.add(f"Verbosity set to {v} ({VERBOSITY_DESCRIPTIONS[v][0]})", C_GREEN)
                self.sp_builder.build()
            except Exception:
                self.chat.add("Usage: /verbosity <1-5>", C_RED)
            return

        if verb == "/prefs":
            t = self.prefs.get("tone", 2)
            v = self.prefs.get("verbosity", 3)
            tn, td = TONE_DESCRIPTIONS.get(t, ("?", ""))
            vn, vd = VERBOSITY_DESCRIPTIONS.get(v, ("?", ""))
            self.chat.add(f"Tone {t}: {tn} — {td}", C_USER)
            self.chat.add(f"Verbosity {v}: {vn} — {vd}", C_USER)
            return

        if verb == "/tune":
            self.chat.add("── Tone ─────────────────────────────", C_DIM)
            for k, (n, d) in TONE_DESCRIPTIONS.items():
                self.chat.add(f"  {k}: {n:10s} {d[:55]}", C_USER)
            self.chat.add("── Verbosity ────────────────────────", C_DIM)
            for k, (n, d) in VERBOSITY_DESCRIPTIONS.items():
                self.chat.add(f"  {k}: {n:10s} {d[:55]}", C_USER)
            self.chat.add("Use /tone <1-3>  /verbosity <1-5>", C_GREEN)
            return

        # ── MEMORY / TASKS ──────────────
        if verb == "/tasks":
            tasks = read_tasks()
            active = tasks.get("active_task")
            if active:
                self.chat.add(
                    f"Active [{active.get('priority','').upper()}]: "
                    f"{active.get('title','')} — {active.get('status','')}",
                    C_GREEN)
            todo = tasks.get("todo", [])
            if todo:
                self.chat.add(f"Todo ({len(todo)}):", C_USER)
                for t in todo:
                    self.chat.add(
                        f"  • [{t.get('priority','med').upper()[:3]}] "
                        f"{t.get('title','')}", C_USER)
            done = tasks.get("completed", [])
            if done:
                self.chat.add(f"Completed ({len(done)}):", C_DIM)
                for t in done[-3:]:
                    self.chat.add(f"  ✓ {t.get('title','')}", C_DIM)
            if not active and not todo and not done:
                self.chat.add("No tasks found.", C_DIM)
            return

        if verb == "/task":
            if not arg:
                self.chat.add("Usage: /task <description>", C_RED)
                return
            if append_task(arg):
                self.chat.add(f"Task added: {arg}", C_GREEN)
            else:
                self.chat.add("Failed to add task", C_RED)
            return

        if verb == "/memory":
            soul    = read_file_safe(os.path.join(MEMORY_DIR, "soul.md"))
            user_md = read_file_safe(os.path.join(MEMORY_DIR, "user.md"))
            self.chat.add("── soul.md ──", C_DIM)
            for ln in soul.split("\n")[:12]:
                self.chat.add(ln or " ", C_USER)
            self.chat.add("── user.md ──", C_DIM)
            for ln in user_md.split("\n")[:12]:
                self.chat.add(ln or " ", C_USER)
            return

        if verb == "/edit":
            valid = {"soul", "user", "session"}
            if arg not in valid:
                self.chat.add("Usage: /edit <soul|user|session>", C_RED)
                return
            fname = f"{arg}.md"
            fpath = os.path.join(MEMORY_DIR, fname)
            editor = os.environ.get("EDITOR", "nano")
            self._open_editor(fpath, editor, fname)
            return

        if verb == "/reload":
            self.chat.add("Reloading memory + rebuilding system prompt...", C_DIM)
            def _do():
                self.sp_builder.refresh_skills()
                self.sp_builder.build()
                self.chat.add("System prompt rebuilt.", C_GREEN)
                self._redraw_needed.set()
            threading.Thread(target=_do, daemon=True).start()
            return

        if verb == "/session":
            if not arg:
                self.chat.add("Usage: /session <note>", C_RED)
                return
            if append_session_note(arg):
                ts = datetime.now().strftime("%H:%M:%S")
                self.chat.add(f"[{ts}] Session note saved.", C_GREEN)
            else:
                self.chat.add("Failed to write session.md", C_RED)
            return

        # ── SYSTEM ──────────────────────
        if verb == "/skills":
            self.chat.add("Fetching skills...", C_DIM)
            def _do():
                skills = fetch_skills()
                if not skills:
                    self.chat.add("No skills / gateway unreachable", C_RED)
                else:
                    self.chat.add(f"Skills ({len(skills)}):", C_USER)
                    for s in skills:
                        n = s.get("name", "")
                        d = s.get("description", "")
                        self.chat.add(f"  • {n}: {d}", C_USER)
                self._redraw_needed.set()
            threading.Thread(target=_do, daemon=True).start()
            return

        if verb == "/status":
            self.chat.add("── Service Status ──", C_DIM)
            def _do():
                checks = [
                    ("Gateway", f"{GATEWAY_URL}/health"),
                    ("Vault",   f"{VAULT_URL}/health"),
                    ("RAG",     f"{RAG_URL}/health"),
                    ("Ollama",  "http://localhost:11434/api/tags"),
                ]
                for name, url in checks:
                    ok = http_get(url, timeout=3) is not None
                    if ok:
                        self.chat.add(f"  ✓ {name}: OK", C_GREEN)
                    else:
                        self.chat.add(f"  ✗ {name}: unreachable", C_RED)
                self._redraw_needed.set()
            threading.Thread(target=_do, daemon=True).start()
            return

        if verb == "/clear":
            self.chat.clear()
            return

        if verb == "/help":
            lines = [
                ("── SecureBot CLI ──────────────────────────────", C_DIM),
                ("MEMORY & TASKS",                                  C_DIM),
                ("  /tasks               List all tasks",           C_USER),
                ("  /task <desc>         Add a task",               C_USER),
                ("  /memory              Show soul + user profile", C_USER),
                ("  /edit <soul|user|session>  Open file in $EDITOR", C_USER),
                ("  /reload              Reload memory files",       C_USER),
                ("  /session <note>      Append to session.md",     C_USER),
                ("SYSTEM",                                           C_DIM),
                ("  /skills             List gateway skills",        C_USER),
                ("  /status             Health check services",      C_USER),
                ("  /clear              Clear chat",                 C_USER),
                ("  /help               This help",                  C_USER),
                ("  /quit  /exit        Exit",                       C_USER),
                ("TUNING",                                           C_DIM),
                ("  /tone <1-3>         1=Formal 2=Balanced 3=Casual", C_USER),
                ("  /verbosity <1-5>    1=Curt … 5=Chatty",         C_USER),
                ("  /v <1-5>            Shorthand verbosity",        C_USER),
                ("  /t <1-3>            Shorthand tone",             C_USER),
                ("  /prefs              Show current settings",      C_USER),
                ("  /tune               Full tuning scale",          C_USER),
                ("AI DELEGATION",                                    C_DIM),
                ("  /cc <prompt>        Stream Claude Code output",  C_YELLOW),
                ("  /haiku <prompt>     Call Claude Haiku API",      C_MAGENTA),
                ("KEYBOARD",                                         C_DIM),
                ("  PgUp/PgDn ↑↓        Scroll chat",               C_USER),
                ("  Ctrl-A/E            Home/End in input",          C_USER),
                ("  Ctrl-U/K            Clear line / clear to end",  C_USER),
            ]
            for text, col in lines:
                self.chat.add(text, col)
            return

        if verb in ("/quit", "/exit"):
            self._running = False
            return

        # ── AI DELEGATION ───────────────
        if verb == "/cc":
            if not arg:
                self.chat.add("Usage: /cc <prompt>", C_RED)
                return
            preview = arg if len(arg) <= 70 else arg[:67] + "..."
            self.chat.add(f"[Claude Code] > {preview}", C_YELLOW)
            def _run():
                try:
                    proc = subprocess.Popen(
                        ["claude", "-p", "--dangerously-skip-permissions", arg],
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                        text=True, bufsize=1,
                    )
                    for line in proc.stdout:
                        stripped = line.rstrip()
                        if stripped:
                            self.chat.add(f"[Claude Code] {stripped}", C_YELLOW)
                            self._redraw_needed.set()
                    proc.wait()
                    self.chat.add(
                        f"[Claude Code] Done (exit {proc.returncode})", C_YELLOW)
                except FileNotFoundError:
                    self.chat.add(
                        "[Claude Code] Not installed. "
                        "Run: npm i -g @anthropic-ai/claude-code", C_RED)
                except Exception as exc:
                    self.chat.add(f"[Claude Code] Error: {exc}", C_RED)
                self._redraw_needed.set()
            threading.Thread(target=_run, daemon=True).start()
            return

        if verb == "/haiku":
            if not arg:
                self.chat.add("Usage: /haiku <prompt>", C_RED)
                return
            self.chat.add("[Haiku] Querying claude-haiku-4-5-20251001...", C_MAGENTA)
            def _run():
                text, err = call_haiku(arg)
                if err:
                    self.chat.add(f"[Haiku] Error: {err}", C_RED)
                else:
                    for ln in text.split("\n"):
                        self.chat.add(f"[Haiku] {ln}", C_MAGENTA)
                self._redraw_needed.set()
            threading.Thread(target=_run, daemon=True).start()
            return

        self.chat.add(f"Unknown command: {verb}  (try /help)", C_RED)

    # ── INPUT HANDLING ────────────────
    def handle_key(self, key: int):
        if key == curses.KEY_RESIZE:
            try:
                h, w = self.stdscr.getmaxyx()
                curses.resizeterm(h, w)
                self.stdscr.clear()
            except Exception:
                pass
            self.redraw()
            return

        # Backspace
        if key in (curses.KEY_BACKSPACE, 127, 8):
            if self.cursor_pos > 0:
                self.input_buf = (self.input_buf[:self.cursor_pos - 1]
                                  + self.input_buf[self.cursor_pos:])
                self.cursor_pos -= 1
            return

        if key == curses.KEY_DC:
            if self.cursor_pos < len(self.input_buf):
                self.input_buf = (self.input_buf[:self.cursor_pos]
                                  + self.input_buf[self.cursor_pos + 1:])
            return

        if key == curses.KEY_LEFT:
            self.cursor_pos = max(0, self.cursor_pos - 1)
            return
        if key == curses.KEY_RIGHT:
            self.cursor_pos = min(len(self.input_buf), self.cursor_pos + 1)
            return
        if key in (curses.KEY_HOME, 1):    # Ctrl-A
            self.cursor_pos = 0
            return
        if key in (curses.KEY_END, 5):     # Ctrl-E
            self.cursor_pos = len(self.input_buf)
            return

        if key == curses.KEY_PPAGE:        # Page Up
            self.scroll_off = min(
                self.scroll_off + 5,
                max(0, len(self.chat.get_lines()) - 5))
            return
        if key == curses.KEY_NPAGE:        # Page Down
            self.scroll_off = max(0, self.scroll_off - 5)
            return
        if key == curses.KEY_UP:
            self.scroll_off += 1
            return
        if key == curses.KEY_DOWN:
            self.scroll_off = max(0, self.scroll_off - 1)
            return

        if key == 21:   # Ctrl-U
            self.input_buf  = ""
            self.cursor_pos = 0
            return
        if key == 11:   # Ctrl-K
            self.input_buf  = self.input_buf[:self.cursor_pos]
            return

        # Enter
        if key in (10, 13, curses.KEY_ENTER):
            msg = self.input_buf.strip()
            self.input_buf  = ""
            self.cursor_pos = 0
            self.scroll_off = 0        # pin to bottom on submit
            if not msg:
                return
            if msg.startswith("/"):
                self._slash(msg)
            else:
                if not self._thinking:
                    self._send_message(msg)
            return

        # Printable
        if 32 <= key <= 126:
            ch = chr(key)
            self.input_buf = (self.input_buf[:self.cursor_pos]
                              + ch
                              + self.input_buf[self.cursor_pos:])
            self.cursor_pos += 1

    # ── STARTUP ───────────────────────
    def _startup(self):
        self.chat.add("SecureBot CLI v1.0  —  type /help for commands", C_DIM)
        self._status_msg = "Warming up..."
        self.redraw()

        def _init():
            try:
                rag_warmup()
                self._status_msg = ""
                self.chat.add("RAG ready.", C_GREEN)
            except Exception:
                self._status_msg = ""
                self.chat.add("RAG unavailable — using full memory injection.", C_YELLOW)

            try:
                self.sp_builder.refresh_skills()
                self.sp_builder.build()
                self.chat.add("System prompt built.", C_DIM)
            except Exception as exc:
                self.chat.add(f"System prompt warning: {exc}", C_YELLOW)

            self._redraw_needed.set()

        threading.Thread(target=_init, daemon=True).start()

    def _prompt_refresh_loop(self):
        while self._running:
            time.sleep(5)
            if not self._running:
                break
            if self.sp_builder.needs_rebuild():
                try:
                    self.sp_builder.refresh_skills()
                    self.sp_builder.build()
                except Exception:
                    pass

    # ── MAIN LOOP ─────────────────────
    def run(self):
        self.setup()
        self.monitor.start()
        self._startup()

        threading.Thread(target=self._prompt_refresh_loop,
                         daemon=True).start()

        last_draw = 0.0
        self.stdscr.nodelay(True)   # non-blocking getch
        try:
            while self._running:
                time.sleep(0.02)    # 20ms = max 50 iter/sec, prevents spin

                # Service redraw requests from background threads
                if self._redraw_needed.is_set():
                    self._redraw_needed.clear()
                    self.redraw()
                    last_draw = time.time()

                # Periodic refresh
                now = time.time()
                if now - last_draw >= 0.3:
                    if self._thinking:
                        self._spin_idx += 1
                    self.redraw()
                    last_draw = now

                # Non-blocking key check
                try:
                    ch = self.stdscr.getch()
                except curses.error:
                    continue

                if ch == -1:
                    continue

                if ch == curses.KEY_RESIZE:
                    curses.resizeterm(*self.stdscr.getmaxyx())
                    self.redraw()
                    continue

                self.handle_key(ch)
                self.redraw()

        except KeyboardInterrupt:
            pass
        finally:
            self._running = False
            self.monitor.stop()


# ═══════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════
def _ensure_psutil():
    try:
        import psutil  # noqa
    except ImportError:
        print("psutil not found — installing...", flush=True)
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "psutil", "-q"],
            check=False)


def main(stdscr):
    app = SecureBotCLI(stdscr)
    app.run()


if __name__ == "__main__":
    _ensure_psutil()
    try:
        curses.wrapper(main)
    except KeyboardInterrupt:
        pass
    except Exception as exc:
        print(f"\nFatal error: {exc}", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)
