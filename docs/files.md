# File Structure Documentation

This document provides a comprehensive overview of all files in the diary application and their roles.

## Root Directory

- **`pyproject.toml`** - Poetry project configuration with dependencies and build settings
- **`poetry.lock`** - Locked dependency versions for reproducible builds
- **`README.md`** - Basic project information
- **`.gitignore`** - Git ignore patterns
- **`.pylintrc`** - Pylint configuration for code quality
- **`LICENSE`** - Apache 2.0 license file
- **`create_large_notebook.py`** - Utility script for creating test notebooks with many pages

## Source Code (`src/diary/`)

### Core Application Files

- **`main.py`** - Application entry point, sets up PyQt6 app and main window
- **`config.py`** - Application configuration and settings management
- **`logger.py`** - Logging configuration and setup
- **`__init__.py`** - Package initialization

### Models (`src/diary/models/`)

Contains UI-independent data models that represent the core business logic:

- **`notebook.py`** - `Notebook` class that contains pages and metadata, handles streak calculations
- **`page.py`** - `Page` class representing individual diary pages with elements and metadata
- **`page_element.py`** - Base `PageElement` class for all content types (strokes, text, images, voice memos)
- **`point.py`** - `Point` class for coordinate data with pressure and timestamp information

#### Data Access Objects (`src/diary/models/dao/`)

- Handles data persistence, serialization, and file I/O operations

#### Elements (`src/diary/models/elements/`)

- Specific implementations of page elements (strokes, text, images, voice memos)

### UI Layer (`src/diary/ui/`)

#### Main UI Files

- **`main_window.py`** - `MainWindow` class, the main application window container

#### Widgets (`src/diary/ui/widgets/`)

Core UI components for the diary interface:

- **`notebook_widget.py`** - `NotebookWidget` class, main notebook view with lazy loading, multiprocessing, and input handling
- **`page_widget.py`** - `PageWidget` class for individual page rendering and user interaction
- **`page_process.py`** - Contains `render_page_in_process()` function for rendering pages in separate processes
- **`save_worker.py`** - `SaveWorker` class for background data persistence using QThread
- **`selection_manager.py`** - Handles element selection and manipulation
- **`tool_selector.py`** - Tool selection UI and management
- **`color_palette.py`** - Color selection widget
- **`bottom_toolbar.py`** - Bottom toolbar with tools and options
- **`days_sidebar.py`** - Sidebar showing days/pages navigation
- **`page_navigator.py`** - Page navigation controls

#### Adapters (`src/diary/ui/adapters/`)

Bridge between UI and model layer for different content types:

- **`stroke_adapter.py`** - Handles stroke/drawing rendering and interaction
- **`text_adapter.py`** - Text element rendering and editing
- **`image_adapter.py`** - Image element handling and display
- **`voice_memo_adapter.py`** - Voice memo recording and playback

### Utilities (`src/diary/utils/`)

Utility modules for cross-cutting concerns:

- **`backup.py`** - `BackupManager` class for automated tiered backup system (daily, weekly, monthly)
- **`encryption.py`** - Encryption and decryption utilities using PyNaCl and Argon2

## Data Directories

- **`data/`** - User data storage directory (notebooks, settings)
- **`backup/`** - Backup files organized by time periods
- **`tests/`** - Test files and test data

## Documentation (`docs/`)

- **`overview.md`** - High-level system architecture and design overview
- **`files.md`** - This file, comprehensive file structure documentation

## Key Architectural Patterns

### Lazy Loading System
- `NotebookWidget` manages lazy loading of pages
- `page_process.py` handles rendering in separate processes
- Pages are loaded on-demand to optimize memory usage

### Multi-Process Architecture
- Main process handles UI and user interaction
- Separate processes for page rendering (via multiprocessing)
- Background threads for saving operations

### Performance Optimizations
- `QPixmap` caching for rendered content
- High-resolution rendering with configurable scaling
- Process separation to prevent UI blocking

### Data Flow
1. User interacts with `NotebookWidget`
2. `PageWidget` handles drawing and input
3. Changes are applied to model objects
4. `SaveWorker` persists data in background
5. `BackupManager` creates automated backups

This structure provides clear separation of concerns while enabling high-performance, responsive user interaction.