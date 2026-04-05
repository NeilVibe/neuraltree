#!/usr/bin/env bash
#
# NeuralTree Installer
# Installs the skill, MCP server dependencies, and registers with Claude Code.
#
# Usage:
#   ./install.sh          Install everything
#   ./install.sh --check  Verify installation without changing anything
#
set -euo pipefail

# ─── Colors ───────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
RESET='\033[0m'

info()  { printf "${BLUE}[info]${RESET}  %s\n" "$1"; }
ok()    { printf "${GREEN}[ok]${RESET}    %s\n" "$1"; }
warn()  { printf "${YELLOW}[warn]${RESET}  %s\n" "$1"; }
fail()  { printf "${RED}[FAIL]${RESET}  %s\n" "$1"; exit 1; }

# ─── Resolve install directory (where this script lives) ─────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_SRC="${SCRIPT_DIR}/src/skill/SKILL.md"
REQUIREMENTS="${SCRIPT_DIR}/requirements.txt"

SKILL_DEST_DIR="${HOME}/.claude/skills/neuraltree"
SKILL_DEST="${SKILL_DEST_DIR}/SKILL.md"
CLAUDE_JSON="${HOME}/.claude.json"

# ─── Header ──────────────────────────────────────────────────────────
printf "\n${BOLD}"
printf "  ╔═══════════════════════════════════════╗\n"
printf "  ║       NeuralTree Installer v0.1.0     ║\n"
printf "  ╚═══════════════════════════════════════╝\n"
printf "${RESET}\n"

# ─── Check-only mode ─────────────────────────────────────────────────
CHECK_ONLY=false
if [[ "${1:-}" == "--check" ]]; then
    CHECK_ONLY=true
    info "Running in check-only mode (no changes will be made)"
    printf "\n"
fi

# ─── Step 1: Verify Python 3.11+ ────────────────────────────────────
info "Checking Python version..."

PYTHON_CMD=""
for cmd in python3.11 python3 python; do
    if command -v "$cmd" &>/dev/null; then
        version=$("$cmd" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || echo "0.0")
        major=$(echo "$version" | cut -d. -f1)
        minor=$(echo "$version" | cut -d. -f2)
        if [[ "$major" -ge 3 && "$minor" -ge 11 ]]; then
            PYTHON_CMD="$cmd"
            break
        fi
    fi
done

if [[ -z "$PYTHON_CMD" ]]; then
    fail "Python 3.11+ is required but not found. Install it and try again."
fi

ok "Found $PYTHON_CMD ($($PYTHON_CMD --version 2>&1))"

# ─── Step 2: Verify source files exist ───────────────────────────────
info "Checking source files..."

if [[ ! -f "$SKILL_SRC" ]]; then
    fail "SKILL.md not found at ${SKILL_SRC}. Are you running from the NeuralTree repo?"
fi

if [[ ! -f "$REQUIREMENTS" ]]; then
    fail "requirements.txt not found at ${REQUIREMENTS}."
fi

ok "Source files found"

# ─── Check-only: report status and exit ──────────────────────────────
if $CHECK_ONLY; then
    printf "\n${BOLD}Installation status:${RESET}\n"

    if [[ -f "$SKILL_DEST" ]]; then
        ok "Skill installed at ${SKILL_DEST}"
    else
        warn "Skill NOT installed (expected at ${SKILL_DEST})"
    fi

    if [[ -f "$CLAUDE_JSON" ]] && $PYTHON_CMD -c "
import json, sys
with open('${CLAUDE_JSON}') as f:
    cfg = json.load(f)
sys.exit(0 if 'neuraltree' in cfg.get('mcpServers', {}) else 1)
" 2>/dev/null; then
        ok "MCP server registered in ${CLAUDE_JSON}"
    else
        warn "MCP server NOT registered in ${CLAUDE_JSON}"
    fi

    if $PYTHON_CMD -c "import fastmcp" 2>/dev/null; then
        ok "Python dependencies installed"
    else
        warn "Python dependencies NOT installed (fastmcp not importable)"
    fi

    printf "\n"
    exit 0
fi

# ─── Step 3: Install Python dependencies ─────────────────────────────
info "Installing Python dependencies..."

$PYTHON_CMD -m pip install -r "$REQUIREMENTS" --quiet 2>&1 | tail -5 || fail "pip install failed. Check your Python environment."

ok "Dependencies installed"

# ─── Step 4: Copy skill files to Claude skills directory ─────────────
info "Installing skill to ${SKILL_DEST_DIR}..."

