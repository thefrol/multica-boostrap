# Design Document — Multica Template Engine

## Goal

Provide a declarative, human-readable way to provision and update Multica
workspace resources (workspace metadata, labels, skills, agents, squads,
autopilots) from version-controlled YAML templates.

## Non-Goals

- Full Helm-style package management (templating with loops, conditionals,
  sub-charts). Parameterized values are on the roadmap but out of scope for
  v0.1.
- State storage outside the Multica platform (the workspace itself is the
  source of truth).

## Architecture

### 1. Template Format

A single `template.yaml` file per template directory. The file follows a
Kubernetes-style API shape for familiarity.

### 2. Apply Flow

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│ template.yaml │ ──▶ │   Parse &    │ ──▶ │  Build intent   │
│  (desired)    │     │   validate   │     │   graph         │
└─────────────┘     └──────────────┘     └─────────────────┘
                                                  │
                                                  ▼
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│   Converge  │ ◀── │   Execute    │ ◀── │  Resolve refs   │
│   state     │     │   plan       │     │  (name → id)    │
└─────────────┘     └──────────────┘     └─────────────────┘
```

**Phase 0 — Resolve Target Workspace**
- Determine the target workspace from CLI flags or the template:
  - `--workspace-id <uuid>` → explicit UUID
  - `--workspace-name <name>` → resolve via `multica workspace list`
  - `spec.targetWorkspace.id` → explicit UUID
  - `spec.targetWorkspace.name` → resolve via `multica workspace list`
  - Fallback → current workspace (from CLI context)
- Precedence: CLI flags override template fields.
- If a target workspace is resolved, every `multica` command the engine runs
  gets prefixed with `--workspace-id <id>`.
- If `targetWorkspace.create` is `true` (or `--create-workspace` is passed) and
  the workspace is not found by name, the engine calls the REST API directly to
  create the workspace before applying the rest of the template.

**Phase 1 — Parse & Validate**
- Read `template.yaml`.
- Validate required fields, reject unknown keys.
- Build a dependency graph (e.g., skills must be applied before agents that
  reference them).

**Phase 2 — Build Intent Graph**
- For each resource block in the template, create an intent object:
  `{ type, name, spec, dependencies }`.
- Detect cycles in dependencies (e.g., agent A requires skill S, skill S
  somehow requires agent A — impossible today, but validated anyway).

**Phase 3 — Resolve References**
- Query the current workspace state via `multica * list --output json`.
- Build a registry: `resource_key → { exists: bool, id: uuid | null }`.
- Replace all symbolic references (`ref: <name>` or plain `<name>` in
  relation fields) with resolved UUIDs.

**Phase 4 — Execute Plan**
- Iterate resources in dependency order.
- For each resource:
  - **If exists by name** → `multica <type> update <id> [...flags]`
  - **If not exists** → `multica <type> create [...flags]`
  - Capture the returned ID and store it in the registry.

**Phase 5 — Converge Relations**
- After all standalone resources are created/updated, apply relational
  bindings:
  - `multica agent skills set <agent-id> --skill-ids <id1,id2>`

### 3. The ID Problem — Detailed Solution

Multica resources are identified by server-generated UUIDs. A declarative
system must not require users to hardcode UUIDs.

#### Strategy: Name-Based Identity with Runtime Resolution

1. **Authoring time** — the user writes symbolic names.
2. **Apply time** — the engine resolves names to UUIDs using the live
   workspace state.

#### Resolution Rules

| Field | Resolution |
|-------|------------|
| `agent.skills[]` | Resolve each skill name to its ID via `multica skill list` |
| `squad.leader` | Resolve agent name to ID via `multica agent list` |
| `autopilot.agent` | Resolve agent name to ID via `multica agent list` |

#### Registry Lifecycle

```
registry = {}

