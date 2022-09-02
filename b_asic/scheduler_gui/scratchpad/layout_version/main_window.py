# This Python file uses the following encoding: utf-8
"""B-ASIC Scheduler-gui Module.

Contains the scheduler-gui class for scheduling operations in an SFG.

Start main-window with start_gui().
"""





import os
import sys
from pathlib        import Path
from types          import ModuleType
from typing         import Any
from pprint         import pprint
#from matplotlib.pyplot import bar
#from diagram import *
from importlib.machinery import SourceFileLoader
import inspect


# Qt/qtpy
import qtpy
from qtpy           import uic, QtCore, QtGui, QtWidgets
from qtpy.QtCore    import QCoreApplication, Qt, Slot, QSettings, QStandardPaths
from qtpy.QtGui     import QCloseEvent
from qtpy.QtWidgets import (
    QApplication, QMainWindow, QMessageBox, QFileDialog, QInputDialog, QCheckBox, QAbstractButton,
    QTableWidgetItem, QSizePolicy)

# QGraphics and QPainter imports
from qtpy.QtCore    import (
    QRect, QRectF, QPoint, QSize, QByteArray)
from qtpy.QtGui     import (
    QPaintEvent, QPainter, QPainterPath, QColor, QBrush, QPen, QFont, QPolygon, QIcon, QPixmap,
    QLinearGradient)
from qtpy.QtWidgets import (
    QGraphicsView, QGraphicsScene, QGraphicsWidget,
    QGraphicsLayout, QGraphicsLinearLayout, QGraphicsGridLayout, QGraphicsLayoutItem, QGraphicsAnchorLayout,
    QGraphicsItem, QGraphicsItemGroup)

# B-ASIC
import logger
from b_asic.schedule    import Schedule
from graphics_scene     import GraphicsScene
from component_item     import ComponentItem


log = logger.getLogger()

# Debug struff
if __debug__:
    log.setLevel('DEBUG')

if __debug__:
    # Print some system version information
    QT_API = os.environ.get('QT_API')
    log.debug('Qt version (runtime):     {}'.format(QtCore.qVersion()))
    log.debug('Qt version (compiletime): {}'.format(QtCore.__version__))
    log.debug('QT_API:                   {}'.format(QT_API))
    if QT_API.lower().startswith('pyside'):
        import PySide2
        log.debug('PySide version:           {}'.format(PySide2.__version__))
    if QT_API.lower().startswith('pyqt'):
        from qtpy.QtCore import PYQT_VERSION_STR
        log.debug('PyQt version:             {}'.format(PYQT_VERSION_STR))
    log.debug('QtPy version:             {}'.format(qtpy.__version__))
    
    # Autocompile the .ui form to a python file.
    try:                                        # PyQt5, try autocompile
        from qtpy.uic import compileUiDir
        uic.compileUiDir('.', map=(lambda dir,file: (dir, 'ui_' + file)))
    except:
        try:                                    # PySide2, try manual compile
            import subprocess
            os_ = sys.platform
            if os_.startswith('linux'):
                cmds = ['pyside2-uic -o ui_main_window.py main_window.ui']
                for cmd in cmds:
                    subprocess.call(cmd.split())
            else:
                #TODO: Implement (startswith) 'win32', 'darwin' (MacOs)
                raise SystemExit
        except:                                 # Compile failed, look for pre-compiled file
            try:
                from ui_main_window import Ui_MainWindow
            except:                             # Everything failed, exit
                log.exception("Could not import 'Ui_MainWindow'.")
                log.exception("Can't autocompile under", QT_API, "eviroment. Try to manual compile 'main_window.ui' to 'ui/main_window_ui.py'")
                os._exit(1)


sys.path.insert(0, 'icons/')                # Needed for the compiled '*_rc.py' files in 'ui_*.py' files
from ui_main_window import Ui_MainWindow    # Only availible when the form (.ui) is compiled


# The folowing QCoreApplication values is used for QSettings among others
QCoreApplication.setOrganizationName('Linöping University')
QCoreApplication.setOrganizationDomain('liu.se')
QCoreApplication.setApplicationName('B-ASIC Scheduler')
#QCoreApplication.setApplicationVersion(__version__)     # TODO: read from packet __version__




