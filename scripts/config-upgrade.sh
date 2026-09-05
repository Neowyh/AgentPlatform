#!/usr/bin/env bash
#
# config-upgrade.sh - Upgrade config.yaml to match config.example.yaml
#
# 1. Runs version-specific migrations (value replacements, renames, etc.)
# 2. Merges missing fields from the example into the user config
# 3. Backs up config.yaml to config.yaml.bak before modifying.

set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EXAMPLE="$REPO_ROOT/config.example.yaml"

# Resolve config.yaml location: env var > backend/ > repo root
if [ -n "$DEER_FLOW_CONFIG_PATH" ] && [ -f "$DEER_FLOW_CONFIG_PATH" ]; then
    CONFIG="$DEER_FLOW_CONFIG_PATH"
elif [ -n "$IDEER_CONFIG_PATH" ] && [ -f "$IDEER_CONFIG_PATH" ]; then
    CONFIG="$IDEER_CONFIG_PATH"
elif [ -f "$REPO_ROOT/backend/config.yaml" ]; then
    CONFIG="$REPO_ROOT/backend/config.yaml"
elif [ -f "$REPO_ROOT/config.yaml" ]; then
    CONFIG="$REPO_ROOT/config.yaml"
else
    CONFIG=""
fi

if [ ! -f "$EXAMPLE" ]; then
    echo "✗ config.example.yaml not found at $EXAMPLE"
    exit 1
fi

if [ -z "$CONFIG" ]; then
    echo "No config.yaml found — creating from example..."
    cp "$EXAMPLE" "$REPO_ROOT/config.yaml"
    echo "OK config.yaml created. Please review and set your API keys."
    exit 0
fi

# Use inline Python to do migrations + recursive merge with PyYAML
if command -v cygpath >/dev/null 2>&1; then
    CONFIG_WIN="$(cygpath -w "$CONFIG")"
    EXAMPLE_WIN="$(cygpath -w "$EXAMPLE")"
else
    CONFIG_WIN="$CONFIG"
    EXAMPLE_WIN="$EXAMPLE"
fi

cd "$REPO_ROOT/backend" && CONFIG_WIN_PATH="$CONFIG_WIN" EXAMPLE_WIN_PATH="$EXAMPLE_WIN" uv run python -c "
import os
import sys, shutil, copy, re
from pathlib import Path

import yaml

config_path = Path(os.environ['CONFIG_WIN_PATH'])
example_path = Path(os.environ['EXAMPLE_WIN_PATH'])

with open(config_path, encoding='utf-8') as f:
    raw_text = f.read()
    user = yaml.safe_load(raw_text) or {}

with open(example_path, encoding='utf-8') as f:
    example = yaml.safe_load(f) or {}

user_version = user.get('config_version', 0)
example_version = example.get('config_version', 0)

if user_version >= example_version:
    print(f'Config schema version {user_version} is current; checking structural migrations...')

print(f'Upgrading config.yaml: version {user_version} -> {example_version}')
print()

# ── Migrations ───────────────────────────────────────────────────────────
# Each migration targets a specific version upgrade.
# 'replacements': list of (old_string, new_string) applied to the raw YAML text.
#   This handles value changes that a dict merge cannot catch.

MIGRATIONS = {
    1: {
        'description': 'Rename src.* module paths to ideer.*',
        'replacements': [
            ('src.community.', 'ideer.community.'),
            ('src.sandbox.', 'ideer.sandbox.'),
            ('src.models.', 'ideer.models.'),
            ('src.tools.', 'ideer.tools.'),
        ],
    },
    # Future migrations go here:
    # 2: {
    #     'description': '...',
    #     'replacements': [('old', 'new')],
    # },
}

# Runtime ownership moved from the legacy ideer harness to DeerFlow.  This
# migration is deliberately independent of ``config_version``: an operator
# may already have a current schema while still carrying old dotted paths.
# Keep product-only community integrations untouched when DeerFlow has no
# equivalent implementation; those remain explicit compatibility extensions.
RUNTIME_PATH_MIGRATIONS = [
    ('ideer.models.', 'deerflow.models.'),
    ('ideer.sandbox.', 'deerflow.sandbox.'),
    ('ideer.agents.', 'deerflow.agents.'),
    ('ideer.tools.', 'deerflow.tools.'),
    ('ideer.skills.', 'deerflow.skills.'),
    ('ideer.guardrails.', 'deerflow.guardrails.'),
    ('ideer.community.ddg_search.', 'deerflow.community.ddg_search.'),
    ('ideer.community.jina_ai.', 'deerflow.community.jina_ai.'),
    ('ideer.community.image_search.', 'deerflow.community.image_search.'),
    ('ideer.community.aio_sandbox.', 'deerflow.community.aio_sandbox.'),
    ('ideer.config.', 'deerflow.config.'),
]

