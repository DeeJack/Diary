# Diary - Privacy-Focused Handwriting Journal

A secure, pen-optimized digital journal application designed for Windows Surface and other tablet devices with stylus support. Built with privacy as the foundation, featuring military-grade XChaCha20-Poly1305 encryption.

## Overview

Diary is a handwriting-first journal application that prioritizes natural pen input while maintaining the highest standards of privacy and security. Every notebook is encrypted at rest, ensuring your personal thoughts remain private.

## Key Features

### Privacy & Security

- **XChaCha20-Poly1305 Encryption**: Military-grade authenticated encryption for all saved notebooks
- **Argon2ID Key Derivation**: Password-based key derivation with configurable parameters (2 iterations, 64MB memory, 4 threads)
- **Zero-Knowledge Architecture**: Passwords never leave your device; encryption keys exist only in memory
- **Secure Memory Management**: Cryptographic material is zeroed from memory after use via `SecureBuffer` class
- **Local-First Storage**: All data stored locally in `~/Documents/diary/` - no cloud sync, no telemetry

### Pen-Optimized Writing Experience

- **Pressure-Sensitive Ink**: Full Surface Pen support with pressure sensitivity for natural handwriting
- **Smooth Rendering**: Hardware-accelerated rendering using Qt's QGraphicsScene for lag-free writing
- **Multiple Input Modes**: Optimized tool configurations for TABLET, MOUSE, and TOUCH inputs
- **Intelligent Palm Rejection**: Write naturally without worrying about accidental touches

### Rich Content Support

- **Handwritten Strokes**: Pressure-sensitive ink with customizable colors and widths
- **Text Elements**: Positioned, resizable text blocks for typed notes
- **Images**: Insert and resize images (base64 encoded, encrypted with notebook)
- **Voice Memos**: Record audio notes with optional transcription support
- **Video Elements**: Insert video with thumbnails and playback controls

### Organization & Productivity

- **Page-Based Structure**: Organize entries into pages within notebooks
- **Streak Tracking**: Built-in streak calculation to maintain daily journaling habits
- **Auto-Save**: Configurable auto-save (default: 120 seconds) with background workers
- **Backup System**: Automatic backups in daily, weekly, and monthly rotations

## System Requirements

- **Operating System**: Windows 10/11 (optimized for Surface devices), Linux
- **Python**: 3.10 or higher
- **Display**: 800x1100px minimum per page (configurable)
- **Input**: Stylus/pen highly recommended; mouse and touch also supported

## Installation

### Using pip

```bash
pip install .
```

### Using Poetry

```bash
poetry install
```

## Usage

### Running the Application

```bash
python -m diary.main
```

### Building Executable

```bash
poetry run build-executable
```

This creates a standalone executable at `dist/diary`.

### First Launch

1. Launch the application
2. Create a new notebook with a secure password
3. Choose your input device (Tablet, Mouse, or Touch)
4. Select the Pen tool and start writing

### Tool Overview

- **Pen**: Handwriting tool with pressure sensitivity
- **Eraser**: Remove strokes or elements
- **Text**: Create positioned text blocks
- **Drag**: Pan and navigate the page
- **Image**: Insert images from files
- **Audio**: Record voice memos
- **Selection**: Select and manipulate elements

## File Format

### Encrypted Notebook Structure

```
DIARY001 (magic bytes)
├── Salt (32 bytes)
├── Nonce (24 bytes for XChaCha20)
├── Encrypted data (chunk-based, 64KB chunks)
└── Authentication tag (Poly1305)
```

### Data Model

```
Notebook
  ├── Metadata (name, creation date, streak info)
  └── Pages[]
      └── PageElements[]
          ├── Stroke (handwritten ink with pressure points)
          ├── Text (positioned text with font info)
          ├── Image (base64 encoded with positioning)
          ├── VoiceMemo (audio data with transcript)
          └── Video (video data with thumbnail)
```

### Serialization

- **Format**: MessagePack (compact binary serialization)
- **Compression**: ZSTD compression before encryption
- **Encoding**: Enum-based keys defined in `config.py` for minimal size

## Configuration

All settings are defined in `src/diary/config.py`:

- **Page Dimensions**: 800x1100px (default)
- **Line Spacing**: 35px (for ruled lines)
- **Data Paths**:
  - Notebooks: `~/Documents/diary/`
  - Config/Backups: `~/.diary/`
- **Auto-Save**: 120 seconds (default)

## Development

### Running Tests

```bash
pytest
```

### Type Checking

```bash
basedpyright
mypy
```

### Linting

```bash
pylint src/diary
```

## Architecture

See [ARCHITECTURE.md](./ARCHITECTURE.md) for detailed technical documentation.

## Security

See [SECURITY.md](./SECURITY.md) for detailed security design and threat model.

## License

[Include your license here]

## Contributing

[Include contribution guidelines here]
