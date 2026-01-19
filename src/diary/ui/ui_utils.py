"""Utility functions for the UI"""

import logging
import math
import time
from pathlib import Path

from PyQt6 import QtWidgets
from PyQt6.QtCore import (
    QBuffer,
    QByteArray,
    QEventLoop,
    QIODevice,
    QSize,
    Qt,
    QTimer,
    QUrl,
)
from PyQt6.QtGui import QPixmap
from PyQt6.QtMultimedia import QMediaPlayer, QVideoFrame, QVideoSink
from PyQt6.QtPdf import QPdfDocument
from PyQt6.QtWidgets import QFileDialog, QMessageBox, QProgressDialog, QWidget

from diary.config import settings
from diary.models import Image, Page, Point
from diary.ui.stroke_beautifier import StrokeBeautifier

# Global beautifier instance
_beautifier: StrokeBeautifier | None = None


def get_beautifier() -> StrokeBeautifier:
    """Get or create the stroke beautifier singleton."""
    global _beautifier
    if _beautifier is None:
        _beautifier = StrokeBeautifier()
    return _beautifier


def beautify_stroke(stroke_points: list[Point]) -> tuple[list[Point], str | None]:
    """
    Attempt to beautify a stroke by recognizing shapes.
    Falls back to advanced smoothing if no shape is recognized.

    Returns:
        Tuple of (points, shape_name). If shape_name is None, no shape was recognized.
    """
    if len(stroke_points) < 10:
        return smooth_stroke_advanced(stroke_points), None

    # Check if beautification is enabled
    if not settings.BEAUTIFICATION_ENABLED:
        return smooth_stroke_advanced(stroke_points), None

    beautifier = get_beautifier()
    beautified, shape_name = beautifier.beautify_stroke(
        stroke_points, threshold=settings.BEAUTIFICATION_THRESHOLD
    )

    if shape_name:
        # Shape was recognized, return beautified version
        print("Recognized shape:", shape_name)
        return beautified, shape_name

    # No shape recognized, apply regular smoothing
    return smooth_stroke_advanced(stroke_points), None


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


def decimate_stroke_points(
    stroke_points: list[Point], min_distance: float = 2.0
) -> list[Point]:
    """
    Remove points that are too close together to reduce noise and redundancy.

    Args:
        stroke_points: List of points to decimate
        min_distance: Minimum distance between consecutive points

    Returns:
        Decimated list of points
    """
    if len(stroke_points) <= 2:
        return stroke_points

    decimated: list[Point] = [stroke_points[0]]  # Always keep first point

    for i in range(1, len(stroke_points) - 1):
        current = stroke_points[i]
        last_kept = decimated[-1]

        # Calculate distance from last kept point
        dx = current.x - last_kept.x
        dy = current.y - last_kept.y
        distance = (dx * dx + dy * dy) ** 0.5

        if distance >= min_distance:
            decimated.append(current)

    # Always keep last point
    if len(stroke_points) > 1:
        decimated.append(stroke_points[-1])

    return decimated


