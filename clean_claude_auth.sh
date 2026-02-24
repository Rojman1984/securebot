#!/usr/bin/env bash
# =============================================================================
# clean_claude_auth.sh
# Removes global ANTHROPIC_API_KEY instances from shell configs,
# resets Claude Code to install defaults, preps for Pro OAuth login.
# Roland / SecureBot-P2
# =============================================================================

set -euo pipefail

# ── Colors ────────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
RESET='\033[0m'

log()    { echo -e "${CYAN}[INFO]${RESET}  $*"; }
ok()     { echo -e "${GREEN}[OK]${RESET}    $*"; }
warn()   { echo -e "${YELLOW}[WARN]${RESET}  $*"; }
danger() { echo -e "${RED}[REMOVE]${RESET} $*"; }
header() { echo -e "\n${BOLD}── $* ──${RESET}"; }

BACKUP_DIR="$HOME/.claude_auth_backup_$(date +%Y%m%d_%H%M%S)"
DRY_RUN=false
[[ "${1:-}" == "--dry-run" ]] && DRY_RUN=true

if $DRY_RUN; then
  warn "DRY RUN MODE — no changes will be made"
fi

echo -e "${BOLD}"
echo "  ╔══════════════════════════════════════════╗"
echo "  ║     Claude Auth Cleanup · SecureBot-P2  ║"
echo "  ╚══════════════════════════════════════════╝"
echo -e "${RESET}"

# ── 1. Locate API key instances ───────────────────────────────────────────────
header "Scanning for ANTHROPIC_API_KEY in shell configs"

SHELL_CONFIGS=(
  "$HOME/.bashrc"
  "$HOME/.bash_profile"
  "$HOME/.bash_aliases"
  "$HOME/.zshrc"
  "$HOME/.zprofile"
  "$HOME/.profile"
  "$HOME/.config/fish/config.fish"
  "$HOME/.envrc"
  "/etc/environment"
)

FOUND=()

for f in "${SHELL_CONFIGS[@]}"; do
  if [[ -f "$f" ]] && grep -q "ANTHROPIC_API_KEY" "$f" 2>/dev/null; then
    danger "Found in: $f"
    grep -n "ANTHROPIC_API_KEY" "$f" | while read -r line; do
      echo "         Line $line"
    done
    FOUND+=("$f")
  fi
done

# Also scan for .env files in common project dirs (non-recursive, shallow)
log "Scanning shallow project dirs for .env files..."
for dir in "$HOME" "$HOME/projects" "$HOME/dev" "$HOME/code"; do
  if [[ -d "$dir" ]]; then
    while IFS= read -r envfile; do
      if grep -q "ANTHROPIC_API_KEY" "$envfile" 2>/dev/null; then
        warn "Found in project .env: $envfile (leaving in place — scoped file)"
        grep -n "ANTHROPIC_API_KEY" "$envfile" | while read -r line; do
          echo "         Line $line"
        done
      fi
    done < <(find "$dir" -maxdepth 2 -name ".env" 2>/dev/null)
  fi
done

