"""
B-ASIC Scheduler-GUI Preferences Dialog Module.

Contains the scheduler_gui PreferencesDialog class.
"""

# QGraphics and QPainter imports
from qtpy.QtCore import (
    QCoreApplication,
    QSettings,
    Qt,
)
from qtpy.QtGui import QColor, QFont, QIcon, QIntValidator
from qtpy.QtWidgets import (
    QColorDialog,
    QDialogButtonBox,
    QFontDialog,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from b_asic.gui_utils.color_button import ColorButton
from b_asic.scheduler_gui._preferences import (
    ACTIVE_COLOR_TYPE,
    EXECUTION_TIME_COLOR_TYPE,
    FONT,
    LATENCY_COLOR_TYPE,
    SIGNAL_COLOR_TYPE,
    SIGNAL_WARNING_COLOR_TYPE,
    ColorDataType,
    reset_color_settings,
)


class PreferencesDialog(QWidget):
    def __init__(self, parent) -> None:
        super().__init__()
        self._parent = parent
        self.setWindowTitle("Preferences")
        layout = QVBoxLayout()
        layout.setSpacing(15)

        # Add label for the dialog
        label = QLabel("Customize fonts and colors")
        layout.addWidget(label)

        groupbox = QGroupBox()
        hlayout = QHBoxLayout()
        label = QLabel("Color settings:")
        layout.addWidget(label)
        hlayout.setSpacing(20)

        hlayout.addWidget(self.create_color_button(EXECUTION_TIME_COLOR_TYPE))
        hlayout.addWidget(self.create_color_button(LATENCY_COLOR_TYPE))
        hlayout.addWidget(
            self.create_color_button(
                ColorDataType(
                    current_color=LATENCY_COLOR_TYPE.DEFAULT,
                    DEFAULT=QColor("skyblue"),
                    name="Latency color per type",
                )
            )
        )

        groupbox.setLayout(hlayout)
        layout.addWidget(groupbox)

        label = QLabel("Signal colors:")
        layout.addWidget(label)
        groupbox = QGroupBox()
        hlayout = QHBoxLayout()
        hlayout.setSpacing(20)

        signal_color_button = self.create_color_button(SIGNAL_COLOR_TYPE)
        signal_color_button.setStyleSheet(
            f"color: {QColor(255, 255, 255, 0).name()}; background-color: {SIGNAL_COLOR_TYPE.DEFAULT.name()}"
        )

        hlayout.addWidget(signal_color_button)
        hlayout.addWidget(self.create_color_button(SIGNAL_WARNING_COLOR_TYPE))
        hlayout.addWidget(self.create_color_button(ACTIVE_COLOR_TYPE))

        groupbox.setLayout(hlayout)
        layout.addWidget(groupbox)

        reset_color_button = ColorButton(QColor("silver"))
        reset_color_button.setText("Reset all color settings")
        reset_color_button.pressed.connect(self.reset_color_clicked)
        layout.addWidget(reset_color_button)

        label = QLabel("Font settings:")
        layout.addWidget(label)

        groupbox = QGroupBox()
        hlayout = QHBoxLayout()
        hlayout.setSpacing(10)

        font_button = ColorButton(QColor("moccasin"))
        font_button.setText("Font settings")
        hlayout.addWidget(font_button)

        font_color_button = ColorButton(QColor("moccasin"))
        font_color_button.setText("Font color")
        font_color_button.pressed.connect(self.font_color_clicked)
        hlayout.addWidget(font_color_button)

        groupbox2 = QGroupBox()
        hlayout2 = QHBoxLayout()

        icon = QIcon.fromTheme("format-text-italic")
        self._italic_button = (
            ColorButton(QColor("silver"))
            if FONT.italic
            else ColorButton(QColor("snow"))
        )
        self._italic_button.setIcon(icon)
        self._italic_button.pressed.connect(self.italic_font_clicked)
        hlayout2.addWidget(self._italic_button)

        icon = QIcon.fromTheme("format-text-bold")
        self._bold_button = ColorButton(
            QColor("silver") if FONT.bold else QColor("snow")
        )
        self._bold_button.setIcon(icon)
        self._bold_button.pressed.connect(self.bold_font_clicked)
        hlayout2.addWidget(self._bold_button)

        groupbox2.setLayout(hlayout2)
        hlayout.addWidget(groupbox2)

        groupbox2 = QGroupBox()
        hlayout2 = QHBoxLayout()
        self._font_size_input = QLineEdit()
        font_button.pressed.connect(self.font_clicked)

        icon = QIcon.fromTheme("list-add")
        increase_font_size_button = ColorButton(QColor("smoke"))
        increase_font_size_button.setIcon(icon)
        increase_font_size_button.pressed.connect(self.increase_font_size_clicked)
        increase_font_size_button.setShortcut(
            QCoreApplication.translate("MainWindow", "Ctrl++")
        )
        hlayout2.addWidget(increase_font_size_button)

        self._font_size_input.setPlaceholderText("Font Size")
        self._font_size_input.setText(f"Font Size: {FONT.size}")
        self._font_size_input.setValidator(QIntValidator(0, 99))
        self._font_size_input.setAlignment(Qt.AlignCenter)
        self._font_size_input.textChanged.connect(self.set_font_size_clicked)
        hlayout2.addWidget(self._font_size_input)

        icon = QIcon.fromTheme("list-remove")
        decrease_font_size_button = ColorButton(QColor("smoke"))
        decrease_font_size_button.setIcon(icon)
        decrease_font_size_button.pressed.connect(self.decrease_font_size_clicked)
        decrease_font_size_button.setShortcut(
            QCoreApplication.translate("MainWindow", "Ctrl+-")
        )

        hlayout2.addWidget(decrease_font_size_button)

        groupbox2.setLayout(hlayout2)
        hlayout.addWidget(groupbox2)

        groupbox.setLayout(hlayout)
        layout.addWidget(groupbox)

        reset_font_button = ColorButton(QColor("silver"))
        reset_font_button.setText("Reset all font Settings")
        reset_font_button.pressed.connect(self.reset_font_clicked)
        layout.addWidget(reset_font_button)

        label = QLabel("")
        layout.addWidget(label)

        reset_all_button = ColorButton(QColor("salmon"))
        reset_all_button.setText("Reset all settings")
        reset_all_button.pressed.connect(self.reset_all_clicked)
        layout.addWidget(reset_all_button)

        self.setLayout(layout)
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Close)
        button_box.ButtonLayout(QDialogButtonBox.MacLayout)
        button_box.accepted.connect(self.close)
        button_box.rejected.connect(self.close)
        layout.addWidget(button_box)

    def increase_font_size_clicked(self) -> None:
        """
        Increase the font size by 1.
        """
        if FONT.size <= 71:
            self._font_size_input.setText(str(FONT.size + 1))
        else:
            self._font_size_input.setText(str(FONT.size))

    def decrease_font_size_clicked(self) -> None:
        """
        Decrease the font size by 1.
        """
        if FONT.size >= 7:
            self._font_size_input.setText(str(FONT.size - 1))
        else:
            self._font_size_input.setText(str(FONT.size))

    def set_font_size_clicked(self) -> None:
        """
        Set the font size to the specified size and update the font.
        """
        size = self._font_size_input.text()
        FONT.size = int(size) if size != "" else 6
        FONT.current_font.setPointSizeF(FONT.size)
        self.update_font()

    def create_color_button(self, color: ColorDataType) -> ColorButton:
        """
        Create a colored button to be used to modify a certain color.

        Parameters
        ----------
        color : ColorDataType
            The ColorDataType assigned to the butten to be created.
        """
        button = ColorButton(color.DEFAULT)
        button.setText(color.name)
        if color.name == "Latency color":
            button.pressed.connect(
                lambda: self.set_latency_color_by_type_name(modify_all=True)
            )
        elif color.name == "Latency color per type":
            button.pressed.connect(
                lambda: self.set_latency_color_by_type_name(modify_all=False)
            )
        else:
            button.pressed.connect(lambda: self.color_button_clicked(color))
        return button

    def italic_font_clicked(self) -> None:
        """
        Toggle the font style to italic if not already italic, otherwise remove italic.
        """
        FONT.italic = not FONT.italic
        FONT.current_font.setItalic(FONT.italic)
        if FONT.italic:
            self._italic_button.set_color(QColor("silver"))
        else:
            self._italic_button.set_color(QColor("snow"))
        self.update_font()

    def bold_font_clicked(self) -> None:
        """
        Toggle the font style to bold if not already bold, otherwise unbold.
        """
        FONT.bold = not FONT.bold
        FONT.current_font.setBold(FONT.bold)
        FONT.current_font.setWeight(50)
        if FONT.bold:
            self._bold_button.set_color(QColor("silver"))
        else:
            self._bold_button.set_color(QColor("snow"))
        self.update_font()

    def set_latency_color_by_type_name(self, modify_all: bool) -> None:
        """
        Set latency color based on operation type names.

        Parameters
        ----------
        modify_all : bool
            Indicates if the color of all type names to be modified.
        """
        if LATENCY_COLOR_TYPE.changed:
            current_color = LATENCY_COLOR_TYPE.current_color
        else:
            current_color = LATENCY_COLOR_TYPE.DEFAULT

        # Prompt user to select operation type if not setting color for all types
        if not modify_all:
            used_types = self._parent._schedule.get_used_type_names()
            operation_type, ok = QInputDialog.getItem(
                self, "Select operation type", "Type", used_types, editable=False
            )
        else:
            operation_type = "all operations"
            ok = False

        # Open a color dialog to get the selected color
        if modify_all or ok:
            color = QColorDialog.getColor(
                current_color, self, f"Select the color of {operation_type}"
            )

            # If a valid color is selected, update color settings and graph
            if color.isValid():
                if modify_all:
                    LATENCY_COLOR_TYPE.changed = True
                    self._parent._color_changed_per_type = False
                    self._parent._changed_operation_colors.clear()
                    LATENCY_COLOR_TYPE.current_color = color
                # Save color settings for each operation type
                else:
                    self._parent._color_changed_per_type = True
                    self._parent._changed_operation_colors[operation_type] = color
                self._parent.update_color_preferences()
                self._parent.update_statusbar("Preferences updated")

    def color_button_clicked(self, color_type: ColorDataType) -> None:
        """
        Open a color dialog to select a color based on the specified color type.

        Parameters
        ----------
        color_type : ColorDataType
            The ColorDataType to be changed.
        """
        settings = QSettings()
        if color_type.changed:
            current_color = color_type.current_color
        else:
            current_color = color_type.DEFAULT

        color = QColorDialog.getColor(current_color, self, f"Select {color_type.name}")
        # If a valid color is selected, update the current color and settings
        if color.isValid():
            color_type.current_color = color
            color_type.changed = color_type.current_color != color_type.DEFAULT
            settings.setValue(f"scheduler/preferences/{color_type.name}", color.name())
            settings.sync()

        self._parent._graph._signals.reopen.emit()
        self._parent.update_statusbar("Preferences Updated")

    def font_clicked(self) -> None:
        """
        Open a font dialog to select a font and update the current font.
        """
        current_font = FONT.current_font if FONT.changed else FONT.DEFAULT

        (font, ok) = QFontDialog.getFont(current_font, self)
        if ok:
            FONT.current_font = font
            FONT.size = int(font.pointSizeF())
            FONT.bold = font.bold()
            FONT.italic = font.italic()
            self.update_font()
            self.match_dialog_font()
            self._parent.update_statusbar("Preferences Updated")

    def reset_font_clicked(self) -> None:
        """
        Reset the font settings.
        """
        FONT.current_font = QFont("Times", 12)
        FONT.changed = False
        FONT.color = FONT.DEFAULT_COLOR
        FONT.size = int(FONT.DEFAULT.pointSizeF())
        FONT.bold = FONT.DEFAULT.bold()
        FONT.italic = FONT.DEFAULT.italic()
        self.update_font()
        self._parent.load_preferences()
        self.match_dialog_font()

    def match_dialog_font(self) -> None:
        """
        Update the widgets on the preference dialog to match the current font.
        """
        self._font_size_input.setText(str(FONT.size))

        if FONT.italic:
            self._italic_button.set_color(QColor("silver"))
        else:
            self._italic_button.set_color(QColor("snow"))

        if FONT.bold:
            self._bold_button.set_color(QColor("silver"))
        else:
            self._bold_button.set_color(QColor("snow"))

    def update_font(self) -> None:
        """Update font preferences based on current Font settings."""
        settings = QSettings()
        FONT.changed = not (
            FONT.current_font == FONT.DEFAULT
            and FONT.size == int(FONT.DEFAULT.pointSizeF())
            and FONT.italic == FONT.DEFAULT.italic()
            and FONT.bold == FONT.DEFAULT.bold()
        )
        settings.setValue("scheduler/preferences/font", FONT.current_font.toString())
        settings.setValue("scheduler/preferences/font_size", FONT.size)
        settings.setValue("scheduler/preferences/font_bold", FONT.bold)
        settings.setValue("scheduler/preferences/font_italic", FONT.italic)
        settings.sync()
        self._parent.load_preferences()

    def font_color_clicked(self) -> None:
        """Select a font color and update preferences."""
        settings = QSettings()
        color = QColorDialog.getColor(FONT.color, self, "Select font color")
        if color.isValid():
            FONT.color = color
            FONT.changed = True
        settings.setValue("scheduler/preferences/font_color", FONT.color.name())
        settings.sync()
        self._parent._graph._font_color_change(FONT.color)

    def reset_color_clicked(self) -> None:
        """Reset the color settings."""
        settings = QSettings()
        reset_color_settings(settings)
        self._parent._color_changed_per_type = False
        self._parent.update_color_preferences()

        self._parent._graph._color_change(LATENCY_COLOR_TYPE.DEFAULT, "all operations")
        self._parent._graph._signals.reopen.emit()
        self._parent.load_preferences()

    def reset_all_clicked(self) -> None:
        """Reset both the color and the font settings."""
        self.reset_color_clicked()
        self.reset_font_clicked()