for resource in topological_order(resources):
    if resource.name in registry and registry[resource.name].exists:
        id = registry[resource.name].id
        multica <type> update <id> ...
    else:
        result = multica <type> create ...
        registry[resource.name] = { exists: true, id: result.id }
```

If a resource references another resource that is *not* in the template,
the engine still resolves it by querying the workspace (allowing partial
updates and shared resources).

### 4. Idempotency

The apply operation must be safe to run repeatedly. This is achieved by:

- **Name-based matching** — updates use the existing resource's UUID.
- **Full replacement on update** — `multica agent update` replaces the entire
  field set, so the template must always declare the complete desired state.
- **No partial merge** — to keep the engine simple and predictable.

### 5. Error Handling

| Scenario | Behavior |
|----------|----------|
| Invalid YAML | Fail fast before any API calls |
| Unknown resource type in template | Fail fast |
| Reference to non-existent resource | Fail fast with clear message |
| `multica` CLI error | Abort apply, print stderr, exit non-zero |
| Network failure | Abort apply, rely on idempotency for retry |
| Target workspace not found (by name) | If `create` is enabled, create via API. Otherwise, fail fast with: `Workspace "X" not found. Create it via the web UI first.` |

## Target Workspace

The engine can apply a template to any workspace the user has access to.

### Resolution Precedence

```
--workspace-id > --workspace-name > spec.targetWorkspace.id > spec.targetWorkspace.name > current workspace
```

### CLI Flags

| Flag | Description |
|------|-------------|
| `--workspace-id <uuid>` | Apply to an explicit workspace ID |
| `--workspace-name <name>` | Resolve name to ID via `multica workspace list`, then apply |

### Template Field

```yaml
spec:
  targetWorkspace:
    id: "4b4ec473-4336-43e6-9992-875fbd70b584"
    name: "Full Stack Team"
```

Only one of `id` or `name` should be used. If both are present, `id` takes
precedence.

## Resource Type Mapping

| Template Key | multica CLI | Create Flags | Update Flags |
|--------------|-------------|--------------|--------------|
| `workspace` | `multica workspace update` | N/A (update only) | `--name`, `--description`, `--issue-prefix` |
| `labels[]` | `multica label create` / `update` | `--name`, `--color` | `--name`, `--color` |
| `skills[]` | `multica skill create` / `update` | `--name`, `--description`, `--content` | `--name`, `--description`, `--content` |
| `skills[].files[]` | `multica skill files upsert` | `--path`, `--content` | same |
| `agents[]` | `multica agent create` / `update` | `--name`, `--runtime-id`, `--model`, `--instructions`, `--visibility`, `--max-concurrent-tasks`, `--custom-args`, `--description` | same + `<id>` |
| `squads[]` | `multica squad create` / `update` | `--name`, `--leader`, `--description` | `--name`, `--leader`, `--description` + `<id>` |
| `autopilots[]` | `multica autopilot create` / `update` | `--title`, `--agent`, `--mode`, `--description`, `--priority` | same + `<id>` |

> **Note on labels:** Existing labels are updated in-place using
> `multica label update <id> --name <name> --color <color>`.

## Dependencies & Ordering

```
workspace (no deps)
  ↓
labels (no deps)
  ↓
skills (no deps)
  ↓
agents (depends on skills for skill bindings)
  ↓
squads (depends on agents for leader)
  ↓
autopilots (depends on agents)
```

Agent skill bindings are applied as a final pass after all agents and skills
are converged.

## Future Enhancements

1. **Diff output** — Show per-field changes before applying.
2. **Variables / Parameters** — Allow `{{ .Values.agentModel }}` style
   interpolation so the same template can be reused across environments.
3. **Git-based catalog** — `multica-template install github.com/org/templates/k8s-team`
4. **State caching** — Cache `multica * list` results to speed up repeated
   applies.
5. **Workspace creation** — ✅ Implemented. The engine creates workspaces via
   the REST API when `targetWorkspace.create: true` is set.
