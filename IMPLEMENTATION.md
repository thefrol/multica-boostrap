# Implementation Guide — Multica Template Engine

This document provides a step-by-step guide for implementing the
`multica-template-apply` engine. It is written for a developer who will turn
the design into working code.

## Tech Stack Recommendation

- **Language:** Python 3 (available on all Multica worker nodes)
- **YAML parsing:** `PyYAML` (already installed)
- **JSON parsing:** Standard library `json`
- **CLI invocation:** Standard library `subprocess`
- **No external dependencies** beyond what ships with the OS.

## File Structure

```
/home/dev/multica-template-space/
├── bin/
│   └── multica-template-apply      # Main entry point
├── lib/
│   ├── parser.py                   # YAML validation
│   ├── registry.py                 # Name → ID registry
│   ├── resolver.py                 # Reference resolution
│   ├── executor.py                 # multica CLI invocation
│   └── resources/
│       ├── workspace.py
│       ├── label.py
│       ├── skill.py
│       ├── agent.py
│       ├── squad.py
│       └── autopilot.py
└── examples/
    └── ...
```

For v0.1, a single-file script (`bin/multica-template-apply`) is sufficient.
Split into modules when the script exceeds ~400 lines.

## Step 1 — Parse the Template

**Input:** Path to a directory containing `template.yaml`.
**Output:** A validated Python dict representing the template.

**Validation rules:**
- `apiVersion` must be `multica.template/v1`
- `kind` must be `WorkspaceTemplate`
- `metadata.name` is required
- `spec` is required
- Unknown keys at any level should raise a clear error

**Code sketch:**
```python
def load_template(directory):
    path = os.path.join(directory, "template.yaml")
    with open(path) as f:
        data = yaml.safe_load(f)
    validate(data)
    return data
```

## Step 0 — Resolve Target Workspace

**Input:** CLI args (`--workspace-id`, `--workspace-name`, `--create-workspace`) + parsed template.
**Output:** A workspace UUID (or `None` for current workspace).

**Precedence:**
```
--workspace-id > --workspace-name > spec.targetWorkspace.id > spec.targetWorkspace.name > current workspace
```

**Name resolution:**
```bash
multica workspace list   # outputs a table: ID  NAME
```
Parse the table, look up the name, return the UUID. If not found:
- If `--create-workspace` is set or `spec.targetWorkspace.create` is `true`,
  create the workspace via the REST API (`POST /api/workspaces`).
- Otherwise, fail fast:
  ```
  Workspace "X" not found. Create it via the web UI first.
  ```

**Workspace creation API call:**
```python
import urllib.request
import json
import os

req = urllib.request.Request(
    f"{os.environ['MULTICA_SERVER_URL']}/api/workspaces",
    data=json.dumps({"name": name, "slug": slug}).encode(),
    headers={
        "Authorization": f"Bearer {os.environ['MULTICA_TOKEN']}",
        "Content-Type": "application/json",
    },
    method="POST",
)
```
The slug is auto-generated from the name if not provided in `spec.targetWorkspace.slug`.

## Step 1 — Parse the Template

**Input:** Path to a directory containing `template.yaml`.
**Output:** A validated Python dict representing the template.

**Validation rules:**
- `apiVersion` must be `multica.template/v1`
- `kind` must be `WorkspaceTemplate`
- `metadata.name` is required
- `spec` is required
- Unknown keys at any level should raise a clear error
- `spec.targetWorkspace` is optional; if present, may contain `id`, `name`, `create`, or `slug`

**Code sketch:**
```python
def load_template(directory):
    path = os.path.join(directory, "template.yaml")
    with open(path) as f:
        data = yaml.safe_load(f)
    validate(data)
    return data
```

## Step 2 — Query Current State

**Input:** Target workspace ID (or `None` for current workspace).
**Output:** A dict mapping `(resource_type, name)` → `id_or_none`.

Run these commands and parse JSON. If a target workspace ID is set, append
`--workspace-id <id>` to every command:
```bash
multica workspace get --output json
multica label list --output json
multica skill list --output json
multica agent list --output json
multica squad list --output json
multica autopilot list --output json
```

**Code sketch:**
```python
def run_json(cmd):
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return json.loads(result.stdout)

def build_registry():
    registry = {}
    for resource_type, cmd in RESOURCE_LISTERS.items():
        items = run_json(cmd)
        for item in items:
            key = (resource_type, item["name"])
            registry[key] = item["id"]
    return registry
```

## Step 3 — Apply Workspace Metadata

**Logic:**
1. Read `spec.workspace` from template.
2. Call `multica workspace update` with any provided fields.

