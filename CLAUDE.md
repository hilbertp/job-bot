# Claude Code Instructions

Before any git, source-control, or release operation in this repo, read and
follow [WORKFLOW.md](WORKFLOW.md). Treat it as mandatory operating policy, not
background documentation.

Source-control ground truth is `git status --short --branch`, not the VS Code
Source Control panel. When the panel appears surprising, verify with git before
describing the state.

Do not commit directly on `main`. For non-trivial work, start from a fresh
`main`, create a branch, make the change there, run the documented checks, and
publish the branch.

Default integration is GitHub PR merge:

1. Push the feature branch.
2. Create and merge a PR into `main`.
3. Check out `main` locally and `git pull --ff-only`.

Do not create local merge commits on `main` or run `git push origin main` unless
the user explicitly asks for that path in the current conversation.

If local `main` is ahead of `origin/main`, stop before starting new edits. Report
the exact `git status --short --branch` state and follow the recovery section in
`WORKFLOW.md`.
