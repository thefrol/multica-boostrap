# Multica Template Space

> **Your Multica workspace as code. Version-controlled. Reproducible. One command away.**

Stop configuring workspaces by hand. Multica Template Space lets you declare your entire team setup — agents, skills, squads, labels, autopilots — in a single `template.yaml` and provision it with one command. Back it up in git. Clone it to a new workspace. Share it with your team.

## The Pain It Cures

| Pain | How we fix it |
|------|---------------|
| **Slow workspace setup** | Spin up a complete working environment in seconds, not hours. |
| **Manual team bootstrapping** | Add a full research team, dev squad, or ops crew with a single `multica-template apply`. |
| **Lost configuration** | Store your workspace and team definitions in git. Restore, migrate, or duplicate anytime. |

## What It Is

A declarative provisioning engine for Multica workspaces. Think of it as
**Helm for Multica** — a human-readable catalog of workspace templates that
creates and updates agents, skills, labels, squads, and autopilots from a
single YAML file.

## Quick Start

### Install

```bash
# One-line install (piped)
curl -sSL https://raw.githubusercontent.com/thefrol/multica-boostrap/main/install.sh | bash

# Or two-step (review before running)
curl -sSL -o install.sh https://raw.githubusercontent.com/thefrol/multica-boostrap/main/install.sh
cat install.sh | less
bash install.sh
```

### Usage

```bash
# Apply a template to the current workspace
multica-template apply ./examples/basic-workspace

# Dry-run to see what would change
multica-template apply ./examples/agent-fleet --dry-run

# Apply to a specific workspace by ID or name
multica-template apply ./examples/basic-workspace --workspace-id <uuid>
multica-template apply ./examples/basic-workspace --workspace-name "Team Alpha"

# Create a new workspace from a template
multica-template apply ./examples/create-workspace
multica-template apply ./examples/create-workspace --workspace-name "My Team" --create-workspace

# Dump an existing workspace to a template file
multica-template dump ./exported-template
multica-template dump ./exported-template --workspace-name "Team Alpha"

# Clone one workspace to another
multica-template clone --from-name "Source Workspace" --to-name "New Workspace" --create-workspace
multica-template clone --from-id <uuid> --to-id <uuid> --dry-run

# Update multica-template to the latest version
multica-template update
multica-template update --dry-run
multica-template update --check-only
```

## Default Template Paths

When you run `multica-template apply` without specifying a source directory, the
tool automatically searches for `template.yaml` in the following default paths
(in order):

1. `.multica-workspace/`
2. `.multica-bootstrap/`
3. `.agents/multica-workspace/`
4. `.agents/multica-bootstrap/`

This lets you keep your Multica team configuration right next to your source code
— version-controlled, governed, and discoverable with a single command:

```bash
# Runs apply against the first matching default path
multica-template apply
```

## How It Works

1. **Author** a `template.yaml` that describes your desired workspace state.
2. **Run** `multica-template apply <folder>` against the target workspace.
3. The engine reads the template, compares it with the current workspace state,
   and issues the minimum set of `multica` CLI commands to converge to the
desired state.

## Dump Workspace Config

The companion `multica-template dump` command exports an existing workspace to a
`template.yaml` file. This is useful for:

- **Backing up** workspace configuration in git
- **Cloning** a workspace setup to another workspace
- **Starting** from an existing workspace and tweaking the template

```bash
# Dump current workspace
multica-template dump ./my-template

# Dump a specific workspace by name
multica-template dump ./my-template --workspace-name "Team Alpha"
```

The dumped template uses symbolic names for all references (skills, agents, squad
leaders, autopilot assignees) so it is fully portable and can be applied with
`multica-template apply`.

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
├── install.sh                # Web installer (curl|bash)
├── multica-template          # Unified CLI entry point
├── schema/
│   └── template-schema.yaml  # Formal template schema
├── examples/
│   ├── basic-workspace/      # Rename a workspace, add labels
│   ├── agent-fleet/          # Multiple agents with skills
│   ├── create-workspace/     # Create a new workspace from a template
│   ├── full-stack/           # Agents + squads + autopilots
│   ├── target-workspace/     # Apply to a specific workspace by name
│   └── templated-workspace/  # Helm-style Jinja2 parameterization
└── bin/
    ├── multica-template-apply    # Backward-compatible wrapper for 'apply'
    └── multica-template-dump     # Backward-compatible wrapper for 'dump'
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
multica-template apply ./examples/basic-workspace --workspace-id <uuid>
multica-template apply ./examples/basic-workspace --workspace-name "Team Alpha"
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

