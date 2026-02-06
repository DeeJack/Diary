"""Streak celebration widgets: toast banner and confetti overlay."""

import random

from PyQt6.QtCore import QPropertyAnimation, QRectF, Qt, QTimer
from PyQt6.QtGui import QBrush, QColor, QPainter, QPen
from PyQt6.QtWidgets import QGraphicsOpacityEffect, QLabel, QVBoxLayout, QWidget

ROUND_MILESTONES: set[int] = {
    10, 25, 50, 75, 100, 150, 200, 250, 300, 365, 500, 1000,
}

CONFETTI_COLORS: list[str] = [
    "#F44336", "#E91E63", "#9C27B0", "#673AB7",
    "#3F51B5", "#2196F3", "#03A9F4", "#00BCD4",
    "#4CAF50", "#8BC34A", "#CDDC39", "#FFEB3B",
    "#FFC107", "#FF9800", "#FF5722",
]


def is_milestone(streak: int) -> bool:
    """Return True if *streak* should trigger a celebration."""
    if streak <= 0:
        return False
    return streak % 7 == 0 or streak in ROUND_MILESTONES


def streak_color(streak: int) -> str:
    """Return a hex color string for the given streak level."""
    if streak >= 365:
        return "#FFD700"
    if streak >= 200:
        return "#FF6F00"
    if streak >= 100:
        return "#F44336"
    if streak >= 50:
        return "#FF9800"
    if streak >= 30:
        return "#9C27B0"
    if streak >= 14:
        return "#2196F3"
    if streak >= 7:
        return "#4CAF50"
    return "#888888"


def _milestone_label(streak: int) -> str:
    if streak % 365 == 0 and streak > 0:
        years = streak // 365
        return f"{years}-Year Streak!" if years > 1 else "1-Year Streak!"
    if streak % 7 == 0:
        weeks = streak // 7
        return f"{weeks}-Week Streak!"
    return f"{streak}-Day Streak!"


# ---------------------------------------------------------------------------
# Toast widget
# ---------------------------------------------------------------------------

class StreakToastWidget(QWidget):
    """Semi-transparent banner that fades in, holds, and fades out."""

    def __init__(self, streak: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setFixedHeight(60)

        color = streak_color(streak)
        label = QLabel(_milestone_label(streak))
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet(
            f"color: {color}; font-size: 22px; font-weight: bold; font-family: 'Times New Roman';"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 8, 20, 8)
        layout.addWidget(label)

        self.setStyleSheet(
            "background-color: rgba(30, 30, 30, 200); border-radius: 12px;"
        )

        # Opacity animation
        self._effect = QGraphicsOpacityEffect(self)
        self._effect.setOpacity(0.0)
        self.setGraphicsEffect(self._effect)

        self._fade_in = QPropertyAnimation(self._effect, b"opacity")
        self._fade_in.setDuration(400)
        self._fade_in.setStartValue(0.0)
        self._fade_in.setEndValue(1.0)

        self._fade_out = QPropertyAnimation(self._effect, b"opacity")
        self._fade_out.setDuration(600)
        self._fade_out.setStartValue(1.0)
        self._fade_out.setEndValue(0.0)
        _ = self._fade_out.finished.connect(self.close)

    def show_animated(self) -> None:
        """Fade in, hold for 3 s, then fade out."""
        self.show()
        self.raise_()
        self._fade_in.start()
        QTimer.singleShot(3000, self._fade_out.start)

    def reposition(self, parent_width: int) -> None:
        """Center at top of parent."""
        w = min(320, parent_width - 40)
        x = (parent_width - w) // 2
        self.setGeometry(x, 18, w, 60)


# ---------------------------------------------------------------------------
# Confetti overlay
# ---------------------------------------------------------------------------

class _Particle:
    __slots__ = ("x", "y", "w", "h", "color", "speed", "wobble", "angle", "da")

    def __init__(self, area_width: int) -> None:
        self.x: float = random.uniform(0, area_width)
        self.y: float = random.uniform(-40, -10)
        self.w: float = random.uniform(5, 10)
        self.h: float = random.uniform(8, 14)
        self.color: QColor = QColor(random.choice(CONFETTI_COLORS))
        self.speed: float = random.uniform(2.0, 5.0)
        self.wobble: float = random.uniform(-1.5, 1.5)
        self.angle: float = random.uniform(0, 360)
        self.da: float = random.uniform(-6, 6)


class ConfettiOverlay(QWidget):
    """Transparent overlay that animates falling confetti particles."""

    PARTICLE_COUNT = 60
    TICK_MS = 16
    DURATION_MS = 3000

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        self._particles: list[_Particle] = []
        self._timer = QTimer(self)
        _ = self._timer.timeout.connect(self._tick)
        self._elapsed = 0

    def start(self) -> None:
        """Spawn particles and begin animation."""
        self._particles = [_Particle(self.width()) for _ in range(self.PARTICLE_COUNT)]
        self._elapsed = 0
        self.show()
        self.raise_()
        self._timer.start(self.TICK_MS)

    def _tick(self) -> None:
        self._elapsed += self.TICK_MS
        h = self.height()
        for p in self._particles:
            p.y += p.speed
            p.x += p.wobble
            p.angle += p.da
            # Reset particles that fall off
            if p.y > h + 20:
                p.y = random.uniform(-30, -10)
                p.x = random.uniform(0, self.width())
        self.update()
        if self._elapsed >= self.DURATION_MS:
            self._timer.stop()
            self.close()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(Qt.PenStyle.NoPen))
        for p in self._particles:
            painter.save()
            painter.translate(p.x + p.w / 2, p.y + p.h / 2)
            painter.rotate(p.angle)
            painter.setBrush(QBrush(p.color))
            painter.drawRect(QRectF(-p.w / 2, -p.h / 2, p.w, p.h))
            painter.restore()
        painter.end()
