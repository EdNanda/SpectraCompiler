import sys
import matplotlib

matplotlib.use('Qt5Agg')

from PyQt5 import QtWidgets, QtGui
from PyQt5.QtWidgets import QWidget, QLineEdit, QFormLayout, QHBoxLayout, QSpacerItem, QGridLayout
from PyQt5.QtWidgets import QFrame, QPushButton, QCheckBox, QLabel, QToolButton, QTextEdit, QScrollBar
from PyQt5.QtWidgets import QSizePolicy, QMessageBox
from PyQt5.QtCore import QObject, QThread, pyqtSignal, QRunnable, pyqtSlot, QThreadPool
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg, NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
from matplotlib import rcParams

rcParams.update({'figure.autolayout': True})
from seabreeze.spectrometers import Spectrometer
import pandas as pd
import numpy as np
import os
import math
import random
from time import time, sleep, strftime, localtime
from datetime import datetime
import traceback
import utils
import pathlib


# global size
# size = 2046


## These two classes make parallel measurement of PL spectra possible
class WorkerSignals(QObject):
    finished = pyqtSignal()
    error = pyqtSignal(tuple)
    result = pyqtSignal(object)
    progress = pyqtSignal(object)


class Worker(QRunnable):

    def __init__(self, fn, *args, **kwargs):
        super(Worker, self).__init__()
        # Store constructor arguments (re-used for processing)
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()
        self.kwargs['progress_callback'] = self.signals.progress

    @pyqtSlot()
    def run(self):
        try:
            results = self.fn(*self.args, **self.kwargs)
        except:
            traceback.print_exc()
            exctype, value = sys.exc_info()[:2]
            self.signals.error.emit((exctype, value, traceback.format_exc()))
        else:
            self.signals.result.emit(results)  # Return the result of the processing
        finally:
            self.signals.finished.emit()  # Done


class Worker2(QObject):
    finished = pyqtSignal()
    progress = pyqtSignal(int)
    result = pyqtSignal(object, object, object)

    def __init__(self, total_frames, array_size, skip, is_dark_data, is_bright_data, dark_mean, bright_mean, timestamp):
        super(Worker2, self).__init__()
        # Store constructor arguments (re-used for processing)
        self.total_frames = total_frames
        self.array_size = array_size
        self.skip = skip  # TODO: make sure skip is non-zero --ashis
        self.is_dark_data = is_dark_data
        self.is_bright_data = is_bright_data
        self.dark_mean = dark_mean
        self.start_time = timestamp
        self.bright_mean = bright_mean
        self.init_spectra_measurement()

    @pyqtSlot(object)
    def run(self, spect):
        # print("Run start")
        # print(spect.shape)
        yarray = utils.spectra_math(spect, self.is_dark_data, self.is_bright_data, self.dark_mean, self.bright_mean)
        self.gathering_spectra_counts(spect, yarray)
        # print("Run end")

    def init_spectra_measurement(self):
        # self.set_integration_time()  ## Reset int time to what is in entry field
        self.spectra_meas_array = np.ones((self.total_frames, self.array_size))
        self.spectra_raw_array = np.ones((self.total_frames, self.array_size))
        self.time_meas_array = np.ones(self.total_frames)
        self.spectra_meas_array[:] = np.nan
        self.spectra_raw_array[:] = np.nan
        self.time_meas_array[:] = np.nan
        # self.measuring = True
        # self.spectra_measurement_bool = True
        self.spectra_counter = 0
        # self.counter = 0
        self.array_count = 0

    def gathering_spectra_counts(self, ydata, yarray):
        # print('gathering_spectra_counts')
        '''
        if self.spectra_counter == 0:  #TODO: do these before starting thread
            self.dis_enable_widgets(True)
            self.create_folder(True) 
        '''
        if self.spectra_counter < self.total_frames:
            if self.spectra_counter == 0 or self.spectra_counter % self.skip == 0:
                # self.spectra_raw_array[self.spectra_counter] = np.array(self.ydata)
                # self.spectra_meas_array[self.spectra_counter] = np.array(self.yarray)
                # self.time_meas_array[self.spectra_counter] = np.round(time()-self.start_time,4)
                self.spectra_raw_array[self.array_count] = np.array(ydata)
                self.spectra_meas_array[self.array_count] = np.array(yarray)
                self.time_meas_array[self.array_count] = np.round(time() - self.start_time, 4)
                self.array_count += 1
            self.spectra_counter += 1
            self.progress.emit(self.spectra_counter)
        else:
            self.time_meas_array = self.time_meas_array - self.time_meas_array[0]
            self.spectra_measurement_bool = False
            self.spectra_data = True
            self.result.emit(self.spectra_raw_array, self.spectra_meas_array, self.time_meas_array)
            self.finished.emit()
            print('finished thread.....')


class MplCanvas(FigureCanvasQTAgg):
    '''
    This makes the plot happen
    '''

    def __init__(self, parent=None, width=5, height=4, dpi=300, tight_layout=True):
        fig = Figure(figsize=(width, height), dpi=dpi)
        self.axes = fig.add_subplot(111)
        self.axes.set_xlabel('Wavelength (nm)')
        self.axes.set_ylabel('Intensity (a.u.)')
        self.axes.grid(True, linestyle='--')
        self.axes.set_xlim([330, 1030])
        # self.axes.set_xlim([400,850])
        self.axes.set_ylim([0, 68000])
        # fig.tight_layout() # to remove warning --ashis
        super(MplCanvas, self).__init__(fig)


