# Input System Documentation

## Overview

The diary application features a comprehensive multi-input system that supports mouse, touch, and pen inputs for natural writing and drawing experiences. The system is designed to handle various input devices seamlessly while providing appropriate feedback and interaction modes for each input type.

## Supported Input Types

### Mouse Input
- **Primary Use**: Navigation, UI interaction, basic drawing
- **Precision**: Moderate precision suitable for general use
- **Pressure**: No pressure sensitivity (constant line width)
- **Hover**: Hover events for UI feedback and tool previews

### Touch Input
- **Primary Use**: Finger-based interaction, gestures, casual drawing
- **Precision**: Lower precision due to finger size
- **Pressure**: Limited or no pressure sensitivity (device dependent)
- **Multi-touch**: Support for pinch-to-zoom and other gestures
- **Palm Rejection**: Intelligent filtering of accidental palm touches

### Pen Input (Graphics Tablet/Stylus)
- **Primary Use**: Precise drawing, handwriting, detailed artwork
- **Precision**: High precision for detailed work
- **Pressure**: Full pressure sensitivity for variable line width
- **Tilt Support**: Pen tilt detection for brush-like effects (if supported)
- **Hover**: Hover detection for cursor preview without touching

## Architecture

### Input Event Handling

The input system is primarily handled in the `NotebookWidget` and `PageWidget` classes:

```python
# Core input event handlers
def mousePressEvent(self, event: QMouseEvent)
def mouseMoveEvent(self, event: QMouseEvent)
def mouseReleaseEvent(self, event: QMouseEvent)

def tabletEvent(self, event: QTabletEvent)
def touchEvent(self, event: QTouchEvent)

def wheelEvent(self, event: QWheelEvent)  # Zoom and scroll
```

### Event Processing Pipeline

1. **Raw Input Capture**: Qt captures system input events
2. **Event Classification**: Determine input type (mouse, touch, pen)
3. **Coordinate Transformation**: Convert to page coordinates
4. **Tool Application**: Apply current tool behavior
5. **Pressure Processing**: Handle pressure data for supported devices
6. **Stroke Generation**: Create stroke elements from input data
7. **Real-time Rendering**: Update display immediately
8. **Data Persistence**: Queue changes for background saving

## Input Processing Details

### Coordinate System

The application uses multiple coordinate systems that require transformation:

- **Screen Coordinates**: Raw pixel coordinates from input device
- **Widget Coordinates**: Coordinates relative to the widget
- **Page Coordinates**: Coordinates relative to the diary page
- **Logical Coordinates**: High-resolution coordinates for rendering

```python
def transform_coordinates(self, screen_pos: QPoint) -> QPointF:
    # Transform from screen to page coordinates
    widget_pos = self.mapFromGlobal(screen_pos)
    page_pos = self.transform_to_page_coordinates(widget_pos)
    return page_pos
```

### Pressure Handling

Pressure sensitivity is crucial for natural drawing experiences:

```python
class Point:
    def __init__(self, x: float, y: float, pressure: float = 1.0, timestamp: float = 0.0):
        self.x = x
        self.y = y
        self.pressure = pressure  # Range: 0.0 - 1.0
        self.timestamp = timestamp
```

### Pressure Sources:
- **Pen/Stylus**: Full pressure range from graphics tablets
- **Touch**: Limited pressure on supported touchscreens
- **Mouse**: Constant pressure (1.0)

## Input Device Detection

### Automatic Device Recognition

The system automatically detects and adapts to different input devices:

```python
def classify_input_device(self, event) -> InputDeviceType:
    if isinstance(event, QTabletEvent):
        return InputDeviceType.PEN
    elif isinstance(event, QTouchEvent):
        return InputDeviceType.TOUCH
    elif isinstance(event, QMouseEvent):
        return InputDeviceType.MOUSE
    return InputDeviceType.UNKNOWN
```

### Device-Specific Behaviors

- **Pen Mode**: High precision, pressure sensitivity, hover preview
- **Touch Mode**: Palm rejection, gesture support, larger hit areas
- **Mouse Mode**: Precise clicking, scroll wheel support, hover effects

## Gesture Support

### Supported Gestures

1. **Pinch-to-Zoom**: Two-finger pinch for zoom in/out
2. **Pan Gesture**: Two-finger drag for page navigation
3. **Rotation**: Two-finger rotation (if enabled)
4. **Swipe**: Page navigation gestures

### Gesture Implementation

```python
def gestureEvent(self, event: QGestureEvent) -> bool:
    pinch = event.gesture(Qt.GestureType.PinchGesture)
    if pinch:
        self.handle_pinch_gesture(pinch)
        return True
    return False

def handle_pinch_gesture(self, gesture: QPinchGesture):
    if gesture.state() == Qt.GestureState.GestureUpdated:
        scale_factor = gesture.scaleFactor()
        self.apply_zoom(scale_factor, gesture.centerPoint())
```

## Palm Rejection

### Algorithm

