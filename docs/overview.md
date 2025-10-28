# Diary Application - System Overview

## What is this Application?

This is a PyQt6-based digital diary application designed for users who value privacy and security. The application provides a notebook-style interface where users can create pages with various types of content including handwritten notes, drawings, text, images, and voice memos.

## Key Features

- **Multi-input Support**: Mouse, touch, and pen inputs for natural writing/drawing
- **Lazy Loading**: Pages are rendered in separate processes for optimal performance
- **High-Resolution Rendering**: Elements are drawn into QPixmaps with configurable scaling
- **Security**: Built-in encryption and backup systems
- **Flexible Content**: Support for strokes, text, images, and voice memos
- **Streak Tracking**: Daily usage tracking system

## Architecture Overview

The application follows a clean architecture pattern with clear separation between models, UI, and utilities:

```
diary/
├── src/diary/
│   ├── models/          # Data models (UI-independent)
│   ├── ui/              # PyQt6 UI components
│   ├── utils/           # Utilities (backup, encryption)
│   ├── config.py        # Application configuration
│   ├── logger.py        # Logging setup
│   └── main.py          # Application entry point
├── data/                # User data storage
├── backup/              # Backup files
└── docs/                # Documentation
```

## Core Components

### Models (Business Logic)
- **Notebook**: Container for all pages and metadata
- **Page**: Individual diary page with elements and metadata
- **PageElement**: Base class for all content types (strokes, text, images, voice memos)
- **Point**: Represents coordinates with pressure and timestamp data

### UI Layer
- **MainWindow**: Application window container
- **NotebookWidget**: Main notebook view with lazy loading
- **PageWidget**: Individual page rendering and interaction
- **Various Widgets**: Toolbars, selectors, navigation components

### Process Architecture
- **Main Process**: UI thread and user interaction
- **Page Process**: Separate processes for page rendering (via `page_process.py`)
- **Save Worker**: Background thread for data persistence

## Performance Optimizations

1. **Lazy Loading**: Pages are only loaded when needed
2. **Process Separation**: Page rendering happens in separate processes
3. **QPixmap Caching**: Rendered content is cached as high-resolution pixmaps
4. **Configurable Rendering Scale**: Adjustable quality vs performance trade-offs

## Data Persistence

- **Format**: Custom serialization using msgpack and pickle
- **Encryption**: Optional encryption using PyNaCl and Argon2
- **Compression**: Zstandard compression for efficient storage
- **Backups**: Automated tiered backup system (daily, weekly, monthly)

## Security Features

- **Encryption**: Strong encryption for sensitive data
- **Backup Management**: Secure backup rotation with configurable retention
- **Privacy Focus**: Local storage with no external dependencies

## Development Notes

- **Python 3.12+**: Modern Python features and type hints
- **PyQt6**: Latest Qt framework for cross-platform GUI
- **Poetry**: Dependency management and packaging
- **Type Safety**: Comprehensive type hints and mypy checking
- **Testing**: Pytest framework for unit testing

This overview provides the foundation for understanding the diary application's architecture and design decisions.