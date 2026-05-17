# Multica Template Space

A declarative provisioning engine for Multica workspaces. Think of it as
**Helm for Multica** — a human-readable catalog of workspace templates that
creates and updates agents, skills, labels, squads, and autopilots from a
single YAML file.

## Quick Start

```bash
# Apply a template to the current workspace
multica-template-apply ./examples/basic-workspace

# Dry-run to see what would change
multica-template-apply ./examples/agent-fleet --dry-run

# Apply to a specific workspace by ID or name
multica-template-apply ./examples/basic-workspace --workspace-id <uuid>
multica-template-apply ./examples/basic-workspace --workspace-name "Team Alpha"
```

## How It Works

1. **Author** a `template.yaml` that describes your desired workspace state.
2. **Run** `multica-template-apply <folder>` against the target workspace.
3. The engine reads the template, compares it with the current workspace state,
   and issues the minimum set of `multica` CLI commands to converge to the
desired state.

## The ID Problem — Solved

The main challenge in declarative Multica provisioning is **UUID references**.
When you create an agent, you get back an ID. Other resources (squads,
autopilots, agent skill assignments) need that ID.

The template engine solves this with **symbolic references**:

```yaml
agents:
  - name: auto-coder
    runtimeId: "1a7010cd-5d33-4206-8208-5767a497ff39"
    instructions: "You are a coding agent."

squads:
  - name: dev-team
    leader: auto-coder        # ← resolved to the agent's UUID at apply time
```

The engine maintains an in-memory registry of `name → id` mappings. When a
resource is created or updated, its ID is captured and made available for
resolution in downstream resources.

## Directory Layout

```
multica-template-space/
├── README.md
├── DESIGN.md                 # Architecture & design decisions
├── IMPLEMENTATION.md         # Step-by-step build guide for the engine
├── schema/
│   └── template-schema.yaml  # Formal template schema
├── examples/
│   ├── basic-workspace/      # Rename a workspace, add labels
│   ├── agent-fleet/          # Multiple agents with skills
│   ├── full-stack/           # Agents + squads + autopilots
│   └── target-workspace/     # Apply to a specific workspace by name
└── bin/
    └── multica-template-apply  # Engine executable (see IMPLEMENTATION.md)
```

## Template Example

```yaml
apiVersion: multica.template/v1
kind: WorkspaceTemplate
metadata:
  name: k8s-team
  description: "Kubernetes team workspace"
spec:
  workspace:
    name: "K8s Team"
    description: "Workspace for the Kubernetes platform team"
    issuePrefix: "K8S"

  labels:
    - name: bug
      color: "#ef4444"
    - name: feature
      color: "#22c55e"

  skills:
    - name: k8s-troubleshooting
      description: "Kubernetes debugging guidelines"
      files:
        - path: SKILL.md
          content: |
            # K8s Troubleshooting
            Always check `kubectl get events` first...

  agents:
    - name: k8s-architect
      runtimeId: "1a7010cd-5d33-4206-8208-5767a497ff39"
      instructions: "You are a Kubernetes architect..."
      visibility: workspace
      maxConcurrentTasks: 3
      skills:
        - k8s-troubleshooting

  squads:
    - name: platform-team
      description: "Platform engineering squad"
      leader: k8s-architect

  autopilots:
    - name: daily-health-check
      title: "Daily Health Check"
      agent: k8s-architect
      mode: create_issue
      description: "Run a daily health check on the cluster"
      priority: high
```

## Target Workspace

By default, the engine applies to the **current workspace** (your active `multica`
CLI context). You can override this in three ways:

### 1. CLI Flags (highest precedence)

```bash
multica-template-apply ./examples/basic-workspace --workspace-id <uuid>
multica-template-apply ./examples/basic-workspace --workspace-name "Team Alpha"
```

### 2. Template Field

```yaml
spec:
  targetWorkspace:
    id: "4b4ec473-4336-43e6-9992-875fbd70b584"
    # or
    name: "Full Stack Team"
```

### 3. Current Workspace (fallback)

If no target is specified, the engine uses the workspace from your `multica`
profile.

### Precedence

```
--workspace-id > --workspace-name > spec.targetWorkspace.id > spec.targetWorkspace.name > current workspace
```

If `--workspace-name` or `spec.targetWorkspace.name` is used but the workspace
does not exist, the engine fails fast with:

```
Workspace "X" not found. Create it via the web UI first.
```

## Safe Development

All template examples in this repository are configured to target the **test workspace**
(`test-space`, `b025515a-259e-4679-963d-35ba3fce947a`) by default. This prevents
accidental changes to production workspaces during development and testing.

### Policy

1. **Never apply templates to a production workspace without explicit review.**
2. **Always verify the target workspace before running `multica-template-apply`.**
3. **Use `MULTICA_WORKSPACE_ID` or `--workspace-id` to override the default target.**

### Default Target Behavior

The engine resolves the target workspace in the following precedence:

```
--workspace-id > --workspace-name > spec.targetWorkspace.id >
spec.targetWorkspace.name > MULTICA_WORKSPACE_ID env var > test-space (default)
```

If no target is specified via CLI flags, template fields, or environment variables,
the engine automatically applies changes to the designated test workspace.

### Setting the Target Workspace

#### Via environment variable (recommended for CI)

```bash
export MULTICA_WORKSPACE_ID="b025515a-259e-4679-963d-35ba3fce947a"
multica-template-apply ./examples/basic-workspace
```

#### Via CLI flag (recommended for one-off runs)

```bash
multica-template-apply ./examples/basic-workspace --workspace-id <uuid>
```

#### Via template field

```yaml
spec:
  targetWorkspace:
    id: "b025515a-259e-4679-963d-35ba3fce947a"
```

### Dry-Run First

Always use `--dry-run` to preview changes before applying:

```bash
multica-template-apply ./examples/full-stack --dry-run
```

## Roadmap

| Phase | Scope |
|-------|-------|
| **v0.1** | Workspace metadata, labels, skills, agents, squads, autopilots, dry-run |
| **v0.2** | Diff output, state caching |
| **v0.3** | Template variables / parameterization |
| **v0.4** | Template registry (git-based catalog) |