def smooth_stroke_catmull_rom(
    stroke_points: list[Point], tension: float = 0.5
) -> list[Point]:
    """
    Smooth a stroke using Catmull-Rom spline interpolation for natural curves.

    Args:
        stroke_points: List of points to smooth
        tension: Controls curve tightness (0.0 = tight, 1.0 = loose)

    Returns:
        Smoothed list of points with interpolated curves
    """
    if len(stroke_points) <= 3:
        return stroke_points

    smoothed: list[Point] = []

    # Add first point
    smoothed.append(stroke_points[0])

    # For each segment between points, create smooth curve
    for i in range(len(stroke_points) - 1):
        # Get control points for Catmull-Rom spline
        p0 = stroke_points[max(0, i - 1)]
        p1 = stroke_points[i]
        p2 = stroke_points[min(len(stroke_points) - 1, i + 1)]
        p3 = stroke_points[min(len(stroke_points) - 1, i + 2)]

        # Number of interpolation steps based on distance
        dx = p2.x - p1.x
        dy = p2.y - p1.y
        segment_length = (dx * dx + dy * dy) ** 0.5
        num_steps = max(2, int(segment_length / 3.0))  # One step every 3 pixels

        # Generate interpolated points along the curve
        for step in range(1, num_steps):
            t = step / num_steps

            # Catmull-Rom spline calculation
            t2 = t * t
            t3 = t2 * t

            # Basis functions for Catmull-Rom
            b0 = -tension * t3 + 2 * tension * t2 - tension * t
            b1 = (2 - tension) * t3 + (tension - 3) * t2 + 1
            b2 = (tension - 2) * t3 + (3 - 2 * tension) * t2 + tension * t
            b3 = tension * t3 - tension * t2

            # Calculate interpolated position
            x = b0 * p0.x + b1 * p1.x + b2 * p2.x + b3 * p3.x
            y = b0 * p0.y + b1 * p1.y + b2 * p2.y + b3 * p3.y
            pressure = (
                b0 * p0.pressure
                + b1 * p1.pressure
                + b2 * p2.pressure
                + b3 * p3.pressure
            )

            # Clamp pressure to valid range
            pressure = max(0.1, min(1.0, pressure))

            smoothed.append(Point(x, y, pressure))

    # Add last point
    smoothed.append(stroke_points[-1])

    return smoothed


