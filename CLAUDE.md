# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A privacy-focused handwriting diary application with Surface Pen support. Uses XChaCha20-Poly1305 encryption with Argon2ID key derivation. Built with Python and PyQt6.

## Commands

```bash
# Install dependencies
pip install .
# Or with poetry
poetry install

# Run the application
python -m diary.main

# Build executable (creates dist/diary)
poetry run build-executable

# Run tests
pytest

# Type checking
basedpyright
mypy

# Linting
pylint src/diary
```

## Architecture

### Data Model Hierarchy
```
Notebook → Page → PageElement (abstract)
                  ├── Stroke (handwritten ink with pressure points)
                  ├── Text (positioned text)
                  ├── Image (base64 encoded)
                  └── VoiceMemo (audio with transcript)
```

### Key Components

**Models** (`src/diary/models/`):
- `notebook.py` - Notebook class with streak calculation logic
- `page.py` - Page with element management
- `dao/notebook_dao.py` - Persistence with msgpack + ZSTD compression + encryption

**Graphics** (`src/diary/ui/graphics_items/`):
- Uses QGraphicsItem/QGraphicsScene pattern (not canvas redraw)
- Factory pattern in `graphics_item_factory.py` creates appropriate item per element type
- `page_graphics_scene.py` manages the scene

**Threading**:
- `LoadWorker` / `SaveWorker` handle async I/O with pyqtSignals
- `SaveManager` coordinates auto-save (default 120s timer)

**Encryption** (`src/diary/utils/encryption.py`):
- Argon2ID (2 iterations, 64MB, 4 threads) → 32-byte key
- XChaCha20-Poly1305 for file encryption
- `SecureBuffer` class zeroes memory on deletion

**Input System** (`src/diary/ui/input.py`):
- Separate tool configs per input type (TABLET, MOUSE, TOUCH)
- Tools: PEN, ERASER, TEXT, DRAG, IMAGE, AUDIO, SELECTION

### Serialization

Uses enum-based keys in `config.py` for compact msgpack representation. Key mappings defined in `SERIALIZATION_KEYS`. Binary data (images) stored as base64.

### File Format

Encrypted files: magic bytes + salt + nonce + encrypted data + auth tag. Chunk-based encryption (64KB) for large files.

## Configuration

All settings in `src/diary/config.py`:
- Page dimensions: 800x1100px, 35px line spacing
- Data paths: `~/Documents/diary/` (notebooks), `~/.diary/` (config/backups)
- Backup dirs: daily, weekly, monthly subdirectories
