---
description: "Add a feature or improvement to an existing project — scopes work to only the agents needed"
---

# /add-feature

You are adding an incremental feature to an existing Databricks application.

## Input

`{{ARGUMENTS}}` — the feature description.

**Auto-detect input type:**
- If the argument is a path to an existing file, use Read to load it as the feature description.
- If the argument is not a file path (or the file doesn't exist), treat the argument as inline text.

## Validation

Before proceeding, verify the project exists:
- `src/` directory must exist, OR
- `databricks.yml` must exist

If neither exists, tell the user:
```
No existing project found. Use /create-team to start a new project instead.
```

## Execution

### 1. Read Feature Description

Load the feature description from the resolved input (file or inline text).

### 2. Invoke feature-scoper Skill

Invoke the `feature-scoper` skill, passing the feature description as input.

The feature-scoper will:
- Scan the current project state
- Map the feature to capability tags
- Select the minimum set of agents needed
- Write a scoped `.agent-team/` configuration
- Create a `feature-start/<slug>` git tag on the current commit

### 3. Confirm Scoped Configuration

After feature-scoper completes, display the scoped plan to the user:
```
Feature: <feature_description>

Scoped agents: [list of selected agents]
Phases:        [list of phases with agent assignments]
Mode:          incremental (existing project preserved)

Git tag created: feature-start/<slug>  (rollback point)
```

Ask the user: "Proceed with /start-team? (yes / review .agent-team/ first / cancel)"

### 4. Invoke /start-team

If the user confirms, invoke `/start-team` to execute the scoped plan.

The start-team command will detect `mode: incremental` in the manifest and
skip project scaffolding steps, proceeding directly to agent dispatch.

## Rollback

If the feature work produces undesirable results, roll back using the git tag:

```bash
# View the rollback point
git show feature-start/<slug>

# Roll back to pre-feature state (discard all feature changes)
git reset --hard feature-start/<slug>

# Or create a new branch from the rollback point to compare
git checkout -b rollback/<slug> feature-start/<slug>
```

The `feature-start/<slug>` tag marks the exact commit state before the feature
team ran, making it safe to experiment and easy to revert.
