---
name: multica-setup-fix
description: >
  Diagnose and fix common Multica CLI setup, git configuration, workspace,
  and template-apply issues. Use whenever an agent encounters blockers that
  prevent normal task execution in Multica or in a checked-out repository.
---

# Multica Setup Fix

A troubleshooting protocol for agents blocked by environment, CLI, git, or
workspace problems.

## When to Use This Skill

- `multica` CLI commands fail, return auth errors, or time out.
- A repository checkout is missing, incomplete, or in a broken git state.
- Required tools (git, node, docker, etc.) are missing or misconfigured.
- Template or skill application produces errors.
- The agent context appears stale or inconsistent with the workspace state.

## 1. Multica CLI Setup Problems

### 1.1 CLI not found or outdated

**Symptoms:** `multica: command not found` or outdated CLI behavior.

**Fixes:**
```bash
# Verify installation
which multica
multica --version

# If missing, reinstall per workspace docs or ask the workspace owner
# for the correct install method (npm, brew, curl, etc.).
```

### 1.2 Auth / connectivity errors

**Symptoms:** `401 Unauthorized`, `403 Forbidden`, or connection timeouts.

**Fixes:**
```bash
# Check that the CLI can reach the workspace
multica workspace get --output json

# If auth fails, verify tokens / env vars:
env | grep -i multica
env | grep -i token

# Common env vars: MULTICA_API_URL, MULTICA_TOKEN
```

- If tokens are missing or expired, ask the workspace owner to refresh them.
- Do **not** hard-code credentials into code or comments.

### 1.3 Permission denied on issue operations

**Symptoms:** `403` when updating an issue or adding a comment.

**Fixes:**
- Confirm the issue is assigned to you or your squad.
- If you need escalation, mention the workspace owner (human) in a comment.
- Never retry the same operation more than 3 times without human input.

## 2. Git Configuration Issues

### 2.1 Missing remotes

**Symptoms:** `fatal: 'origin' does not appear to be a git repository`.

**Fixes:**
```bash
git remote -v
# If empty, add the remote from the project resource or issue context:
git remote add origin <url>
git fetch origin
```

### 2.2 Unmerged branches

**Symptoms:** Commits exist on a feature branch but not on `main`.

**Fixes:**
```bash
# List branches with unmerged commits
git branch -a --no-merged main

# Merge to main (preferred for agent worktrees)
git checkout main
git merge <feature-branch>
git push origin main

# If the project requires PRs, create the PR and report the URL.
```

**Rule:** Never leave committed work on an unmerged branch without explicit
user instruction.

### 2.3 Broken git state

**Symptoms:** Merge conflicts, detached HEAD, corrupted index.

**Fixes:**
```bash
# Check current state
git status
git branch --show-current

# Resolve merge conflicts manually, then:
git add -A
git commit -m "Resolve conflicts"

# For detached HEAD, create a branch or checkout an existing one:
git checkout -b recovery-branch
# Or
git checkout main
```

## 3. Basic Workspace Troubleshooting

### 3.1 Missing tools / dependencies

**Symptoms:** Build failures, `command not found` during task execution.

**Fixes:**
```bash
# Common tools check
which node && node --version
which pnpm && pnpm --version
which docker && docker --version
which go && go version

# Install missing dependencies according to project docs
# (package.json, go.mod, requirements.txt, etc.)
```

### 3.2 Disk / memory pressure

**Symptoms:** `No space left on device`, OOM kills, slow execution.

**Fixes:**
```bash
# Disk usage
df -h .
du -sh .

# Memory
free -h

# Cleanup (use with caution)
docker system prune -f   # if docker is available
rm -rf node_modules/.cache
```

### 3.3 Stale agent context

**Symptoms:** Files on disk do not match issue description or recent comments.

**Fixes:**
1. Re-read the issue and the latest comments with `multica issue get` and
   `multica issue comment list`.
2. Re-check the working directory state.
3. If the mismatch persists, post a comment describing the discrepancy and
   wait for the workspace owner to clarify.

## 4. Common Template Apply Errors

### 4.1 Skill or template not found

**Symptoms:** `Skill 'xxx' not found` or template path errors.

**Fixes:**
```bash
# List installed skills
ls .kimi/skills/
# or
ls .agents/skills/
# or
ls skills/

# Verify the skill directory name matches the skill reference exactly.
```

### 4.2 File-path collisions

**Symptoms:** Template overwrite warnings, merge conflicts in generated files.

**Fixes:**
- Review the existing file before overwriting.
- If the file is mission-critical, back it up or ask the owner before
  replacing.
- Use targeted edits instead of full-file overwrites when possible.

## 5. Escalation Rules

Escalate to the workspace owner (human) when:

- Auth tokens are missing or expired and you cannot refresh them.
- Git remote URLs are unknown or the repository has been moved.
- The workspace configuration (agents, squads, autopilots) appears broken.
- You encounter a bug in the `multica` CLI itself.
- Disk or memory issues cannot be resolved by routine cleanup.

## 6. Verification Checklist

After applying any fix, verify:

- [ ] `multica workspace get --output json` returns valid data.
- [ ] `git status` shows a clean or expected state.
- [ ] The current branch is `main` (or the intended default branch).
- [ ] Required commands (`node`, `pnpm`, `go`, etc.) are available and at
      expected versions.
- [ ] The original blocker is resolved by retrying the failed operation.
- [ ] If the fix changed files, the changes are committed and merged to
      `main` (or a PR is opened and its URL is reported).

## See Also

- Git Merge Policy skill
- Code Review skill
