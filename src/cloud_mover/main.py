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

### Step 1: Auto-collect Claude Code Data (No User Input Needed)

These are TEXT files and configs - always include them:

```bash
# Core settings (always include)
~/.claude/settings.json
~/.claude/settings.local.json
~/.claude/keybindings.json
~/.claude/.clauderc

# Conversation history / resume threads
~/.claude/projects/          # Project memories and threads
~/.claude/statsig/           # Usage stats

# Plugins with skills
~/.claude/plugins/           # Include everything EXCEPT node_modules
# For each plugin, include: plugin.json, *.md (SKILL.md, README.md), src/, etc.
# EXCLUDE: node_modules/ (will reinstall on new machine)

# MCP configurations
~/.claude/.mcp.json
~/.claude/mcp.json
~/.config/claude-code/mcp.json
```

Run this to find all Claude-related configs:
```bash
# List ~/.claude/ structure
find ~/.claude -type f -name "*.json" -o -name "*.md" -o -name "*.yaml" -o -name "*.yml" 2>/dev/null

# Check for MCP configs
cat ~/.claude/.mcp.json 2>/dev/null
cat ~/.claude/mcp.json 2>/dev/null

# List plugins (exclude node_modules)
find ~/.claude/plugins -type f ! -path "*/node_modules/*" 2>/dev/null
```

### Step 2: Ask User About Project-Specific Data

Ask the user:

> "I'll pack all your Claude Code settings, plugins, and conversation history.
>
> Do you also want to include project-specific CLAUDE.md files?
> These contain project instructions and memories.
>
> Please tell me which project folders to include, or I can search for them.
> Current directory: [show pwd]
>
> Options:
> 1. Include current project only ([current dir])
> 2. Search for all CLAUDE.md files in home directory
> 3. Specify folders manually
> 4. Skip project files"

If user chooses to search:
```bash
# Find all CLAUDE.md and .claude/ directories
find ~ -name "CLAUDE.md" -o -type d -name ".claude" 2>/dev/null | grep -v "/.claude/" | head -20
```

### Step 3: Create INSTALL.md

Create `INSTALL.md` listing exactly what's included:

```markdown
# Claude Code Migration - Installation Guide

## Global Settings (extract to ~/.claude/)
- settings.json - User preferences
- keybindings.json - Keyboard shortcuts
- projects/ - Conversation history and project memories
- plugins/ - Installed plugins (run npm install after)

## MCP Configurations
- .mcp.json - MCP server settings
[List which MCPs are configured]

## Plugins Included
[List each plugin and note if it needs npm install]

## Project-Specific Files
[List each project CLAUDE.md or .claude/ included]

## Post-Installation Steps
1. Extract global settings: `unzip -d ~ backup.zip "dot-claude/*"`
2. For each plugin with package.json: `cd ~/.claude/plugins/[name] && npm install`
3. Copy project CLAUDE.md files to their respective directories
4. Restart Claude Code
```

### Step 4: Ask User for Zip Password

Ask: "Please set a password to protect your backup (the server won't store it):"

### Step 5: Create the Zip

Structure the zip clearly:
```
backup.zip
├── INSTALL.md
├── dot-claude/                    # Maps to ~/.claude/
│   ├── settings.json
│   ├── keybindings.json
│   ├── .mcp.json
│   ├── projects/
│   └── plugins/
│       └── my-plugin/             # Exclude node_modules
└── projects/                      # Project-specific files
    ├── my-project/
    │   └── CLAUDE.md
    └── another-project/
        └── .claude/
```

```bash
# Create temp directory and organize
mkdir -p /tmp/claude-backup/dot-claude
mkdir -p /tmp/claude-backup/projects

# Copy global settings
cp -r ~/.claude/settings.json /tmp/claude-backup/dot-claude/ 2>/dev/null
cp -r ~/.claude/keybindings.json /tmp/claude-backup/dot-claude/ 2>/dev/null
cp -r ~/.claude/.mcp.json /tmp/claude-backup/dot-claude/ 2>/dev/null
cp -r ~/.claude/projects /tmp/claude-backup/dot-claude/ 2>/dev/null

# Copy plugins (exclude node_modules)
rsync -a --exclude='node_modules' ~/.claude/plugins/ /tmp/claude-backup/dot-claude/plugins/

# Copy project files (as specified by user)
# cp -r /path/to/project/CLAUDE.md /tmp/claude-backup/projects/project-name/

# Create INSTALL.md
# [write INSTALL.md to /tmp/claude-backup/]

# Create password-protected zip
cd /tmp/claude-backup
zip -r -P "USER_PASSWORD" ~/claude-backup.zip .
```

### Step 6: Upload

```
POST {settings.base_url}/upload
Content-Type: multipart/form-data
file: <zip file>
```

### Step 7: Tell User

Tell the user:
- **Verification code**: [6 chars] - to identify the file
- **Zip password**: [their password] - to decrypt
- **Valid for**: {settings.expiry_hours} hours
- **What's included**: [summary of settings, plugins, projects]

---

## Download (Target Machine)

### Step 1: Get Credentials

Ask user for:
1. **Verification code** (6 alphanumeric)
2. **Zip password**

### Step 2: Download and Extract

```bash
# Download
curl -o claude-backup.zip {settings.base_url}/download/[CODE]

# Extract
unzip -P "PASSWORD" claude-backup.zip -d ~/claude-restore/
```

### Step 3: Follow INSTALL.md

Read `INSTALL.md` and execute:

1. **Restore global settings:**
```bash
cp -r ~/claude-restore/dot-claude/* ~/.claude/
```

2. **Install plugin dependencies:**
```bash
for plugin in ~/.claude/plugins/*/; do
  if [ -f "$plugin/package.json" ]; then
    echo "Installing deps for $plugin"
    (cd "$plugin" && npm install)
  fi
done
```

3. **Restore project files:**
Copy each project's CLAUDE.md or .claude/ to its location.

4. **Verify MCP configs:**
Check if MCP servers referenced in .mcp.json are available on this machine.

### Step 4: Restart

Tell user to restart Claude Code.

---

## Error Handling

**File too large:**
- Global ~/.claude/ with text files should be <10MB typically
- If large, check for: models, cache, node_modules
- Exclude reinstallable items

**Missing items on restore:**
- Plugin node_modules: run `npm install`
- MCP servers: may need to install separately
- Project paths differ: adjust CLAUDE.md locations

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