The palm rejection system filters out unintended touches:

1. **Size Detection**: Large contact areas likely indicate palms
2. **Simultaneous Input**: Multiple simultaneous touches suggest palm contact
3. **Movement Pattern**: Erratic or minimal movement patterns
4. **Timing Analysis**: Very brief contacts are often accidental

### Implementation

```python
def is_palm_touch(self, touch_point: QTouchEvent.TouchPoint) -> bool:
    # Check contact size
    if touch_point.ellipseDiameters().width() > PALM_SIZE_THRESHOLD:
        return True
    
    # Check for simultaneous touches
    if self.active_touch_count > 1:
        return self.analyze_touch_pattern(touch_point)
    
    return False
```

## Tool Integration

### Drawing Tools

Different tools respond differently to input:

- **Pen Tool**: Direct stroke creation with pressure sensitivity
- **Eraser Tool**: Remove elements under cursor/touch
- **Selection Tool**: Select and manipulate existing elements
- **Text Tool**: Create text input areas

### Tool-Specific Input Handling

```python
def handle_drawing_input(self, point: Point, tool: Tool):
    if tool == Tool.PEN:
        self.add_stroke_point(point)
    elif tool == Tool.ERASER:
        self.erase_at_point(point)
    elif tool == Tool.SELECTION:
        self.update_selection(point)
```

## Performance Considerations

### Input Latency Optimization

- **Direct Event Handling**: Minimal processing between input and display
- **Predictive Rendering**: Anticipate next stroke points
- **Efficient Updates**: Update only affected screen regions
- **Background Processing**: Move heavy operations to background threads

### Smooth Line Rendering

```python
def smooth_stroke_points(self, points: list[Point]) -> list[Point]:
    # Apply smoothing algorithms to reduce jitter
    # Cubic spline interpolation for natural curves
    # Pressure smoothing for consistent line width
    return smoothed_points
```

## Configuration Options

### Input Sensitivity Settings

```python
class InputSettings:
    pressure_sensitivity: float = 1.0      # Pressure multiplier
    mouse_pressure: float = 0.7            # Simulated pressure for mouse
    touch_pressure: float = 0.8            # Simulated pressure for touch
    palm_rejection_enabled: bool = True    # Enable palm rejection
    gesture_enabled: bool = True           # Enable gesture recognition
    hover_preview_enabled: bool = True     # Show hover cursor
```

### Device-Specific Tuning

- **Graphics Tablet Calibration**: Pressure curve adjustments
- **Touch Sensitivity**: Minimum touch pressure thresholds
- **Mouse Acceleration**: Cursor movement sensitivity
- **Gesture Thresholds**: Minimum distances for gesture recognition

## Error Handling

### Input Event Errors

```python
def handle_input_error(self, error: Exception, event):
    self.logger.warning(f"Input processing error: {error}")
    # Graceful fallback to basic mouse input
    self.fallback_to_mouse_mode()
```

### Device Disconnection

- **Automatic Detection**: Monitor device connection status
- **Graceful Degradation**: Fall back to available input methods
- **User Notification**: Inform user of device changes
- **State Recovery**: Maintain drawing state across device changes

## Testing and Debugging

### Input Event Logging

```python
def log_input_event(self, event, device_type: str):
    self.logger.debug(f"Input: {device_type} at ({event.x()}, {event.y()}) "
                     f"pressure: {getattr(event, 'pressure', 'N/A')}")
```

### Performance Metrics

- **Input Latency**: Time from input event to screen update
- **Event Rate**: Input events per second
- **Pressure Accuracy**: Pressure value consistency
- **Gesture Recognition Rate**: Successful gesture detection percentage

## Accessibility Features

### Input Alternatives

- **Keyboard Navigation**: Full keyboard control for drawing and navigation
- **Voice Commands**: Voice-controlled tool selection and commands
- **Eye Tracking**: Experimental support for eye-tracking devices
- **Switch Input**: Support for accessibility switches

### Customization Options

- **Input Remapping**: Customize button and gesture assignments
- **Sensitivity Adjustment**: Accommodate different motor abilities
- **Visual Feedback**: Enhanced visual indicators for input actions
- **Audio Feedback**: Optional audio cues for input events

## Future Enhancements

### Planned Features

1. **Advanced Pressure Curves**: Customizable pressure response curves
2. **Tilt Support**: Full pen tilt and rotation support
3. **Multi-device Input**: Simultaneous input from multiple devices
4. **AI-Enhanced Palm Rejection**: Machine learning-based palm detection
5. **Haptic Feedback**: Tactile feedback for supported devices

### Experimental Features

- **3D Input**: Support for 3D input devices and spatial drawing
- **Brain-Computer Interface**: Experimental BCI input support
- **Gesture Learning**: AI-powered custom gesture recognition
- **Predictive Input**: Anticipate user intentions for smoother interaction

This comprehensive input system ensures that users can interact with the diary application naturally and efficiently using their preferred input method while maintaining high precision and responsiveness.