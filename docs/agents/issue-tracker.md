# Issue tracker: GitHub

Issues and specs for this repo live as GitHub issues. Use the `gh` CLI for all operations.

> 本仓库 issues 归属 **Neowyh/AgentPlatform**（`git remote agentplatform`），`origin`/`upstream` 仍指向上游 `bytedance/deer-flow`。`gh` 默认按 `origin` 推断仓库，操作本仓库时请显式加 `--repo Neowyh/AgentPlatform`，或在克隆内执行 `gh repo set-default Neowyh/AgentPlatform`。

## Conventions

- **Create an issue**: `gh issue create --title "..." --body "..." --repo Neowyh/AgentPlatform`. Use a heredoc for multi-line bodies.
- **Read an issue**: `gh issue view <number> --comments --repo Neowyh/AgentPlatform`, filtering comments by `jq` and also fetching labels.
- **List issues**: `gh issue list --repo Neowyh/AgentPlatform --state open --json number,title,body,labels,comments --jq '[.[] | {number, title, body, labels: [.labels[].name], comments: [.comments[].body]}]'` with appropriate `--label` and `--state` filters.
- **Comment on an issue**: `gh issue comment <number> --body "..." --repo Neowyh/AgentPlatform`
- **Apply / remove labels**: `gh issue edit <number> --add-label "..." --repo Neowyh/AgentPlatform` / `--remove-label "..." --repo Neowyh/AgentPlatform`
- **Close**: `gh issue close <number> --comment "..." --repo Neowyh/AgentPlatform`

Infer the repo from `git remote -v`; `gh` does this automatically when run inside a clone. For this repo prefer `--repo Neowyh/AgentPlatform` as noted above.

## Pull requests as a triage surface

**PRs as a request surface: no.** _(Set to `yes` if this repo treats external PRs as feature requests; `/triage` reads this flag.)_

When set to `yes`, PRs run through the same labels and states as issues, using the `gh pr` equivalents:

- **Read a PR**: `gh pr view <number> --comments --repo Neowyh/AgentPlatform` and `gh pr diff <number> --repo Neowyh/AgentPlatform` for the diff.
- **List external PRs for triage**: `gh pr list --repo Neowyh/AgentPlatform --state open --json number,title,body,labels,author,authorAssociation,comments` then keep only `authorAssociation` of `CONTRIBUTOR`, `FIRST_TIME_CONTRIBUTOR`, or `NONE` (drop `OWNER`/`MEMBER`/`COLLABORATOR`).
- **Comment / label / close**: `gh pr comment`, `gh pr edit --add-label`/`--remove-label`, `gh pr close` (each with `--repo Neowyh/AgentPlatform` for this repo).

GitHub shares one number space across issues and PRs, so a bare `#42` may be either: resolve with `gh pr view 42 --repo Neowyh/AgentPlatform` and fall back to `gh issue view 42 --repo Neowyh/AgentPlatform`.

## When a skill says "publish to the issue tracker"

Create a GitHub issue in `Neowyh/AgentPlatform`.

## When a skill says "fetch the relevant ticket"

Run `gh issue view <number> --comments --repo Neowyh/AgentPlatform`.

## Wayfinding operations

Used by `/wayfinder`. The **map** is a single issue with **child** issues as tickets.

- **Map**: a single issue labelled `wayfinder:map`, holding the Notes / Decisions-so-far / Fog body. `gh issue create --label wayfinder:map --repo Neowyh/AgentPlatform`.
- **Child ticket**: an issue linked to the map as a GitHub sub-issue (`gh api` on the sub-issues endpoint). Where sub-issues aren't enabled, add the child to a task list in the map body and put `Part of #<map>` at the top of the child body. Labels: `wayfinder:<type>` (`research`/`prototype`/`grilling`/`task`). Once claimed, the ticket is assigned to the driving dev.
- **Blocking**: GitHub's **native issue dependencies**, the canonical, UI-visible representation. Add an edge with `gh api --method POST repos/Neowyh/AgentPlatform/issues/<child>/dependencies/blocked_by -F issue_id=<blocker-db-id>`, where `<blocker-db-id>` is the blocker's numeric **database id** (`gh api repos/Neowyh/AgentPlatform/issues/<n> --jq .id`, _not_ the `#number` or `node_id`). GitHub reports `issue_dependencies_summary.blocked_by` (open blockers only, the live gate). Where dependencies aren't available, fall back to a `Blocked by: #<n>, #<n>` line at the top of the child body. A ticket is unblocked when every blocker is closed.
- **Frontier query**: list the map's open children (`gh issue list --repo Neowyh/AgentPlatform --state open`, scoped to the map's sub-issues / task list), drop any with an open blocker (`issue_dependencies_summary.blocked_by > 0`, or an open issue in the `Blocked by` line) or an assignee; first in map order wins.
- **Claim**: `gh issue edit <n> --add-assignee @me --repo Neowyh/AgentPlatform`, the session's first write.
- **Resolve**: `gh issue comment <n> --body "<answer>" --repo Neowyh/AgentPlatform`, then `gh issue close <n> --repo Neowyh/AgentPlatform`, then append a context pointer (gist + link) to the map's Decisions-so-far.
