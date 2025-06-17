################################################################################
## Form generated from reading UI file 'main_window.ui'
##
## Created by: Qt User Interface Compiler version 6.9.0
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from qtpy.QtCore import QCoreApplication, QMetaObject, QRect, QSize, Qt
from qtpy.QtGui import QAction, QBrush, QColor, QFont, QIcon, QPainter
from qtpy.QtWidgets import (
    QAbstractItemView,
    QGraphicsView,
    QHBoxLayout,
    QMenu,
    QMenuBar,
    QSizePolicy,
    QSplitter,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QToolBar,
    QWidget,
)


class Ui_MainWindow:
    def setupUi(self, MainWindow) -> None:
        if not MainWindow.objectName():
            MainWindow.setObjectName("MainWindow")
        MainWindow.resize(800, 600)
        sizePolicy = QSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred
        )
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(MainWindow.sizePolicy().hasHeightForWidth())
        MainWindow.setSizePolicy(sizePolicy)
        icon = QIcon()
        icon.addFile(
            ":/icons/basic/small_logo.png", QSize(), QIcon.Mode.Normal, QIcon.State.Off
        )
        MainWindow.setWindowIcon(icon)
        self.menu_load_from_file = QAction(MainWindow)
        self.menu_load_from_file.setObjectName("menu_load_from_file")
        icon1 = QIcon()
        iconThemeName = "document-open-folder"
        if QIcon.hasThemeIcon(iconThemeName):
            icon1 = QIcon.fromTheme(iconThemeName)
        else:
            icon1.addFile(
                "../../../.designer/backup", QSize(), QIcon.Mode.Normal, QIcon.State.Off
            )

        self.menu_load_from_file.setIcon(icon1)
        self.menu_save = QAction(MainWindow)
        self.menu_save.setObjectName("menu_save")
        self.menu_save.setEnabled(False)
        icon2 = QIcon()
        iconThemeName = "document-save"
        if QIcon.hasThemeIcon(iconThemeName):
            icon2 = QIcon.fromTheme(iconThemeName)
        else:
            icon2.addFile(
                "../../../.designer/backup", QSize(), QIcon.Mode.Normal, QIcon.State.Off
            )

        self.menu_save.setIcon(icon2)
        self.menu_node_info = QAction(MainWindow)
        self.menu_node_info.setObjectName("menu_node_info")
        self.menu_node_info.setCheckable(True)
        self.menu_node_info.setChecked(True)
        icon3 = QIcon()
        icon3.addFile(
            ":/icons/misc/right_panel.svg", QSize(), QIcon.Mode.Normal, QIcon.State.Off
        )
        icon3.addFile(
            ":/icons/misc/right_filled_panel.svg",
            QSize(),
            QIcon.Mode.Normal,
            QIcon.State.On,
        )
        self.menu_node_info.setIcon(icon3)
        self.menu_node_info.setIconVisibleInMenu(False)
        self.menu_quit = QAction(MainWindow)
        self.menu_quit.setObjectName("menu_quit")
        icon4 = QIcon()
        iconThemeName = "application-exit"
        if QIcon.hasThemeIcon(iconThemeName):
            icon4 = QIcon.fromTheme(iconThemeName)
        else:
            icon4.addFile(
                "../../../.designer/backup", QSize(), QIcon.Mode.Normal, QIcon.State.Off
            )

        self.menu_quit.setIcon(icon4)
        self.menu_save_as = QAction(MainWindow)
        self.menu_save_as.setObjectName("menu_save_as")
        self.menu_save_as.setEnabled(False)
        icon5 = QIcon()
        iconThemeName = "document-save-as"
        if QIcon.hasThemeIcon(iconThemeName):
            icon5 = QIcon.fromTheme(iconThemeName)
        else:
            icon5.addFile(
                "../../../.designer/backup", QSize(), QIcon.Mode.Normal, QIcon.State.Off
            )

        self.menu_save_as.setIcon(icon5)
        self.menu_exit_dialog = QAction(MainWindow)
        self.menu_exit_dialog.setObjectName("menu_exit_dialog")
        self.menu_exit_dialog.setCheckable(True)
        self.menu_exit_dialog.setChecked(True)
        icon6 = QIcon()
        iconThemeName = "view-close"
        if QIcon.hasThemeIcon(iconThemeName):
            icon6 = QIcon.fromTheme(iconThemeName)
        else:
            icon6.addFile(
                "../../../.designer/backup", QSize(), QIcon.Mode.Normal, QIcon.State.Off
            )

        self.menu_exit_dialog.setIcon(icon6)
        self.menu_close_schedule = QAction(MainWindow)
        self.menu_close_schedule.setObjectName("menu_close_schedule")
        self.menu_close_schedule.setEnabled(False)
        self.menu_close_schedule.setIcon(icon6)
        self.actionAbout = QAction(MainWindow)
        self.actionAbout.setObjectName("actionAbout")
        self.actionDocumentation = QAction(MainWindow)
        self.actionDocumentation.setObjectName("actionDocumentation")
        self.actionReorder = QAction(MainWindow)
        self.actionReorder.setObjectName("actionReorder")
        self.actionPlot_schedule = QAction(MainWindow)
        self.actionPlot_schedule.setObjectName("actionPlot_schedule")
        self.action_view_variables = QAction(MainWindow)
        self.action_view_variables.setObjectName("action_view_variables")
        self.action_view_variables.setEnabled(False)
        self.action_view_port_accesses = QAction(MainWindow)
        self.action_view_port_accesses.setObjectName("action_view_port_accesses")
        self.action_view_port_accesses.setEnabled(False)
        self.actionUndo = QAction(MainWindow)
        self.actionUndo.setObjectName("actionUndo")
        self.actionUndo.setEnabled(False)
        self.actionRedo = QAction(MainWindow)
        self.actionRedo.setObjectName("actionRedo")
        self.actionRedo.setEnabled(False)
        self.actionIncrease_time_resolution = QAction(MainWindow)
        self.actionIncrease_time_resolution.setObjectName(
            "actionIncrease_time_resolution"
        )
        self.actionDecrease_time_resolution = QAction(MainWindow)
        self.actionDecrease_time_resolution.setObjectName(
            "actionDecrease_time_resolution"
        )
        self.actionZoom_to_fit = QAction(MainWindow)
        self.actionZoom_to_fit.setObjectName("actionZoom_to_fit")
        self.actionStatus_bar = QAction(MainWindow)
        self.actionStatus_bar.setObjectName("actionStatus_bar")
        self.actionStatus_bar.setCheckable(True)
        self.actionStatus_bar.setChecked(True)
        self.actionToolbar = QAction(MainWindow)
        self.actionToolbar.setObjectName("actionToolbar")
        self.actionToolbar.setCheckable(True)
        self.actionToolbar.setChecked(True)
        self.action_show_port_numbers = QAction(MainWindow)
        self.action_show_port_numbers.setObjectName("action_show_port_numbers")
        self.action_show_port_numbers.setCheckable(True)
        self.action_show_port_numbers.setChecked(False)
        self.action_show_port_numbers.setIconVisibleInMenu(False)
        self.action_incorrect_execution_time = QAction(MainWindow)
        self.action_incorrect_execution_time.setObjectName(
            "action_incorrect_execution_time"
        )
        self.action_incorrect_execution_time.setCheckable(True)
        self.action_incorrect_execution_time.setChecked(True)
        self.action_incorrect_execution_time.setIconVisibleInMenu(False)
        self.menu_open = QAction(MainWindow)
        self.menu_open.setObjectName("menu_open")
        icon7 = QIcon()
        iconThemeName = "personal"
        if QIcon.hasThemeIcon(iconThemeName):
            icon7 = QIcon.fromTheme(iconThemeName)
        else:
            icon7.addFile(".", QSize(), QIcon.Mode.Normal, QIcon.State.Off)

        self.menu_open.setIcon(icon7)
        self.actionToggle_full_screen = QAction(MainWindow)
        self.actionToggle_full_screen.setObjectName("actionToggle_full_screen")
        self.actionToggle_full_screen.setCheckable(True)
        self.actionPreferences = QAction(MainWindow)
        self.actionPreferences.setObjectName("actionPreferences")
        icon8 = QIcon()
        iconThemeName = "preferences-desktop-personal"
        if QIcon.hasThemeIcon(iconThemeName):
            icon8 = QIcon.fromTheme(iconThemeName)
        else:
            icon8.addFile(".", QSize(), QIcon.Mode.Normal, QIcon.State.Off)

        self.actionPreferences.setIcon(icon8)
        self.actionZoom_to_fit_ignore_aspect_ratio = QAction(MainWindow)
        self.actionZoom_to_fit_ignore_aspect_ratio.setObjectName(
            "actionZoom_to_fit_ignore_aspect_ratio"
        )
        self.actionRestore_aspect_ratio = QAction(MainWindow)
        self.actionRestore_aspect_ratio.setObjectName("actionRestore_aspect_ratio")
        self.action_total_execution_times_of_variables = QAction(MainWindow)
        self.action_total_execution_times_of_variables.setObjectName(
            "action_total_execution_times_of_variables"
        )
        self.action_total_execution_times_of_variables.setEnabled(False)
        self.centralwidget = QWidget(MainWindow)
        self.centralwidget.setObjectName("centralwidget")
        sizePolicy.setHeightForWidth(
            self.centralwidget.sizePolicy().hasHeightForWidth()
        )
        self.centralwidget.setSizePolicy(sizePolicy)
        self.horizontalLayout = QHBoxLayout(self.centralwidget)
        self.horizontalLayout.setSpacing(0)
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.horizontalLayout.setContentsMargins(0, 0, 0, 0)
        self.splitter = QSplitter(self.centralwidget)
        self.splitter.setObjectName("splitter")
        self.splitter.setOrientation(Qt.Horizontal)
        self.splitter.setHandleWidth(0)
        self.view = QGraphicsView(self.splitter)
        self.view.setObjectName("view")
        self.view.setAlignment(Qt.AlignLeading | Qt.AlignLeft | Qt.AlignTop)
        self.view.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing)
        self.view.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.splitter.addWidget(self.view)
        self.info_table = QTableWidget(self.splitter)
        if self.info_table.columnCount() < 2:
            self.info_table.setColumnCount(2)
        font = QFont()
        font.setBold(False)
        __qtablewidgetitem = QTableWidgetItem()
        __qtablewidgetitem.setTextAlignment(Qt.AlignLeading | Qt.AlignVCenter)
        __qtablewidgetitem.setFont(font)
        self.info_table.setHorizontalHeaderItem(0, __qtablewidgetitem)
        __qtablewidgetitem1 = QTableWidgetItem()
        __qtablewidgetitem1.setTextAlignment(Qt.AlignLeading | Qt.AlignVCenter)
        self.info_table.setHorizontalHeaderItem(1, __qtablewidgetitem1)
        if self.info_table.rowCount() < 2:
            self.info_table.setRowCount(2)
        __qtablewidgetitem2 = QTableWidgetItem()
        self.info_table.setVerticalHeaderItem(0, __qtablewidgetitem2)
        __qtablewidgetitem3 = QTableWidgetItem()
        self.info_table.setVerticalHeaderItem(1, __qtablewidgetitem3)
        brush = QBrush(QColor(255, 255, 255, 255))
        brush.setStyle(Qt.BrushStyle.SolidPattern)
        brush1 = QBrush(QColor(160, 160, 164, 255))
        brush1.setStyle(Qt.BrushStyle.SolidPattern)
        font1 = QFont()
        font1.setBold(False)
        font1.setKerning(True)
        __qtablewidgetitem4 = QTableWidgetItem()
        __qtablewidgetitem4.setFont(font1)
        __qtablewidgetitem4.setBackground(brush1)
        __qtablewidgetitem4.setForeground(brush)
        __qtablewidgetitem4.setFlags(
            Qt.ItemIsSelectable
            | Qt.ItemIsEditable
            | Qt.ItemIsDragEnabled
            | Qt.ItemIsDropEnabled
            | Qt.ItemIsUserCheckable
        )
        self.info_table.setItem(0, 0, __qtablewidgetitem4)
        __qtablewidgetitem5 = QTableWidgetItem()
        __qtablewidgetitem5.setFont(font)
        __qtablewidgetitem5.setBackground(brush1)
        __qtablewidgetitem5.setForeground(brush)
        __qtablewidgetitem5.setFlags(
            Qt.ItemIsSelectable
            | Qt.ItemIsEditable
            | Qt.ItemIsDragEnabled
            | Qt.ItemIsDropEnabled
            | Qt.ItemIsUserCheckable
        )
        self.info_table.setItem(1, 0, __qtablewidgetitem5)
        self.info_table.setObjectName("info_table")
        self.info_table.setStyleSheet(
            "alternate-background-color: #fadefb;background-color: #ebebeb;"
        )
        self.info_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.info_table.setAlternatingRowColors(True)
        self.info_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.info_table.setRowCount(2)
        self.info_table.setColumnCount(2)
        self.splitter.addWidget(self.info_table)
        self.info_table.horizontalHeader().setHighlightSections(False)
        self.info_table.horizontalHeader().setStretchLastSection(True)
        self.info_table.verticalHeader().setVisible(False)
        self.info_table.verticalHeader().setDefaultSectionSize(24)

        self.horizontalLayout.addWidget(self.splitter)

        MainWindow.setCentralWidget(self.centralwidget)
        self.menubar = QMenuBar(MainWindow)
        self.menubar.setObjectName("menubar")
        self.menubar.setGeometry(QRect(0, 0, 800, 22))
        self.menuFile = QMenu(self.menubar)
        self.menuFile.setObjectName("menuFile")
        self.menu_Recent_Schedule = QMenu(self.menuFile)
        self.menu_Recent_Schedule.setObjectName("menu_Recent_Schedule")
        self.menuView = QMenu(self.menubar)
        self.menuView.setObjectName("menuView")
        self.menu_view_execution_times = QMenu(self.menuView)
        self.menu_view_execution_times.setObjectName("menu_view_execution_times")
        self.menu_view_execution_times.setEnabled(False)
        self.menu_view_total_execution_times_of_type = QMenu(self.menuView)
        self.menu_view_total_execution_times_of_type.setObjectName(
            "menu_view_total_execution_times_of_type"
        )
        self.menu_Edit = QMenu(self.menubar)
        self.menu_Edit.setObjectName("menu_Edit")
        self.menuWindow = QMenu(self.menubar)
        self.menuWindow.setObjectName("menuWindow")
        self.menuHelp = QMenu(self.menubar)
        self.menuHelp.setObjectName("menuHelp")
        MainWindow.setMenuBar(self.menubar)
        self.statusbar = QStatusBar(MainWindow)
        self.statusbar.setObjectName("statusbar")
        MainWindow.setStatusBar(self.statusbar)
        self.toolBar = QToolBar(MainWindow)
        self.toolBar.setObjectName("toolBar")
        MainWindow.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.toolBar)

        self.menubar.addAction(self.menuFile.menuAction())
        self.menubar.addAction(self.menu_Edit.menuAction())
        self.menubar.addAction(self.menuView.menuAction())
        self.menubar.addAction(self.menuWindow.menuAction())
        self.menubar.addAction(self.menuHelp.menuAction())
        self.menuFile.addAction(self.menu_open)
        self.menuFile.addAction(self.menu_Recent_Schedule.menuAction())
        self.menuFile.addAction(self.menu_load_from_file)
        self.menuFile.addSeparator()
        self.menuFile.addAction(self.menu_save)
        self.menuFile.addAction(self.menu_save_as)
        self.menuFile.addSeparator()
        self.menuFile.addAction(self.actionPreferences)
        self.menuFile.addSeparator()
        self.menuFile.addAction(self.menu_close_schedule)
        self.menuFile.addAction(self.menu_quit)
        self.menuView.addAction(self.menu_node_info)
        self.menuView.addAction(self.actionToolbar)
        self.menuView.addAction(self.actionStatus_bar)
        self.menuView.addAction(self.action_incorrect_execution_time)
        self.menuView.addAction(self.action_show_port_numbers)
        self.menuView.addSeparator()
        self.menuView.addAction(self.actionPlot_schedule)
        self.menuView.addAction(self.action_view_variables)
        self.menuView.addAction(self.action_total_execution_times_of_variables)
        self.menuView.addAction(self.action_view_port_accesses)
        self.menuView.addAction(self.menu_view_execution_times.menuAction())
        self.menuView.addAction(
            self.menu_view_total_execution_times_of_type.menuAction()
        )
        self.menuView.addSeparator()
        self.menuView.addAction(self.actionZoom_to_fit)
        self.menuView.addAction(self.actionZoom_to_fit_ignore_aspect_ratio)
        self.menuView.addAction(self.actionRestore_aspect_ratio)
        self.menuView.addAction(self.actionToggle_full_screen)
        self.menu_Edit.addAction(self.actionUndo)
        self.menu_Edit.addAction(self.actionRedo)
        self.menu_Edit.addSeparator()
        self.menu_Edit.addAction(self.actionReorder)
        self.menu_Edit.addAction(self.actionIncrease_time_resolution)
        self.menu_Edit.addAction(self.actionDecrease_time_resolution)
        self.menuWindow.addAction(self.menu_exit_dialog)
        self.menuHelp.addAction(self.actionDocumentation)
        self.menuHelp.addSeparator()
        self.menuHelp.addAction(self.actionAbout)
        self.toolBar.addAction(self.menu_open)
        self.toolBar.addAction(self.menu_save)
        self.toolBar.addAction(self.menu_save_as)
        self.toolBar.addSeparator()
        self.toolBar.addAction(self.actionUndo)
        self.toolBar.addAction(self.actionRedo)
        self.toolBar.addSeparator()
        self.toolBar.addAction(self.menu_node_info)
        self.toolBar.addAction(self.action_incorrect_execution_time)
        self.toolBar.addAction(self.action_show_port_numbers)
        self.toolBar.addAction(self.actionReorder)

        self.retranslateUi(MainWindow)

        QMetaObject.connectSlotsByName(MainWindow)

    # setupUi

    def retranslateUi(self, MainWindow) -> None:
        self.menu_load_from_file.setText(
            QCoreApplication.translate(
                "MainWindow", "&Import schedule from file...", None
            )
        )
        # if QT_CONFIG(tooltip)
        self.menu_load_from_file.setToolTip(
            QCoreApplication.translate(
                "MainWindow", "Import schedule from python script", None
            )
        )
        # endif // QT_CONFIG(tooltip)
        # if QT_CONFIG(statustip)
        self.menu_load_from_file.setStatusTip("")
        # endif // QT_CONFIG(statustip)
        # if QT_CONFIG(shortcut)
        self.menu_load_from_file.setShortcut(
            QCoreApplication.translate("MainWindow", "Ctrl+I", None)
        )
        # endif // QT_CONFIG(shortcut)
        self.menu_save.setText(QCoreApplication.translate("MainWindow", "&Save", None))
        # if QT_CONFIG(tooltip)
        self.menu_save.setToolTip(
            QCoreApplication.translate("MainWindow", "Save schedule", None)
        )
        # endif // QT_CONFIG(tooltip)
        # if QT_CONFIG(shortcut)
        self.menu_save.setShortcut(
            QCoreApplication.translate("MainWindow", "Ctrl+S", None)
        )
        # endif // QT_CONFIG(shortcut)
        self.menu_node_info.setText(
            QCoreApplication.translate("MainWindow", "&Node info", None)
        )
        # if QT_CONFIG(tooltip)
        self.menu_node_info.setToolTip(
            QCoreApplication.translate("MainWindow", "Show/hide node information", None)
        )
        # endif // QT_CONFIG(tooltip)
        # if QT_CONFIG(shortcut)
        self.menu_node_info.setShortcut(
            QCoreApplication.translate("MainWindow", "Ctrl+N", None)
        )
        # endif // QT_CONFIG(shortcut)
        self.menu_quit.setText(QCoreApplication.translate("MainWindow", "&Quit", None))
        # if QT_CONFIG(shortcut)
        self.menu_quit.setShortcut(
            QCoreApplication.translate("MainWindow", "Ctrl+Q", None)
        )
        # endif // QT_CONFIG(shortcut)
        self.menu_save_as.setText(
            QCoreApplication.translate("MainWindow", "Save &as...", None)
        )
        # if QT_CONFIG(tooltip)
        self.menu_save_as.setToolTip(
            QCoreApplication.translate(
                "MainWindow", "Save schedule with new file name", None
            )
        )
        # endif // QT_CONFIG(tooltip)
        # if QT_CONFIG(shortcut)
        self.menu_save_as.setShortcut(
            QCoreApplication.translate("MainWindow", "Ctrl+Shift+S", None)
        )
        # endif // QT_CONFIG(shortcut)
        self.menu_exit_dialog.setText(
            QCoreApplication.translate("MainWindow", "&Hide exit dialog", None)
        )
        # if QT_CONFIG(tooltip)
        self.menu_exit_dialog.setToolTip(
            QCoreApplication.translate("MainWindow", "Hide exit dialog", None)
        )
        # endif // QT_CONFIG(tooltip)
        self.menu_close_schedule.setText(
            QCoreApplication.translate("MainWindow", "&Close schedule", None)
        )
        # if QT_CONFIG(shortcut)
        self.menu_close_schedule.setShortcut(
            QCoreApplication.translate("MainWindow", "Ctrl+W", None)
        )
        # endif // QT_CONFIG(shortcut)
        self.actionAbout.setText(
            QCoreApplication.translate("MainWindow", "&About", None)
        )
        # if QT_CONFIG(tooltip)
        self.actionAbout.setToolTip(
            QCoreApplication.translate("MainWindow", "Open about window", None)
        )
        # endif // QT_CONFIG(tooltip)
        self.actionDocumentation.setText(
            QCoreApplication.translate("MainWindow", "&Documentation", None)
        )
        # if QT_CONFIG(tooltip)
        self.actionDocumentation.setToolTip(
            QCoreApplication.translate("MainWindow", "Open documentation", None)
        )
        # endif // QT_CONFIG(tooltip)
        self.actionReorder.setText(
            QCoreApplication.translate("MainWindow", "Reorder", None)
        )
        # if QT_CONFIG(tooltip)
        self.actionReorder.setToolTip(
            QCoreApplication.translate(
                "MainWindow", "Reorder schedule based on start time", None
            )
        )
        # endif // QT_CONFIG(tooltip)
        # if QT_CONFIG(shortcut)
        self.actionReorder.setShortcut(
            QCoreApplication.translate("MainWindow", "Ctrl+R", None)
        )
        # endif // QT_CONFIG(shortcut)
        self.actionPlot_schedule.setText(
            QCoreApplication.translate("MainWindow", "&Plot schedule", None)
        )
        # if QT_CONFIG(tooltip)
        self.actionPlot_schedule.setToolTip(
            QCoreApplication.translate("MainWindow", "Plot schedule", None)
        )
        # endif // QT_CONFIG(tooltip)
        self.action_view_variables.setText(
            QCoreApplication.translate(
                "MainWindow", "View execution times of variables", None
            )
        )
        # if QT_CONFIG(tooltip)
        self.action_view_variables.setToolTip(
            QCoreApplication.translate("MainWindow", "View all variables", None)
        )
        # endif // QT_CONFIG(tooltip)
        self.action_view_port_accesses.setText(
            QCoreApplication.translate(
                "MainWindow", "View port access statistics", None
            )
        )
        # if QT_CONFIG(tooltip)
        self.action_view_port_accesses.setToolTip(
            QCoreApplication.translate(
                "MainWindow", "View port access statistics for storage", None
            )
        )
        # endif // QT_CONFIG(tooltip)
        self.actionUndo.setText(QCoreApplication.translate("MainWindow", "Undo", None))
        # if QT_CONFIG(shortcut)
        self.actionUndo.setShortcut(
            QCoreApplication.translate("MainWindow", "Ctrl+Z", None)
        )
        # endif // QT_CONFIG(shortcut)
        self.actionRedo.setText(QCoreApplication.translate("MainWindow", "Redo", None))
        # if QT_CONFIG(shortcut)
        self.actionRedo.setShortcut(
            QCoreApplication.translate("MainWindow", "Ctrl+Y, Ctrl+Shift+Z", None)
        )
        # endif // QT_CONFIG(shortcut)
        self.actionIncrease_time_resolution.setText(
            QCoreApplication.translate(
                "MainWindow", "Increase time resolution...", None
            )
        )
        self.actionDecrease_time_resolution.setText(
            QCoreApplication.translate(
                "MainWindow", "Decrease time resolution...", None
            )
        )
        self.actionZoom_to_fit.setText(
            QCoreApplication.translate(
                "MainWindow", "Zoom to &fit, keep aspect ratio", None
            )
        )
        self.actionStatus_bar.setText(
            QCoreApplication.translate("MainWindow", "&Status bar", None)
        )
        # if QT_CONFIG(tooltip)
        self.actionStatus_bar.setToolTip(
            QCoreApplication.translate("MainWindow", "Show/hide status bar", None)
        )
        # endif // QT_CONFIG(tooltip)
        self.actionToolbar.setText(
            QCoreApplication.translate("MainWindow", "&Toolbar", None)
        )
        # if QT_CONFIG(tooltip)
        self.actionToolbar.setToolTip(
            QCoreApplication.translate("MainWindow", "Show/hide toolbar", None)
        )
        # endif // QT_CONFIG(tooltip)
        self.action_show_port_numbers.setText(
            QCoreApplication.translate("MainWindow", "S&how port numbers", None)
        )
        # if QT_CONFIG(tooltip)
        self.action_show_port_numbers.setToolTip(
            QCoreApplication.translate(
                "MainWindow", "Show port numbers of operation", None
            )
        )
        # endif // QT_CONFIG(tooltip)
        self.action_incorrect_execution_time.setText(
            QCoreApplication.translate("MainWindow", "&Incorrect execution time", None)
        )
        # if QT_CONFIG(tooltip)
        self.action_incorrect_execution_time.setToolTip(
            QCoreApplication.translate(
                "MainWindow",
                "Highlight processes with execution time longer than schedule time",
                None,
            )
        )
        # endif // QT_CONFIG(tooltip)
        self.menu_open.setText(
            QCoreApplication.translate("MainWindow", "&Open...", None)
        )
        # if QT_CONFIG(tooltip)
        self.menu_open.setToolTip(
            QCoreApplication.translate(
                "MainWindow", "Open previously saved schedule", None
            )
        )
        # endif // QT_CONFIG(tooltip)
        # if QT_CONFIG(shortcut)
        self.menu_open.setShortcut(
            QCoreApplication.translate("MainWindow", "Ctrl+O", None)
        )
        # endif // QT_CONFIG(shortcut)
        self.actionToggle_full_screen.setText(
            QCoreApplication.translate("MainWindow", "Toggle f&ull screen", None)
        )
        # if QT_CONFIG(shortcut)
        self.actionToggle_full_screen.setShortcut(
            QCoreApplication.translate("MainWindow", "F11", None)
        )
        # endif // QT_CONFIG(shortcut)
        self.actionPreferences.setText(
            QCoreApplication.translate("MainWindow", "Preferences", None)
        )
        # if QT_CONFIG(tooltip)
        self.actionPreferences.setToolTip(
            QCoreApplication.translate("MainWindow", "Color and Fonts", None)
        )
        # endif // QT_CONFIG(tooltip)
        # if QT_CONFIG(shortcut)
        self.actionPreferences.setShortcut(
            QCoreApplication.translate("MainWindow", "Ctrl+M", None)
        )
        # endif // QT_CONFIG(shortcut)
        self.actionZoom_to_fit_ignore_aspect_ratio.setText(
            QCoreApplication.translate(
                "MainWindow", "Zoom to fit, ignore aspect ratio", None
            )
        )
        self.actionRestore_aspect_ratio.setText(
            QCoreApplication.translate("MainWindow", "Restore aspect ratio", None)
        )
        self.action_total_execution_times_of_variables.setText(
            QCoreApplication.translate(
                "MainWindow", "View total execution times of variables", None
            )
        )
        ___qtablewidgetitem = self.info_table.horizontalHeaderItem(0)
        ___qtablewidgetitem.setText(
            QCoreApplication.translate("MainWindow", "Property", None)
        )
        ___qtablewidgetitem1 = self.info_table.horizontalHeaderItem(1)
        ___qtablewidgetitem1.setText(
            QCoreApplication.translate("MainWindow", "Value", None)
        )
        ___qtablewidgetitem2 = self.info_table.verticalHeaderItem(0)
        ___qtablewidgetitem2.setText(
            QCoreApplication.translate("MainWindow", "1", None)
        )
        ___qtablewidgetitem3 = self.info_table.verticalHeaderItem(1)
        ___qtablewidgetitem3.setText(
            QCoreApplication.translate("MainWindow", "2", None)
        )

        __sortingEnabled = self.info_table.isSortingEnabled()
        self.info_table.setSortingEnabled(False)
        ___qtablewidgetitem4 = self.info_table.item(0, 0)
        ___qtablewidgetitem4.setText(
            QCoreApplication.translate("MainWindow", "Schedule", None)
        )
        ___qtablewidgetitem5 = self.info_table.item(1, 0)
        ___qtablewidgetitem5.setText(
            QCoreApplication.translate("MainWindow", "Operator", None)
        )
        self.info_table.setSortingEnabled(__sortingEnabled)

        self.menuFile.setTitle(QCoreApplication.translate("MainWindow", "&File", None))
        self.menu_Recent_Schedule.setTitle(
            QCoreApplication.translate("MainWindow", "Open &recent", None)
        )
        self.menuView.setTitle(QCoreApplication.translate("MainWindow", "&View", None))
        self.menu_view_execution_times.setTitle(
            QCoreApplication.translate(
                "MainWindow", "View execution times of type", None
            )
        )
        self.menu_view_total_execution_times_of_type.setTitle(
            QCoreApplication.translate(
                "MainWindow", "View total execution times of type", None
            )
        )
        self.menu_Edit.setTitle(QCoreApplication.translate("MainWindow", "&Edit", None))
        self.menuWindow.setTitle(
            QCoreApplication.translate("MainWindow", "&Window", None)
        )
        self.menuHelp.setTitle(QCoreApplication.translate("MainWindow", "&Help", None))
        self.toolBar.setWindowTitle(
            QCoreApplication.translate("MainWindow", "toolBar", None)
        )

    # retranslateUi
