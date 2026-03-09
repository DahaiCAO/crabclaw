---
name: clawhub
description: Search and install agent skills from ClawHub, the public skill registry.
homepage: https://clawhub.ai
metadata: {"crabclaw":{"emoji":"ðŸ¦ž"}}
---

# ClawHub

Public skill registry for AI agents. Search by natural language (vector search).

## When to use

Use this skill when the user asks any of:
- "find a skill for â€?
- "search for skills"
- "install a skill"
- "what skills are available?"
- "update my skills"

## Search

```bash
npx --yes clawhub@latest search "web scraping" --limit 5
```

## Install

```bash
npx --yes clawhub@latest install <slug> --workdir ~/.crabclaw/workspace
```

Replace `<slug>` with the skill name from search results. This places the skill into `~/.crabclaw/workspace/skills/`, where crabclaw loads workspace skills from. Always include `--workdir`.

## Update

```bash
npx --yes clawhub@latest update --all --workdir ~/.crabclaw/workspace
```

## List installed

```bash
npx --yes clawhub@latest list --workdir ~/.crabclaw/workspace
```

## Notes

- Requires Node.js (`npx` comes with it).
- No API key needed for search and install.
- Login (`npx --yes clawhub@latest login`) is only required for publishing.
- `--workdir ~/.crabclaw/workspace` is critical â€?without it, skills install to the current directory instead of the crabclaw workspace.
- After install, remind the user to start a new session to load the skill.
