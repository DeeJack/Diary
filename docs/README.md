# Diary Application Documentation

This directory contains comprehensive documentation for the diary PyQt6 application, designed to help developers, contributors, and future LLM agents understand the system architecture and implementation details.

## Quick Start

For a quick overview of the system, start with:
1. **[Overview](overview.md)** - High-level system architecture and key features
2. **[File Structure](files.md)** - Comprehensive guide to all files and their roles

## Documentation Index

### Architecture & Design
- **[System Overview](overview.md)** - Application architecture, core features, and design decisions
- **[File Structure](files.md)** - Complete file organization and module responsibilities
- **[Rendering System](rendering-system.md)** - QPixmap-based high-performance rendering architecture
- **[Lazy Loading](lazy-loading.md)** - Multi-process lazy loading system for large notebooks
- **[Input System](input-system.md)** - Multi-input support (mouse, touch, pen) with gesture recognition

### Core Concepts

#### Data Models
- **Notebook**: Container for diary pages with metadata and streak tracking
- **Page**: Individual diary page with elements and rendering cache
- **PageElement**: Base class for content (strokes, text, images, voice memos)
- **Point**: Coordinate data with pressure and timestamp information

#### UI Architecture
- **NotebookWidget**: Main notebook view with lazy loading and input handling
- **PageWidget**: Individual page rendering and user interaction
- **Adapters**: Bridge between UI and model layers for different content types

#### Performance Systems
- **Process Separation**: Page rendering in separate processes via `page_process.py`
- **QPixmap Caching**: High-resolution rendered page cache system
- **Background Workers**: Asynchronous saving and loading operations

## Key Features

### Multi-Input Support
- **Mouse**: Standard navigation and drawing
- **Touch**: Gesture support with palm rejection
- **Pen/Stylus**: Pressure-sensitive drawing with hover detection

### Performance Optimizations
- **Lazy Loading**: Pages loaded on-demand with intelligent prefetching
- **High-Resolution Rendering**: Configurable rendering scale for quality vs performance
- **Process Architecture**: Separate processes prevent UI blocking during rendering
- **Memory Management**: Automatic cache cleanup and memory pressure handling

### Security & Privacy
- **Encryption**: Strong encryption using PyNaCl and Argon2
- **Backup System**: Tiered backup rotation (daily, weekly, monthly)
- **Local Storage**: No external dependencies or cloud requirements

## Development Information

### Technology Stack
- **Python 3.12+**: Modern Python with comprehensive type hints
- **PyQt6**: Latest Qt framework for cross-platform GUI
- **Poetry**: Dependency management and packaging
- **Testing**: Pytest framework with comprehensive test coverage
- **Code Quality**: Pylint and mypy for static analysis

### Dependencies
- **PyQt6**: GUI framework and rendering
- **PyNaCl**: Encryption and security
- **Argon2-cffi**: Password hashing
- **msgpack**: Efficient serialization
- **zstd**: Compression for storage optimization

### Project Structure
```
diary/
├── src/diary/           # Main application code
│   ├── models/          # Data models (UI-independent)
│   ├── ui/              # PyQt6 UI components
│   │   ├── widgets/     # UI widgets and components
│   │   └── adapters/    # UI-model bridge adapters
│   ├── utils/           # Utilities (backup, encryption)
│   ├── config.py        # Application configuration
│   ├── logger.py        # Logging configuration
│   └── main.py          # Application entry point
├── data/                # User data storage
├── backup/              # Automated backup storage
├── tests/               # Test suite
└── docs/                # This documentation
```

## For LLM Agents

This documentation is specifically designed to help AI assistants understand the codebase quickly without needing to explore all files. Key points:

- **Start with [overview.md](overview.md)** for system understanding
- **Use [files.md](files.md)** to locate specific functionality
- **Refer to architecture docs** for understanding complex systems (lazy loading, rendering, input)
- **All major patterns and optimizations are documented** to avoid reinventing solutions

### Common Tasks
- **Adding new page element types**: See adapters pattern in `ui/adapters/`
- **Performance optimization**: Review lazy loading and rendering system docs
- **Input handling**: Check input system documentation for multi-device support
- **Data persistence**: Examine models and DAO patterns

## Contributing

When contributing to this project:
1. Maintain the clean architecture separation (models/ui/utils)
2. Follow the established patterns for new features
3. Update documentation for significant changes
4. Ensure all new code includes comprehensive type hints
5. Test with various input devices and large notebooks

## License

This project is licensed under the Apache 2.0 License - see the LICENSE file for details.