**CLI mapping:**
```bash
multica workspace update \
  --name "<name>" \
  --description "<description>" \
  --issue-prefix "<prefix>"
```

**Note:** Only update fields that are present in the template. Omitting a field
means "leave as-is."

## Step 4 — Apply Labels

**Logic:**
1. For each label in `spec.labels`:
   - Look up `(label, name)` in registry.
   - If exists → `multica label update <id> --name <name> --color <color>`.
   - If missing → `multica label create --name <name> --color <color>`.

## Step 5 — Apply Skills

**Logic:**
1. For each skill in `spec.skills`:
   - Look up `(skill, name)` in registry.
   - If exists → `multica skill update <id> --name <name> --description <desc> --content <content>`.
   - If missing → `multica skill create --name <name> --description <desc> --content <content>`.
   - Capture returned ID and update registry.

2. For each file in `skill.files`:
   - `multica skill files upsert <skill-id> --path <path> --content <content>`.

## Step 6 — Apply Agents

**Logic:**
1. For each agent in `spec.agents`:
   - Resolve `skills[]` names to IDs using the registry.
   - Look up `(agent, name)` in registry.
   - Build the CLI command with all agent fields.
   - If exists → `multica agent update <id> [...]`.
   - If missing → `multica agent create [...]`.
   - Capture returned ID and update registry.

2. **After all agents are converged**, apply skill bindings:
   - For each agent with `skills`:
     - `multica agent skills set <agent-id> --skill-ids <id1,id2,...>`.

**Field mapping:**
| Template field | CLI flag |
|----------------|----------|
| `name` | `--name` |
| `runtimeId` | `--runtime-id` |
| `model` | `--model` |
| `instructions` | `--instructions` |
| `visibility` | `--visibility` |
| `maxConcurrentTasks` | `--max-concurrent-tasks` |
| `customArgs` | `--custom-args` |
| `description` | `--description` |

## Step 7 — Apply Squads

**Logic:**
1. For each squad in `spec.squads`:
   - Resolve `leader` name to agent ID using registry.
   - Look up `(squad, name)` in registry.
   - If exists → `multica squad update <id> --name <name> --leader <leader-id> --description <desc> --instructions <instructions>`.
   - If missing → `multica squad create --name <name> --leader <leader-id> --description <desc>`, then `multica squad update <id> --instructions <instructions>`.
   - Capture returned ID and update registry.

## Step 8 — Apply Autopilots

**Logic:**
1. For each autopilot in `spec.autopilots`:
   - Resolve `agent` name to agent ID using registry.
   - Look up `(autopilot, name)` in registry.
     - Note: `multica autopilot list` uses `title` as the display name; the
       engine should match on `title` (since autopilots do not appear to have a
       separate `name` field in the API).
   - If exists → `multica autopilot update <id> [...]`.
   - If missing → `multica autopilot create [...]`.
   - Capture returned ID and update registry.

**Field mapping:**
| Template field | CLI flag |
|----------------|----------|
| `title` | `--title` |
| `agent` (resolved to ID) | `--agent` |
| `mode` | `--mode` |
| `description` | `--description` |
| `priority` | `--priority` |

## Error Handling & UX

- Print a clear header for each resource being applied:
  ```
  [label] bug — already exists, skipping
  [agent] auto-coder — creating
  [squad] dev-team — updating (id: cfeb4dc0-...)
  ```
- On CLI error, print the failed command, stderr, and exit immediately with
the same exit code.
- Support a `--dry-run` flag that prints commands without executing them.

## Testing Strategy

1. **Unit tests** (mock `subprocess.run`) for parsing and registry logic.
2. **Integration tests** against a disposable workspace:
   - Apply template A → verify resources created.
   - Apply template A again → verify idempotent (no errors).
   - Apply template B (modifies A) → verify updates applied.
3. **Example templates** in `examples/` serve as manual test cases.

## Acceptance Criteria

- [ ] `multica-template-apply ./examples/basic-workspace` successfully updates
  workspace metadata and creates labels.
- [ ] `multica-template-apply ./examples/agent-fleet` creates agents, skills,
  and binds skills to agents.
- [ ] `multica-template-apply ./examples/full-stack` creates squads and
  autopilots with correct leader/agent references.
- [ ] `multica-template-apply ./examples/target-workspace` resolves workspace
  by name and applies labels there.
- [ ] `multica-template-apply ./examples/basic-workspace --workspace-id <uuid>`
  applies to the explicit workspace.
- [ ] Running the same apply command twice produces no errors and no duplicate
  resources.
- [ ] `--dry-run` prints all planned commands without side effects.
- [ ] Missing or invalid templates produce clear error messages.
- [ ] Applying to a non-existent workspace by name fails fast with a clear error.
