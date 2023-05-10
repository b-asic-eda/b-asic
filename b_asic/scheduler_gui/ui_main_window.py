# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file './main_window.ui'
#
# Created by: PyQt5 UI code generator 5.15.7
#
# WARNING: Any manual changes made to this file will be lost when pyuic5 is
# run again.  Do not edit this file unless you know what you are doing.


from qtpy import QtCore, QtGui, QtWidgets


class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        MainWindow.setObjectName("MainWindow")
        MainWindow.resize(800, 600)
        sizePolicy = QtWidgets.QSizePolicy(
            QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Preferred
        )
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(MainWindow.sizePolicy().hasHeightForWidth())
        MainWindow.setSizePolicy(sizePolicy)
        icon = QtGui.QIcon()
        icon.addPixmap(
            QtGui.QPixmap(":/icons/basic/small_logo.png"),
            QtGui.QIcon.Normal,
            QtGui.QIcon.Off,
        )
        MainWindow.setWindowIcon(icon)
        self.centralwidget = QtWidgets.QWidget(MainWindow)
        sizePolicy = QtWidgets.QSizePolicy(
            QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Preferred
        )
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(
            self.centralwidget.sizePolicy().hasHeightForWidth()
        )
        self.centralwidget.setSizePolicy(sizePolicy)
        self.centralwidget.setObjectName("centralwidget")
        self.horizontalLayout = QtWidgets.QHBoxLayout(self.centralwidget)
        self.horizontalLayout.setContentsMargins(0, 0, 0, 0)
        self.horizontalLayout.setSpacing(0)
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.splitter = QtWidgets.QSplitter(self.centralwidget)
        self.splitter.setOrientation(QtCore.Qt.Horizontal)
        self.splitter.setHandleWidth(0)
        self.splitter.setObjectName("splitter")
        self.view = QtWidgets.QGraphicsView(self.splitter)
        self.view.setAlignment(
            QtCore.Qt.AlignLeading | QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop
        )
        self.view.setRenderHints(
            QtGui.QPainter.Antialiasing | QtGui.QPainter.TextAntialiasing
        )
        self.view.setViewportUpdateMode(QtWidgets.QGraphicsView.FullViewportUpdate)
        self.view.setObjectName("view")
        self.info_table = QtWidgets.QTableWidget(self.splitter)
        self.info_table.setStyleSheet(
            "alternate-background-color: #fadefb;background-color: #ebebeb;"
        )
        self.info_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.info_table.setAlternatingRowColors(True)
        self.info_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.info_table.setRowCount(2)
        self.info_table.setColumnCount(2)
        self.info_table.setObjectName("info_table")
        item = QtWidgets.QTableWidgetItem()
        self.info_table.setVerticalHeaderItem(0, item)
        item = QtWidgets.QTableWidgetItem()
        self.info_table.setVerticalHeaderItem(1, item)
        item = QtWidgets.QTableWidgetItem()
        item.setTextAlignment(QtCore.Qt.AlignLeading | QtCore.Qt.AlignVCenter)
        font = QtGui.QFont()
        font.setBold(False)
        font.setWeight(50)
        item.setFont(font)
        self.info_table.setHorizontalHeaderItem(0, item)
        item = QtWidgets.QTableWidgetItem()
        item.setTextAlignment(QtCore.Qt.AlignLeading | QtCore.Qt.AlignVCenter)
        self.info_table.setHorizontalHeaderItem(1, item)
        item = QtWidgets.QTableWidgetItem()
        font = QtGui.QFont()
        font.setBold(False)
        font.setWeight(50)
        font.setKerning(True)
        item.setFont(font)
        brush = QtGui.QBrush(QtGui.QColor(160, 160, 164))
        brush.setStyle(QtCore.Qt.SolidPattern)
        item.setBackground(brush)
        brush = QtGui.QBrush(QtGui.QColor(255, 255, 255))
        brush.setStyle(QtCore.Qt.SolidPattern)
        item.setForeground(brush)
        item.setFlags(
            QtCore.Qt.ItemIsSelectable
            | QtCore.Qt.ItemIsEditable
            | QtCore.Qt.ItemIsDragEnabled
            | QtCore.Qt.ItemIsDropEnabled
            | QtCore.Qt.ItemIsUserCheckable
        )
        self.info_table.setItem(0, 0, item)
        item = QtWidgets.QTableWidgetItem()
        font = QtGui.QFont()
        font.setBold(False)
        font.setWeight(50)
        item.setFont(font)
        brush = QtGui.QBrush(QtGui.QColor(160, 160, 164))
        brush.setStyle(QtCore.Qt.SolidPattern)
        item.setBackground(brush)
        brush = QtGui.QBrush(QtGui.QColor(255, 255, 255))
        brush.setStyle(QtCore.Qt.SolidPattern)
        item.setForeground(brush)
        item.setFlags(
            QtCore.Qt.ItemIsSelectable
            | QtCore.Qt.ItemIsEditable
            | QtCore.Qt.ItemIsDragEnabled
            | QtCore.Qt.ItemIsDropEnabled
            | QtCore.Qt.ItemIsUserCheckable
        )
        self.info_table.setItem(1, 0, item)
        self.info_table.horizontalHeader().setHighlightSections(False)
        self.info_table.horizontalHeader().setStretchLastSection(True)
        self.info_table.verticalHeader().setVisible(False)
        self.info_table.verticalHeader().setDefaultSectionSize(24)
        self.horizontalLayout.addWidget(self.splitter)
        MainWindow.setCentralWidget(self.centralwidget)
        self.menubar = QtWidgets.QMenuBar(MainWindow)
        self.menubar.setGeometry(QtCore.QRect(0, 0, 800, 22))
        self.menubar.setObjectName("menubar")
        self.menuFile = QtWidgets.QMenu(self.menubar)
        self.menuFile.setObjectName("menuFile")
        self.menu_Recent_Schedule = QtWidgets.QMenu(self.menuFile)
        self.menu_Recent_Schedule.setObjectName("menu_Recent_Schedule")
        self.menuView = QtWidgets.QMenu(self.menubar)
        self.menuView.setObjectName("menuView")
        self.menu_Edit = QtWidgets.QMenu(self.menubar)
        self.menu_Edit.setObjectName("menu_Edit")
        self.menuWindow = QtWidgets.QMenu(self.menubar)
        self.menuWindow.setObjectName("menuWindow")
        self.menuHelp = QtWidgets.QMenu(self.menubar)
        self.menuHelp.setObjectName("menuHelp")
        MainWindow.setMenuBar(self.menubar)
        self.statusbar = QtWidgets.QStatusBar(MainWindow)
        self.statusbar.setObjectName("statusbar")
        MainWindow.setStatusBar(self.statusbar)
        self.toolBar = QtWidgets.QToolBar(MainWindow)
        self.toolBar.setObjectName("toolBar")
        MainWindow.addToolBar(QtCore.Qt.TopToolBarArea, self.toolBar)
        self.menu_load_from_file = QtWidgets.QAction(MainWindow)
        icon = QtGui.QIcon.fromTheme("document-open-folder")
        self.menu_load_from_file.setIcon(icon)
        self.menu_load_from_file.setStatusTip("")
        self.menu_load_from_file.setObjectName("menu_load_from_file")
        self.menu_save = QtWidgets.QAction(MainWindow)
        self.menu_save.setEnabled(False)
        icon = QtGui.QIcon.fromTheme("document-save")
        self.menu_save.setIcon(icon)
        self.menu_save.setObjectName("menu_save")
        self.menu_node_info = QtWidgets.QAction(MainWindow)
        self.menu_node_info.setCheckable(True)
        self.menu_node_info.setChecked(True)
        icon1 = QtGui.QIcon()
        icon1.addPixmap(
            QtGui.QPixmap(":/icons/misc/right_panel.svg"),
            QtGui.QIcon.Normal,
            QtGui.QIcon.Off,
        )
        icon1.addPixmap(
            QtGui.QPixmap(":/icons/misc/right_filled_panel.svg"),
            QtGui.QIcon.Normal,
            QtGui.QIcon.On,
        )
        self.menu_node_info.setIcon(icon1)
        self.menu_node_info.setIconVisibleInMenu(False)
        self.menu_node_info.setObjectName("menu_node_info")
        self.menu_quit = QtWidgets.QAction(MainWindow)
        icon = QtGui.QIcon.fromTheme("application-exit")
        self.menu_quit.setIcon(icon)
        self.menu_quit.setObjectName("menu_quit")
        self.menu_save_as = QtWidgets.QAction(MainWindow)
        self.menu_save_as.setEnabled(False)
        icon = QtGui.QIcon.fromTheme("document-save-as")
        self.menu_save_as.setIcon(icon)
        self.menu_save_as.setObjectName("menu_save_as")
        self.menu_exit_dialog = QtWidgets.QAction(MainWindow)
        self.menu_exit_dialog.setCheckable(True)
        self.menu_exit_dialog.setChecked(True)
        icon = QtGui.QIcon.fromTheme("view-close")
        self.menu_exit_dialog.setIcon(icon)
        self.menu_exit_dialog.setObjectName("menu_exit_dialog")
        self.menu_close_schedule = QtWidgets.QAction(MainWindow)
        self.menu_close_schedule.setEnabled(False)
        icon = QtGui.QIcon.fromTheme("view-close")
        self.menu_close_schedule.setIcon(icon)
        self.menu_close_schedule.setObjectName("menu_close_schedule")
        self.actionAbout = QtWidgets.QAction(MainWindow)
        self.actionAbout.setObjectName("actionAbout")
        self.actionDocumentation = QtWidgets.QAction(MainWindow)
        self.actionDocumentation.setObjectName("actionDocumentation")
        self.actionReorder = QtWidgets.QAction(MainWindow)
        self.actionReorder.setObjectName("actionReorder")
        self.actionPlot_schedule = QtWidgets.QAction(MainWindow)
        self.actionPlot_schedule.setObjectName("actionPlot_schedule")
        self.actionUndo = QtWidgets.QAction(MainWindow)
        self.actionUndo.setEnabled(False)
        self.actionUndo.setObjectName("actionUndo")
        self.actionRedo = QtWidgets.QAction(MainWindow)
        self.actionRedo.setEnabled(False)
        self.actionRedo.setObjectName("actionRedo")
        self.actionIncrease_time_resolution = QtWidgets.QAction(MainWindow)
        self.actionIncrease_time_resolution.setObjectName(
            "actionIncrease_time_resolution"
        )
        self.actionDecrease_time_resolution = QtWidgets.QAction(MainWindow)
        self.actionDecrease_time_resolution.setObjectName(
            "actionDecrease_time_resolution"
        )
        self.actionZoom_to_fit = QtWidgets.QAction(MainWindow)
        self.actionZoom_to_fit.setObjectName("actionZoom_to_fit")
        self.actionStatus_bar = QtWidgets.QAction(MainWindow)
        self.actionStatus_bar.setCheckable(True)
        self.actionStatus_bar.setChecked(True)
        self.actionStatus_bar.setObjectName("actionStatus_bar")
        self.actionToolbar = QtWidgets.QAction(MainWindow)
        self.actionToolbar.setCheckable(True)
        self.actionToolbar.setChecked(True)
        self.actionToolbar.setObjectName("actionToolbar")
        self.action_show_port_numbers = QtWidgets.QAction(MainWindow)
        self.action_show_port_numbers.setCheckable(True)
        self.action_show_port_numbers.setChecked(False)
        self.action_show_port_numbers.setIconVisibleInMenu(False)
        self.action_show_port_numbers.setObjectName("action_show_port_numbers")
        self.action_incorrect_execution_time = QtWidgets.QAction(MainWindow)
        self.action_incorrect_execution_time.setCheckable(True)
        self.action_incorrect_execution_time.setChecked(True)
        self.action_incorrect_execution_time.setIconVisibleInMenu(False)
        self.action_incorrect_execution_time.setObjectName(
            "action_incorrect_execution_time"
        )
        self.menu_open = QtWidgets.QAction(MainWindow)
        self.menu_open.setObjectName("menu_open")
        self.actionToggle_full_screen = QtWidgets.QAction(MainWindow)
        self.actionToggle_full_screen.setCheckable(True)
        self.actionToggle_full_screen.setObjectName("actionToggle_full_screen")
        self.menuFile.addAction(self.menu_open)
        self.menuFile.addAction(self.menu_save)
        self.menuFile.addAction(self.menu_save_as)
        self.menuFile.addAction(self.menu_load_from_file)
        self.menuFile.addAction(self.menu_close_schedule)
        self.menuFile.addSeparator()
        self.menuFile.addAction(self.menu_Recent_Schedule.menuAction())
        self.menuFile.addSeparator()
        self.menuFile.addAction(self.menu_quit)
        self.menuView.addAction(self.menu_node_info)
        self.menuView.addAction(self.actionToolbar)
        self.menuView.addAction(self.actionStatus_bar)
        self.menuView.addAction(self.action_incorrect_execution_time)
        self.menuView.addAction(self.action_show_port_numbers)
        self.menuView.addSeparator()
        self.menuView.addAction(self.actionPlot_schedule)
        self.menuView.addSeparator()
        self.menuView.addAction(self.actionZoom_to_fit)
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
        self.menubar.addAction(self.menuFile.menuAction())
        self.menubar.addAction(self.menu_Edit.menuAction())
        self.menubar.addAction(self.menuView.menuAction())
        self.menubar.addAction(self.menuWindow.menuAction())
        self.menubar.addAction(self.menuHelp.menuAction())
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
        QtCore.QMetaObject.connectSlotsByName(MainWindow)

    def retranslateUi(self, MainWindow):
        _translate = QtCore.QCoreApplication.translate
        item = self.info_table.verticalHeaderItem(0)
        item.setText(_translate("MainWindow", "1"))
        item = self.info_table.verticalHeaderItem(1)
        item.setText(_translate("MainWindow", "2"))
        item = self.info_table.horizontalHeaderItem(0)
        item.setText(_translate("MainWindow", "Property"))
        item = self.info_table.horizontalHeaderItem(1)
        item.setText(_translate("MainWindow", "Value"))
        __sortingEnabled = self.info_table.isSortingEnabled()
        self.info_table.setSortingEnabled(False)
        item = self.info_table.item(0, 0)
        item.setText(_translate("MainWindow", "Schedule"))
        item = self.info_table.item(1, 0)
        item.setText(_translate("MainWindow", "Operator"))
        self.info_table.setSortingEnabled(__sortingEnabled)
        self.menuFile.setTitle(_translate("MainWindow", "&File"))
        self.menu_Recent_Schedule.setTitle(_translate("MainWindow", "Open &recent"))
        self.menuView.setTitle(_translate("MainWindow", "&View"))
        self.menu_Edit.setTitle(_translate("MainWindow", "&Edit"))
        self.menuWindow.setTitle(_translate("MainWindow", "&Window"))
        self.menuHelp.setTitle(_translate("MainWindow", "&Help"))
        self.toolBar.setWindowTitle(_translate("MainWindow", "toolBar"))
        self.menu_load_from_file.setText(
            _translate("MainWindow", "&Import schedule from file...")
        )
        self.menu_load_from_file.setToolTip(
            _translate("MainWindow", "Import schedule from python script")
        )
        self.menu_load_from_file.setShortcut(_translate("MainWindow", "Ctrl+I"))
        self.menu_save.setText(_translate("MainWindow", "&Save"))
        self.menu_save.setToolTip(_translate("MainWindow", "Save schedule"))
        self.menu_save.setShortcut(_translate("MainWindow", "Ctrl+S"))
        self.menu_node_info.setText(_translate("MainWindow", "&Node info"))
        self.menu_node_info.setToolTip(
            _translate("MainWindow", "Show/hide node information")
        )
        self.menu_node_info.setShortcut(_translate("MainWindow", "Ctrl+I"))
        self.menu_quit.setText(_translate("MainWindow", "&Quit"))
        self.menu_quit.setShortcut(_translate("MainWindow", "Ctrl+Q"))
        self.menu_save_as.setText(_translate("MainWindow", "Save &as..."))
        self.menu_save_as.setToolTip(
            _translate("MainWindow", "Save schedule with new file name")
        )
        self.menu_exit_dialog.setText(_translate("MainWindow", "&Hide exit dialog"))
        self.menu_exit_dialog.setToolTip(_translate("MainWindow", "Hide exit dialog"))
        self.menu_close_schedule.setText(_translate("MainWindow", "&Close schedule"))
        self.actionAbout.setText(_translate("MainWindow", "&About"))
        self.actionAbout.setToolTip(_translate("MainWindow", "Open about window"))
        self.actionDocumentation.setText(_translate("MainWindow", "&Documentation"))
        self.actionDocumentation.setToolTip(
            _translate("MainWindow", "Open documentation")
        )
        self.actionReorder.setText(_translate("MainWindow", "Reorder"))
        self.actionReorder.setToolTip(
            _translate("MainWindow", "Reorder schedule based on start time")
        )
        self.actionPlot_schedule.setText(_translate("MainWindow", "&Plot schedule"))
        self.actionPlot_schedule.setToolTip(_translate("MainWindow", "Plot schedule"))
        self.actionUndo.setText(_translate("MainWindow", "Undo"))
        self.actionUndo.setShortcut(_translate("MainWindow", "Ctrl+Z"))
        self.actionRedo.setText(_translate("MainWindow", "Redo"))
        self.actionRedo.setShortcut(_translate("MainWindow", "Ctrl+R"))
        self.actionIncrease_time_resolution.setText(
            _translate("MainWindow", "Increase time resolution...")
        )
        self.actionDecrease_time_resolution.setText(
            _translate("MainWindow", "Decrease time resolution...")
        )
        self.actionZoom_to_fit.setText(_translate("MainWindow", "Zoom to &fit"))
        self.actionStatus_bar.setText(_translate("MainWindow", "&Status bar"))
        self.actionStatus_bar.setToolTip(
            _translate("MainWindow", "Show/hide status bar")
        )
        self.actionToolbar.setText(_translate("MainWindow", "&Toolbar"))
        self.actionToolbar.setToolTip(_translate("MainWindow", "Show/hide toolbar"))
        self.action_show_port_numbers.setText(
            _translate("MainWindow", "S&how port numbers")
        )
        self.action_show_port_numbers.setToolTip(
            _translate("MainWindow", "Show port numbers of operation")
        )
        self.action_incorrect_execution_time.setText(
            _translate("MainWindow", "&Incorrect execution time")
        )
        self.action_incorrect_execution_time.setToolTip(
            _translate(
                "MainWindow",
                "Highlight processes with execution time longer than schedule time",
            )
        )
        self.menu_open.setText(_translate("MainWindow", "&Open..."))
        self.menu_open.setToolTip(
            _translate("MainWindow", "Open previously saved schedule")
        )
        self.menu_open.setShortcut(_translate("MainWindow", "Ctrl+O"))
        self.actionToggle_full_screen.setText(
            _translate("MainWindow", "Toggle f&ull screen")
        )
        self.actionToggle_full_screen.setShortcut(_translate("MainWindow", "F11"))