if [[ ${#FOUND[@]} -eq 0 ]]; then
  ok "No global ANTHROPIC_API_KEY found in shell configs."
else
  echo ""
  warn "Found in ${#FOUND[@]} global config file(s). Proceeding to clean..."
fi

# ── 2. Backup and clean ───────────────────────────────────────────────────────
header "Backing up and cleaning shell configs"

if [[ ${#FOUND[@]} -gt 0 ]]; then
  if ! $DRY_RUN; then
    mkdir -p "$BACKUP_DIR"
    log "Backups → $BACKUP_DIR"
  fi

  for f in "${FOUND[@]}"; do
    if $DRY_RUN; then
      warn "[DRY RUN] Would remove ANTHROPIC_API_KEY lines from: $f"
    else
      cp "$f" "$BACKUP_DIR/$(basename "$f").bak"
      ok "Backed up: $f"
      # Remove lines containing ANTHROPIC_API_KEY (export and plain assignment)
      sed -i '/ANTHROPIC_API_KEY/d' "$f"
      ok "Cleaned:   $f"
    fi
  done
fi

# ── 3. Unset from current session ─────────────────────────────────────────────
header "Unsetting from current shell session"

if [[ -n "${ANTHROPIC_API_KEY:-}" ]]; then
  if $DRY_RUN; then
    warn "[DRY RUN] Would unset ANTHROPIC_API_KEY from current session"
  else
    unset ANTHROPIC_API_KEY
    ok "ANTHROPIC_API_KEY unset from current session"
  fi
else
  ok "ANTHROPIC_API_KEY not set in current session"
fi

# ── 4. Reset Claude Code config ───────────────────────────────────────────────
header "Resetting Claude Code to install defaults"

CLAUDE_DIRS=(
  "$HOME/.claude"
  "$HOME/.config/claude"
  "$HOME/.local/share/claude"
)

for d in "${CLAUDE_DIRS[@]}"; do
  if [[ -d "$d" ]]; then
    if $DRY_RUN; then
      warn "[DRY RUN] Would back up and reset: $d"
    else
      mkdir -p "$BACKUP_DIR"
      cp -r "$d" "$BACKUP_DIR/$(basename "$d")_backup" 2>/dev/null || true
      ok "Backed up: $d → $BACKUP_DIR"
      rm -rf "$d"
      ok "Removed:   $d"
    fi
  fi
done

# Run claude logout to clear any cached OAuth sessions
if command -v claude &>/dev/null; then
  if $DRY_RUN; then
    warn "[DRY RUN] Would run: claude logout"
  else
    log "Running: claude logout"
    claude logout 2>/dev/null || warn "claude logout returned non-zero (may already be logged out)"
    ok "Claude Code session cleared"
  fi
else
  warn "claude command not found in PATH — skipping logout"
fi

# ── 5. Verify clean ───────────────────────────────────────────────────────────
header "Verification"

if [[ -z "${ANTHROPIC_API_KEY:-}" ]]; then
  ok "ANTHROPIC_API_KEY is not set in this session ✓"
else
  danger "ANTHROPIC_API_KEY is STILL SET: ${ANTHROPIC_API_KEY:0:12}... (source a new shell)"
fi

for f in "${SHELL_CONFIGS[@]}"; do
  if [[ -f "$f" ]] && grep -q "ANTHROPIC_API_KEY" "$f" 2>/dev/null; then
    danger "Still present in: $f — manual review needed"
  fi
done

# ── 6. Next steps ─────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}══ Next Steps ══════════════════════════════════════════${RESET}"
echo ""
echo -e "  ${GREEN}1.${RESET} Open a ${BOLD}fresh terminal${RESET} (source the cleaned shell config)"
echo -e "     ${CYAN}source ~/.bashrc${RESET}  or  ${CYAN}source ~/.zshrc${RESET}"
echo ""
echo -e "  ${GREEN}2.${RESET} Re-authenticate Claude Code to your ${BOLD}Pro account${RESET}:"
echo -e "     ${CYAN}claude login${RESET}"
echo -e "     → Use claude.ai credentials only"
echo -e "     → ${RED}Do NOT add Console/API credentials when prompted${RESET}"
echo ""
echo -e "  ${GREEN}3.${RESET} Verify Claude Code is using ${BOLD}subscription billing${RESET}:"
echo -e "     ${CYAN}claude /status${RESET}"
echo -e "     → Should show ${GREEN}Pro plan${RESET}, not API usage"
echo ""
echo -e "  ${GREEN}4.${RESET} Inject API key into SecureBot at runtime via vault:"
echo -e "     In your ${CYAN}docker-compose.yml${RESET} or vault secret → container env"
echo -e "     ${CYAN}ANTHROPIC_API_KEY: \${VAULT_SECRET_ANTHROPIC_KEY}${RESET}"
echo ""
if [[ -d "$BACKUP_DIR" ]]; then
  echo -e "  ${YELLOW}⚠${RESET}  Backups saved to: ${BOLD}$BACKUP_DIR${RESET}"
  echo -e "     Safe to delete after confirming everything works."
fi
echo ""
echo -e "${GREEN}${BOLD}  Done. Your Pro allowance is now yours again. 🎯${RESET}"
echo ""
