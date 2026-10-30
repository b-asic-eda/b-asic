"""I/O-latency table for the Scheduling GUI."""

from collections.abc import Mapping

from natsort import natsorted
from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QAbstractItemView,
    QAbstractScrollArea,
    QDialog,
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from b_asic.graph_component import GraphID


class IOLatencyWindow(QDialog):
    """Display the calculated latency between input/output pairs."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setWindowTitle("I/O latency")
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.WindowSystemMenuHint
            | Qt.WindowType.WindowTitleHint
            | Qt.WindowType.WindowCloseButtonHint
            | Qt.WindowType.WindowMinimizeButtonHint
            | Qt.WindowType.WindowMaximizeButtonHint
        )

        self._table = QTableWidget(self)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self._table.setSizeAdjustPolicy(
            QAbstractScrollArea.SizeAdjustPolicy.AdjustToContentsOnFirstShow
        )
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )

        layout = QVBoxLayout(self)
        layout.addWidget(self._table)

    @property
    def table(self) -> QTableWidget:
        """The table containing the I/O-latency values."""
        return self._table

    def set_io_latency(
        self, io_latency: Mapping[GraphID, Mapping[GraphID, int]]
    ) -> None:
        """Replace the table contents with *io_latency*."""
        input_ids = list(io_latency)
        output_ids = natsorted(
            dict.fromkeys(
                output_id
                for output_latencies in io_latency.values()
                for output_id in output_latencies
            )
        )

        self._table.clear()
        self._table.clearSpans()
        self._table.setColumnCount(len(output_ids) + 1)
        self._table.setHorizontalHeaderLabels(["Input", *map(str, output_ids)])

        if not input_ids or not output_ids:
            self._table.setRowCount(1)
            self._table.setSpan(0, 0, 1, len(output_ids) + 1)
            self._table.setItem(0, 0, QTableWidgetItem("No input/output paths"))
            return

        self._table.setRowCount(len(input_ids))
        for row, input_id in enumerate(input_ids):
            self._table.setItem(row, 0, QTableWidgetItem(str(input_id)))
            for column, output_id in enumerate(output_ids, start=1):
                latency = io_latency[input_id].get(output_id, "-")
                latency_item = QTableWidgetItem(str(latency))
                latency_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self._table.setItem(row, column, latency_item)

        self._table.resizeRowsToContents()