mkdir -p "$SKILL_DEST_DIR"
cp "$SKILL_SRC" "$SKILL_DEST"

# Copy section files (skill router reads these on demand)
SECTIONS_SRC="${SCRIPT_DIR}/src/skill/sections"
SECTIONS_DEST="${SKILL_DEST_DIR}/sections"
if [[ -d "$SECTIONS_SRC" ]]; then
    mkdir -p "$SECTIONS_DEST"
    cp "$SECTIONS_SRC"/*.md "$SECTIONS_DEST/"
    ok "Skill installed ($(wc -l < "$SKILL_DEST") lines + $(ls "$SECTIONS_DEST"/*.md | wc -l) section files)"
else
    ok "Skill installed ($(wc -l < "$SKILL_DEST") lines, no sections found)"
fi

# ─── Step 5: Register MCP server in ~/.claude.json ───────────────────
info "Registering MCP server in ${CLAUDE_JSON}..."

# Use Python for safe JSON manipulation (no jq dependency)
$PYTHON_CMD << PYEOF
import json
import os

claude_json_path = os.path.expanduser("${CLAUDE_JSON}")
config = {}

# Read existing config if present
import shutil
if os.path.exists(claude_json_path):
    # Always back up before modifying
    backup = claude_json_path + ".neuraltree-backup"
    shutil.copy2(claude_json_path, backup)
    print(f"  Backed up existing config to {backup}")
    with open(claude_json_path, "r") as f:
        try:
            config = json.load(f)
        except json.JSONDecodeError:
            print(f"  WARNING: Existing {claude_json_path} was invalid JSON — starting fresh.")
            config = {}

# Ensure mcpServers key exists
if "mcpServers" not in config:
    config["mcpServers"] = {}

# Check if already registered
if "neuraltree" in config["mcpServers"]:
    existing_cwd = config["mcpServers"]["neuraltree"].get("cwd", "")
    if existing_cwd == "${SCRIPT_DIR}":
        print("  Already registered with correct path — no changes needed.")
    else:
        config["mcpServers"]["neuraltree"]["cwd"] = "${SCRIPT_DIR}"
        print(f"  Updated cwd from {existing_cwd} to ${SCRIPT_DIR}")
else:
    config["mcpServers"]["neuraltree"] = {
        "command": "${PYTHON_CMD}",
        "args": ["-m", "neuraltree_mcp.server"],
        "cwd": "${SCRIPT_DIR}",
        "env": {"PYTHONPATH": "src"}
    }

# Write back
with open(claude_json_path, "w") as f:
    json.dump(config, f, indent=2)
    f.write("\n")
PYEOF

ok "MCP server registered"

# ─── Step 6: Verify installation ─────────────────────────────────────
info "Verifying installation..."

# Verify tools load
TOOL_COUNT=$(PYTHONPATH="${SCRIPT_DIR}/src" $PYTHON_CMD -c "
import asyncio
from neuraltree_mcp.server import mcp
tools = asyncio.run(mcp.list_tools())
print(len(tools))
" 2>/dev/null || echo "0")

if [[ "$TOOL_COUNT" -eq 24 ]]; then
    ok "All 24 MCP tools loaded successfully"
else
    warn "Expected 24 tools but got ${TOOL_COUNT}. The server may still work — check manually."
fi

# ─── Done ─────────────────────────────────────────────────────────────
printf "\n${BOLD}${GREEN}"
printf "  ╔═══════════════════════════════════════╗\n"
printf "  ║       Installation Complete!          ║\n"
printf "  ╚═══════════════════════════════════════╝\n"
printf "${RESET}\n"

printf "  ${BOLD}What was installed:${RESET}\n"
printf "    Skill:      ${SKILL_DEST}\n"
printf "    MCP Server: ${CLAUDE_JSON} (neuraltree entry)\n"
printf "    Dependencies: fastmcp, pytest, pytest-asyncio\n"
printf "\n"
printf "  ${BOLD}Next steps:${RESET}\n"
printf "    1. Start (or restart) Claude Code\n"
printf "    2. Make sure Viking MCP is running for full scoring\n"
printf "    3. Make sure Ollama is running with Qwen3.5: ${YELLOW}ollama pull qwen3:latest${RESET}\n"
printf "    4. Run: ${GREEN}/neuraltree${RESET}\n"
printf "\n"
printf "  ${BOLD}Verify anytime:${RESET} ./install.sh --check\n"
printf "\n"
