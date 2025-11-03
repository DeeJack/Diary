"""Utility functions for the UI"""

import logging
from pathlib import Path

from PyQt6 import QtWidgets
from PyQt6.QtCore import QBuffer, QByteArray, QIODevice, QSize, Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtPdf import QPdfDocument
from PyQt6.QtWidgets import QFileDialog, QMessageBox, QProgressDialog, QWidget

from diary.config import settings
from diary.models import Image, Page, Point


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


def smooth_stroke_advanced(stroke_points: list[Point]) -> list[Point]:
    """
    Apply advanced smoothing pipeline: decimation + Catmull-Rom spline interpolation.

    Args:
        stroke_points: Original stroke points

    Returns:
        Smoothed and interpolated stroke points
    """
    if len(stroke_points) <= 2:
        return stroke_points

    # Decimate points to remove noise and redundancy
    decimated = decimate_stroke_points(stroke_points, min_distance=1.4)

    # Apply Catmull-Rom smoothing for natural curves
    smoothed = smooth_stroke_catmull_rom(decimated, tension=0.17)

    averaged = smooth_stroke_moving_average(smoothed, 3)

    return averaged


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
        _ = pixmap.save(buffer, "JPEG", quality=95)
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

    DPI = 250
    pages: list[QPixmap] = []
    for page_num in range(doc.pageCount()):
        logging.getLogger("Utils").debug(
            "Rendering page %s/%s", page_num, doc.pageCount()
        )
        page_size = doc.pagePointSize(page_num)
        width_in_pixels = int(page_size.width() * DPI / 72)
        height_in_pixels = int(page_size.height() * DPI / 72)

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
