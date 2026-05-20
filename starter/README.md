# Starter Template

A minimal, self-contained template to bootstrap a new Multica workspace.

## What's Included

- **Workspace** — configurable name, description, and issue prefix
- **Labels** — `bug`, `feature`, `docs`, `fast-path`
- **Skill** — `getting-started` with basic agent guidance
- **Agent** — `auto-coder` with sensible defaults

## Quick Start

### 1. Fork or copy this directory

```bash
cp -r starter my-workspace
cd my-workspace
```

### 2. Customize `values.yaml`

Edit `values.yaml` to match your team:

```yaml
workspaceName: "My Team"
workspaceDescription: "My awesome team workspace"
issuePrefix: "MY"
agentRuntimeId: "91a7efd7-9b8a-4818-94b9-6e3451e32826"
agentModel: "gpt-4o"
```

### 3. Apply the template

```bash
multica-template apply . --create-workspace
```

Or apply to an existing workspace:

```bash
multica-template apply . --workspace-name "My Team"
```

### 4. Dry-run first (optional)

```bash
multica-template apply . --dry-run
```

## Customizing the Template

- Add more labels, agents, squads, or autopilots in `template.yaml`
- Add more skills under the `skills:` section
- Use `.env` files for secrets (see the main README)
- Reference the `examples/` folder in the repo for advanced patterns