class MainWindow(QMainWindow, Ui_MainWindow):
    """Schedule of an SFG with scheduled Operations."""
    # _schedules: dict
    _scenes: dict[str, GraphicsScene]
    _scene: QGraphicsScene
    _diagrams: dict[str, QGraphicsWidget]
    _diagram_count: int
    _scene_count: int
    _open_file_dialog_opened: bool
    _scale: float
    
    def __init__(self):
        """Initialize Schedule-gui."""
        super().__init__()
        self._scenes = {}
        self._diagrams = {}
        self._scene_count = 0
        self._diagram_count = 0
        self._open_file_dialog_opened = False
        self._scale = 100.0
        
        QIcon.setThemeName('breeze')
        log.debug('themeName: \'{}\''.format(QIcon.themeName()))
        log.debug('themeSearchPaths: {}'.format(QIcon.themeSearchPaths()))
        self._init_ui()
        self._init_graphics()
        self._read_settings()

        

    def _init_ui(self) -> None:
        """Initialize the ui"""
        self.setupUi(self)
        
        # Connect signals to slots
        self.menu_load_from_file.triggered      .connect(self._load_schedule_from_pyfile)
        self.menu_save          .triggered      .connect(self.save)
        self.menu_save_as       .triggered      .connect(self.save_as)
        self.menu_quit          .triggered      .connect(self.close)
        self.menu_node_info     .triggered      .connect(self.toggle_component_info)
        self.menu_exit_dialog   .triggered      .connect(self.toggle_exit_dialog)
        self.actionT            .triggered      .connect(self.actionTbtn)
        self.splitter_center    .splitterMoved  .connect(self._splitter_center_moved)

        # Setup event member functions
        self.closeEvent = self._close_event
        
        # Setup info table
        self.info_table.setHorizontalHeaderLabels(['Property','Value'])
        # test = '#b085b2'
        # self.info_table.setStyleSheet('alternate-background-color: lightGray;background-color: white;')
        self.info_table.setStyleSheet('alternate-background-color: #fadefb;background-color: #ebebeb;')
        for i in range(10):
            self.info_table.insertRow(i)
            item = QTableWidgetItem('this is a very very very very long string that says abolutly nothing')
            self.info_table.setItem(i,0, QTableWidgetItem('property {}: '.format(i)))
            self.info_table.setItem(i,1,item)

        # Init central-widget splitter
        self.splitter_center.setStretchFactor(0, 1)
        self.splitter_center.setStretchFactor(1, 0)
        self.splitter_center.setCollapsible(0, False)
        self.splitter_center.setCollapsible(1, True)

    def _init_graphics(self) -> None:
        """Initialize the QGraphics framework"""
        # scene = GraphicsScene(0, parent=self)
        # self.graphic_view.setScene(scene)
        # self.graphic_view.setRenderHint(QPainter.Antialiasing)
        # self.graphic_view.setGeometry(20, 20, self.width(), self.height())
        self.graphics_view.setDragMode(QGraphicsView.RubberBandDrag)
        self.graphics_view.scale(self._scale, self._scale)
        self._scene = QGraphicsScene()
        self.graphics_view.setScene(self._scene)
        
        


    ###############
    #### Slots ####
    ###############
    @Slot()
    def actionTbtn(self) -> None:
        # print('_scene_count:', self._scene_count)
        scene = self._scenes[self._scene_count - 1]
        sched = scene.schedule
        print('From MainWindow:\t\t\t', end='')
        pprint(sched)
        # print('')
        self._scenes[self._scene_count - 1].plot_schedule()
        # self.printButtonPressed('callback_pushButton()')
    
    @Slot()
    def _load_schedule_from_pyfile(self) -> None:
        open_dir = QStandardPaths.standardLocations(QStandardPaths.HomeLocation)[0] if not self._open_file_dialog_opened else ''
        abs_path_filename = QFileDialog.getOpenFileName(self, self.tr("Open python file"),
                                               open_dir,
                                               self.tr("Python Files (*.py *.py3)"))
        abs_path_filename = abs_path_filename[0]

        if not abs_path_filename:       # return if empty filename (QFileDialog was canceled)
            return
        log.debug('abs_path_filename = {}.'.format(abs_path_filename))
        self._open_file_dialog_opened = True
            
        module_name = inspect.getmodulename(abs_path_filename)
        if not module_name:             # return if empty module name
            log.error('Could not load module from file \'{}\'.'.format(abs_path_filename))
            return 
        
        try:
            module = SourceFileLoader(module_name, abs_path_filename).load_module()
        except:
            log.exception('Exception occurred. Could not load module from file \'{}\'.'.format(abs_path_filename))
            return

        schedule_obj_list = dict(inspect.getmembers(module, (lambda x: type(x) == Schedule)))
        
        if not schedule_obj_list:       # return if no Schedule objects in script
            QMessageBox.warning(self,
                                self.tr('File not found'),
                                self.tr('Could not find any Schedule object in file \'{}\'.')
                                .format(os.path.basename(abs_path_filename)))
            log.info('Could not find any Schedule object in file \'{}\'.'
                     .format(os.path.basename(abs_path_filename)))
            del module
            return
        
        ret_tuple = QInputDialog.getItem(self,
                                         self.tr('Load object'),
                                         self.tr('Found the following Schedule object(s) in file.)\n\n'
                                                 'Select an object to proceed:'),
                                         schedule_obj_list.keys(),0,False)

        if not ret_tuple[1]:                  # User canceled the operation
            log.debug('Load schedule operation: user canceled')
            del module
            return
        
        self.open(schedule_obj_list[ret_tuple[0]])
        del module
        
    
    #@Slot()
    def open(self, schedule: Schedule) -> None:
        """Takes in an Schedule and place it in the schedule list."""
        #TODO: all

        #TODO: Unique hash keys
        #TODO: self.open(schedule_obj_list[ret_tuple[0])
        
        # scene = GraphicsScene(self._scene_count, schedule, self.graphics_view)
        # #scene = QGraphicsScene()
        # self._scenes[self._scene_count] = scene
        # self.graphics_view.setScene(scene)
        
        # self.graphics_view.setRenderHint(QPainter.Antialiasing)
        # # self.graphics_view.setGeometry(20, 20, self.width(), self.height())
        # self.graphics_view.setDragMode(QGraphicsView.RubberBandDrag)
        # # self.graphics_view.scale(10.0, 10.0)

        # self._scene_count += 1


        # windowLayout = QGraphicsLinearLayout(Qt.Vertical)
        vertical = QGraphicsLinearLayout(Qt.Vertical)
        # linear1 = QGraphicsLinearLayout(windowLayout)
        linear1 = QGraphicsLinearLayout(Qt.Horizontal)
        # linear1.setAlignment(Qt.AlignLeft| Qt.AlignTop)
        linear2 = QGraphicsLinearLayout(Qt.Horizontal)
        linear1.setMaximumSize(linear1.minimumSize())
        linear2.setMaximumSize(linear2.minimumSize())
        vertical.setMaximumSize(vertical.minimumSize())
        linear1.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred, QSizePolicy.DefaultType)
        linear2.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred, QSizePolicy.DefaultType)
        vertical.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred, QSizePolicy.DefaultType)
        widget = QGraphicsWidget()
        item1 = ComponentItem(self._scale)
        item2 = ComponentItem(self._scale)
        item3 = ComponentItem(self._scale)
        linear1.addItem(item1)
        linear1.setStretchFactor(item1, 1)
        linear1.addItem(item2)
        linear2.addItem(item3)
        print('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!! 1')
        vertical.addItem(linear1)
        vertical.addItem(linear2)
        print('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!! 2')
        print(f'boundingRect: {item1.boundingRect()}')
        print(f'vertical.getContentsMargins(): {vertical.getContentsMargins()}')
        print(f'linear1.getContentsMargins(): {linear1.getContentsMargins()}')
        print(f'linear2.getContentsMargins(): {linear2.getContentsMargins()}')

        # widget.setLayout(windowLayout)
        widget.setLayout(vertical)
        widget.setWindowTitle(self.tr("Basic Graphics Layouts Example"))
        print('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!! 3')

        self._scene.addItem(widget)
        
        print('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!! 4')
        self._diagrams[self._diagram_count] = widget
        self._diagram_count += 1
        self.update_statusbar(self.tr('Schedule loaded successfully'))
    
    @Slot()
    def save(self) -> None:
        """This method save an schedule."""
        #TODO: all
        self.printButtonPressed('save_schedule()')
        self.update_statusbar(self.tr('Schedule saved successfully'))

    @Slot()
    def save_as(self) -> None:
        """This method save as an schedule."""
        #TODO: all
        self.printButtonPressed('save_schedule()')
        self.update_statusbar(self.tr('Schedule saved successfully'))
    
    @Slot(bool)
    def toggle_component_info(self, checked: bool) -> None:
        """This method toggles the right hand side info window."""
        # Note: splitter handler index 0 is a hidden splitter handle far most left, use index 1
        settings = QSettings()
        range = self.splitter_center.getRange(1)    # tuple(min, max)
        
        if checked:
            self.splitter_center.restoreState(settings.value("mainwindow/splitter_center/last_state"))
            # self.splitter_center.restoreState(settings.value("splitterSizes"))
        else:
            settings.setValue("mainwindow/splitter_center/last_state", self.splitter_center.saveState())
            self.splitter_center.moveSplitter(range[1], 1)
            
    @Slot(bool)
    def toggle_exit_dialog(self, checked: bool) -> None:
        s = QSettings()
        s.setValue("mainwindow/hide_exit_dialog", checked)

    @Slot(int, int)
    def _splitter_center_moved(self, pos: int, index: int) -> None:
        """Callback method used to check if the right widget (info window) 
        has collapsed. Update the checkbutton accordingly."""
        # TODO: Custom move handler, save state on click-release?
        widths: list[int, int] = list(self.splitter_center.sizes())
        
        if widths[1] == 0:
            self.menu_node_info.setChecked(False)
        else:
            self.menu_node_info.setChecked(True)
    


    ################
    #### Events ####
    ################
    def _close_event(self, event: QCloseEvent) -> None:
        """Replaces QMainWindow default closeEvent(QCloseEvent) event"""
        s = QSettings()
        hide_dialog = s.value('mainwindow/hide_exit_dialog', False, bool)
        ret = QMessageBox.StandardButton.Yes
        
        if not hide_dialog:
            box = QMessageBox(self)
            box.setWindowTitle(self.tr('Confirm Exit'))
            box.setText('<h3>' + self.tr('Confirm Exit') + '</h3><p><br>' +
                        self.tr('Are you sure you want to exit?') +
                        '&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<br></p>')
            box.setIcon(QMessageBox.Question)
            box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            buttons: list[QAbstractButton] = box.buttons()
            buttons[0].setText(self.tr('&Exit'))
            buttons[1].setText(self.tr('&Cancel'))
            checkbox = QCheckBox(self.tr('Don\'t ask again'))
            box.setCheckBox(checkbox)
            ret = box.exec_()
        
        if ret == QMessageBox.StandardButton.Yes:
            if not hide_dialog:
                s.setValue('mainwindow/hide_exit_dialog', checkbox.isChecked())
            self._write_settings()
            log.info('Exit: {}'.format(os.path.basename(__file__)))
            event.accept()
        else:
            event.ignore()
        


    #################################
    #### Helper member functions ####
    #################################
    def printButtonPressed(self, func_name: str) -> None:
        #TODO: remove
        self.label.setText("hello")
        

        alert = QMessageBox(self)
        alert.setText("Called from " + func_name + '!')
        alert.exec_()

    def update_statusbar(self, msg: str) -> None:
        """Write the given str to the statusbar with temporarily policy."""
        self.statusbar.showMessage(msg)
        
    def _write_settings(self) -> None:
        """Write settings from MainWindow to Settings."""
        s = QSettings()
        s.setValue('mainwindow/maximized',      self.isMaximized())     # window: maximized, in X11 - alwas False
        s.setValue('mainwindow/pos',            self.pos())             # window: pos
        s.setValue('mainwindow/size',           self.size())            # window: size
        s.setValue('mainwindow/state',          self.saveState())       # toolbars, dockwidgets: pos, size
        s.setValue('mainwindow/menu/node_info', self.menu_node_info.isChecked())
        s.setValue('mainwindow/splitter/state', self.splitter_center.saveState())

        if s.isWritable():
            log.debug('Settings written to \'{}\'.'.format(s.fileName()))
        else:
            log.warning('Settings cant be saved to file, read-only.')
    
    def _read_settings(self) -> None:
        """Read settings from Settings to MainWindow."""
        s = QSettings()
        if s.value('mainwindow/maximized', defaultValue=False, type=bool):
            self.showMaximized()
        else:
            self.move(                      s.value('mainwindow/pos', self.pos()))
            self.resize(                    s.value('mainwindow/size', self.size()))
        self.restoreState(                  s.value('mainwindow/state', QByteArray()))
        self.menu_node_info.setChecked(     s.value('mainwindow/menu/node_info', True, bool))
        self.splitter_center.restoreState(  s.value('mainwindow/splitter/state', QByteArray()))
        self.menu_exit_dialog.setChecked(s.value('mainwindow/hide_exit_dialog', False, bool))

        log.debug('Settings read from \'{}\'.'.format(s.fileName()))



def start_gui():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    start_gui()