# Memory schema migration is structural rather than a versioned text
# replacement. Keep this here as the operator-facing upgrade path so a
# config already stamped at the latest version still moves from the legacy
# top-level DeerMem fields to the host-shared ``backend_config`` contract.
LEGACY_MEMORY_FIELDS = {
    'storage_path', 'storage_class', 'debounce_seconds', 'max_facts',
    'fact_confidence_threshold', 'max_injection_tokens', 'token_counting',
    'guaranteed_categories', 'guaranteed_token_budget',
    'staleness_review_enabled', 'staleness_age_days', 'staleness_min_candidates',
    'staleness_max_removals_per_cycle', 'staleness_protected_categories',
    'staleness_max_lifetime_multiplier', 'staleness_max_extension_days',
    'consolidation_enabled', 'consolidation_min_facts',
    'consolidation_max_groups_per_cycle', 'consolidation_max_sources',
    'model_name',
}

# Apply migrations in order for versions (user_version, example_version]
migrated = []
for version in range(user_version + 1, example_version + 1):
    migration = MIGRATIONS.get(version)
    if not migration:
        continue
    desc = migration.get('description', f'Migration to v{version}')
    for old, new in migration.get('replacements', []):
        if old in raw_text:
            raw_text = raw_text.replace(old, new)
            migrated.append(f'{old} -> {new}')

for old, new in RUNTIME_PATH_MIGRATIONS:
    if old in raw_text:
        raw_text = raw_text.replace(old, new)
        migrated.append(f'{old} -> {new}')

# Re-parse after text migrations
user = yaml.safe_load(raw_text) or {}

if migrated:
    print(f'Applied {len(migrated)} migration(s):')
    for m in migrated:
        print(f'  ~ {m}')
    print()

# ── Structural Memory migration ────────────────────────────────────────
memory = user.get('memory')
memory_migrated = []
if isinstance(memory, dict):
    backend_config = dict(memory.get('backend_config') or {})
    for key in list(memory):
        if key not in LEGACY_MEMORY_FIELDS:
            continue
        value = memory.pop(key)
        if value is None or value == '':
            continue
        if key == 'storage_path' and str(value).endswith('.json'):
            # The old value names a shared file. The new contract requires a
            # directory root; omitting it preserves DeerMem's per-user default.
            memory_migrated.append(f'{key} dropped (legacy file path)')
            continue
        if key == 'model_name':
            model_config = dict(backend_config.get('model') or {})
            model_config.setdefault('model', value)
            backend_config['model'] = model_config
            memory_migrated.append(f'{key} -> memory.backend_config.model.model')
            continue
        backend_config.setdefault(key, value)
        memory_migrated.append(f'{key} -> memory.backend_config.{key}')
    if memory_migrated:
        memory['backend_config'] = backend_config
        user['memory'] = memory
        print('Migrated legacy Memory fields:')
        for item in memory_migrated:
            print(f'  ~ {item}')
        print()

# ── Merge missing fields ─────────────────────────────────────────────────

added = []

def merge(target, source, path=''):
    \"\"\"Recursively merge source into target, adding missing keys only.\"\"\"
    for key, value in source.items():
        key_path = f'{path}.{key}' if path else key
        if key not in target:
            target[key] = copy.deepcopy(value)
            added.append(key_path)
        elif isinstance(value, dict) and isinstance(target[key], dict):
            merge(target[key], value, key_path)

merge(user, example)

# Always update config_version
user['config_version'] = example_version

if not migrated and not memory_migrated and not added and user_version == example_version:
    print('No changes needed (config and structural migrations are current).')
    sys.exit(0)

# ── Write ─────────────────────────────────────────────────────────────────

backup = config_path.with_suffix('.yaml.bak')
shutil.copy2(config_path, backup)
print(f'Backed up to {backup.name}')

with open(config_path, 'w', encoding='utf-8') as f:
    yaml.dump(user, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

if added:
    print(f'Added {len(added)} new field(s):')
    for a in added:
        print(f'  + {a}')

print()
print(f'OK config.yaml upgraded to version {example_version}.')
print('  Please review the changes and set any new required values.')
"
