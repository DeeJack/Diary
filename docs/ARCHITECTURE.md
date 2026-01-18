# Architecture Documentation

## Overview

Diary is built using Python and PyQt6, following a model-view architecture with a focus on security, performance, and natural pen input.

## Technology Stack

- **Language**: Python 3.10+
- **GUI Framework**: PyQt6
- **Graphics**: QGraphicsScene/QGraphicsItem pattern
- **Serialization**: MessagePack
- **Compression**: ZSTD
- **Encryption**: XChaCha20-Poly1305 with Argon2ID KDF
- **Testing**: pytest
- **Type Checking**: basedpyright, mypy

## Project Structure

```
src/diary/
├── main.py                    # Application entry point
├── config.py                  # Global configuration and constants
├── models/                    # Data models
│   ├── notebook.py           # Notebook with streak calculation
│   ├── page.py               # Page with element management
│   ├── elements/             # Page element types
│   │   ├── stroke.py         # Handwritten ink strokes
│   │   ├── text.py           # Text elements
│   │   ├── image.py          # Image elements
│   │   └── voice_memo.py     # Audio recording elements
│   └── dao/                  # Data access layer
│       └── notebook_dao.py   # Persistence with encryption
├── ui/                       # User interface
│   ├── input.py              # Input handling and tool system
│   ├── graphics_items/       # QGraphicsItem implementations
│   │   ├── graphics_item_factory.py  # Factory pattern
│   │   ├── page_graphics_scene.py    # Scene management
│   │   ├── stroke_item.py            # Stroke rendering
│   │   ├── text_item.py              # Text rendering
│   │   └── image_item.py             # Image rendering
│   └── workers/              # Background threads
│       ├── load_worker.py    # Async loading
│       └── save_worker.py    # Async saving
└── utils/                    # Utilities
    └── encryption.py         # Encryption/decryption logic
```

## Core Architecture Patterns

### 1. Data Model Hierarchy

```
Notebook (root entity)
  ├── Properties: name, created_at, pages, metadata
  ├── Methods: streak calculation, page management
  └── Pages[] (ordered collection)
      ├── Properties: page_id, elements, background
      └── PageElements[] (polymorphic collection)
          ├── Stroke (handwriting)
          │   └── points: [(x, y, pressure), ...]
          ├── Text (positioned text)
          │   └── position, content, font, size
          ├── Image (embedded images)
          │   └── position, data (base64), dimensions
          ├── VoiceMemo (audio recordings)
          │   └── audio_data, transcript, timestamp
          └── Video (video clips)
              └── video_data, thumbnail, position
```

**Key Design Decisions**:
- **Polymorphic Elements**: Abstract `PageElement` base class enables extensibility
- **Immutable IDs**: UUIDs for pages and elements ensure reference stability
- **Flat Structure**: Pages are a flat list (not hierarchical) for simplicity

### 2. Graphics Rendering (QGraphicsScene Pattern)

Instead of canvas redraw (paint entire scene on each frame), uses Qt's scene graph:

```
QGraphicsView (viewport)
  └── PageGraphicsScene (manages items)
      └── QGraphicsItems (cached, hardware-accelerated)
          ├── StrokeItem (renders one stroke)
          ├── TextItem (renders one text element)
          └── ImageItem (renders one image)
```

**Benefits**:
- **Performance**: Only changed items redraw; OS handles caching
- **Hardware Acceleration**: Qt uses GPU when available
- **Event Handling**: Each item handles its own mouse/pen events
- **Layering**: Z-order management built-in

**Factory Pattern**:
`GraphicsItemFactory.create_item(element)` returns appropriate QGraphicsItem subclass based on element type. This centralizes item creation and ensures consistent behavior.

### 3. Input System Architecture

Separate tool configurations per input device type:

```python
InputConfig
  ├── TABLET (Surface Pen, Wacom, etc.)
  │   ├── PEN tool → handwriting with pressure
  │   ├── ERASER tool → stroke removal
  │   └── ...
  ├── MOUSE (desktop users)
  │   ├── PEN tool → handwriting without pressure
  │   └── ...
  └── TOUCH (finger input)
      ├── DRAG tool (default) → pan/scroll
      └── ...
```

**Tool Types**:
- `PEN`: Create stroke elements
- `ERASER`: Remove strokes/elements
- `TEXT`: Create text elements
- `DRAG`: Pan the viewport
- `IMAGE`: Insert image elements
- `AUDIO`: Record voice memos
- `SELECTION`: Select/move/resize elements

**Why Separate Configs?**
- Tablet users expect pen-to-write, finger-to-scroll
- Mouse users need click-to-write
- Touch users need tap-to-type, drag-to-scroll

### 4. Threading & Async I/O

**Problem**: File I/O (encryption, compression, serialization) blocks UI

**Solution**: Worker threads with Qt signals

```
SaveManager (orchestrator)
  ├── Auto-save timer (120s default)
  └── SaveWorker (QThread)
      ├── serialize_notebook()
      ├── compress_with_zstd()
      ├── encrypt_with_xchacha20()
      └── write_to_file()
      └── emit: save_complete signal

LoadWorker (QThread)
  ├── read_from_file()
  ├── decrypt_with_xchacha20()
  ├── decompress_with_zstd()
  └── deserialize_notebook()
  └── emit: load_complete signal
```

**Signal Flow**:
1. User changes notebook → mark dirty
2. Timer fires → SaveManager.save()
3. SaveWorker runs in background thread
4. save_complete signal → UI shows "Saved" indicator

### 5. Encryption Pipeline

