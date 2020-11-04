import sys
import os
import threading
import subprocess
import time
from PyQt5.QtWidgets import QPushButton
import PyQt5.QtCore as QtCore
from PyQt5.QtCore import pyqtSlot
from PyQt5.QtWidgets import *
from PyQt5.QtGui import QIcon
from PyQt5.QtGui import QTextCursor
from PyQt5.QtWidgets import QApplication, QPlainTextEdit
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtGui import QFont
MYPATH = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(MYPATH, 'MicrOSDevEnv'))
import MicrOSDevEnv
import LocalMachine
import socketClient
sys.path.append(os.path.dirname(os.path.dirname(MYPATH)))
import devToolKit
APP_DIR = os.path.join(MYPATH, '../apps')
sys.path.append(APP_DIR)


DUMMY_EXEC = False


class ProgressbarTimers:
    usb_deploy = 180
    ota_update = 100
    usb_update = usb_deploy + 10
    serach_devices = 180
    simulator = 3
    lm_update = int(ota_update/2)


class ProgressbarUpdateThread(QThread):
    # Create a counter thread
    callback = pyqtSignal(int)
    eta_sec = 20

    def run(self):
        step_in_sec = self.eta_sec / 100
        cnt = 0
        while cnt < 100:
            cnt += 1
            time.sleep(step_in_sec)
            self.callback.emit(cnt)

    def terminate(self):
        self.callback.emit(99)
        time.sleep(0.3)
        self.callback.emit(100)
        super().terminate()


