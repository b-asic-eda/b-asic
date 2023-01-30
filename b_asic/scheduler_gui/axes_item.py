#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""B-ASIC Scheduler-gui Graphics Axes Item Module.

Contains the scheduler-gui AxesItem class for drawing and maintain the
axes in a graph.
"""
from math import pi, sin
from typing import List, Optional, Union

# QGraphics and QPainter imports
from qtpy.QtCore import QPoint, QPointF, Qt
from qtpy.QtGui import QBrush, QPen, QPolygonF
from qtpy.QtWidgets import (
    QGraphicsItem,
    QGraphicsItemGroup,
    QGraphicsLineItem,
    QGraphicsPolygonItem,
    QGraphicsSimpleTextItem,
)

# B-ASIC
from b_asic.scheduler_gui.timeline_item import TimelineItem


class AxesItem(QGraphicsItemGroup):
    """A class to represent axes in a graph."""

    _scale: float = 1.0
    """Static, changed from MainWindow."""
    _width: int
    _width_indent: float
    _width_padding: float
    _height: int
    _height_indent: float
    _height_padding: float
    _x_axis: QGraphicsLineItem
    _x_label: QGraphicsSimpleTextItem
    _x_arrow: QGraphicsPolygonItem
    _x_scale: List[QGraphicsLineItem]
    _x_scale_labels: List[QGraphicsSimpleTextItem]
    _x_ledger: List[Union[QGraphicsLineItem, TimelineItem]]
    _x_label_offset: float
    _y_axis: QGraphicsLineItem
    _event_items: List[QGraphicsItem]
    _base_pen: QPen
    _ledger_pen: QPen
    _timeline_pen: QPen

    def __init__(
        self,
        width: float,
        height: float,
        width_indent: float = 0.2,
        height_indent: float = 0.2,
        width_padding: float = 0.6,
        height_padding: float = 0.5,
        parent: Optional[QGraphicsItem] = None,
    ):
        """
        Constructs a AxesItem.
        *parent* is passed to QGraphicsItemGroup's constructor.
        """
        super().__init__(parent=parent)
        if width < 0:
            raise ValueError(
                f"'width' greater or equal to 0 expected, got: {width}."
            )
        if height < 0:
            raise ValueError(
                f"'height' greater or equal to 0 expected, got: {height}."
            )

        self._width = width
        self._height = height
        self._width_indent = width_indent
        self._height_indent = height_indent
        self._width_padding = width_padding
        self._height_padding = height_padding
        self._x_axis = QGraphicsLineItem()
        self._x_label = QGraphicsSimpleTextItem()
        self._x_arrow = QGraphicsPolygonItem()
        self._x_scale = []
        self._x_scale_labels = []
        self._x_ledger = []
        self._x_label_offset = 0.2
        self._y_axis = QGraphicsLineItem()
        self._event_items = []

        self._base_pen = QPen()
        self._base_pen.setWidthF(2 / self._scale)
        self._base_pen.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
        self._ledger_pen = QPen(Qt.GlobalColor.lightGray)
        self._ledger_pen.setWidthF(0)  # 0 = cosmetic pen 1px width
        self._timeline_pen = QPen(Qt.GlobalColor.black)
        self._timeline_pen.setWidthF(2 / self._scale)
        self._timeline_pen.setStyle(Qt.PenStyle.DashLine)

        self._make_base()

    def clear(self) -> None:
        """Sets all children's parent to 'None' and delete the axes."""
        # TODO: update, needed?
        # self._timeline.setParentItem(None)
        self._event_items = []
        keys = list(self._axes.keys())
        for key in keys:
            self._axes[key].setParentItem(None)
            del self._axes[key]

    @property
    def width(self) -> int:
        """
        Get or set the current x-axis width. Setting the width to a new
        value will update the axes automatically.
        """
        return self._width

    # @width.setter
    # def width(self, width: int) -> None:
    #     if self._width != width:
    #         self.update_axes(width = width)

    @property
    def height(self) -> int:
        """
        Get or set the current y-axis height. Setting the height to a new
        value will update the axes automatically.
        """
        return self._height

    # @height.setter
    # def height(self, height: int) -> None:
    #     if self._height != height:
    #         self.update_axes(height = height)

    # @property
    # def width_indent(self) -> float:
    #     """Get or set the current x-axis indent. Setting the indent to a new
    #     value will update the axes automatically."""
    #     return self._width_indent
    # @width_indent.setter
    # def width_indent(self, width_indent: float) -> None:
    #     if self._width_indent != width_indent:
    #         self.update_axes(width_indent = width_indent)

    @property
    def event_items(self) -> List[QGraphicsItem]:
        """Return a list of objects, that receives events."""
        return [self._x_ledger[-1]]

    def _register_event_item(self, item: QGraphicsItem) -> None:
        """Register an object that receives events."""
        self._event_items.append(item)

    def set_height(self, height: int) -> "AxesItem":
        # TODO: implement, docstring
        if height < 0:
            raise ValueError(
                f"'height' greater or equal to 0 expected, got: {height}."
            )
        raise NotImplementedError

    def set_width(self, width: int) -> "AxesItem":
        # TODO: docstring
        if width < 0:
            raise ValueError(
                f"'width' greater or equal to 0 expected, got: {width}."
            )

        delta_width = width - self._width

        if delta_width > 0:
            for _ in range(delta_width):
                self._append_x_tick()
                self._width += 1
        elif delta_width < 0:
            for _ in range(abs(delta_width)):
                self._pop_x_tick()
                self._width -= 1

        return self

    def _pop_x_tick(self) -> None:
        # TODO: docstring

        # remove the next to last x_scale, x_scale_labels and x_ledger
        x_scale = self._x_scale.pop(-2)
        x_scale_labels = self._x_scale_labels.pop(-2)
        x_ledger = self._x_ledger.pop(-2)
        x_scale.setParentItem(None)
        x_scale_labels.setParentItem(None)
        x_ledger.setParentItem(None)
        del x_scale
        del x_scale_labels
        del x_ledger

        # move timeline x_scale and x_scale_labels (timeline already moved by event)
        self._x_scale[-1].setX(self._x_scale[-1].x() - 1)
        self._x_scale_labels[-1].setX(self._x_scale_labels[-1].x() - 1)
        self._x_scale_labels[-1].setText(str(len(self._x_scale) - 1))

        # move arrow, x-axis label and decrease x-axis
        self._x_arrow.setX(self._x_arrow.x() - 1)
        self._x_label.setX(self._x_label.x() - 1)
        self._x_axis.setLine(
            0, 0, self._width_indent + self._width - 1 + self._width_padding, 0
        )

    def _append_x_tick(self) -> None:
        # TODO: docstring

        index = len(self._x_scale)
        is_timeline = True
        if index != 0:
            index -= 1
            is_timeline = False

        # make a new x-tick
        # x-axis scale line
        self._x_scale.insert(index, QGraphicsLineItem(0, 0, 0, 0.05))
        self._x_scale[index].setPen(self._base_pen)
        pos = self.mapToScene(QPointF(self._width_indent + index, 0))
        self._x_scale[index].setPos(pos)
        self.addToGroup(self._x_scale[index])

        # x-axis scale number
        self._x_scale_labels.insert(index, QGraphicsSimpleTextItem(str(index)))
        self._x_scale_labels[index].setScale(1 / self._scale)
        x_pos = self._width_indent + index
        x_pos -= (
            self.mapRectFromItem(
                self._x_scale_labels[index],
                self._x_scale_labels[index].boundingRect(),
            ).width()
            / 2
        )
        pos = self.mapToScene(QPointF(x_pos, self._x_label_offset))
        self._x_scale_labels[index].setPos(pos)
        self.addToGroup(self._x_scale_labels[index])

        self._x_ledger.insert(
            index,
            TimelineItem(
                0,
                0,
                0,
                -(self._height_indent + self._height + self._height_padding),
            ),
        )
        # x-axis vertical ledger
        if is_timeline:  # last line is a timeline
            self._x_ledger[index].setPen(self._timeline_pen)
            self._x_ledger[index].set_text_scale(1.05 / self._scale)
            self._register_event_item(self._x_ledger[index])
        else:
            self._x_ledger[index].setPen(self._ledger_pen)
        pos = self.mapToScene(QPointF(self._width_indent + index, 0))
        self._x_ledger[index].setPos(pos)
        self.addToGroup(self._x_ledger[index])
        self._x_ledger[index].stackBefore(self._x_axis)

        # expand x-axis and move arrow,x-axis label, last x-scale, last x-scale-label
        if not is_timeline:
            # expand x-axis, move arrow and x-axis label
            self._x_axis.setLine(
                0, 0, self._width_indent + index + 1 + self._width_padding, 0
            )
            self._x_arrow.setX(self._x_arrow.x() + 1)
            self._x_label.setX(self._x_label.x() + 1)
            # move last x-scale and x-scale-label
            self._x_scale_labels[index + 1].setX(
                self._x_scale_labels[index + 1].x() + 1
            )
            self._x_scale_labels[index + 1].setText(str(index + 1))
            self._x_scale[index + 1].setX(self._x_scale[index + 1].x() + 1)

    def _make_base(self) -> None:
        # x axis
        self._x_axis.setLine(0, 0, self._width_indent + self._width_padding, 0)
        self._x_axis.setPen(self._base_pen)
        self.addToGroup(self._x_axis)

        # x-axis arrow
        arrow_size = 8 / self._scale
        point_0 = QPointF(0, sin(pi / 6) * arrow_size)
        point_1 = QPointF(arrow_size, 0)
        point_2 = QPointF(0, -sin(pi / 6) * arrow_size)
        polygon = QPolygonF([point_0, point_1, point_2])
        self._x_arrow.setPolygon(polygon)
        self._x_arrow.setPen(self._base_pen)
        self._x_arrow.setBrush(QBrush(Qt.SolidPattern))
        self._x_arrow.setPos(self._width_indent + self._width_padding, 0)
        self.addToGroup(self._x_arrow)

        # x-axis label
        self._x_label.setText("time")
        self._x_label.setScale(1 / self._scale)
        x_pos = self._width_indent + 0 + self._width_padding  # end of x-axis
        x_pos += (
            self.mapRectFromItem(
                self._x_arrow, self._x_arrow.boundingRect()
            ).width()
            / 2
        )  # + half arrow width
        x_pos -= (
            self.mapRectFromItem(
                self._x_label, self._x_label.boundingRect()
            ).width()
            / 2
        )  # - center of label
        self._x_label.setPos(x_pos, self._x_label_offset)
        self.addToGroup(self._x_label)

        # x-axis timeline
        self._append_x_tick()
        for _ in range(self._width):
            self._append_x_tick()
        pos = self._x_ledger[-1].pos()
        self._x_ledger[-1].setPos(
            pos + QPoint(self._width, 0)
        )  # move timeline

        # y-axis
        self._y_axis.setLine(
            0,
            0,
            0,
            -(
                self._height_indent
                + self._height
                + self._height_padding
                + 0.05
            ),
        )
        self._y_axis.setPen(self._base_pen)
        self.addToGroup(self._y_axis)
