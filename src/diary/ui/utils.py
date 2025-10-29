from PyQt6.QtCore import QBuffer, QByteArray, QIODevice, Qt
from PyQt6.QtGui import QPixmap

from diary.models import Point


def smooth_stroke_moving_average(
    stroke_points: list[Point], window_size: int = 4
) -> list[Point]:
    """
    Smooths a stroke using a simple moving average filter.
    """
    if len(stroke_points) < window_size:
        return stroke_points  # Not enough points to smooth, return as is

    smoothed_points: list[Point] = []
    # Start with the first few points to avoid a harsh jump
    for i in range(window_size):
        smoothed_points.append(stroke_points[i])

    for i in range(window_size, len(stroke_points)):
        # Get the slice of points for the moving average window
        window = stroke_points[i - window_size : i]

        # Calculate the average x, y, and pressure
        avg_x = sum(p.x for p in window) / window_size
        avg_y = sum(p.y for p in window) / window_size
        avg_pressure = sum(p.pressure for p in window) / window_size

        smoothed_points.append(Point(avg_x, avg_y, avg_pressure))

    return smoothed_points


def read_image(file_path: str) -> tuple[bytes, int, int]:
    """Reads the image from a path, and returns bytes, height, width"""
    pixmap = QPixmap(file_path)
    if pixmap.isNull():
        raise ValueError("Couldn't load image")

    MAX_DIMENSION = 1024.0
    if pixmap.width() > MAX_DIMENSION or pixmap.height() > MAX_DIMENSION:
        # Scale the pixmap down, keeping aspect ratio
        pixmap = pixmap.scaled(
            int(MAX_DIMENSION),
            int(MAX_DIMENSION),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

    # Compress to JPG, quality 80
    byte_array = QByteArray()
    buffer = QBuffer(byte_array)
    _ = buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    # Save the pixmap to the buffer in JPEG format, quality 80
    _ = pixmap.save(buffer, "JPG", 80)

    image_bytes = byte_array.data()
    return (image_bytes, pixmap.height(), pixmap.width())
