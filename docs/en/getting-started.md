# Getting Started

## 1) Install

```bash
git clone https://github.com/DahaiCAO/crabclaw.git
cd crabclaw
python -m venv .venv
. .venv/bin/activate
pip install -U pip
pip install -e .
```

Alternative:

```bash
pip install crabclaw-ai
```

## 2) Initialize

```bash
crabclaw onboard
```

This creates config/workspace and default admin account.

## 3) Configure Provider

Edit `~/.crabclaw/config.json` and set:
- `providers.<name>.apiKey`
- `agents.defaults.provider`
- `agents.defaults.model`

## 4) Start Runtime

```bash
crabclaw gateway
```

Optional dashboard:

```bash
crabclaw dashboard
```

## 5) Login

- URL: `http://127.0.0.1:18791`
- default: `admin / admin2891`

## 6) Verify End-to-End

```bash
python scripts/e2e_multichannel_sync_check.py --help
```

See:
- [Architecture](architecture.md)
- [Channels](channels.md)
- [User Guide](user-guide.md)
