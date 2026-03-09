# Project Structure, Contributing & Roadmap (EN)

<p align="center">
  <a href="../en/project-structure-contributing-roadmap.md"><strong>English</strong></a> | <a href="../zh-CN/project-structure-contributing-roadmap.md"><strong>中文</strong></a>
</p>

## Project Structure
```
crabclaw/
├── agent/          # Core agent logic
│   ├── loop.py     #    Agent loop (LLM + tool execution)
│   ├── context.py  #    Prompt builder
│   ├── memory.py   #    Persistent memory
│   ├── skills.py   #    Skills loader
│   ├── subagent.py #    Background task execution
│   └── tools/      #    Built-in tools (incl. spawn)
├── skills/         # Bundled skills (github, weather, tmux...)
├── channels/       # Chat channel integrations
├── bus/            # Message routing
├── cron/           # Scheduled tasks
├── heartbeat/      # Proactive wake-up
├── providers/      # LLM providers + transcription
├── session/        # Conversation sessions
├── config/         # Configuration
├── proactive/      # Proactive engine (engine, selector, state, triggers)
├── reflection/     # Reflection engine (evaluate & log)
├── prompts/        # Prompt manager & defaults
├── i18n/           # Localization
├── templates/      # Workspace templates (HEARTBEAT, SOUL, TOOLS)
├── utils/          # Utilities (logging, http_pool, metrics, plugins)
├── dashboard/      # Minimal dashboard (static web, broadcaster)
└── cli/            # Commands
```

```
Top-level
├── bridge/         # TypeScript bridge (WhatsApp, server)
├── dashboard/      # Dashboard service (Python)
└── tests/          # Unit tests
```

## Contributing
PRs welcome. The codebase is intentionally small and readable.

## Roadmap
- Multi-modal (images, voice, video)
- Long-term memory
- Better reasoning (planning & reflection)
- More integrations (calendar)
- Self-improvement (feedback loop)

Details: see [README.md](../../README.md#L1005).