def generate_video_thumbnail(
    video_path: str, max_size: QSize | None = None, timeout_ms: int = 2000
) -> bytes | None:
    """Generate a thumbnail for a video file as PNG bytes."""
    max_size = max_size or QSize(320, 180)
    sink = QVideoSink()
    player = QMediaPlayer()
    player.setVideoSink(sink)
    player.setSource(QUrl.fromLocalFile(video_path))

    loop = QEventLoop()
    result: bytes | None = None

    def on_frame_changed(frame: QVideoFrame) -> None:
        nonlocal result
        image = frame.toImage()
        if image.isNull():
            return
        if (
            image.size().width() > max_size.width()
            or image.size().height() > max_size.height()
        ):
            image = image.scaled(
                max_size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        buffer = QBuffer()
        _ = buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        _ = image.save(buffer, "PNG")
        result = buffer.data().data()
        player.stop()
        loop.quit()

    _ = sink.videoFrameChanged.connect(on_frame_changed)

    def on_timeout() -> None:
        player.stop()
        loop.quit()

    timer = QTimer()
    timer.setSingleShot(True)
    _ = timer.timeout.connect(on_timeout)

    player.play()
    timer.start(timeout_ms)
    _ = loop.exec()

    _ = sink.videoFrameChanged.disconnect(on_frame_changed)
    return result


class OneEuroFilter:
    """1€ Filter for adaptive smoothing based on movement speed.

    Applies heavy filtering when moving slowly (reduces jitter) and
    light filtering when moving fast (reduces lag).
    """

    def __init__(
        self,
        t0: float,
        x0: float,
        min_cutoff: float = 1.0,
        beta: float = 0.007,
        d_cutoff: float = 1.0,
    ):
        """
        Args:
            t0: Initial timestamp
            x0: Initial value
            min_cutoff: Decrease to smooth more (removes jitter). Default: 1.0
            beta: Increase to reduce lag (makes responsive). Default: 0.007
            d_cutoff: Cutoff for derivative. Default: 1.0
        """
        self.frequency: float = 0.0
        self.min_cutoff: float = min_cutoff
        self.beta: float = beta
        self.d_cutoff: float = d_cutoff
        self.x_prev: float = x0
        self.dx_prev: float = 0.0
        self.t_prev: float = t0

    def alpha(self, cutoff: float) -> float:
        """Calculate smoothing factor based on cutoff frequency."""
        tau = 1.0 / (2 * math.pi * cutoff)
        return 1.0 / (1.0 + tau * self.frequency)

    def __call__(self, t: float, x: float) -> float:
        """Apply filter to new value.

        Args:
            t: Current timestamp
            x: Current value

        Returns:
            Filtered value
        """
        # Calculate time delta
        dt = t - self.t_prev
        self.frequency = 1.0 / dt if dt > 0 else 0.0

        # Filter the derivative (speed of change)
        a_d = self.alpha(self.d_cutoff)
        dx = (x - self.x_prev) / dt if dt > 0 else 0.0
        dx_hat = a_d * dx + (1.0 - a_d) * self.dx_prev

        # Calculate dynamic cutoff based on speed
        # High speed = high cutoff (less filtering, less lag)
        # Low speed = low cutoff (more filtering, smoother line)
        cutoff = self.min_cutoff + self.beta * abs(dx_hat)

        # Filter the main value
        a = self.alpha(cutoff)
        x_hat = a * x + (1.0 - a) * self.x_prev

        # Update memory
        self.x_prev = x_hat
        self.dx_prev = dx_hat
        self.t_prev = t

        return x_hat


def smooth_stroke_one_euro(
    stroke_points: list[Point], min_cutoff: float = 0.5, beta: float = 0.01
) -> list[Point]:
    """Apply 1€ Filter to smooth stroke points.

    The 1€ Filter adapts to movement speed:
    - Moving slowly: Heavy filtering (kills jitter)
    - Moving fast: Light filtering (reduces lag)

    Args:
        stroke_points: Original stroke points
        min_cutoff: Lower = more smoothing (0.1-1.0). Default: 0.5
        beta: Higher = more responsive (0.001-0.1). Default: 0.01

    Returns:
        Smoothed stroke points
    """
    if len(stroke_points) <= 2:
        return stroke_points

    # Generate synthetic timestamps (assume uniform spacing)
    base_time = time.time()
    dt = 0.01  # 10ms between points (100 Hz)

    # Initialize filters for x and y
    filter_x = OneEuroFilter(base_time, stroke_points[0].x, min_cutoff, beta)
    filter_y = OneEuroFilter(base_time, stroke_points[0].y, min_cutoff, beta)

    smoothed = [stroke_points[0]]  # Keep first point as-is

    for i in range(1, len(stroke_points)):
        t = base_time + i * dt
        smoothed_x = filter_x(t, stroke_points[i].x)
        smoothed_y = filter_y(t, stroke_points[i].y)
        smoothed.append(Point(smoothed_x, smoothed_y, stroke_points[i].pressure))

    return smoothed


def smooth_stroke_advanced(stroke_points: list[Point]) -> list[Point]:
    """
    Apply advanced smoothing pipeline with 1€ Filter for professional results.

    Args:
        stroke_points: Original stroke points

    Returns:
        Smoothed and interpolated stroke points
    """
    if len(stroke_points) <= 2:
        return stroke_points

    # Apply 1€ Filter if enabled
    if settings.ONE_EURO_FILTER_ENABLED:
        one_euro_smoothed = smooth_stroke_one_euro(
            stroke_points,
            min_cutoff=settings.ONE_EURO_MIN_CUTOFF,
            beta=settings.ONE_EURO_BETA,
        )
    else:
        one_euro_smoothed = stroke_points

    # Then decimate to remove redundant points
    decimated = decimate_stroke_points(
        one_euro_smoothed, min_distance=settings.SMOOTHING_MIN_DISTANCE
    )

    # Apply Catmull-Rom smoothing for natural curves
    smoothed = smooth_stroke_catmull_rom(decimated, tension=settings.SMOOTHING_TENSION)

    return smoothed


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
    _ = pixmap.save(buffer, "PNG", 100)

    image_bytes = byte_array.data()
    return (image_bytes, pixmap.height(), pixmap.width())


def import_from_pdf() -> list[Page]:
    """Opens a FileDialog to import a PDF file, converting it to images and creating a new notebook"""
    pdf_file, _ = QFileDialog.getOpenFileName(
        None, caption="Choose PDF file", filter="PDF File (*.pdf)"
    )
    if not pdf_file:
        return []

    pixmaps_pages = _import_from_pdf(Path(pdf_file))

    results: list[Page] = []
    for pixmap in pixmaps_pages:
        image_data = QByteArray()
        buffer = QBuffer(image_data)
        _ = buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        _ = pixmap.save(buffer, "PNG", quality=100)
        page_img = Image(
            Point(0, 0), pixmap.width(), pixmap.height(), image_data=image_data.data()
        )
        results.append(Page(elements=[page_img]))
    return results


def _import_from_pdf(pdf_path: Path) -> list[QPixmap]:
    if not pdf_path.exists():
        raise ValueError("PDF file doesn't exists!")

    doc = QPdfDocument(None)
    e = doc.load(pdf_path.as_posix())
    if e != QPdfDocument.Error.None_:
        logging.getLogger("Utils").error("Error in PDF: %s\n%s", pdf_path, e)
        return []

    if doc.status() != QPdfDocument.Status.Ready:
        logging.getLogger("Utils").error("Error loading PDF file: %s", doc.status())
        return []
    logging.getLogger("Utils").info(
        "PDF document read and ready, with %s pages!", doc.pageCount()
    )

    DPI = 1.5
    pages: list[QPixmap] = []
    for page_num in range(doc.pageCount()):
        logging.getLogger("Utils").debug(
            "Rendering page %s/%s", page_num, doc.pageCount()
        )
        page_size = doc.pagePointSize(page_num)
        width_in_pixels = int(page_size.width() * DPI)
        height_in_pixels = int(page_size.height() * DPI)

        image = doc.render(page_num, QSize(width_in_pixels, height_in_pixels))
        pixmap = QPixmap.fromImage(image)

        if (
            pixmap.width() > settings.PAGE_WIDTH
            or pixmap.height() > settings.PAGE_HEIGHT
        ):
            pixmap = pixmap.scaled(
                settings.PAGE_WIDTH,
                settings.PAGE_HEIGHT,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )

        pages.append(pixmap)

    logging.getLogger("Utils").info("Returning the pages as Pixmaps")

    doc.close()
    return pages


def show_error_dialog(
    parent: QWidget | None, title: str, text: str
) -> QMessageBox.StandardButton:
    """Show an error dialog, given the title and the text to show"""
    button = QMessageBox.critical(
        parent,
        title,
        text,
        buttons=QMessageBox.StandardButton.Ok,
        defaultButton=QMessageBox.StandardButton.Ok,
    )

    return button


def show_info_dialog(
    parent: QWidget | None, title: str, text: str
) -> QMessageBox.StandardButton:
    """Show an info dialog, given the title and the text to show"""
    button = QMessageBox.information(
        parent,
        title,
        text,
        buttons=QMessageBox.StandardButton.Ok,
        defaultButton=QMessageBox.StandardButton.Ok,
    )

    return button


def show_progress_dialog(
    parent: QWidget | None, title: str, text: str
) -> QProgressDialog:
    """Show a continuous progress dialog"""
    dialog = QProgressDialog(parent)
    dialog.setWindowTitle(title)
    dialog.setLabelText(text)
    dialog.setMaximum(0)
    dialog.setMinimumWidth(400)
    dialog.resize(400, dialog.sizeHint().height())
    dialog.show()
    return dialog


def confirm_delete(parent: QWidget | None) -> bool:
    """Show confirmation dialog and emit delete signal if confirmed"""
    reply = QtWidgets.QMessageBox.question(
        parent,
        "Delete Page",
        "Are you sure you want to delete this page?\n\nThis action cannot be undone.",
        QtWidgets.QMessageBox.StandardButton.Yes
        | QtWidgets.QMessageBox.StandardButton.No,
        QtWidgets.QMessageBox.StandardButton.No,
    )

    return reply == QtWidgets.QMessageBox.StandardButton.Yes