```
Raw Notebook Data (Python objects)
  ↓ serialize
MessagePack Binary (compact representation)
  ↓ compress
ZSTD Compressed Data (reduced size)
  ↓ derive key
Argon2ID(password, salt) → 32-byte key
  ↓ encrypt (chunked)
XChaCha20-Poly1305 (64KB chunks)
  ↓ format
File: [magic][salt][nonce][encrypted_chunks][auth_tag]
```

**Chunk-Based Encryption**:
- Large notebooks split into 64KB chunks
- Each chunk encrypted separately (streaming)
- Prevents memory exhaustion on large files
- Auth tag covers entire file (tamper detection)

**Key Derivation Parameters**:
```python
Argon2ID:
  time_cost=2      # iterations
  memory_cost=64MB # RAM usage
  parallelism=4    # threads
```

**Security Features**:
- Random salt per file (32 bytes)
- Random nonce per encryption (24 bytes for XChaCha20)
- Authenticated encryption (Poly1305 prevents tampering)
- SecureBuffer class zeros memory on deletion

### 6. Serialization Strategy

**Enum-Based Keys** (for compact msgpack):

```python
# Instead of:
{"notebook_name": "My Diary", "created_at": 1234567890}

# Use:
{1: "My Diary", 2: 1234567890}  # 1=name, 2=created_at
```

**Key Mapping** (in `config.py`):
```python
SERIALIZATION_KEYS = {
    "notebook_name": 1,
    "created_at": 2,
    "pages": 3,
    "page_id": 10,
    "elements": 11,
    "element_type": 20,
    "stroke_points": 21,
    # ... etc
}
```

**Benefits**:
- Smaller file size (integer keys vs string keys)
- Consistent serialization across versions
- Easy to add new fields (just assign next number)

### 7. Persistence Layer (DAO Pattern)

**NotebookDAO** (Data Access Object):
```python
class NotebookDAO:
    def save(notebook: Notebook, password: str) -> None:
        """Serialize → Compress → Encrypt → Write"""

    def load(file_path: str, password: str) -> Notebook:
        """Read → Decrypt → Decompress → Deserialize"""
```

**Separation of Concerns**:
- `Notebook` model knows nothing about files/encryption
- `NotebookDAO` knows nothing about Qt/UI
- `SaveWorker` bridges the two with threading

## Data Flow Diagrams

### Save Flow

```
User writes → Page.add_element(stroke)
              ↓
          Notebook.mark_dirty()
              ↓
          Timer expires (120s)
              ↓
          SaveManager.save()
              ↓
          Create SaveWorker thread
              ↓
          [Background Thread]
          Notebook.to_dict() → msgpack.packb() → zstd.compress()
              ↓
          encryption.derive_key(password, salt)
              ↓
          encryption.encrypt_file(data, key) [chunked]
              ↓
          atomic_write(temp_file → rename)
              ↓
          emit save_complete signal
              ↓
          [Main Thread]
          UI shows "Saved at 14:32"
```

### Load Flow

```
User selects file → show password dialog
                    ↓
                Password entered
                    ↓
                Create LoadWorker thread
                    ↓
                [Background Thread]
                read_file()
                    ↓
                encryption.derive_key(password, salt)
                    ↓
                encryption.decrypt_file(data, key)
                    ↓
                zstd.decompress()
                    ↓
                msgpack.unpackb()
                    ↓
                Notebook.from_dict()
                    ↓
                emit load_complete signal
                    ↓
                [Main Thread]
                GraphicsItemFactory.create_items(notebook.pages)
                    ↓
                Display notebook in UI
```

### Stroke Rendering Flow

```
User touches pen to screen
    ↓
Qt TabletEvent (with pressure)
    ↓
InputHandler.handle_tablet_event()
    ↓
If current_tool == PEN:
    Create new Stroke element
    Add point (x, y, pressure)
    ↓
Create StrokeItem (QGraphicsItem)
    ↓
Add to PageGraphicsScene
    ↓
StrokeItem.paint() called by Qt
    ↓
QPainter draws path with pressure-varying width
    ↓
OS composites to screen (hardware accelerated)
```

## Performance Considerations

### 1. Lazy Loading
- Graphics items created on-demand (when page viewed)
- Images decoded only when visible
- Audio loaded only when playing

### 2. Caching
- QGraphicsItem caching enabled for static elements
- Stroke paths pre-computed and cached
- Compressed data cached in memory (avoid re-compression)

### 3. Incremental Updates
- Only changed elements re-serialized on save
- Unchanged pages reuse previous serialization
- Asset deduplication (future: archive format)

### 4. Memory Management
- Old page graphics items destroyed when switching pages
- Large images compressed before encryption
- Secure buffers zeroed after use

## Future Architecture Plans

### Archive-Based Save Format

See `docs/archive-save-system-plan.md` for detailed plan. Summary:

```
Current: Single encrypted blob with all data
Future:  Encrypted TAR archive with separate assets

Benefits:
- Avoid re-encoding unchanged images/videos
- Faster incremental saves
- Better memory efficiency
```

### Plugin System

Potential architecture for extensibility:
- Plugin interface for new element types
- Graphics item plugins for rendering
- Tool plugins for custom input handling

## Testing Strategy

### Unit Tests
- Model serialization/deserialization
- Encryption/decryption round-trips
- Stroke point calculations
- Streak logic

### Integration Tests
- Full save/load cycle
- Multi-threaded save operations
- Password changes
- Migration from old formats

### UI Tests
- Pen input simulation
- Tool switching
- Element manipulation

## Build & Deployment

### Executable Creation
- PyInstaller bundles Python + dependencies
- Single-file executable for Windows
- AppImage for Linux (future)

### Configuration
- Settings stored in `~/.diary/config.json`
- First-run setup wizard
- Portable mode (all data in app directory)

## Security Architecture

See [SECURITY.md](./SECURITY.md) for detailed security design.