class micrOSGUI(QWidget):
    # HEX COLOR: https://www.hexcolortool.com/C0BBFE#1f0000
    TEXTCOLOR = "#1f0000"

    def __init__(self):
        super().__init__()
        self.title = 'micrOS devToolKit GUI dashboard'
        self.left = 10
        self.top = 10
        self.width = 850
        self.height = 400
        self.buttons_list = []
        self.pbar = None
        self.pbar_status = 0
        self.dropdown_objects_list = {}
        self.ui_state_machine = {'ignore_version_check': False, 'unsafe_ota': False}
        self.console = None
        self.device_conn_struct = []
        self.micropython_bin_pathes = []
        self.devtool_obj = MicrOSDevEnv.MicrOSDevTool(cmdgui=False, dummy_exec=DUMMY_EXEC)
        self.socketcli_obj = socketClient.ConnectionData()
        self.bgjob_thread_obj_dict = {}
        self.bgjon_progress_monitor_thread_obj_dict = {}
        # Init UI elements
        self.initUI()
        self.__thread_progress_monitor()

    def __thread_progress_monitor(self):
        th = threading.Thread(target=self.__thread_monitor_logic, daemon=True)
        th.start()

    def __thread_monitor_logic(self):
        while True:
            remove_from_key = None
            for bgprog, bgjob in self.bgjob_thread_obj_dict.items():
                if not bgjob.is_alive():
                    remove_from_key = bgprog
                    # Get job (execution) verdicts
                    job_verdict = '\n'.join(self.devtool_obj.execution_verdict)
                    self.devtool_obj.execution_verdict = []
                    # Print to console GUI
                    self.console.append_output("[DONE] Job was finished: {}\n{}".format(bgprog, job_verdict))
            if remove_from_key is not None:
                self.bgjob_thread_obj_dict.pop(remove_from_key, None)
                if remove_from_key in self.bgjon_progress_monitor_thread_obj_dict:
                    self.bgjon_progress_monitor_thread_obj_dict[remove_from_key].terminate()
                    self.bgjon_progress_monitor_thread_obj_dict.pop(remove_from_key, None)
            time.sleep(2)

    def initUI(self):
        self.setWindowTitle(self.title)
        QToolTip.setFont(QFont('Helvetica', 15))
        self.setGeometry(self.left, self.top, self.width, self.height)
        self.setFixedWidth(self.width)
        self.setFixedHeight(self.height)
        self.setStyleSheet("background-color: grey; color: {};".format(micrOSGUI.TEXTCOLOR))
        self.venv_indicator()
        self.version_label()
        self.main_ui()

    def start_bg_application_popup(self, text="Please verify data before continue:", verify_data_dict={}):
        _text = '{}\n'.format(text)
        for key, value in verify_data_dict.items():
            _text += '  {}: {}\n'.format(key, value)
        choice = QMessageBox.question(self, "Quetion", _text,
                                            QMessageBox.Yes | QMessageBox.No)
        if choice == QMessageBox.Yes:
            return True
        else:
            return False

    def main_ui(self):
        self.__create_console()
        self.devtool_obj = MicrOSDevEnv.MicrOSDevTool(cmdgui=False, dummy_exec=DUMMY_EXEC)

        self.init_progressbar()
        self.draw_logo()
        self.buttons()
        self.dropdown_board()
        self.dropdown_micropythonbin()
        self.dropdown_device()
        self.dropdown_application()
        self.ignore_version_check_checkbox()
        self.unsafe_core_update_ota_check_checkbox()

    def __create_console(self):
        dropdown_label = QLabel(self)
        dropdown_label.setText("Console".upper())
        dropdown_label.setStyleSheet("background-color : darkGray; color: {};".format(micrOSGUI.TEXTCOLOR))
        dropdown_label.setGeometry(250, 117, 420, 15)
        self.console = MyConsole(self)

    def __detect_virtualenv(self):
        def get_base_prefix_compat():
            """Get base/real prefix, or sys.prefix if there is none."""
            return getattr(sys, "base_prefix", None) or getattr(sys, "real_prefix", None) or sys.prefix

        def in_virtualenv():
            return get_base_prefix_compat() != sys.prefix
        return in_virtualenv()

    def venv_indicator(self):
        if self.__detect_virtualenv():
            label = QLabel(' [devEnv] virtualenv active', self)
            label.setGeometry(20, 5, self.width-150, 20)
            label.setStyleSheet("background-color : green; color: {};".format(micrOSGUI.TEXTCOLOR))
        else:
            label = QLabel(' [devEnv] virtualenv inactive', self)
            label.setGeometry(20, 5, self.width-150, 20)
            label.setStyleSheet("background-color : yellow; color: {};".format(micrOSGUI.TEXTCOLOR))
            label.setToolTip("Please create your dependency environment:\nvirtualenv -p python3 venv\
            \nsource venv/bin/activate\npip install -r micrOS/tools/requirements.txt")

    def version_label(self):
        width = 110
        repo_version, _ = self.devtool_obj.get_micrOS_version()
        label = QLabel("Version: {}".format(repo_version), self)
        label.setGeometry(self.width-width-20, 5, width, 20)
        label.setStyleSheet("background-color : gray; color: {}; border: 1px solid black;".format(micrOSGUI.TEXTCOLOR))

    def __validate_selected_device_with_micropython(self):
        print(self.ui_state_machine)
        selected_micropython_bin = self.ui_state_machine.get('micropython', None)
        selected_device_type = self.ui_state_machine.get('board', None)
        if selected_micropython_bin is None or selected_device_type is None:
            print("Selected\ndevice {} and/or\nmicropython {} was not selected properly,incompatibilityty.".format(selected_micropython_bin, selected_device_type))
        if selected_device_type in selected_micropython_bin:
            return True
        return False

    def buttons(self):
        height = 35
        width = 200
        yoffset = 3
        buttons = {'Deploy (USB)': ['[BOARD] [MICROPYTHON]\nInstall "empty" device.\nDeploy micropython and micrOS Framework',
                                       20, 115, width, height, self.__on_click_usb_deploy, 'darkCyan'],
                   'Update (OTA)': ['[DEVICE]\nOTA - Over The Air (wifi) update.\nUpload micrOS resources over webrepl',
                                    20, 115 + height + yoffset, width, height, self.__on_click_ota_update, 'darkCyan'],
                   'LM Update (OTA)': ['[DEVICE]\nUpdate LM (LoadModules) only\nUpload micrOS LM resources over webrepl)',
                                    20, 115 + (height + yoffset) * 2, width, height, self.__on_click_lm_update, 'darkCyan'],
                   'Update (USB)': ['[BOARD] [MICROPYTHON]\nUpdate micrOS over USB\nIt will redeploy micropython as well)',
                                      20, 115 + (height + yoffset) * 3, width, height, self.__on_click_usb_update, 'darkCyan'],
                   'Search device': ['Search online micrOS devices\nOn local wifi network.',
                                     20, 115 + (height + yoffset) * 4, width, height, self.__on_click_search_devices, 'darkCyan'],
                   'Simulator': ['Start micrOS on host.\nRuns with micropython dummy (module) interfaces',
                                      20, 115 + (height + yoffset) * 5, width, height, self.__on_click_simulator, 'lightGreen']
                   }

        for key, data_struct in buttons.items():
            tool_tip = data_struct[0]
            x = data_struct[1]
            y = data_struct[2]
            w = data_struct[3]
            h = data_struct[4]
            event_cbf = data_struct[5]
            bg = data_struct[6]

            button = QPushButton(key, self)
            button.setToolTip(tool_tip)
            button.setGeometry(x, y, w, h)
            button.setStyleSheet("QPushButton{background-color: " + bg + ";}QPushButton::pressed{background-color : green;}")
            button.clicked.connect(event_cbf)

    @pyqtSlot()
    def __on_click_usb_deploy(self):
        if 'usb_deploy' in self.bgjob_thread_obj_dict.keys():
            if self.bgjob_thread_obj_dict['usb_deploy'].is_alive():
                self.console.append_output('[usb_deploy]SKIP] already running.')
                return False
        if not self.__validate_selected_device_with_micropython():
            self.console.append_output("[usb_deploy][WARN] Selected device is not compatible with selected micropython.")
            return False
        # Verify data
        if not self.start_bg_application_popup(text="Deploy new device?", verify_data_dict={'board': self.ui_state_machine['board'],
                                                                                  'micropython': os.path.basename(self.ui_state_machine['micropython']),
                                                                                  'force': self.ui_state_machine['ignore_version_check']}):
            return

        # Start init_progressbar
        pth = ProgressbarUpdateThread()
        pth.eta_sec = ProgressbarTimers.usb_deploy
        pth.callback.connect(self.progressbar_update)
        pth.start()
        pth.setTerminationEnabled(True)
        self.bgjon_progress_monitor_thread_obj_dict['usb_deploy'] = pth

        self.console.append_output('[usb_deploy] Deploy micrOS on new device with factory config')
        # Start job
        self.devtool_obj.selected_device_type = self.ui_state_machine['board']
        self.devtool_obj.selected_micropython_bin = self.ui_state_machine['micropython']
        self.devenv_usb_deployment_is_active = True
        # Create a Thread with a function without any arguments
        self.console.append_output('[usb_deploy] |- start usb_deploy job')
        th = threading.Thread(target=self.devtool_obj.deploy_micros, kwargs={'restore': False, 'purge_conf': True}, daemon=True)
        th.start()
        self.bgjob_thread_obj_dict['usb_deploy'] = th
        self.console.append_output('[usb_deploy] |- usb_deploy job was started')
        return True

    @pyqtSlot()
    def __on_click_ota_update(self):
        if 'ota_update' in self.bgjob_thread_obj_dict.keys():
            if self.bgjob_thread_obj_dict['ota_update'].is_alive():
                self.console.append_output('[ota_update][SKIP] already running.')
                return
        # Verify data
        if not self.start_bg_application_popup(text="OTA update?", verify_data_dict={'device': self.ui_state_machine['device'],
                                                                            'force': self.ui_state_machine['ignore_version_check'],
                                                                            'unsafe_ota': self.ui_state_machine['unsafe_ota']}):
            return

        self.console.append_output('[ota_update] Upload micrOS resources to selected device.')
        # Start init_progressbar
        pth = ProgressbarUpdateThread()
        pth.eta_sec = ProgressbarTimers.ota_update
        pth.callback.connect(self.progressbar_update)
        pth.start()
        pth.setTerminationEnabled(True)
        self.bgjon_progress_monitor_thread_obj_dict['ota_update'] = pth

        # Start job
        fuid = self.ui_state_machine['device']
        ignore_version_check = self.ui_state_machine['ignore_version_check']
        unsafe_ota_update = self.ui_state_machine['unsafe_ota']
        devip = None
        for conn_data in self.device_conn_struct:
            if fuid == conn_data[0]:
                devip = conn_data[1]
        if devip is None:
            self.console.append_output("[ota_update][ERROR] Selecting device")
        self.console.append_output("[ota_update] Start OTA update on {}:{}".format(fuid, devip))
        # create a thread with a function without any arguments
        self.console.append_output('[ota_update] |- start ota_update job')
        th = threading.Thread(target=self.devtool_obj.update_with_webrepl, kwargs={'device': (fuid, devip), 'force': ignore_version_check, 'unsafe': unsafe_ota_update}, daemon=True)
        th.start()
        self.bgjob_thread_obj_dict['ota_update'] = th
        self.console.append_output('[ota_update] |- ota_update job was started')

    @pyqtSlot()
    def __on_click_usb_update(self):
        if 'usb_update' in self.bgjob_thread_obj_dict.keys():
            if self.bgjob_thread_obj_dict['usb_update'].is_alive():
                self.console.append_output('[usb_update][SKIP] already running.')
                return False
        if not self.__validate_selected_device_with_micropython():
            self.console.append_output("[usb_update] [WARN] Selected device is not compatible with selected micropython.")
            return False
        # Verify data
        if not self.start_bg_application_popup(text="Start USB update?", verify_data_dict={'board': self.ui_state_machine['board'],
                                                                                  'micropython': os.path.basename(self.ui_state_machine['micropython']),
                                                                                  'force': self.ui_state_machine['ignore_version_check']}):
            return

        self.console.append_output('[usb_update] (Re)Install micropython and upload micrOS resources')
        # Start init_progressbar
        pth = ProgressbarUpdateThread()
        pth.eta_sec = ProgressbarTimers.usb_update
        pth.callback.connect(self.progressbar_update)
        pth.start()
        pth.setTerminationEnabled(True)
        self.bgjon_progress_monitor_thread_obj_dict['usb_update'] = pth

        # Start job
        self.devtool_obj.selected_device_type = self.ui_state_machine['board']
        self.devtool_obj.selected_micropython_bin = self.ui_state_machine['micropython']
        self.devenv_usb_deployment_is_active = True
        # create a thread with a function without any arguments
        self.console.append_output('[usb_update] |- start usb_update job')
        th = threading.Thread(target=self.devtool_obj.update_micros_via_usb, kwargs={'force': self.ui_state_machine['ignore_version_check']}, daemon=True)
        th.start()
        self.bgjob_thread_obj_dict['usb_update'] = th
        self.console.append_output('[usb_update] |- usb_update job was started')
        return True

    @pyqtSlot()
    def __on_click_search_devices(self):
        if 'serach_devices' in self.bgjob_thread_obj_dict.keys():
            if self.bgjob_thread_obj_dict['serach_devices'].is_alive():
                self.console.append_output('[search_devices][SKIP] already running.')
                return

        # Verify data
        if not self.start_bg_application_popup(text="Search devices? Press Yes to continue!"):
            return

        self.console.append_output('[search_devices] Search online devices on local network')
        # Start init_progressbar
        pth = ProgressbarUpdateThread()
        pth.eta_sec = ProgressbarTimers.serach_devices
        pth.callback.connect(self.progressbar_update)
        pth.start()
        pth.setTerminationEnabled(True)
        self.bgjon_progress_monitor_thread_obj_dict['serach_devices'] = pth

        # Start job
        self.console.append_output('[search_devices] |- start serach_devices job')
        # Create a Thread with a function without any arguments
        th = threading.Thread(target=self.socketcli_obj.filter_MicrOS_devices, daemon=True)
        th.start()
        self.bgjob_thread_obj_dict['serach_devices'] = th
        self.console.append_output('[search_devices] |- serach_devices job was started')

    @pyqtSlot()
    def __on_click_simulator(self):
        if 'simulator' in self.bgjob_thread_obj_dict.keys():
            if self.bgjob_thread_obj_dict['simulator'].is_alive():
                self.console.append_output('[search_devices][SKIP] already running.')
                return

        # Verify data
        if not self.start_bg_application_popup(text="Start micrOS on host?"):
            return

        self.console.append_output('[search_devices] Start micrOS on host (local machine)')
        # Start init_progressbar
        pth = ProgressbarUpdateThread()
        pth.eta_sec = ProgressbarTimers.simulator
        pth.callback.connect(self.progressbar_update)
        pth.start()
        pth.setTerminationEnabled(True)
        self.bgjon_progress_monitor_thread_obj_dict['simulator'] = pth

        # Start job
        self.console.append_output('[search_devices] |- start simulator job')
        self.progressbar_update()
        th = threading.Thread(target=devToolKit.simulate_micrOS, daemon=True)
        th.start()
        self.bgjob_thread_obj_dict['simulator'] = th
        self.console.append_output('[search_devices] |- simulator job was started')
        self.progressbar_update()

    def __on_click_lm_update(self):
        if 'lm_update' in self.bgjob_thread_obj_dict.keys():
            if self.bgjob_thread_obj_dict['lm_update'].is_alive():
                self.console.append_output('[lm_update][SKIP] already running.')
                return

        # Verify data
        if not self.start_bg_application_popup(text="Update load modules?", verify_data_dict={'device': self.ui_state_machine['device'],
                                                                                     'force': self.ui_state_machine['ignore_version_check']}):
            return

        self.console.append_output('[lm_update] Update Load Modules over wifi')
        # Start init_progressbar
        pth = ProgressbarUpdateThread()
        pth.eta_sec = ProgressbarTimers.lm_update
        pth.callback.connect(self.progressbar_update)
        pth.start()
        pth.setTerminationEnabled(True)
        self.bgjon_progress_monitor_thread_obj_dict['lm_update'] = pth

        # Start job
        fuid = self.ui_state_machine['device']
        ignore_version_check = self.ui_state_machine['ignore_version_check']
        devip = None
        for conn_data in self.device_conn_struct:
            if fuid == conn_data[0]:
                devip = conn_data[1]
        if devip is None:
            self.console.append_output("[lm_update][ERROR] Selecting device")
        self.console.append_output("[lm_update] Start OTA lm_update on {}:{}".format(fuid, devip))
        self.console.append_output('[lm_update] |- start lm_update job')
        self.progressbar_update()
        th = threading.Thread(target=self.devtool_obj.update_with_webrepl, kwargs={'device': (fuid, devip), 'force': ignore_version_check, 'lm_only': True}, daemon=True)
        th.start()
        self.bgjob_thread_obj_dict['lm_update'] = th
        self.console.append_output('[lm_update] |- lm_update job was started')
        self.progressbar_update()

    def draw_logo(self):
        """
        Logo as static label
        label = QLabel(self)
        label.setGeometry(20, 30, 80, 80)
        label.setScaledContents(True)
        logo_path = os.path.join(MYPATH, '../media/logo_mini.png')
        pixmap = QPixmap(logo_path)
        label.setPixmap(pixmap)
        label.setToolTip("micrOS: https://github.com/BxNxM/micrOS")
        """

        logo_path = os.path.join(MYPATH, '../media/logo_mini.png')
        button = QPushButton('', self)
        button.setIcon(QIcon(logo_path))
        button.setIconSize(QtCore.QSize(80, 80))
        button.setGeometry(20, 30, 80, 80)
        button.setToolTip("Open micrOS repo documentation")
        button.setStyleSheet('border: 0px solid black;')
        button.clicked.connect(self.__open_micrOS_URL)

    def init_progressbar(self):
        # creating progress bar
        self.pbar = QProgressBar(self)

        # setting its geometry
        self.pbar.setGeometry(20, self.height-30, self.width-50, 30)

    def progressbar_update(self, value=None, reset=False):
        if reset:
            self.pbar_status = 0
        if value is not None and 0 <= value <= 100:
            self.pbar_status = value
        self.pbar_status = self.pbar_status + 1 if self.pbar_status < 100 else 0
        self.pbar.setValue(self.pbar_status)

    def draw(self):
        self.show()

    def dropdown_board(self):
        dropdown_label = QLabel(self)
        dropdown_label.setText("Select board".upper())
        dropdown_label.setGeometry(120, 30, 160, 30)

        # creating a combo box widget
        combo_box = QComboBox(self)
        combo_box.setToolTip("Select board type to install micrOS:\nmicropython + micrOS resources.")

        # setting geometry of combo box
        combo_box.setGeometry(120, 60, 160, 30)

        # GET DEVICE TYPES
        geek_list = self.devtool_obj.dev_types_and_cmds.keys()
        self.ui_state_machine['board'] = list(geek_list)[0]

        # making it editable
        combo_box.setEditable(False)

        # adding list of items to combo box
        combo_box.addItems(geek_list)

        combo_box.setStyleSheet("QComboBox"
                                     "{"
                                     "border : 3px solid purple;"
                                     "}"
                                     "QComboBox::on"
                                     "{"
                                     "border : 4px solid;"
                                     "border-color : orange orange orange orange;"
                                
                                     "}")

        # getting view part of combo box
        view = combo_box.view()

        # making view box hidden
        view.setHidden(False)

        self.dropdown_objects_list['board'] = combo_box
        combo_box.activated.connect(self.__on_click_board_dropdown)

    def dropdown_micropythonbin(self):
        dropdown_label = QLabel(self)
        dropdown_label.setText("Select micropython".upper())
        dropdown_label.setGeometry(290, 30, 200, 30)

        # creating a combo box widget
        combo_box = QComboBox(self)
        combo_box.setToolTip("Select micropython binary for the selected board.")

        # setting geometry of combo box
        combo_box.setGeometry(290, 60, 200, 30)

        # GET MICROPYTHON BINARIES
        self.micropython_bin_pathes = self.devtool_obj.get_micropython_binaries()
        geek_list = [os.path.basename(path) for path in self.micropython_bin_pathes]
        self.ui_state_machine['micropython'] = geek_list[0]

        # making it editable
        combo_box.setEditable(False)

        # adding list of items to combo box
        combo_box.addItems(geek_list)

        combo_box.setStyleSheet("QComboBox"
                                "{"
                                "border : 3px solid green;"
                                "}"
                                "QComboBox::on"
                                "{"
                                "border : 4px solid;"
                                "border-color : orange orange orange orange;"

                                "}")

        # getting view part of combo box
        view = combo_box.view()

        # making view box hidden
        view.setHidden(False)

        self.dropdown_objects_list['micropython'] = combo_box
        combo_box.activated.connect(self.__on_click_micropython_dropdown)

    def dropdown_device(self):
        dropdown_label = QLabel(self)
        dropdown_label.setText("Select device".upper())
        dropdown_label.setGeometry(500, 35, 170, 20)

        # creating a combo box widget
        combo_box = QComboBox(self)
        combo_box.setToolTip("Select device for OTA operations or APP execution.")


        # setting geometry of combo box
        combo_box.setGeometry(500, 60, 170, 30)

        # Get stored devices
        conn_data = self.socketcli_obj
        conn_data.read_MicrOS_device_cache()
        self.device_conn_struct = []
        for uid in conn_data.MICROS_DEV_IP_DICT.keys():
            devip = conn_data.MICROS_DEV_IP_DICT[uid][0]
            fuid = conn_data.MICROS_DEV_IP_DICT[uid][2]
            tmp = (fuid, devip, uid)
            self.device_conn_struct.append(tmp)
            print("\t{}".format(tmp))

        # Get devices friendly unique identifier
        geek_list = [fuid[0] for fuid in self.device_conn_struct]
        self.ui_state_machine['device'] = geek_list[0]

        # making it editable
        combo_box.setEditable(False)

        # adding list of items to combo box
        combo_box.addItems(geek_list)

        combo_box.setStyleSheet("QComboBox"
                                "{"
                                "border : 3px solid darkCyan;"
                                "}"
                                "QComboBox::on"
                                "{"
                                "border : 4px solid;"
                                "border-color : orange orange orange orange;"
                                "}")

        # getting view part of combo box
        view = combo_box.view()

        # making view box hidden
        view.setHidden(False)

        self.dropdown_objects_list['device'] = combo_box
        combo_box.activated.connect(self.__on_click_device_dropdown)

    def dropdown_application(self):
        start_x = 682
        y_offset = 80
        dropdown_label = QLabel(self)
        dropdown_label.setText("Select app".upper())
        dropdown_label.setGeometry(start_x, y_offset+35, 150, 20)

        # creating a combo box widget
        combo_box = QComboBox(self)
        combo_box.setToolTip("[DEVICE] Select python application to execute")

        # setting geometry of combo box
        combo_box.setGeometry(start_x, y_offset+60, 150, 30)

        # Get stored devices
        conn_data = self.socketcli_obj
        conn_data.read_MicrOS_device_cache()
        self.device_conn_struct = []
        for uid in conn_data.MICROS_DEV_IP_DICT.keys():
            devip = conn_data.MICROS_DEV_IP_DICT[uid][0]
            fuid = conn_data.MICROS_DEV_IP_DICT[uid][2]
            tmp = (fuid, devip, uid)
            self.device_conn_struct.append(tmp)
            print("\t{}".format(tmp))

        # Get devices friendly unique identifier
        app_list = [app.replace('.py', '') for app in LocalMachine.FileHandler.list_dir(APP_DIR) if app.endswith('.py') and not app.startswith('Template')]
        self.ui_state_machine['app'] = app_list[0]

        # making it editable
        combo_box.setEditable(False)

        # adding list of items to combo box
        combo_box.addItems(app_list)

        combo_box.setStyleSheet("QComboBox"
                                "{"
                                "border : 3px solid blue;"
                                "}"
                                "QComboBox::on"
                                "{"
                                "border : 4px solid;"
                                "border-color : orange orange orange orange;"
                                "}")

        # getting view part of combo box
        view = combo_box.view()

        # making view box hidden
        view.setHidden(False)

        self.dropdown_objects_list['app'] = combo_box
        combo_box.activated.connect(self.__on_click_app_dropdown)

        # Set execution button
        button = QPushButton("Execute", self)
        button.setToolTip("[DEVICE] Execute selected application on the selected device")
        button.setGeometry(start_x, y_offset+90, 150, 20)
        button.setStyleSheet("QPushButton{background-color: darkCyan;}QPushButton::pressed{background-color : green;}")
        button.clicked.connect(self.__on_click_exec_app)

    def __on_click_exec_app(self):
        """
        Execute application with selected device here
        """
        def __execute_app(app_name, dev_name, app_postfix='_app'):
            app_name = "{}{}".format(app_name, app_postfix)
            print("[APP] import {}".format(app_name))
            exec("import {}".format(app_name))
            print("[APP] {}.app(devfid='{}')".format(app_name, dev_name))
            return_value = eval("{}.app(devfid='{}')".format(app_name, dev_name))
            if return_value is not None:
                print(return_value)

        selected_app = self.ui_state_machine['app']
        selected_device = self.ui_state_machine['device']
        process_key = "{}_{}".format(selected_app, selected_device)

        if process_key in self.bgjob_thread_obj_dict.keys():
            if self.bgjob_thread_obj_dict[process_key].is_alive():
                self.console.append_output('[{}][SKIP] already running.'.format(process_key))
                return

        print("Execute: {} on {}".format(selected_app, selected_device))
        try:
            app_name = selected_app.replace('_app', '')
            th = threading.Thread(target=__execute_app,
                                  args=(app_name, selected_device),
                                  daemon=True)
            th.start()
            self.bgjob_thread_obj_dict[process_key] = th
            self.console.append_output('[{}] |- application was started'.format(process_key))
        except Exception as e:
            print("Application error: {}".format(e))

    def __on_click_app_dropdown(self, index):
        """
            Update dataset with selected application
        """
        self.ui_state_machine['app'] = self.dropdown_objects_list['app'].itemText(index)
        self.get_widget_values()

    def get_widget_values(self):
        self.__show_gui_state_on_console()
        return self.ui_state_machine

    def __on_click_board_dropdown(self, index):
        self.ui_state_machine['board'] = self.dropdown_objects_list['board'].itemText(index)
        self.get_widget_values()

    def __on_click_micropython_dropdown(self, index):
        micropython = self.dropdown_objects_list['micropython'].itemText(index)
        self.ui_state_machine['micropython'] = [path for path in self.micropython_bin_pathes if micropython in path][0]
        self.get_widget_values()

    def __on_click_device_dropdown(self, index):
        self.ui_state_machine['device'] = self.dropdown_objects_list['device'].itemText(index)
        self.get_widget_values()

    def __show_gui_state_on_console(self):
        self.console.append_output("micrOS GUI Info")
        for key, value in self.ui_state_machine.items():
            self.console.append_output("  {}: {}".format(key, value))

    def ignore_version_check_checkbox(self):
        checkbox = QCheckBox('Ignore version check', self)
        checkbox.setStyleSheet("QCheckBox::indicator:hover{background-color: yellow;}")
        checkbox.move(20, self.height-50)
        checkbox.setToolTip("[OTA][USB]\nIgnore version check.\nYou can force resource update on the same software version.")
        checkbox.toggled.connect(self.__on_click_ignore_version_check)

    def unsafe_core_update_ota_check_checkbox(self):
        checkbox = QCheckBox('FSCO', self)      # ForceSystemCoreOta update
        checkbox.setStyleSheet("QCheckBox::indicator:hover{background-color: red;}")
        checkbox.move(self.width-240, self.height-50)
        checkbox.setToolTip("[!!!][OTA] ForceSystemCoreOta update.\nIn case of failure, USB re-deployment required!")
        checkbox.toggled.connect(self.__on_click_unsafe_core_update_ota)

    @pyqtSlot()
    def __on_click_ignore_version_check(self):
        radioBtn = self.sender()
        if radioBtn.isChecked():
            self.ui_state_machine['ignore_version_check'] = True
        else:
            self.ui_state_machine['ignore_version_check'] = False
        self.__show_gui_state_on_console()

    def __on_click_unsafe_core_update_ota(self):
        radioBtn = self.sender()
        if radioBtn.isChecked():
            self.ui_state_machine['unsafe_ota'] = True
        else:
            self.ui_state_machine['unsafe_ota'] = False
        self.__show_gui_state_on_console()

    def __open_micrOS_URL(self):
        self.console.append_output("Open micrOS repo documentation")
        url = 'https://github.com/BxNxM/micrOS'
        if sys.platform == 'win32':
            os.startfile(url)
        elif sys.platform == 'darwin':
            subprocess.Popen(['open', url])
        else:
            try:
                subprocess.Popen(['xdg-open', url])
            except OSError:
                print('Please open a browser on: {}'.format(url))


class MyConsole(QPlainTextEdit):
    console = None
    lock = False

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setReadOnly(True)
        self.setMaximumBlockCount(20000)  # limit console to 20000 lines
        self._cursor_output = self.textCursor()
        self.setGeometry(250, 132, 420, 210)
        MyConsole.console = self

    @pyqtSlot(str)
    def append_output(self, text, end='\n'):
        if not MyConsole.lock:
            MyConsole.lock = True
            try:
                self._cursor_output.insertText("{}{}".format(text, end))
                self.scroll_to_last_line()
            except Exception as e:
                print("MyConsole.append_output failure: {}".format(e))
            MyConsole.lock = False

    def scroll_to_last_line(self):
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.movePosition(QTextCursor.Up if cursor.atBlockStart() else QTextCursor.StartOfLine)
        self.setTextCursor(cursor)


def main():
    app = QApplication(sys.argv)
    ex = micrOSGUI()
    ex.draw()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
