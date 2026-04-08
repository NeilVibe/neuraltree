#!/usr/bin/env node
// NeuralTree Installer — GitHub Direct
//
// Usage:
//   npx github:NeilVibe/neuraltree          # fresh install
//   npx github:NeilVibe/neuraltree update    # update existing
//
// What it does:
//   1. Clones/pulls the repo to ~/.neuraltree-src
//   2. Runs install.sh (pip deps + skill symlink + MCP registration)
//   3. Installs SessionStart hook for auto-update checking
//

const { execFileSync, spawnSync } = require('child_process');
const fs = require('fs');
const path = require('path');
const os = require('os');

const HOME = os.homedir();
const INSTALL_DIR = path.join(HOME, '.neuraltree-src');
const REPO_URL = 'https://github.com/NeilVibe/neuraltree.git';
const VERSION_FILE = path.join(INSTALL_DIR, 'VERSION');

// ─── Colors ──────────────────────────────────────────────────────────
const c = {
  r: '\x1b[0m', b: '\x1b[1m', green: '\x1b[32m', blue: '\x1b[34m',
  yellow: '\x1b[33m', red: '\x1b[31m',
};
const info = (msg) => console.log(`${c.blue}[info]${c.r}  ${msg}`);
const ok = (msg) => console.log(`${c.green}[ok]${c.r}    ${msg}`);
const warn = (msg) => console.log(`${c.yellow}[warn]${c.r}  ${msg}`);
const fail = (msg) => { console.error(`${c.red}[FAIL]${c.r}  ${msg}`); process.exit(1); };

// ─── Header ──────────────────────────────────────────────────────────
console.log(`
${c.b}  ╔═══════════════════════════════════════╗
  ║     NeuralTree — GitHub Direct        ║
  ╚═══════════════════════════════════════╝${c.r}
`);

// ─── Step 1: Clone or pull ───────────────────────────────────────────
if (fs.existsSync(path.join(INSTALL_DIR, '.git'))) {
  info('Updating existing installation...');
  try {
    const result = execFileSync('git', ['pull'], { cwd: INSTALL_DIR, encoding: 'utf8', timeout: 30000 });
    if (result.includes('Already up to date')) {
      ok('Already on latest version');
    } else {
      ok('Updated to latest');
      console.log(`  ${result.trim()}`);
    }
  } catch (e) {
    warn(`git pull failed: ${e.message}`);
    warn('Continuing with existing version...');
  }
} else {
  info(`Cloning NeuralTree to ${INSTALL_DIR}...`);
  try {
    execFileSync('git', ['clone', REPO_URL, INSTALL_DIR], { encoding: 'utf8', timeout: 60000, stdio: 'inherit' });
    ok('Cloned successfully');
  } catch (e) {
    fail(`git clone failed: ${e.message}`);
  }
}

// ─── Step 2: Read version ────────────────────────────────────────────
let version = '0.0.0';
try {
  const pkg = JSON.parse(fs.readFileSync(path.join(INSTALL_DIR, 'package.json'), 'utf8'));
  version = pkg.version || '0.0.0';
} catch (e) {}

// Write VERSION file for update checking
fs.writeFileSync(VERSION_FILE, version + '\n');
info(`Version: ${version}`);

// ─── Step 3: Run install.sh ──────────────────────────────────────────
info('Running install.sh...');
const installScript = path.join(INSTALL_DIR, 'install.sh');
if (!fs.existsSync(installScript)) {
  fail('install.sh not found in repo');
}

const result = spawnSync('bash', [installScript], {
  cwd: INSTALL_DIR,
  stdio: 'inherit',
  timeout: 120000,
});

if (result.status !== 0) {
  fail('install.sh failed');
}

// ─── Step 4: Install update-check hook ───────────────────────────────
info('Installing auto-update hook...');

// Detect config dir (Claude, Gemini, etc.)
let configDir = path.join(HOME, '.claude');
for (const dir of ['.claude', '.gemini', '.config/kilo']) {
  if (fs.existsSync(path.join(HOME, dir))) {
    configDir = path.join(HOME, dir);
    break;
  }
}

const hooksDir = path.join(configDir, 'hooks');
fs.mkdirSync(hooksDir, { recursive: true });

const hookSrc = path.join(INSTALL_DIR, 'bin', 'neuraltree-check-update.js');
const hookDest = path.join(hooksDir, 'neuraltree-check-update.js');

if (fs.existsSync(hookSrc)) {
  fs.copyFileSync(hookSrc, hookDest);
  ok('Update-check hook installed');
} else {
  warn('Update-check hook not found in repo — skipping');
}

// ─── Step 5: Register hook in settings.json if not present ───────────
const settingsFile = path.join(configDir, 'settings.json');
try {
  let settings = {};
  if (fs.existsSync(settingsFile)) {
    settings = JSON.parse(fs.readFileSync(settingsFile, 'utf8'));
  }

  if (!settings.hooks) settings.hooks = {};
  if (!settings.hooks.SessionStart) settings.hooks.SessionStart = [];

  const hookCmd = `node "${hookDest}"`;
  const alreadyRegistered = settings.hooks.SessionStart.some(h => {
    const hooks = h.hooks || [];
    return hooks.some(hh => hh.command && hh.command.includes('neuraltree-check-update'));
  });

  if (!alreadyRegistered) {
    settings.hooks.SessionStart.push({
      hooks: [{ type: 'command', command: hookCmd }]
    });
    fs.writeFileSync(settingsFile, JSON.stringify(settings, null, 2) + '\n');
    ok('SessionStart hook registered in settings.json');
  } else {
    ok('SessionStart hook already registered');
  }
} catch (e) {
  warn(`Could not register hook: ${e.message}`);
}

// ─── Done ────────────────────────────────────────────────────────────
console.log(`
${c.b}${c.green}  ╔═══════════════════════════════════════╗
  ║       NeuralTree Installed!           ║
  ╚═══════════════════════════════════════╝${c.r}

  ${c.b}Installed to:${c.r}  ${INSTALL_DIR}
  ${c.b}Version:${c.r}       ${version}
  ${c.b}Auto-update:${c.r}   SessionStart hook active

  ${c.b}Next:${c.r} Restart Claude Code, then run ${c.green}/neuraltree${c.r}

  ${c.b}Update anytime:${c.r} ${c.green}npx github:NeilVibe/neuraltree update${c.r}
`);
