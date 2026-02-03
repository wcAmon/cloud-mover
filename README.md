# Cloud-Mover

[繁體中文](README.zh-TW.md) | English

AI Assistant migration and template sharing service.

**Try it now:** https://loader.land

## Features

### Migration (Settings Transfer)
- Upload backup files with a 6-character verification code
- Download backups on your new machine
- Auto-delete after 24 hours (files + records)
- Password-protected zip files

### Template Sharing (NEW)
- Share CLAUDE.md or AGENTS.md templates
- Simple 6-character code for sharing
- 7-day expiry for templates
- Download count tracking

## Quick Start with Claude Code

Tell Claude Code:

```
幫我用 loader.land 搬家
```

or

```
Help me migrate using loader.land
```

Claude Code will read the API documentation and guide you through the process.

## Supported AI Tools

| Tool | Config File | Migration | Template |
|------|-------------|-----------|----------|
| Claude Code | CLAUDE.md | ✅ | ✅ |
| OpenAI Codex | AGENTS.md | ✅ | ✅ |
| GitHub Copilot | AGENTS.md | - | ✅ |
| Cursor | .cursorrules | - | ✅ |
| OpenClaw (Moltbot) | ~/.openclaw/ | ✅ | - |

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | API documentation (for AI to read) |
| `/upload` | POST | Upload backup, returns code |
| `/download/{code}` | GET | Download backup |
| `/templates` | POST | Share template, returns code |
| `/templates/{code}` | GET | Get template (JSON) |
| `/templates/{code}/raw` | GET | Get raw markdown |

## Self-Hosting

### Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager

### Installation

```bash
git clone https://github.com/wcAmon/cloud-mover.git
cd cloud-mover
uv sync
```

### Configuration

Create a `.env` file:

```env
HOST=0.0.0.0
PORT=8080
BASE_URL=https://your-domain.com
UPLOAD_DIR=./uploads
DATA_DIR=./data
MAX_FILE_SIZE_MB=59
EXPIRY_HOURS=24
TEMPLATE_EXPIRY_DAYS=7
MAX_TEMPLATE_SIZE_KB=100
```

### Run

```bash
uv run cloud-mover
```

### Run with systemd

```ini
[Unit]
Description=Cloud-Mover API
After=network-online.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/cloud-mover
EnvironmentFile=/path/to/cloud-mover/.env
ExecStart=/home/your-user/.local/bin/uv run cloud-mover
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### Reverse Proxy (Caddy)

```
your-domain.com {
    reverse_proxy localhost:8080
}
```

## Privacy & Security

- Server does NOT store zip passwords - only users know them
- Complete deletion after expiry - no records retained
- Verification codes only identify files - cannot decrypt contents
- Templates are public (no password) but expire after 7 days

## Development

```bash
# Install dev dependencies
uv sync --group dev

# Run tests
uv run pytest

# Run with auto-reload (development)
uv run uvicorn cloud_mover.main:app --reload
```

## License

MIT
