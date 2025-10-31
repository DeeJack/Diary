"""Utility functions for the UI"""

import logging
from pathlib import Path

from PyQt6.QtCore import QBuffer, QByteArray, QIODevice, QSize, Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtPdf import QPdfDocument
from PyQt6.QtWidgets import QFileDialog

from diary.config import settings
from diary.models import Image, Notebook, Page, Point


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


def import_from_pdf() -> Notebook:
    """Opens a FileDialog to import a PDF file, converting it to images and creating a new notebook"""
    pdf_file, _ = QFileDialog.getOpenFileName(
        None, caption="Choose PDF file", filter="PDF File (*.pdf)"
    )
    if not pdf_file:
        return Notebook()

    pixmaps_pages = _import_from_pdf(Path(pdf_file))

    notebook = Notebook()
    for pixmap in pixmaps_pages:
        image_data = QByteArray()
        buffer = QBuffer(image_data)
        _ = buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        _ = pixmap.save(buffer, "JPEG", quality=95)
        page_img = Image(
            Point(0, 0), pixmap.width(), pixmap.height(), image_data=image_data.data()
        )
        notebook.add_page(Page(elements=[page_img]))
    return notebook


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
