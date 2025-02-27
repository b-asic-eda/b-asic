#!/usr/bin/env python3
"""
B-ASIC Scheduler-GUI Timeline Item Module.

Contains the scheduler_gui TimelineItem class for drawing and
maintain the timeline in a schedule.
"""
from typing import overload

# QGraphics and QPainter imports
from qtpy.QtCore import QLineF, Qt
from qtpy.QtGui import QCursor
from qtpy.QtWidgets import QGraphicsItem, QGraphicsLineItem, QGraphicsTextItem


class TimelineItem(QGraphicsLineItem):
    """A class to represent the timeline in AxesItem."""

    # _scale:             float
    _delta_time_label: QGraphicsTextItem

    @overload
    def __init__(self, line: QLineF, parent: QGraphicsItem | None = None) -> None:
        """
        Constructs a TimelineItem out of *line*.

        *parent* is passed to QGraphicsLineItem's constructor.
        """

    @overload
    def __init__(self, parent: QGraphicsItem | None = None) -> None:
        """Constructs a TimelineItem.

        *parent* is passed to QGraphicsLineItem's constructor."""

    @overload
    def __init__(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        parent: QGraphicsItem | None = None,
    ) -> None:
        """
        Constructs a TimelineItem from (x1, y1) to (x2, y2).

        *parent* is passed to QGraphicsLineItem's constructor.
        """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.setFlag(QGraphicsItem.ItemIsMovable)  # mouse move events
        # self.setAcceptHoverEvents(True)                 # mouse hover events
        self.setAcceptedMouseButtons(
            Qt.MouseButton.LeftButton
        )  # accepted buttons for movements
        self.setCursor(
            QCursor(Qt.CursorShape.SizeHorCursor)
        )  # default cursor when hovering over object

        self._delta_time_label = QGraphicsTextItem()
        self._delta_time_label.hide()
        self._delta_time_label.setScale(1.05 / 75)  # TODO: dont hardcode scale
        self._delta_time_label.setParentItem(self)
        x_pos = (
            -self._delta_time_label.mapRectToParent(
                self._delta_time_label.boundingRect()
            ).width()
            / 2
        )
        y_pos = 0.5
        self._delta_time_label.setPos(x_pos, y_pos)
        # pen = QPen(Qt.black)
        # self._delta_time_label.setPen(pen)

    # @property
    # def label(self) -> None:
    #     return self._delta_time_label

    def set_text(self, number: int) -> None:
        """
        Set the label text to *number*.

        Parameters
        ----------
        number : int
            The label number.
        """
        # self.prepareGeometryChange()
        self._delta_time_label.setPlainText(f"( {number:+} )")
        self._delta_time_label.setX(
            -self._delta_time_label.mapRectToParent(
                self._delta_time_label.boundingRect()
            ).width()
            / 2
        )

    # def set_text_pen(self, pen: QPen) -> None:
    #     """Set the label pen to 'pen'."""
    #     self._delta_time_label.setPen(pen)

    # def set_label_visible(self, visible: bool) -> None:
    #     """If visible is True, the item is made visible. Otherwise, the item is
    #     made invisible"""
    #     self._delta_time_label.setVisible(visible)

    def show_label(self) -> None:
        """Show the label."""
        self._delta_time_label.show()

    def hide_label(self) -> None:
        """Hide the label."""
        self._delta_time_label.hide()

    def set_text_scale(self, scale: float) -> None:
        """
        Set the text scale.

        Parameters
        ----------
        scale : float
            The text scale.
        """
        self._delta_time_label.setScale(scale)

    @property
    def event_items(self) -> list[QGraphicsItem]:
        """Return a list of objects that receives events."""
        return [self]
