# Repository workflow

The user prefers all changes to this project to be made in the local checkout at
`/Users/davidngerebara/Documents/ai-failure-limits/`, then committed and pushed to
`https://github.com/david-ngerebara/ai-failure-limits.git`.

- Use this local checkout for editing, validation, commits, and pushes. Do not use
  generated output copies or GitHub file-editing APIs as the primary workspace.
- Check the current branch, working tree, and remote state before making changes.
  Preserve unrelated local edits and remote commits.
- After completing requested changes, run the relevant checks, review the diff,
  commit only the task's files locally, and push to the branch's upstream unless
  the user asks to keep the changes local. The normal branch is `main`.
- Do not force-push or discard unrelated work. Verify the push and report the
  resulting commit and any remaining local changes.
- For Python changes, the current test command is
  `python3 -m unittest discover -s tests -v` from the repository root.