class MainWindow(QtWidgets.QMainWindow):

    def __init__(self, icon_path: pathlib.Path, *args, **kwargs):
        '''
        Initialize parameters
        :param args:
        :param kwargs:
        '''
        super(MainWindow, self).__init__(*args, **kwargs)
        self.dark_measurement_bool = False  # TODO: change bool variable naming convention --ashis
        self.bright_measurement_bool = False
        self.spectra_measurement_bool = False
        self.dark_data = False
        self.bright_data = False
        self.spectra_data = False
        self.show_raw = False
        self.measuring = False

        self.dark_mean = None  # TODO: add all missing variables here --ashis
        self.bright_mean = None

        self.setWindowTitle("Spectra Compiler")
        self.setWindowIcon(QtGui.QIcon(str(icon_path.joinpath("rainbow.ico"))))
        np.seterr(divide='ignore', invalid='ignore')

        try:
            self.spec = Spectrometer.from_first_available()
            self.spec.integration_time_micros(200000)
            self.xdata = self.spec.wavelengths()[2:]
            self.array_size = len(self.xdata)
            self.spec_counts = []
            self.spectrometer = True
        except:
            self.array_size = 2046
            self.xdata = np.linspace(340, 1015, self.array_size)
            self.spectrometer = False

        self.threadpool = QThreadPool()
        self.spec_thread = QThread()

        self.statusBar().showMessage("Program by Edgar Nandayapa - 2021", 10000)
        # self.statusBar().showMessage("Multithreading with maximum %d threads" % self.threadpool.maxThreadCount(),10000)

        self.create_widgets()
        self.arr_scrbar = utils.array_for_scrollbar()  ##This function makes an array for the scrollbar
        self.set_integration_time()  ##This resets the starting integration time value
        self.button_actions()  ##Set button actions

    def create_widgets(self):  # TODO: could rename to setupUi --ashis
        widget = QWidget()
        layH1 = QHBoxLayout()  ##Main (horizontal) Layout

        ## Create the maptlotlib FigureCanvas for plotting
        self.canvas = MplCanvas(self, width=5, height=4, dpi=100)
        self.canvas.axes.set_xlim([min(self.xdata) * 0.98, max(self.xdata) * 1.02])
        self.canvas.setMinimumWidth(600)  ##Fix width so it doesn't change
        self.canvas.setMinimumHeight(450)
        self.setCentralWidget(self.canvas)
        self._plot_ref = None
        ## Add a toolbar to control plotting area
        toolbar = NavigationToolbar(self.canvas, self)

        self.Braw = QCheckBox("Show Raw Data")  ## Button to select visualization
        self.Brange = QCheckBox("Fix y-axis")  ## Button to select visualization
        self.BSavePlot = QCheckBox("Create heatplot")
        self.BSavePlot.setChecked(True)

        ### Place all widgets
        ## First in a grid
        LBgrid = QGridLayout()
        LBgrid.addWidget(QLabel(" "), 0, 0)
        LBgrid.addWidget(self.Braw, 0, 1)
        LBgrid.addWidget(self.Brange, 0, 2)
        LBgrid.addWidget(self.BSavePlot, 0, 3)
        LBgrid.addWidget(QLabel(" "), 0, 4)
        ## Add to (first) vertical layout
        layV1 = QtWidgets.QVBoxLayout()
        ## Add Widgets to the layout
        layV1.addWidget(toolbar)
        layV1.addWidget(self.canvas)
        layV1.addLayout(LBgrid)

        ## Add first vertical layout to the main horizontal one
        layH1.addLayout(layV1, 5)

        ### Make second vertical layout for measurement settings
        layV2 = QtWidgets.QVBoxLayout()
        verticalSpacerV2 = QSpacerItem(20, 10, QSizePolicy.Minimum, QSizePolicy.Expanding)  ## To center the layout

        ## Relevant fields for sample, user and folder names
        self.LEsample = QLineEdit()
        self.LEuser = QLineEdit()
        self.LEfolder = QLineEdit()
        # self.LEsample.setMaximumWidth(350)
        # self.LEuser.setMaximumWidth(350)
        # self.LEfolder.setMaximumWidth(350)

        ## Make a grid layout and add labels and fields to it
        LGsetup = QGridLayout()
        LGsetup.addWidget(QLabel("Sample:"), 0, 0)
        LGsetup.addWidget(self.LEsample, 0, 1)
        LGsetup.addWidget(QLabel("User:"), 1, 0)
        LGsetup.addWidget(self.LEuser, 1, 1)
        self.Bpath = QToolButton()
        self.Bpath.setToolTip("Create a folder containing today's date")
        LGsetup.addWidget(self.Bpath, 1, 2)
        LGsetup.addWidget(QLabel("Folder:"), 2, 0)
        LGsetup.addWidget(self.LEfolder, 2, 1)
        self.Bfolder = QToolButton()
        self.Bfolder.setToolTip("Choose a folder where to save the data")
        LGsetup.addWidget(self.Bfolder, 2, 2)

        ## Set defaults
        self.Bpath.setText("\U0001F4C6")
        self.Bfolder.setText("\U0001F4C1")
        self.LEfolder.setText("C:/Data/")

        ## Second set of setup values
        LTsetup = QGridLayout()
        self.LEinttime = QLineEdit()
        self.LEdeltime = QLineEdit()
        self.LEmeatime = QLineEdit()
        self.LEskip = QLineEdit()
        # self.LEinttime.setMaximumWidth(160)
        # self.LEdeltime.setMaximumWidth(160)
        # self.LEmeatime.setMaximumWidth(160)
        self.Binttime = QToolButton()
        self.Binttime.setText("SET")
        self.SBinttime = QScrollBar()
        self.SBinttime.setOrientation(Qt.Horizontal)
        self.SBinttime.setStyleSheet("background : white;")

        ## Position labels and field in a grid
        LTsetup.addWidget(QLabel(" "), 0, 0)
        LTsetup.addWidget(QLabel("Integration Time (s)"), 1, 0)
        LTsetup.addWidget(self.LEinttime, 1, 1)
        LTsetup.addWidget(self.Binttime, 1, 2)
        LTsetup.addWidget(self.SBinttime, 2, 0, 1, 2)
        LTsetup.addWidget(QLabel("Delay start by (s)"), 3, 0)
        LTsetup.addWidget(self.LEdeltime, 3, 1)
        LTsetup.addWidget(QLabel("Measurement Length (s)"), 4, 0)
        LTsetup.addWidget(self.LEmeatime, 4, 1)
        LTsetup.addWidget(QLabel("Skip # measurements"), 5, 0)
        LTsetup.addWidget(self.LEskip, 5, 1)
        LTsetup.addWidget(QLabel(" "), 6, 0)

        ## Set defaults
        self.LEinttime.setText("0.2")
        self.LEdeltime.setText("0")
        self.LEmeatime.setText("10")
        self.LEskip.setText("1")

        ## Third set of setup values
        self.LEcurave = QLineEdit()
        self.LEcurave.setText("5")
        # self.LEcurave.setMaximumWidth(160)
        self.BBrightMeas = QPushButton("Measure")
        self.BBrightMeas.setStyleSheet("color : red;")
        self.BBrightDel = QToolButton()
        self.BBrightDel.setText("\U0001F5D1")
        self.BBrightDel.setToolTip("Delete previous measurement")
        self.BDarkMeas = QPushButton("Measure")
        self.BDarkMeas.setStyleSheet("color : red;")
        self.BDarkDel = QToolButton()
        self.BDarkDel.setText("\U0001F5D1")
        self.BDarkDel.setToolTip("Delete previous measurement")
        # Lsetup = QFormLayout()
        # Lsetup.addRow(" ",QFrame())
        # Lsetup.addRow("Bright measurement",self.BBrightMeas)
        # Lsetup.addRow("Dark measurement",self.BDarkMeas)
        # Lsetup.addRow("Curves to average",self.LEcurave)
        # Lsetup.addRow(" ",QFrame())
        Lsetup = QGridLayout()
        Lsetup.addWidget(QLabel(" "), 0, 0)
        Lsetup.addWidget(QLabel("Bright measurement"), 1, 0)
        Lsetup.addWidget(self.BBrightMeas, 1, 1)
        Lsetup.addWidget(self.BBrightDel, 1, 2)
        Lsetup.addWidget(QLabel("Dark measurement"), 2, 0)
        Lsetup.addWidget(self.BDarkMeas, 2, 1)
        Lsetup.addWidget(self.BDarkDel, 2, 2)
        Lsetup.addWidget(QLabel("Curves to average"), 3, 0)
        Lsetup.addWidget(self.LEcurave, 3, 1)
        Lsetup.addWidget(QLabel(" "), 4, 0)

        ## Four set of setup values
        LGlabels = QGridLayout()
        self.LAelapse = QLabel("00:00")
        self.LAelapse.setFont(QtGui.QFont("Arial", 10, weight=QtGui.QFont.Bold))
        self.LAframes = QLabel("000")
        self.LAframes.setFont(QtGui.QFont("Arial", 10, weight=QtGui.QFont.Bold))
        LGlabels.addWidget(QLabel("Elapsed time:"), 0, 0)
        LGlabels.addWidget(self.LAelapse, 0, 1)
        LGlabels.addWidget(QLabel("       Frames"), 0, 2)
        LGlabels.addWidget(self.LAframes, 0, 3)
        self.BStart = QPushButton("START")
        self.BStart.setFont(QFont("Arial", 14, QFont.Bold))
        self.BStart.setStyleSheet("color : green;")
        LGlabels.addWidget(self.BStart, 1, 0, 1, 4)
        # Lsetup.addRow(" ",QFrame())

        ## Position all these sets into the second layout V2
        layV2.addItem(verticalSpacerV2)
        layV2.addLayout(LGsetup)
        layV2.addLayout(LTsetup)
        layV2.addLayout(Lsetup)
        layV2.addLayout(LGlabels)
        layV2.addItem(verticalSpacerV2)

        ## Add to main horizontal layout with a spacer (for good looks)
        horizontalSpacerH1 = QSpacerItem(10, 70, QSizePolicy.Minimum, QSizePolicy.Minimum)
        layH1.addItem(horizontalSpacerH1)
        layH1.addLayout(layV2, 3)

        ### Make third vertical layout for metadata
        layV3 = QtWidgets.QVBoxLayout()

        ## List of relevant values
        self.exp_labels = ["Material", "Additives", "Concentration", "Solvents", "Solvents Ratio", "Substrate"]
        self.exp_vars = []
        self.glv_labels = ["Temperature ('C)", "Water content (ppm)", "Oxygen content (ppm)"]
        self.glv_vars = []

        self.setup_labs = ["Sample", "User", "Folder", "Integration Time (s)", "Delay time (s)",
                           "Measurement length (s)",
                           "Averaged Curves"]
        self.setup_vals = [self.LEsample, self.LEuser, self.LEfolder, self.LEinttime, self.LEdeltime, self.LEmeatime,
                           self.LEcurave]

        ## Make a new layout and position relevant values
        LmDataExp = QFormLayout()
        LmDataExp.addRow(QLabel('EXPERIMENT VARIABLES'))

        for ev in self.exp_labels:
            Evar = QLineEdit()
            # Evar.setMaximumWidth(160)
            LmDataExp.addRow(ev, Evar)
            self.exp_vars.append(Evar)

        LmDataBox = QFormLayout()
        LmDataBox.addRow(" ", QFrame())
        LmDataBox.addRow(QLabel('GLOVEBOX VARIABLES'))
        for eb in self.glv_labels:
            Evar = QLineEdit()
            # Evar.setMaximumWidth(120)
            LmDataBox.addRow(eb, Evar)
            self.glv_vars.append(Evar)
        self.com_labels = QTextEdit()
        self.com_labels.setMaximumHeight(50)
        self.com_labels.setMaximumWidth(120)
        LmDataBox.addRow("Comments", self.com_labels)

        LGmeta = QGridLayout()
        self.BsaveM = QToolButton()
        self.BloadM = QToolButton()
        self.BsaveM.setText("Save")
        self.BloadM.setText("Load")

        LGmeta.addWidget(QLabel(""), 0, 0)
        LGmeta.addWidget(QLabel("Metadata:"), 0, 1)
        LGmeta.addWidget(self.BsaveM, 0, 2)
        LGmeta.addWidget(self.BloadM, 0, 3)

        ## Position layouts inside of the third vertical layout V3
        layV3.addItem(verticalSpacerV2)
        layV3.addLayout(LmDataExp)
        layV3.addLayout(LmDataBox)
        layV3.addLayout(LGmeta)
        layV3.addItem(verticalSpacerV2)

        ## Add to main horizontal layout with a spacer (for good looks)
        horizontalSpacerH2 = QSpacerItem(30, 70, QSizePolicy.Minimum, QSizePolicy.Minimum)
        layH1.addItem(horizontalSpacerH2)
        layH1.addLayout(layV3, 2)

        # self.statusBar = QStatusBar()

        widget.setLayout(layH1)
        self.setCentralWidget(widget)
        self.show()

    def button_actions(self):
        self.send_to_Qthread()
        self.folder = self.LEfolder.text()
        self.Bfolder.clicked.connect(self.select_folder)
        self.Bpath.clicked.connect(self.automatic_folder)
        self.BsaveM.clicked.connect(self.save_meta)
        self.BloadM.clicked.connect(self.load_meta)
        self.Binttime.clicked.connect(self.set_integration_time)
        self.LEinttime.returnPressed.connect(self.set_integration_time)
        self.SBinttime.valueChanged.connect(self.scrollbar_action)
        self.BDarkMeas.clicked.connect(self.dark_measurement)
        self.BBrightMeas.clicked.connect(self.bright_measurement)
        self.BStart.clicked.connect(self.press_start)
        self.LEmeatime.textChanged.connect(self.update_number_of_frames)
        self.Brange.stateChanged.connect(self.set_axis_range)
        self.Braw.stateChanged.connect(self.set_axis_range)
        self.BBrightDel.clicked.connect(self.delete_bright_measurement)
        self.BDarkDel.clicked.connect(self.delete_dark_measurement)

    @pyqtSlot()
    def select_folder(self):
        old_folder = self.LEfolder.text()  ##Read entry line

        if not old_folder:  ## If empty, go to default
            old_folder = "C:/Data/"

        ## Select directory from selection
        directory = QtWidgets.QFileDialog.getExistingDirectory(self, "Where do you want your data saved?", old_folder)

        if not directory:  ## if cancelled, keep the old one
            directory = old_folder

        self.LEfolder.setText(directory)
        self.folder = directory

        ## Arrow function, to create folderpath with User and Date

    @pyqtSlot()
    def automatic_folder(self):
        user = self.LEuser.text()
        folder = self.LEfolder.text()
        date = datetime.now().strftime("%Y%m%d")

        if len(user) > 0:
            newfolder = folder + user + "/" + date + "/"
        else:
            newfolder = folder + date

        self.LEfolder.setText(newfolder)
        self.folder = newfolder

        self.create_folder(False)

        self.Bpath.setEnabled(False)

    def create_folder(self, sample, retry=1):
        self.folder = self.LEfolder.text()
        if self.folder[-1] != "/":
            self.folder = self.folder + "/"  ## Add "/" if non existent
            self.LEfolder.setText(self.folder)
        else:
            pass
        if sample:
            self.sample = self.LEsample.text()
            self.folder = self.folder + self.sample + "/"

            ## If sample name is duplicated, make a "-d#" folder
            if os.path.exists(self.folder):
                self.folder = self.folder.rsplit("/", 1)[0] + "-d" + str(retry) + "/"
                if os.path.exists(self.folder):
                    retry += 1
                    self.create_folder(True, retry)
                self.statusBar().showMessage("Sample is duplicated", 10000)

        ##If folders don't exist, make them
        if not os.path.exists(self.folder):
            os.makedirs(self.folder)
            self.statusBar().showMessage("Folder " + self.folder + " created", 5000)
        else:
            pass

    @pyqtSlot()
    def save_meta(self):
        self.create_folder(False)
        self.gather_all_metadata()
        metadata = pd.DataFrame.from_dict(self.meta_dict, orient='index')
        metadata.to_csv(self.folder + "metadata.csv", header=False)
        self.statusBar().showMessage("Metadata file saved successfully", 5000)

    @pyqtSlot()
    def load_meta(self):
        folder = self.LEfolder.text()
        metafile = QtWidgets.QFileDialog.getOpenFileName(self, "Choose your metadata file", folder)
        # print(metafile[0])
        metadata = pd.read_csv(metafile[0], header=None, index_col=0, squeeze=True, nrows=21)
        # print(metadata)
        labels = self.setup_labs + self.exp_labels
        objects = self.setup_vals + self.exp_vars

        for cc, oo in enumerate(objects):
            if labels[cc] == "Sample":
                pass
            else:
                if labels[cc] == "Material":
                    try:
                        oo.setText(metadata["Perovskite"])
                    except:
                        oo.setText(str(metadata["Material"]))
                else:
                    oo.setText(str(metadata[labels[cc]]))
        self.LEfolder.setText(metadata["Folder"])

        self.statusBar().showMessage("Metadata successfully loaded", 5000)

    def gather_all_metadata(self):
        self.sample = self.LEsample.text()
        self.meta_dict = {}  ## All variables will be collected here
        ## Gather all relevant information
        # addit_data = [self.dark_data, self.bright_data]
        # addit_labl = ["Dark measurement", "Bright measurement"]

        all_metaD_labs = self.setup_labs + self.exp_labels + self.glv_labels
        all_metaD_vals = self.setup_vals + self.exp_vars + self.glv_vars

        ## Add data to dictionary
        try:
            self.meta_dict["Date"] = strftime("%H:%M:%S - %d.%m.%Y", localtime(self.start_time))
        except:
            self.meta_dict["Date"] = strftime("%H:%M:%S - %d.%m.%Y", localtime(time()))
        self.meta_dict["Location"] = utils.get_host_name()
        try:
            self.meta_dict["Device"] = (self.spec.model + " - Serial No.:" + self.spec.serial_number)
        except:
            pass

        for cc, di in enumerate(all_metaD_labs):
            self.meta_dict[di] = all_metaD_vals[cc].text()

        self.meta_dict["Dark measurement"] = self.dark_data
        self.meta_dict["Bright measurement"] = self.bright_data

        self.meta_dict["Comments"] = self.com_labels.toPlainText()  ## This field has a diffferent format than the others

    ## Makes sure that number of skipped measurements is a positive integer
    def _LEskip_positive_number(self):
        string = self.LEskip.text()
        try:
            num = int(string)
            if num < 0:
                self.LEskip.setText("1")
            else:
                pass
        except:
            self.LEskip.setText("1")

    ## To update the field with total number of measurement frames
    @pyqtSlot()
    def update_number_of_frames(self):
        try:
            total_time = float(self.LEmeatime.text())
        except:
            total_time = 0

        inttime = float(self.LEinttime.text())
        self.total_frames = int(np.ceil(total_time / inttime))
        if self.total_frames == 0:
            self.total_frames = 1
        self.LAframes.setText(str(self.total_frames))

    @pyqtSlot()
    def scrollbar_action(self):
        bar = self.SBinttime.value()  ##Read scrollbar value
        self.LEinttime.setText(str(self.arr_scrbar[bar]))  ##Put value on entryline
        self.set_integration_time()

    @pyqtSlot()
    def set_integration_time(self):
        # print('set_integration_time')
        try:
            inttime = self.LEinttime.text()
            inttime = float(inttime.replace(',', '.'))  ## Read Entry field
        except:
            inttime = 0.1
        array_sb = np.array(self.arr_scrbar)  ## Load array of scrollbar values
        pos = np.abs(array_sb - inttime).argmin()  ## Find location of closest value in array

        ## Set Scrollbar with respect to value chosen
        if array_sb[pos] - inttime == 0:
            self.SBinttime.setValue(pos)
        else:
            self.SBinttime.setValue(pos)
            self.LEinttime.setText(str(inttime))

        ## Update frames label
        self.update_number_of_frames()

        if self.spectrometer:
            self.spec.integration_time_micros(int(inttime * 1000000))
        else:
            self.integration_time = inttime  # TODO: unused variable? --ashis

    def dis_enable_widgets(self, status):  # TODO: Rename to "disable_widgets" ? --ashis
        ##Disable the following buttons and fields
        wi_dis = [self.LEinttime, self.Binttime, self.SBinttime,  # self.BStart,
                  self.LEsample, self.LEuser, self.LEfolder, self.BBrightMeas,
                  self.BDarkMeas, self.LEdeltime, self.LEmeatime, self.Bfolder,
                  self.Bpath]

        for wd in wi_dis:
            if status:
                wd.setEnabled(False)
                self.BStart.setText("S T O P")
                self.BStart.setStyleSheet("color : red;")
            else:
                wd.setEnabled(True)
                self.BStart.setText("START")
                self.BStart.setStyleSheet("color : green;")

    def _save_data(self):
        self.gather_all_metadata()
        metadata = pd.DataFrame.from_dict(self.meta_dict, orient='index')
        wave = pd.DataFrame({"Wavelength (nm)": self.xdata})

        if self.Braw.isChecked():
            PLspecR = pd.DataFrame(self.spectra_raw_array.T, columns=self.time_meas_array)
            ## Remove all unused columns
            PLspecR = PLspecR.drop(list(PLspecR.filter(regex='Test')), axis=1, inplace=True)
            if self.dark_data:
                dark = pd.DataFrame({"Dark spectra": self.dark_mean})
            if self.bright_data:
                bright = pd.DataFrame({"Bright spectra": self.bright_mean})

            if self.dark_data and self.bright_data:
                spectral_data = pd.concat([wave, dark, bright, PLspecR], axis=1, join="inner")
            elif self.dark_data:
                spectral_data = pd.concat([wave, dark, PLspecR], axis=1, join="inner")
            elif self.bright_data:
                spectral_data = pd.concat([wave, bright, PLspecR], axis=1, join="inner")
            else:
                spectral_data = pd.concat([wave, PLspecR], axis=1, join="inner")
        else:
            spectra = self.spectra_meas_array

            # if self.dark_data:
            #     spectra = (self.spectra_meas_array-self.dark_mean)
            # elif self.bright_data and self.dark_data:
            #     spectra = (self.spectra_meas_array-self.dark_mean) / (self.spectra_meas_array-self.dark_mean)
            # else:
            #     spectra = self.spectra_meas_array

            PLspec = pd.DataFrame(spectra.T, columns=self.time_meas_array)
            spectral_data = pd.concat([wave, PLspec], axis=1, join="inner")

        # print(spectral_data)
        ## Remove all unused columns
        spectral_data = spectral_data.dropna(axis=1, how="all")
        # print(spectral_data)

        filename = self.folder + self.sample + "_PL_measurement.csv"
        metadata.to_csv(filename, header=False)
        spectral_data.to_csv(filename, mode="a", index=False)

        if self.BSavePlot.isChecked():
            self.make_heatplot(None)
        # self.Qthread_plotting(self.make_heatplot)

        self.statusBar().showMessage("Data saved successfully", 5000)
        # get_ipython().magic('reset -sf')

    @pyqtSlot(object, object, object)
    def save_data(self, spectra_raw_array, spectra_meas_array, time_meas_array):
        self.gather_all_metadata()
        metadata = pd.DataFrame.from_dict(self.meta_dict, orient='index')
        wave = pd.DataFrame({"Wavelength (nm)": self.xdata})

        if self.Braw.isChecked():
            PLspecR = pd.DataFrame(spectra_raw_array.T, columns= time_meas_array)
            ## Remove all unused columns
            PLspecR = PLspecR.drop(list(PLspecR.filter(regex='Test')), axis=1, inplace=True)
            if self.dark_data:
                dark = pd.DataFrame({"Dark spectra": self.dark_mean})
            if self.bright_data:
                bright = pd.DataFrame({"Bright spectra": self.bright_mean})

            if self.dark_data and self.bright_data:
                spectral_data = pd.concat([wave, dark, bright, PLspecR], axis=1, join="inner")
            elif self.dark_data:
                spectral_data = pd.concat([wave, dark, PLspecR], axis=1, join="inner")
            elif self.bright_data:
                spectral_data = pd.concat([wave, bright, PLspecR], axis=1, join="inner")
            else:
                spectral_data = pd.concat([wave, PLspecR], axis=1, join="inner")
        else:
            spectra = spectra_meas_array

            # if self.dark_data:
            #     spectra = (self.spectra_meas_array-self.dark_mean)
            # elif self.bright_data and self.dark_data:
            #     spectra = (self.spectra_meas_array-self.dark_mean) / (self.spectra_meas_array-self.dark_mean)
            # else:
            #     spectra = self.spectra_meas_array

            PLspec = pd.DataFrame(spectra.T, columns= time_meas_array)
            spectral_data = pd.concat([wave, PLspec], axis=1, join="inner")

        # print(spectral_data)
        ## Remove all unused columns
        spectral_data = spectral_data.dropna(axis=1, how="all")
        # print(spectral_data)

        filename = self.folder + self.sample + "_PL_measurement.csv"
        metadata.to_csv(filename, header=False)
        spectral_data.to_csv(filename, mode="a", index=False)

        if self.BSavePlot.isChecked():
            self.make_heatplot(spectra_raw_array, spectra_meas_array, time_meas_array)
        # self.Qthread_plotting(self.make_heatplot)

        self.statusBar().showMessage("Data saved successfully", 5000)
        # get_ipython().magic('reset -sf')


    ## This function is sent to the parallel Qthread
    def get_ydata(self, progress_callback):
        try:
            while True:
                # for i in range(25):
                ydata = self.spec.intensities()[2:]
                if "FLMS12200" in self.spec.serial_number:
                    dp = 1420  ##dead pixel on spectrometer @831.5nm
                    # ydata[dp] = np.nan
                    ydata[dp] = np.mean(ydata[dp - 2:dp + 2])
                progress_callback.emit(ydata)
        except:
            optimize = True  # TODO: remove non-optimized code --ashis
            if optimize:
                xx = np.arange(self.array_size)
            else:
                ydata = np.ones(len(self.xdata))
            # for i in range(25)
            while True:
                inttime = self.LEinttime.text()
                sleep(float(inttime))
                if optimize:
                    ydata = 50000 * np.exp(-(xx - 900) ** 2 / (2 * 100000)) + np.random.randint(0,
                                                                                                10001)  # result is in [start, end). hence 10001 instead of 10000
                else:
                    for cc, xx in enumerate(range(self.array_size)):
                        ydata[cc] = 50000 * math.exp(-(xx - 900) ** 2 / (2 * 100000)) + random.randint(0,
                                                                                                       10000)  # result is in [start, end]
                progress_callback.emit(ydata)
        return "Done!!"

    @pyqtSlot()
    def dark_measurement(self):
        self.average_cycles = int(self.LEcurave.text())  ## Read number in GUI
        ## Set initial values
        self.dark_meas_array = None  # np.ones((self.average_cycles, self.array_size)) TODO: None frees memory. Introduce None check if this causes problems --ashis
        self.dark_measurement_bool = True
        self.dark_counter = 0

    @pyqtSlot()
    def delete_dark_measurement(self):
        self.dark_mean = None  # np.ones(len(self.xdata)) TODO: None frees memory. Introduce None check if this causes problems --ashis
        self.dark_data = False
        self.BDarkMeas.setStyleSheet("color : black;")
        self.BDarkMeas.setText("Measure (deleted)")

    def gathering_dark_counts(self):
        if self.dark_counter == 0:
            self.BDarkMeas.setStyleSheet("color : yellow;")
            self.BDarkMeas.setText("Measuring...")

        if self.dark_counter < self.average_cycles:
            self.dark_meas_array[self.dark_counter] = np.array(self.ydata)
            self.dark_counter += 1
        else:
            self.dark_measurement_bool = False
            self.dark_mean = np.mean(self.dark_meas_array, axis=0)
            self.dark_data = True
            self.BDarkMeas.setStyleSheet("color : green;")
            self.BDarkMeas.setText("Measured")
            self.statusBar().showMessage('Measurement of dark spectra completed', 5000)

    @pyqtSlot()
    def bright_measurement(self):
        self.average_cycles = int(self.LEcurave.text())
        self.bright_meas_array = np.ones((self.average_cycles, self.array_size))
        self.bright_measurement_bool = True
        self.bright_counter = 0

    @pyqtSlot()
    def delete_bright_measurement(self):
        self.bright_mean = np.ones(len(self.xdata))
        self.bright_data = False
        self.BBrightMeas.setStyleSheet("color : black;")
        self.BBrightMeas.setText("Measure (deleted)")
        self.set_axis_range()

    def gathering_bright_counts(self):
        if self.bright_counter == 0:
            self.BBrightMeas.setStyleSheet("color : yellow;")
            self.BBrightMeas.setText("Measuring...")

        if self.bright_counter < self.average_cycles:
            self.bright_meas_array[self.bright_counter] = np.array(self.ydata)
            self.bright_counter += 1
        else:
            self.bright_measurement_bool = False
            self.bright_mean = np.mean(self.bright_meas_array, axis=0)
            self.bright_data = True
            self.BBrightMeas.setStyleSheet("color : green;")
            self.BBrightMeas.setText("Measured")
            self.statusBar().showMessage('Measurement of bright spectra completed', 5000)
            self.set_axis_range()

    @pyqtSlot()
    def press_start(self):
        if not self.measuring:
            self.delay = float(self.LEdeltime.text())
            self.LEskip.setText(utils.LEskip_positive_number(self.LEskip.text()))
            self.timer = QTimer()
            self.timer_interval = 0.1
            self.timer.setInterval(int(self.timer_interval * 1000))  # TODO: use single shot timer with delay?? --ashis
            self.timer.timeout.connect(self.delayed_start)
            self.timer.start()
        else:
            self.spec_thread.quit()
            self.measuring = False
            self.spectra_measurement_bool = False #TODO: Check and remove this variable --ashis
            self.dis_enable_widgets(False)
            self.save_data(self.meas_worker.spectra_raw_array, self.meas_worker.spectra_meas_array, self.meas_worker.time_meas_array)

    def delayed_start(self):
        print("delyed start")
        self.LAelapse.setStyleSheet("color :red;")
        self.LAelapse.setText("00:{:02.2f}".format(float(round(self.delay, 2))))
        self.delay = self.delay - self.timer_interval
        skip = int(self.LEskip.text())  # TODO: make sure skip is non-zero --ashis

        if self.delay <= 0:
            self.timer.stop()  # TODO: use single shot timer instead of stop?? --ashis
            self.LAelapse.setStyleSheet("color :black;")
            self.LAelapse.setText("00:00")

            self.start_time = time()
            print("Starting Worker with the parameters:")
            print("total_frames=", self.total_frames)
            print("array_size =", self.array_size)
            print("skip =", skip)
            print("is_dark_data =", self.dark_data)
            print("is_bright_data =", self.bright_data)
            print("dark_mean =", self.dark_mean)
            print("Bright Mean", self.bright_mean)
            print("timestamp=", self.start_time)

            self.meas_worker = Worker2(total_frames=self.total_frames,
                                       array_size=self.array_size,
                                       skip=skip,
                                       is_dark_data=self.dark_data,
                                       is_bright_data=self.bright_data,
                                       dark_mean=self.dark_mean,
                                       bright_mean=self.bright_mean,
                                       timestamp=self.start_time)
            self.worker.signals.progress.connect(self.meas_worker.run)
            self.meas_worker.moveToThread(self.spec_thread)

            self.meas_worker.finished.connect(self.spec_thread.quit)
            self.meas_worker.finished.connect(self.meas_worker.deleteLater)
            # self.spec_thread.finished.connect(self.spec_thread.deleteLater)
            self.meas_worker.progress.connect(self.during_measurement)
            self.meas_worker.result.connect(self.save_data)
            self.spec_thread.finished.connect(self.after_measurement)
            self.measuring = True
            self.dis_enable_widgets(True)
            self.create_folder(True)
            self.set_integration_time()
            self.spec_thread.start() #TODO: increase priority --ashis

    def _spectra_measurement(self):  # TODO: rename to init_spectra_measurement
        self.start_time = time()  ## Start of stopwatch
        self.set_integration_time()  ## Reset int time to what is in entry field
        self.spectra_meas_array = np.ones((self.total_frames, self.array_size))
        self.spectra_raw_array = np.ones((self.total_frames, self.array_size))
        self.time_meas_array = np.ones(self.total_frames)
        self.spectra_meas_array[:] = np.nan
        self.spectra_raw_array[:] = np.nan
        self.time_meas_array[:] = np.nan
        self.measuring = True
        self.spectra_measurement_bool = True
        self.spectra_counter = 0
        self.counter = 0
        self.array_count = 0

    def _gathering_spectra_counts(
            self):  # TODO: CALLED MANY TIMES --migrate to new thread --ashis.... inputs-> skip, total frames, ydata, yarray, spectra_raw_
        print('gathering_spectra_counts')
        skip = int(self.LEskip.text())  # TODO: make sure skip is non-zero --ashis

        if self.spectra_counter == 0:
            self.dis_enable_widgets(True)
            self.create_folder(True)

        if self.spectra_counter < self.total_frames:
            if self.spectra_counter == 0 or self.spectra_counter % skip == 0:
                # self.spectra_raw_array[self.spectra_counter] = np.array(self.ydata)
                # self.spectra_meas_array[self.spectra_counter] = np.array(self.yarray)
                # self.time_meas_array[self.spectra_counter] = np.round(time()-self.start_time,4)
                self.spectra_raw_array[self.array_count] = np.array(self.ydata)
                self.spectra_meas_array[self.array_count] = np.array(self.yarray)
                self.time_meas_array[self.array_count] = np.round(time() - self.start_time, 4)
                self.array_count += 1
            self.spectra_counter += 1
        else:
            self.time_meas_array = self.time_meas_array - self.time_meas_array[0]
            self.spectra_measurement_bool = False
            self.spectra_data = True
            self.dis_enable_widgets(False)
            self.statusBar().showMessage('Measurement finished', 5000)

    def _spectra_math(self):  # TODO: Migrate this function to utils --ashis
        if self.dark_data and not self.bright_data:
            self.yarray = (self.ydata - self.dark_mean)
        elif self.bright_data and not self.dark_data:
            self.yarray = self.ydata / self.bright_mean
        elif self.bright_data and self.dark_data:
            self.yarray = 1 - np.divide((self.ydata - self.dark_mean), (self.bright_mean - self.dark_mean))
        else:
            self.yarray = self.ydata

    def reset_plot(self):
        self.canvas.axes.cla()
        self.canvas.axes.set_xlabel('Wavelength (nm)')
        self.canvas.axes.set_ylabel('Intensity (a.u.)')
        self.canvas.axes.grid(True, linestyle='--')
        self.canvas.axes.set_xlim([min(self.xdata) * 0.98, max(self.xdata) * 1.02])
        # self.canvas.axes.set_xlim([400,850])
        self.canvas.axes.set_ylim([0, 68000])
        self.show_raw = False

    @pyqtSlot(object)
    def plot_spectra(self, spect):
        self.ydata = spect #TODO: idea is to remove ydata as state variable of this class --ashis
        # print(ydata)
        ## Check if button to collect data has been pressed
        if self.dark_measurement_bool:
            self.gathering_dark_counts()
        if self.bright_measurement_bool:
            self.gathering_bright_counts()
        # if self.spectra_measurement_bool:
        #   self.gathering_spectra_counts()
        #    self.during_measurement()

        ## Plot the data accordingly
        if self._plot_ref is None:  ## For initializing the plot
            # self.ydata = np.ones(len(self.xdata)) #TODO: Why change ydata if not used anywhere? --ashis
            # self._plot_ref, = self.canvas.axes.plot(self.xdata, self.ydata, 'r')
            self._plot_ref, = self.canvas.axes.plot(self.xdata, np.ones(len(self.xdata)), 'r')
            if not self.spectrometer:
                self._plot_ref.set_label("Spectrometer not found: Demo Data")
                self.canvas.axes.legend()
            else:
                pass  # TODO: else case really needed? --ashis

        else:
            yarray = utils.spectra_math(spect, self.dark_data, self.bright_data, self.dark_mean, self.bright_mean)
            ## raw button checked
            if self.Braw.isChecked():
                if not self.show_raw:
                    if self.dark_data:
                        self._plot_re1 = self.canvas.axes.plot(self.xdata, self.dark_mean, 'b', label="Dark")
                    if self.bright_data:
                        self._plot_re2 = self.canvas.axes.plot(self.xdata, self.bright_mean, 'y', label="Bright")

                self._plot_ref.set_ydata(self.ydata)
                self._plot_ref.set_label("Spectra")
                self.canvas.axes.legend()
                self.show_raw = True

            else:  ## If raw button is unchecked, clean and restart the plot
                if self.show_raw:
                    self.show_raw = False
                    self.reset_plot()
                    self._plot_ref, = self.canvas.axes.plot(self.xdata, self.ydata, 'r')

                self._plot_ref.set_ydata(yarray)

        self.canvas.draw_idle()

    @pyqtSlot()
    def set_axis_range(self):
        self.canvas.axes.set_xlim([min(self.xdata) * 0.98, max(self.xdata) * 1.02])

        if self.Brange.isChecked():
            if self.bright_data:
                self.canvas.axes.set_ylim([-10, 10])
            else:
                fix_arr = np.ma.masked_invalid(self.yarray)
                self.canvas.axes.set_ylim([min(fix_arr) * 0.9, max(fix_arr) * 1.1])

        elif self.bright_data and not self.Braw.isChecked():
            self.canvas.axes.set_ylim([-0.5, 1.5])
            self.canvas.axes.set_xlim([380, 820])
        elif self.bright_data and self.Braw.isChecked():
            glob_min = np.min([np.min(self.bright_mean), np.min(self.dark_mean)])
            glob_max = np.max([np.max(self.bright_mean), np.min(self.dark_mean)])
            self.canvas.axes.set_ylim([glob_min * 0.9, glob_max * 1.1])
            self.canvas.axes.set_xlim([350, 850])

        else:
            self.canvas.axes.set_ylim([0, 68000])
            self.canvas.axes.set_xlim([330, 1030])

    def _during_measurement(self):  ## To update values in GUI
        ## This updates the number of measurements that will be made
        self.LAframes.setText(str(self.counter) + "/" + str(self.total_frames))
        ## This is to show the elapsed time
        self.elapsed_time = time() - self.start_time
        minute, second = divmod(self.elapsed_time, 60)
        self.LAelapse.setText("{:02}:{:02}".format(int(minute), int(second)))

        ## Dissable widgets during the measurement time
        if self.counter < self.total_frames:
            self.dis_enable_widgets(True)

        else:  ## Re-enable widgets after measurement is done
            self.dis_enable_widgets(False)
            self.counter = 0
            self.measuring = False
            self.save_data()

        self.counter += 1

    @pyqtSlot(int)
    def during_measurement(self, counter):  ## To update values in GUI
        ## This updates the number of measurements that will be made
        self.LAframes.setText(str(counter) + "/" + str(self.total_frames))
        ## This is to show the elapsed time
        self.elapsed_time = time() - self.start_time
        minute, second = divmod(self.elapsed_time, 60)
        self.LAelapse.setText("{:02}:{:02}".format(int(minute), int(second)))

    @pyqtSlot()
    def after_measurement(self):
        self.dis_enable_widgets(False)
        self.measuring = False

    def make_heatplot(self, spectra_raw_array, spectra_meas_array, time_meas_array):  ## Triggered at the End
        matplotlib.use('Agg')
        plt.ioff()

        fig = plt.figure(figsize=[8, 6])
        ax1 = fig.add_subplot(1, 1, 1)

        # progress_callback.emit(None)

        # xsize = len(self.time_meas_array)

        if self.Braw.isChecked():
            time = time_meas_array
            heatplot = spectra_raw_array.T
            waveleng = self.xdata
        else:
            time = time_meas_array
            heatplot = spectra_meas_array.T[215:1455]
            waveleng = self.xdata[215:1455]

        time = time[~np.isnan(time)]
        waveleng = waveleng[~np.isnan(waveleng)]
        heatplot = heatplot[:, :time.shape[0]]

        ax1.set_title("PL spectra")
        ax1.set_xlabel("Time(seconds)")
        ax1.set_ylabel("Wavelength (nm)")

        waveLen = len(waveleng)
        PLmin = np.min(waveleng)
        PLmax = np.max(waveleng)

        ## fix axis ticks so they match the data (else they are array positions)
        ax1.set_yticks(np.linspace(0, waveLen, 8))
        ax1.set_yticklabels(np.linspace(PLmin, PLmax, 8).astype(int))
        ax1.set_xticks(np.linspace(0, len(time), 8))
        ax1.set_xticklabels(np.around(np.linspace(0, np.max(time), 8), decimals=1))
        ax1.pcolorfast(heatplot)
        fig.savefig(
            self.folder + "0_preview_" + self.sample + "_heatplot.png")  # ,bbox_inches = "tight")   # save the figure to file
        plt.close()  # close the figure window

    def send_to_Qthread(self):
        ## Create a QThread object
        # self.thread = QThread()
        ## Create a worker object and send function to it
        self.worker = Worker(self.get_ydata)
        ## Whenever signal exists, send it to plot
        self.worker.signals.progress.connect(self.plot_spectra)
        ## Start threadpool
        self.threadpool.start(self.worker)


    @pyqtSlot()
    def finished_plotting(self):
        self.statusBar().showMessage("Plotting process finished and images saved", 5000)

    # TODO: funtion not called? --ashis
    '''
    def Qthread_plotting(self, func):
        ## Create a QThread object
        self.thread = QThread()
        ## Create a worker object and send function to it
        self.worker = Worker(func)
        ## Whenever signal exists, send it to plot
        self.thread.finished.connect(self.finished_plotting)
        ## Start threadpool
        self.threadpool.start(self.worker)
    '''

    def closeEvent(self, event):
        reply = QMessageBox.question(self, 'Window Close', 'Are you sure you want to close the window?',
                       QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.spec_thread.quit() #TODO: close threadpool too? --ashis
            self.spec_thread.wait()
            event.accept()
            # print('Window closed')
            if self.spectrometer:
                self.spec.close()
        else:
            event.ignore()
