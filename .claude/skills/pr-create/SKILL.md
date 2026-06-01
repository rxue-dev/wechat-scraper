---
name: pr-create
description: Stage and commit changes, rebase onto master, push, and open a PR via gh api. Use when the user runs /pr-create or asks to create a pull request for the current branch.
---

# pr-create

Take the current working state and turn it into a pushed branch with an open PR.

## Steps

1. **Inspect state.** Run `git status --short` and `git diff --stat` (plus `git diff` for unstaged/staged content) to understand what changed. Determine the current branch with `git rev-parse --abbrev-ref HEAD`.

2. **Branch if on master.** If the current branch is `master`, create and switch to a new branch first — never commit PR work directly to master. Pick a short, descriptive kebab-case branch name from the changes (e.g. `fix-ocr-paddleocr-3x`). Run `git checkout -b <name>`.

3. **Stage and commit.** `git add -A`, then commit with a clear message summarizing the changes. End the commit message body with:

   ```
   Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
   ```

   If there is nothing to commit and the branch already has commits ahead of master, skip to rebase.

4. **Rebase onto master.** Fetch and rebase to keep history linear:

   ```
   git fetch origin master
   git rebase origin/master   # or `git rebase master` if there is no remote-tracking master
   ```

   If the rebase hits conflicts, stop and report them — do not force-resolve. Note: `git rebase -i` is not supported in this environment, so only use non-interactive rebase.

5. **Push.** `git push -u origin <branch>` (use `--force-with-lease` if the branch was previously pushed and the rebase rewrote history — never plain `--force`).

6. **Create the PR via gh api.** Use the GitHub API rather than `gh pr create`:

   ```
   gh api repos/{owner}/{repo}/pulls \
     -f title="<title>" \
     -f head="<branch>" \
     -f base="master" \
     -f body="<body>"
   ```

   Derive `{owner}/{repo}` from `gh repo view --json nameWithOwner -q .nameWithOwner`. Write a concise PR body summarizing the changes and end it with:

   ```
   🤖 Generated with [Claude Code](https://claude.com/claude-code)
   ```

7. **Report.** Print the resulting PR URL from the API response.

## Notes

- Confirm the title and body reflect the actual diff, not assumptions.
- If `gh` is not authenticated, tell the user to run `gh auth login` (suggest they type `! gh auth login`).
- Do not push or open the PR if the rebase failed or tests/commits are in a broken state — surface the problem instead.
