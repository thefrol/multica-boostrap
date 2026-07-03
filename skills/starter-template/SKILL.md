---
name: starter-template
description: >
  Help users get started with the Multica starter template.
  Use this skill when a user asks how to create a new workspace,
  how to fork a template, or how to bootstrap a team setup.
---

# Starter Template Skill

Guide users to a quick, working workspace setup using the starter template.

## When to Use

- User asks "How do I create a workspace?"
- User wants a basic team setup
- User wants to fork a template to customize
- User is starting from scratch and needs a minimal example

## Quick Start Path

### Option A — Apply directly from the repo

```bash
# Clone the template space repo
git clone https://github.com/thefrol/multica-boostrap.git
cd multica-boostrap/starter

# Customize values.yaml
# Then apply
multica-template apply . --create-workspace
```

### Option B — Copy the starter to a new directory

```bash
cp -r multica-boostrap/starter ./my-team
cd my-team
# Edit values.yaml
multica-template apply . --create-workspace
```

## Customization Checklist

When helping a user start from the template, walk them through:

1. **Workspace name** — `values.yaml` → `workspaceName`
2. **Issue prefix** — `values.yaml` → `issuePrefix`
3. **Agent model** — `values.yaml` → `agentModel` (e.g. `gpt-4o`, `claude-sonnet-4-6`)
4. **Agent runtime** — `values.yaml` → `agentRuntimeId` (check available runtimes with `multica runtime list`)
5. **Labels** — add/remove labels in `template.yaml` as needed
6. **Agents** — duplicate the agent block for additional team members
7. **Skills** — add domain-specific skills under the `skills:` section
8. **Squads** — group agents into squads for larger teams

## Common Next Steps

After applying the starter template, users often want to:

- **Add autopilots** — see `examples/full-stack/template.yaml`
- **Use .env for secrets** — see the `.env Templating` section in the main README
- **Parameterize further** — see `examples/templated-workspace/template.yaml`
- **Export an existing workspace** — use `multica-template dump ./backup`

## Troubleshooting

- `multica-template: command not found` — run the install script from the repo root
- `runtimeId not found` — run `multica runtime list --output json` to get a valid runtime ID
- Workspace already exists — remove `--create-workspace` and use `--workspace-name` instead
