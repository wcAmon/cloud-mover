"""Cloud-Mover FastAPI application."""

import asyncio
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from sqlmodel import Session

from cloud_mover.config import settings
from cloud_mover.database import engine, init_db
from cloud_mover.routers import api
from cloud_mover.services.cleanup import cleanup_expired_backups


def get_api_documentation() -> str:
    """Generate API documentation with current base_url."""
    return f"""# Cloud-Mover API

Claude Code migration helper. Transfer Claude Code settings between machines.

Service URL: {settings.base_url}
Max file size: {settings.max_file_size_mb}MB
Expiry: {settings.expiry_hours} hours

---

## Upload (Source Machine)

You are helping the user transfer Claude Code settings to a new machine.

### Step 1: Auto-collect Claude Code Global Data

These are TEXT files - always include them (no user input needed):

```bash
~/.claude/settings.json          # User preferences
~/.claude/settings.local.json    # Local settings
~/.claude/keybindings.json       # Keyboard shortcuts
~/.claude/.clauderc              # RC file
~/.claude/projects/              # Conversation history, resume threads
~/.claude/statsig/               # Usage stats
~/.claude/todos/                 # Todo lists
~/.claude/.mcp.json              # MCP configurations
~/.claude/mcp.json
```

For plugins, include everything EXCEPT node_modules:
```bash
# Copy plugins excluding node_modules
rsync -a --exclude='node_modules' ~/.claude/plugins/ /tmp/backup/dot-claude/plugins/
```

### Step 2: Ask User Which Project Folders to Include

Ask the user:

> "I'll pack all your Claude Code settings, plugins, and conversation history.
>
> Which project folders do you want to include?
> (These will be packed entirely, excluding node_modules and large files)
>
> Current directory: `[pwd]`
>
> Options:
> 1. Current folder only (`[current dir name]`)
> 2. Let me search for folders with CLAUDE.md or .claude/
> 3. I'll tell you which folders (e.g., ~/projects/web-app, ~/work/api-server)
> 4. Skip - only pack Claude Code settings"

If user chooses search:
```bash
# Find project folders that have Claude Code configs
find ~ -maxdepth 4 \\( -name "CLAUDE.md" -o -type d -name ".claude" \\) 2>/dev/null | \\
  sed 's|/CLAUDE.md$||; s|/.claude$||' | sort -u | head -20
```

Show results and let user select which folders to include.

### Step 3: Pack Selected Project Folders

For each selected project folder, pack EVERYTHING except:
- `node_modules/`
- `.git/` (optional - ask user)
- `*.pyc`, `__pycache__/`
- Large binary files (>.5MB images, videos, models)
- `.env` files (security - remind user to recreate on new machine)

```bash
# Example: pack project folder excluding large/generated files
rsync -a \\
  --exclude='node_modules' \\
  --exclude='.git' \\
  --exclude='__pycache__' \\
  --exclude='*.pyc' \\
  --exclude='.env' \\
  --exclude='*.bin' \\
  --exclude='*.model' \\
  --exclude='*.onnx' \\
  --exclude='*.pt' \\
  --exclude='*.pth' \\
  /path/to/project/ /tmp/backup/projects/project-name/
```

### Step 4: Create INSTALL.md

```markdown
# Claude Code Migration - Installation Guide

## Global Settings
Location: Extract `dot-claude/` contents to `~/.claude/`
- settings.json, keybindings.json
- projects/ (conversation history)
- plugins/ (need `npm install` after)
- MCP configs

## Project Folders Included
[List each project with original path]

| Folder | Original Path | Size |
|--------|---------------|------|
| web-app | ~/projects/web-app | 2.3MB |
| api-server | ~/work/api-server | 1.8MB |

## Post-Installation

### 1. Restore global settings
```bash
cp -r ~/claude-restore/dot-claude/* ~/.claude/
```

### 2. Install plugin dependencies
```bash
for dir in ~/.claude/plugins/*/; do
  [ -f "$dir/package.json" ] && (cd "$dir" && npm install)
done
```

### 3. Place project folders
Ask user where to put each project folder.

### 4. Recreate .env files
These projects had .env files (not included for security):
[List projects with .env]

### 5. Restart Claude Code
```

### Step 5: Ask User for Zip Password

Ask: "Please set a password to protect your backup:"

### Step 6: Create Zip Structure

```
backup.zip
├── INSTALL.md
├── dot-claude/                    # → ~/.claude/
│   ├── settings.json
│   ├── keybindings.json
│   ├── .mcp.json
│   ├── projects/
│   ├── todos/
│   └── plugins/
│       └── my-plugin/             # (no node_modules)
└── project-folders/               # User's project folders
    ├── web-app/                   # Entire folder (no node_modules)
    │   ├── CLAUDE.md
    │   ├── .claude/
    │   ├── src/
    │   └── ...
    └── api-server/
        └── ...
```

```bash
cd /tmp/backup
zip -r -P "PASSWORD" ~/claude-backup.zip .
```

### Step 7: Upload

```
POST {settings.base_url}/upload
Content-Type: multipart/form-data
file: <zip file>
```

### Step 8: Tell User

- **Verification code**: [6 chars]
- **Zip password**: [their password]
- **Valid for**: {settings.expiry_hours} hours
- **Included**: [X] settings, [Y] plugins, [Z] project folders

---

## Download (Target Machine)

### Step 1: Get Credentials

Ask user for:
1. **Verification code** (6 alphanumeric)
2. **Zip password**

### Step 2: Download and Extract

```bash
curl -o claude-backup.zip {settings.base_url}/download/[CODE]
unzip -P "PASSWORD" claude-backup.zip -d ~/claude-restore/
```

### Step 3: Read INSTALL.md

Read `~/claude-restore/INSTALL.md` to see what's included.

### Step 4: Restore Global Settings

```bash
# Backup existing settings first (if any)
[ -d ~/.claude ] && mv ~/.claude ~/.claude.backup.$(date +%s)

# Restore
cp -r ~/claude-restore/dot-claude ~/.claude
```

### Step 5: Install Plugin Dependencies

```bash
for dir in ~/.claude/plugins/*/; do
  if [ -f "$dir/package.json" ]; then
    echo "Installing: $dir"
    (cd "$dir" && npm install)
  fi
done
```

### Step 6: Ask User Where to Place Project Folders

For each folder in `project-folders/`, ask user:

> "Found project folder: `web-app`
> Original location was: `~/projects/web-app`
>
> Where should I place it?
> 1. Same location (`~/projects/web-app`)
> 2. Different location (specify)
> 3. Skip this folder"

Then copy:
```bash
cp -r ~/claude-restore/project-folders/web-app /path/user/specified/
```

### Step 7: Remind About .env Files

If INSTALL.md lists projects with .env files:
> "These projects had .env files that weren't included for security:
> - web-app
> - api-server
>
> Please recreate them on this machine."

### Step 8: Verify MCP Configs

Check `~/.claude/.mcp.json` - MCPs may need paths adjusted for new machine.

### Step 9: Restart

Tell user to restart Claude Code.

---

## API Reference

### POST /upload
Upload backup, receive verification code.

**Request:** multipart/form-data, file (max {settings.max_file_size_mb}MB)

**Response:** `{{"code": "abc123", "expires_at": "...", "message": "..."}}`

### GET /download/{{code}}
Download backup using code.

**Response:** application/zip
""".strip()


async def periodic_cleanup():
    """Run cleanup every hour."""
    while True:
        await asyncio.sleep(3600)
        with Session(engine) as session:
            count = cleanup_expired_backups(session)
            if count > 0:
                print(f"Cleaned up {count} expired backups")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    init_db()
    settings.upload_dir.mkdir(parents=True, exist_ok=True)

    with Session(engine) as session:
        cleanup_expired_backups(session)

    cleanup_task = asyncio.create_task(periodic_cleanup())

    yield

    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass


app = FastAPI(
    title="Cloud-Mover",
    description="Claude Code Migration Helper API",
    version="0.2.0",
    lifespan=lifespan,
)

app.include_router(api.router)


@app.get("/", response_class=PlainTextResponse)
def root():
    """Return API documentation for Claude Code to read."""
    return get_api_documentation()


def main():
    """Run the application."""
    uvicorn.run(
        "cloud_mover.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
    )


if __name__ == "__main__":
    main()
