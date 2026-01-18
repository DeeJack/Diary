# Plan: Encrypted Archive Save System

## Summary

Convert from single encrypted JSON blob to an encrypted TAR archive that stores pages and binary assets separately. This avoids re-encoding unchanged assets on every save.

## New File Format

```
DIARYARC02 (magic, 10 bytes)
<2 bytes version>
<32 bytes salt>
[encrypted chunks containing ZSTD-compressed TAR]
    ├── manifest.msgpack      (notebook metadata + asset index)
    ├── pages/
    │   └── {page_uuid}.msgpack
    └── assets/
        └── {uuid}.bin        (raw image/video/audio bytes)
```

## Key Design Decisions

- **TAR format**: Simple, streams well with existing chunked encryption
- **UUID references**: Elements reference assets by UUID (not inline base64)
- **Avoid re-encoding**: Cache previous asset bytes; reuse unchanged assets when building new archive
- **Backward compatible**: Detect format by magic bytes, auto-migrate legacy files

## Implementation Phases

### Phase 1: Core Archive System
1. Create `src/diary/models/asset.py` - Asset class with `asset_id`, `asset_type`, `mime_type`, `data`, `checksum`
2. Create `src/diary/models/manifest.py` - ArchiveManifest with page list + asset index
3. Create `src/diary/models/dao/archive_dao.py` - Archive read/write logic
4. Create `src/diary/models/dao/asset_cache.py` - Asset caching for incremental saves

### Phase 2: Element Updates
5. Modify `src/diary/models/elements/image.py` - Add `asset_id` field
6. Modify `src/diary/models/elements/voice_memo.py` - Add `asset_id` field
7. Add new serialization keys to `src/diary/config.py`

### Phase 3: Migration & Integration
8. Create `src/diary/models/dao/migration.py` - Legacy → archive migration
9. Modify `src/diary/models/dao/notebook_dao.py` - Format detection + delegation

### Phase 4: Video Support (Later)
10. Create `src/diary/models/elements/video.py` - Video element
11. Update `src/diary/models/page.py` - Handle Video in `from_dict()`

### Phase 5: Testing (Later)
12. Create `tests/test_archive_dao.py`
13. Create `tests/test_migration.py`

## Files to Create

| File | Purpose |
|------|---------|
| `src/diary/models/asset.py` | Asset + AssetType classes |
| `src/diary/models/manifest.py` | ArchiveManifest class |
| `src/diary/models/dao/archive_dao.py` | Archive read/write |
| `src/diary/models/dao/migration.py` | Legacy → archive migration |
| `src/diary/models/dao/asset_cache.py` | Asset caching |

## Files to Modify

| File | Changes |
|------|---------|
| `src/diary/models/elements/image.py` | Add `asset_id` field |
| `src/diary/models/elements/voice_memo.py` | Add `asset_id` field |
| `src/diary/models/dao/notebook_dao.py` | Format detection + delegation |
| `src/diary/config.py` | New serialization keys |

## Incremental Save Strategy

```python
def _build_archive(manifest, pages, assets, previous_asset_bytes=None):
    with tarfile.open(mode='w') as tar:
        # Always re-serialize manifest and pages (small)
        tar.add("manifest.msgpack", msgpack.packb(manifest.to_dict()))
        for page in pages:
            tar.add(f"pages/{page.page_id}.msgpack", msgpack.packb(page.to_dict()))

        # Reuse unchanged asset bytes
        for asset_id, asset in assets.items():
            if previous_asset_bytes and asset_id in previous_asset_bytes:
                data = previous_asset_bytes[asset_id]  # Reuse!
            else:
                data = asset.data  # New asset
            tar.add(f"assets/{asset_id}.bin", data)
```

## Verification

1. **Unit tests**: Create `tests/test_archive_dao.py`
   - Round-trip: save → load → compare
   - Incremental: verify unchanged assets aren't re-encoded
   - Migration: legacy file converts correctly

2. **Manual testing**:
   - Create notebook with images via UI
   - Save, close, reopen - verify images intact
   - Add new image, save - verify quick save
   - Check file size is reasonable (no base64 bloat)

## Risk Mitigation

- **Data loss**: Always backup before migration; atomic writes (temp file → rename)
- **Memory**: Stream large assets where possible; lazy-load on demand
- **Compatibility**: Keep legacy load code; format detection by magic bytes
