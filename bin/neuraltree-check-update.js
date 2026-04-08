#!/usr/bin/env node
// neuraltree-hook-version: 3.2.0
// Check for NeuralTree updates via git — runs on SessionStart
// Compares local HEAD with remote HEAD, writes result to cache

const fs = require('fs');
const path = require('path');
const os = require('os');
const { spawn } = require('child_process');

const HOME = os.homedir();
const INSTALL_DIR = path.join(HOME, '.neuraltree-src');
const cacheDir = path.join(HOME, '.cache', 'neuraltree');
const cacheFile = path.join(cacheDir, 'update-check.json');

// Ensure cache dir exists
if (!fs.existsSync(cacheDir)) {
  fs.mkdirSync(cacheDir, { recursive: true });
}

// Skip if not installed
if (!fs.existsSync(path.join(INSTALL_DIR, '.git'))) {
  process.exit(0);
}

// Run check in background (non-blocking, detached)
const child = spawn(process.execPath, ['-e', `
  const { execFileSync } = require('child_process');
  const fs = require('fs');

  const installDir = ${JSON.stringify(INSTALL_DIR)};
  const cacheFile = ${JSON.stringify(cacheFile)};

  let localHead = '';
  let remoteHead = '';
  let localVersion = '0.0.0';

  try {
    localHead = execFileSync('git', ['rev-parse', 'HEAD'], {
      cwd: installDir, encoding: 'utf8', timeout: 5000
    }).trim();
  } catch (e) {}

  try {
    const pkg = JSON.parse(fs.readFileSync(installDir + '/package.json', 'utf8'));
    localVersion = pkg.version || '0.0.0';
  } catch (e) {}

  try {
    // Fetch latest remote HEAD without pulling
    execFileSync('git', ['fetch', '--quiet'], {
      cwd: installDir, encoding: 'utf8', timeout: 15000
    });
    remoteHead = execFileSync('git', ['rev-parse', 'origin/main'], {
      cwd: installDir, encoding: 'utf8', timeout: 5000
    }).trim();
  } catch (e) {}

  const updateAvailable = remoteHead && localHead && remoteHead !== localHead;

  let behindCount = 0;
  if (updateAvailable) {
    try {
      const log = execFileSync('git', ['log', '--oneline', localHead + '..' + remoteHead], {
        cwd: installDir, encoding: 'utf8', timeout: 5000
      });
      behindCount = log.trim().split('\\n').filter(Boolean).length;
    } catch (e) {}
  }

  const result = {
    update_available: updateAvailable,
    installed_version: localVersion,
    local_head: localHead.slice(0, 8),
    remote_head: remoteHead.slice(0, 8),
    behind_commits: behindCount,
    checked: Math.floor(Date.now() / 1000),
  };

  fs.writeFileSync(cacheFile, JSON.stringify(result));
`], {
  stdio: 'ignore',
  windowsHide: true,
  detached: true,
});

child.unref();
