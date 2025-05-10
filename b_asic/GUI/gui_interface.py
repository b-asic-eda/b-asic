"""
B-ASIC GUI interface module.

Contains a GUI class for the interface.
Originally generated from QT designer, but now manually maintained.
"""

from qtpy import QtCore, QtWidgets


class Ui_main_window:
    def setupUi(self, main_window) -> None:
        main_window.setObjectName("main_window")
        main_window.setEnabled(True)
        main_window.resize(897, 633)
        sizePolicy = QtWidgets.QSizePolicy(
            QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Preferred
        )
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(main_window.sizePolicy().hasHeightForWidth())
        main_window.setSizePolicy(sizePolicy)
        self.centralwidget = QtWidgets.QWidget(main_window)
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
        # self.view = QtWidgets.QGraphicsView(self.splitter)
        # self.view.setAlignment(
        #     QtCore.Qt.AlignLeading | QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop
        # )
        # self.view.setRenderHints(
        #     QtGui.QPainter.Antialiasing | QtGui.QPainter.TextAntialiasing
        # )
        # self.view.setViewportUpdateMode(QtWidgets.QGraphicsView.FullViewportUpdate)
        # self.view.setObjectName("view")
        self.horizontalLayout.addWidget(self.splitter)
        self.operation_box = QtWidgets.QGroupBox(self.splitter)
        # self.operation_box.setGeometry(QtCore.QRect(10, 10, 201, 531))
        self.operation_box.setLayoutDirection(QtCore.Qt.LeftToRight)
        self.operation_box.setAutoFillBackground(False)
        self.operation_box.setStyleSheet(
            "QGroupBox { \n"
            "     border: 2px solid gray; \n"
            "     border-radius: 3px;\n"
            "     margin-top: 0.5em; \n"
            " } \n"
            "\n"
            "QGroupBox::title {\n"
            "    subcontrol-origin: margin;\n"
            "    left: 10px;\n"
            "    padding: 0 3px 0 3px;\n"
            "}"
        )
        self.operation_box.setAlignment(
            QtCore.Qt.AlignLeading | QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter
        )
        self.operation_box.setFlat(False)
        self.operation_box.setCheckable(False)
        self.operation_box.setObjectName("operation_box")
        sizePolicy = QtWidgets.QSizePolicy(
            QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Preferred
        )
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(
            self.operation_box.sizePolicy().hasHeightForWidth()
        )
        self.operation_box.setSizePolicy(sizePolicy)
        self.operation_list = QtWidgets.QToolBox(self.operation_box)
        self.operation_list.setGeometry(QtCore.QRect(10, 20, 171, 271))
        self.operation_list.setAutoFillBackground(False)
        self.operation_list.setObjectName("operation_list")
        sizePolicy = QtWidgets.QSizePolicy(
            QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Preferred
        )
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(
            self.operation_list.sizePolicy().hasHeightForWidth()
        )
        self.operation_list.setSizePolicy(sizePolicy)
        self.core_operations_page = QtWidgets.QWidget()
        self.core_operations_page.setGeometry(QtCore.QRect(0, 0, 171, 217))
        self.core_operations_page.setObjectName("core_operations_page")
        self.core_operations_list = QtWidgets.QListWidget(self.core_operations_page)
        self.core_operations_list.setGeometry(QtCore.QRect(10, 0, 141, 211))
        self.core_operations_list.setMinimumSize(QtCore.QSize(141, 0))
        self.core_operations_list.setEditTriggers(
            QtWidgets.QAbstractItemView.DoubleClicked
            | QtWidgets.QAbstractItemView.EditKeyPressed
        )
        self.core_operations_list.setDragEnabled(False)
        self.core_operations_list.setDragDropMode(
            QtWidgets.QAbstractItemView.NoDragDrop
        )
        self.core_operations_list.setMovement(QtWidgets.QListView.Static)
        self.core_operations_list.setFlow(QtWidgets.QListView.TopToBottom)
        self.core_operations_list.setProperty("isWrapping", False)
        self.core_operations_list.setResizeMode(QtWidgets.QListView.Adjust)
        self.core_operations_list.setLayoutMode(QtWidgets.QListView.SinglePass)
        self.core_operations_list.setViewMode(QtWidgets.QListView.ListMode)
        self.core_operations_list.setUniformItemSizes(False)
        self.core_operations_list.setWordWrap(False)
        self.core_operations_list.setSelectionRectVisible(False)
        self.core_operations_list.setObjectName("core_operations_list")
        self.operation_list.addItem(self.core_operations_page, "")
        self.special_operations_page = QtWidgets.QWidget()
        self.special_operations_page.setGeometry(QtCore.QRect(0, 0, 171, 217))
        self.special_operations_page.setObjectName("special_operations_page")
        self.special_operations_list = QtWidgets.QListWidget(
            self.special_operations_page
        )
        self.special_operations_list.setGeometry(QtCore.QRect(10, 0, 141, 211))
        self.special_operations_list.setObjectName("special_operations_list")
        self.operation_list.addItem(self.special_operations_page, "")
        self.utility_operations_page = QtWidgets.QWidget()
        self.utility_operations_page.setGeometry(QtCore.QRect(0, 0, 171, 217))
        self.utility_operations_page.setObjectName("utility_operations_page")
        self.utility_operations_list = QtWidgets.QListWidget(
            self.utility_operations_page
        )
        self.utility_operations_list.setGeometry(QtCore.QRect(10, 0, 141, 211))
        self.utility_operations_list.setObjectName("utility_operations_list")
        self.operation_list.addItem(self.utility_operations_page, "")
        self.custom_operations_page = QtWidgets.QWidget()
        self.custom_operations_page.setGeometry(QtCore.QRect(0, 0, 171, 217))
        self.custom_operations_page.setObjectName("custom_operations_page")
        self.custom_operations_list = QtWidgets.QListWidget(self.custom_operations_page)
        self.custom_operations_list.setGeometry(QtCore.QRect(10, 0, 141, 211))
        self.custom_operations_list.setObjectName("custom_operations_list")
        self.operation_list.addItem(self.custom_operations_page, "")
        main_window.setCentralWidget(self.centralwidget)
        self.menu_bar = QtWidgets.QMenuBar(main_window)
        self.menu_bar.setGeometry(QtCore.QRect(0, 0, 897, 21))
        self.menu_bar.setObjectName("menu_bar")
        self.file_menu = QtWidgets.QMenu(self.menu_bar)
        self.file_menu.setObjectName("file_menu")
        self.edit_menu = QtWidgets.QMenu(self.menu_bar)
        self.edit_menu.setObjectName("edit_menu")
        self.view_menu = QtWidgets.QMenu(self.menu_bar)
        self.view_menu.setObjectName("view_menu")
        self.run_menu = QtWidgets.QMenu(self.menu_bar)
        self.run_menu.setObjectName("run_menu")
        self.help_menu = QtWidgets.QMenu(self.menu_bar)
        self.help_menu.setObjectName("help_menu")
        main_window.setMenuBar(self.menu_bar)
        self.status_bar = QtWidgets.QStatusBar(main_window)
        self.status_bar.setObjectName("status_bar")
        main_window.setStatusBar(self.status_bar)
        self.load_menu = QtWidgets.QAction(main_window)
        self.load_menu.setObjectName("load_menu")
        self.save_menu = QtWidgets.QAction(main_window)
        self.save_menu.setObjectName("save_menu")
        self.load_operations = QtWidgets.QAction(main_window)
        self.load_operations.setObjectName("load_operations")
        self.recent_sfg = QtWidgets.QMenu(main_window)
        self.recent_sfg.setObjectName("recent_sfg")
        self.exit_menu = QtWidgets.QAction(main_window)
        self.exit_menu.setObjectName("exit_menu")
        self.select_all = QtWidgets.QAction(main_window)
        self.select_all.setObjectName("select_all")
        self.unselect_all = QtWidgets.QAction(main_window)
        self.unselect_all.setObjectName("unselect_all")
        self.actionSimulateSFG = QtWidgets.QAction(main_window)
        self.actionSimulateSFG.setObjectName("actionSimulateSFG")
        self.actionShowPC = QtWidgets.QAction(main_window)
        self.actionShowPC.setObjectName("actionShowPC")
        self.faqBASIC = QtWidgets.QAction(main_window)
        self.faqBASIC.setObjectName("faqBASIC")
        self.keybindsBASIC = QtWidgets.QAction(main_window)
        self.keybindsBASIC.setObjectName("keybindsBASIC")
        self.aboutBASIC = QtWidgets.QAction(main_window)
        self.aboutBASIC.setObjectName("aboutBASIC")
        self.documentationBASIC = QtWidgets.QAction(main_window)
        self.documentationBASIC.setObjectName("documentationBASIC")
        self.file_menu.addAction(self.load_menu)
        self.file_menu.addAction(self.save_menu)
        self.file_menu.addAction(self.load_operations)
        self.file_menu.addSeparator()
        self.file_menu.addMenu(self.recent_sfg)
        self.file_menu.addSeparator()
        self.file_menu.addAction(self.exit_menu)
        self.edit_menu.addAction(self.select_all)
        self.edit_menu.addAction(self.unselect_all)
        self.run_menu.addAction(self.actionShowPC)
        self.run_menu.addAction(self.actionSimulateSFG)
        self.help_menu.addAction(self.documentationBASIC)
        self.help_menu.addAction(self.faqBASIC)
        self.help_menu.addAction(self.keybindsBASIC)
        self.help_menu.addSeparator()
        self.help_menu.addAction(self.aboutBASIC)
        self.menu_bar.addAction(self.file_menu.menuAction())
        self.menu_bar.addAction(self.edit_menu.menuAction())
        self.menu_bar.addAction(self.view_menu.menuAction())
        self.menu_bar.addAction(self.run_menu.menuAction())
        self.menu_bar.addAction(self.help_menu.menuAction())

        self.retranslateUi(main_window)
        self.operation_list.setCurrentIndex(1)
        self.core_operations_list.setCurrentRow(-1)
        QtCore.QMetaObject.connectSlotsByName(main_window)

    def retranslateUi(self, main_window) -> None:
        _translate = QtCore.QCoreApplication.translate
        main_window.setWindowTitle(_translate("main_window", "B-ASIC"))
        self.operation_box.setTitle(_translate("main_window", "Operations"))
        self.core_operations_list.setSortingEnabled(False)
        __sortingEnabled = self.core_operations_list.isSortingEnabled()
        self.core_operations_list.setSortingEnabled(False)
        self.core_operations_list.setSortingEnabled(__sortingEnabled)
        self.operation_list.setItemText(
            self.operation_list.indexOf(self.core_operations_page),
            _translate("main_window", "Core operations"),
        )
        __sortingEnabled = self.special_operations_list.isSortingEnabled()
        self.special_operations_list.setSortingEnabled(False)
        self.special_operations_list.setSortingEnabled(__sortingEnabled)
        self.operation_list.setItemText(
            self.operation_list.indexOf(self.special_operations_page),
            _translate("main_window", "Special operations"),
        )
        __sortingEnabled = self.utility_operations_list.isSortingEnabled()
        self.utility_operations_list.setSortingEnabled(False)
        self.utility_operations_list.setSortingEnabled(__sortingEnabled)
        self.operation_list.setItemText(
            self.operation_list.indexOf(self.utility_operations_page),
            _translate("main_window", "Utility operations"),
        )
        __sortingEnabled = self.utility_operations_list.isSortingEnabled()
        self.custom_operations_list.setSortingEnabled(False)
        self.custom_operations_list.setSortingEnabled(__sortingEnabled)
        self.operation_list.setItemText(
            self.operation_list.indexOf(self.custom_operations_page),
            _translate("main_window", "Custom operation"),
        )
        self.file_menu.setTitle(_translate("main_window", "&File"))
        self.edit_menu.setTitle(_translate("main_window", "&Edit"))
        self.view_menu.setTitle(_translate("main_window", "&View"))
        self.run_menu.setTitle(_translate("main_window", "&Run"))
        self.actionShowPC.setText(_translate("main_window", "Show &precedence graph"))
        self.help_menu.setTitle(_translate("main_window", "&Help"))
        self.select_all.setText(_translate("main_window", "Select &all"))
        self.unselect_all.setText(_translate("main_window", "&Unselect all"))
        self.actionSimulateSFG.setText(_translate("main_window", "&Simulate SFG"))
        self.aboutBASIC.setText(_translate("main_window", "&About B-ASIC"))
        self.faqBASIC.setText(_translate("main_window", "&FAQ"))
        self.keybindsBASIC.setText(_translate("main_window", "&Keybinds"))
        self.documentationBASIC.setText(_translate("main_window", "&Documentation"))
        self.load_menu.setText(_translate("main_window", "&Load SFG"))
        self.save_menu.setText(_translate("main_window", "&Save SFG"))
        self.load_operations.setText(_translate("main_window", "Load &operations"))
        self.recent_sfg.setTitle(_translate("main_window", "&Recent SFG"))
        self.exit_menu.setText(_translate("main_window", "E&xit"))
        self.exit_menu.setShortcut(_translate("main_window", "Ctrl+Q"))


if __name__ == "__main__":
    import sys

    app = QtWidgets.QApplication(sys.argv)
    main_window = QtWidgets.QMainWindow()
    ui = Ui_main_window()
    ui.setupUi(main_window)
    main_window.show()
    sys.exit(app.exec_())
