#!/usr/bin/env node
// ponytail — shared configuration resolver
//
// Resolution order for default mode:
//   1. PONYTAIL_DEFAULT_MODE environment variable
//   2. Config file defaultMode field:
//      - $XDG_CONFIG_HOME/ponytail/config.json (any platform, if set)
//      - ~/.config/ponytail/config.json (macOS / Linux fallback)
//      - %APPDATA%\ponytail\config.json (Windows fallback)
//   3. 'full'

const fs = require('fs');
const path = require('path');
const os = require('os');

const DEFAULT_MODE = 'full';
const VALID_MODES = ['off', 'lite', 'full', 'ultra', 'review'];
const RUNTIME_MODES = ['off', 'lite', 'full', 'ultra'];
// Sets for O(1) membership checks — replaces Array.includes throughout.
const RUNTIME_MODES_SET = new Set(RUNTIME_MODES);
const VALID_MODES_SET = new Set(VALID_MODES);

// Config content cache. Avoids re-reading and re-parsing the same file in
// getDefaultMode, getQuietStartup, and getHideStatus within one process.
// Keyed by resolved config path so env-var changes (XDG_CONFIG_HOME in tests)
// are handled correctly: a different path forces a fresh read.
let _cachedConfigPath = null;
let _cachedConfig = undefined; // undefined = not yet read for _cachedConfigPath

function _readConfig() {
  const configPath = getConfigPath();
  if (configPath === _cachedConfigPath) return _cachedConfig;
  _cachedConfigPath = configPath;
  try {
    const raw = fs.readFileSync(configPath, 'utf8').replace(/^﻿/, '');
    const parsed = JSON.parse(raw);
    _cachedConfig = (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) ? parsed : null;
  } catch (_) {
    _cachedConfig = null;
  }
  return _cachedConfig;
}

function normalizeMode(mode) {
  if (typeof mode !== 'string') return null;
  const normalized = mode.trim().toLowerCase();
  return RUNTIME_MODES_SET.has(normalized) ? normalized : null;
}

function normalizeConfigMode(mode) {
  if (typeof mode !== 'string') return null;
  const normalized = mode.trim().toLowerCase();
  return VALID_MODES_SET.has(normalized) ? normalized : null;
}

function normalizePersistedMode(mode) {
  return normalizeMode(mode) || normalizeConfigMode(mode);
}

// "stop ponytail" / "normal mode" turn ponytail off, but only as a standalone
// command. Matching the phrase anywhere in the message turned it off mid-task
// for ordinary requests like "add a normal mode toggle" — so require the whole
// message to be the command, ignoring case and trailing punctuation.
function isDeactivationCommand(text) {
  const t = String(text || '').trim().toLowerCase().replace(/[.!?\s]+$/, '');
  return t === 'stop ponytail' || t === 'normal mode';
}

// ponytail: only embed the plugin install path in a statusline shell command when
// it's made of ordinary path characters. An allowlist beats escaping every shell's
// metacharacters; a hostile clone path (quotes, &, $, backtick, ;, etc.) falls back
// to manual setup instead. Allows : \ / for normal Windows and POSIX paths. Full
// per-shell escaper only if a real need appears.
function isShellSafe(p) {
  return typeof p === 'string' && /^[A-Za-z0-9 _.\-:/\\~]+$/.test(p);
}

function getConfigDir() {
  if (process.env.XDG_CONFIG_HOME) {
    return path.join(process.env.XDG_CONFIG_HOME, 'ponytail');
  }
  if (process.platform === 'win32') {
    return path.join(
      process.env.APPDATA || path.join(os.homedir(), 'AppData', 'Roaming'),
      'ponytail'
    );
  }
  return path.join(os.homedir(), '.config', 'ponytail');
}

function getConfigPath() {
  return path.join(getConfigDir(), 'config.json');
}

function getClaudeDir() {
  // ponytail: CLAUDE_CONFIG_DIR overrides ~/.claude, matching Claude Code.
  return process.env.CLAUDE_CONFIG_DIR || path.join(os.homedir(), '.claude');
}

function getDefaultMode() {
  // 1. Environment variable (highest priority)
  const envMode = process.env.PONYTAIL_DEFAULT_MODE;
  // ponytail: a default must be a runtime level (off/lite/full/ultra); review is
  // a session-only mode, never a valid default (#377).
  if (envMode && RUNTIME_MODES_SET.has(envMode.toLowerCase())) {
    return envMode.toLowerCase();
  }

  // 2. Config file (cached — shared with getQuietStartup / getHideStatus)
  const config = _readConfig();
  if (config && config.defaultMode && RUNTIME_MODES_SET.has(config.defaultMode.toLowerCase())) {
    return config.defaultMode.toLowerCase();
  }

  // 3. Default
  return DEFAULT_MODE;
}

// Silence the pi "Ponytail loaded" startup toast while keeping ponytail active.
// PONYTAIL_QUIET_STARTUP=1 (or any truthy value; 0/false/empty mean "show it")
// takes precedence, else config.quietStartup === true. Mirrors getHideStatus.
function getQuietStartup() {
  const env = process.env.PONYTAIL_QUIET_STARTUP;
  if (env !== undefined) {
    const v = env.trim().toLowerCase();
    return v !== '' && v !== '0' && v !== 'false' && v !== 'no';
  }
  const config = _readConfig();
  return config ? config.quietStartup === true : false;
}

// Hide the status-bar indicator while keeping ponytail active (#324).
// PONYTAIL_HIDE_STATUS=1 (or any truthy value; 0/false/empty mean "don't hide")
// takes precedence, else config.hideStatus === true.
function getHideStatus() {
  const env = process.env.PONYTAIL_HIDE_STATUS;
  if (env !== undefined) {
    const v = env.trim().toLowerCase();
    return v !== '' && v !== '0' && v !== 'false' && v !== 'no';
  }
  const config = _readConfig();
  return config ? config.hideStatus === true : false;
}

function writeDefaultMode(mode) {
  // ponytail: only a runtime level can be a default; review is session-only (#377).
  const normalized = normalizeMode(mode);
  if (!normalized) return null;

  const configPath = getConfigPath();
  fs.mkdirSync(path.dirname(configPath), { recursive: true });
  const existing = _readConfig();
  const config = (existing && typeof existing === 'object') ? existing : {};
  if (!existing) {
    // Seed a fresh object when the file was absent; don't reuse existing null.
    Object.assign(config, {});
  }
  config.defaultMode = normalized;
  fs.writeFileSync(configPath, JSON.stringify(config, null, 2), 'utf8');
  // Update cache so subsequent reads in this process see the new default.
  _cachedConfigPath = configPath;
  _cachedConfig = config;
  return normalized;
}

module.exports = {
  DEFAULT_MODE,
  VALID_MODES,
  RUNTIME_MODES,
  getDefaultMode,
  getConfigDir,
  getConfigPath,
  getClaudeDir,
  getHideStatus,
  getQuietStartup,
  isShellSafe,
  normalizeMode,
  normalizeConfigMode,
  normalizePersistedMode,
  isDeactivationCommand,
  writeDefaultMode,
};
