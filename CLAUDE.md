# CLAUDE.md

Guidance for Claude Code when working in this repository.

## Project

**PAB** — matchup analyses between **PACE** (satellite ocean color) and
**BGC-Argo** (autonomous float) data. The goal is to produce matchup analyses
and share the results with the community.

The Python package lives in [pab/](pab/).

## Working agreements

- **Git is handled by the user.** Do not run `git add`, `git commit`,
  `git push`, branch, merge, or any other state-changing git command. The user
  performs all git operations themselves. (Read-only inspection such as
  `git status` or `git diff` is fine when needed.)

## Logging

The project keeps a work log in [claude_prompts/start_up.md](claude_prompts/start_up.md)
under the "Logs" section. When asked to log work, append an entry using the
format documented there:

```
### <Date> (Short summary of the work)

<Detailed description of the work and what you learned>
```