You can override this and create the workspace on the fly:

```bash
multica-template apply ./examples/create-workspace --workspace-name "New Team" --create-workspace
```

Or declare it in the template:

```yaml
spec:
  targetWorkspace:
    name: "New Team"
    create: true
    slug: "new-team"          # optional, auto-generated from name if omitted
```

## Safe Development

All template examples in this repository are configured to target the **test workspace**
(`test-space`, `b025515a-259e-4679-963d-35ba3fce947a`) by default. This prevents
accidental changes to production workspaces during development and testing.

### Policy

1. **Never apply templates to a production workspace without explicit review.**
2. **Always verify the target workspace before running `multica-template apply`.**
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
multica-template apply ./examples/basic-workspace
```

#### Via CLI flag (recommended for one-off runs)

```bash
multica-template apply ./examples/basic-workspace --workspace-id <uuid>
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
multica-template apply ./examples/full-stack --dry-run
```

## Template Variables (v0.3)

Templates support Helm-style Jinja2 parameterization. Use `{{ .Values.key }}` to
substitute values at apply time.

### Default values

Place a `values.yaml` file next to `template.yaml` to define defaults:

```yaml
# values.yaml
workspaceName: "K8s Team"
agentModel: "gpt-4o"
```

```yaml
# template.yaml
spec:
  workspace:
    name: "{{ .Values.workspaceName }}"
  agents:
    - name: architect
      model: "{{ .Values.agentModel }}"
```

### Environment-specific overlays

Pass additional values files with `--values` (applied in order, later overrides
earlier):

```bash
multica-template apply ./examples/templated-workspace \
  --values ./staging-values.yaml \
  --values ./secrets-values.yaml
```

### Ad-hoc overrides

Use `--set key=value` for quick one-off overrides (highest precedence):

```bash
multica-template apply ./examples/templated-workspace \
  --set agentModel=gpt-4o-mini \
  --set workspaceName="Staging"
```

Dot notation is supported for nested values:

```bash
multica-template apply ./my-template --set agent.model=gpt-4o
```

### Multiline values

For multiline strings inside YAML block scalars (`|`), use the Jinja2 `indent`
filter to preserve indentation:

```yaml
instructions: |
  {{ .Values.agentInstructions | indent(2) }}
```

### Scope

v0.3 supports **simple variable substitution only**. Loops, conditionals, and
includes are reserved for future releases.

## .env Templating (Secrets)

Keep credentials out of `template.yaml` by storing them in a separate `.env` file.
This keeps your templates safe to commit to git while still provisioning agents
with their required secrets.

### Per-agent `envFile`

Reference a `.env` file directly on an agent definition. The file is loaded
relative to the template directory and merged into `customEnv`. Values in
`customEnv` take precedence over the `.env` file.

```yaml
agents:
  - name: backend-lead
    envFile: .env
    customEnv:
      PUBLIC_VAR: "not a secret"
```

```bash
# .env
OPENAI_API_KEY=sk-...
DB_PASSWORD=secret
```

### Template variables from `.env`

You can also reference `.env` values via Jinja2 using `{{ .Env.VARNAME }}`:

```yaml
agents:
  - name: backend-lead
    customEnv:
      API_KEY: "{{ .Env.OPENAI_API_KEY }}"
```

By default, the engine looks for `.env` in the template directory. Use
`--env-file` to specify a different path:

```bash
multica-template apply ./my-template --env-file ./secrets.env
```

### Dump with `.env` extraction

When exporting a workspace, use `--env-file` to extract agent `customEnv` values
into a `.env` file and replace them in `template.yaml` with `{{ .Env.VARNAME }}`
placeholders:

```bash
multica-template dump ./exported-template --env-file .env
```

This produces:

```bash
# exported-template/.env
AGENT_NAME_API_KEY=secret-value
```

```yaml
# exported-template/template.yaml
agents:
  - name: agent-name
    customEnv:
      API_KEY: "{{ .Env.AGENT_NAME_API_KEY }}"
```

### Security note

`.env` files are listed in `.gitignore` by default. Never commit them.

## Roadmap

| Phase | Scope |
|-------|-------|
| **v0.1** | Workspace metadata, labels, skills, agents, squads, autopilots, dry-run, workspace creation |
| **v0.2** | Diff output, state caching |
| **v0.3** | Template variables / parameterization |
| **v0.4** | Template registry (git-based catalog) |
