import os
from PyQt5 import QtWidgets, QtGui
from PyQt5.QtWidgets import QWidget, QLineEdit, QFormLayout, QHBoxLayout, QSpacerItem, QGridLayout, QApplication
from PyQt5.QtWidgets import QFrame, QPushButton, QCheckBox, QLabel, QToolButton, QTextEdit, QScrollBar
from PyQt5.QtWidgets import QSizePolicy, QMessageBox
from PyQt5.QtCore import QThread, pyqtSlot
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont
import matplotlib
matplotlib.use('Qt5Agg')
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg, NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
from matplotlib import rcParams
rcParams.update({'figure.autolayout': True})
import pandas as pd
import numpy as np
from time import time, strftime, localtime
from datetime import datetime
import utils
import pathlib
from workers import PlotWorker, SpectraGatherer, DarkBrightGatherer


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

    def __init__(self, icon_path: pathlib.Path, is_spectrometer: bool, emitter, child_process_queue, xdata, array_size,
                 *args, **kwargs):
        '''
        Initialize parameters
        :param args:
        :param kwargs:
        '''
        super(MainWindow, self).__init__(*args, **kwargs)
        self.is_dark_measurement = False  # TODO: change bool variable naming convention --ashis
        self.is_spectra_measurement = False
        self.is_dark_data = False
        self.is_bright_data = False
        self.is_spectra_data = False
        self.is_show_raw = False
        self.is_measuring = False
        self.current_inttime_ms: float = 0
        self.dark_mean = None  # TODO: add all missing variables here --ashis
        self.bright_mean = None
        self.setWindowTitle("Spectra Compiler")
        self.setWindowIcon(QtGui.QIcon(str(icon_path)))
        np.seterr(divide='ignore', invalid='ignore')

        self.is_spectrometer = is_spectrometer  # TODO: Remove unused
        self.process_queue = child_process_queue
        self.xdata = xdata
        self.array_size = array_size
        self.emitter = emitter
        self.emitter.daemon = True
        self.emitter.start()

        self.spec_thread = QThread()
        self.plot_thread = QThread()
        self.brightdark_meas_thread = QThread()
        self.brightdark_meas_worker = None

        self.statusBar().showMessage("Program by Edgar Nandayapa - 2021", 10000)

        self.create_widgets()
        self.arr_scrbar = utils.array_for_scrollbar()  ##This function makes an array for the scrollbar
        self.set_integration_time()  ##This resets the starting integration time value
        self.button_actions()  ##Set button actions

    def create_widgets(self):
        '''
        Setups up the GUI
        '''
        widget = QWidget()
        layH1 = QHBoxLayout()  ##Main (horizontal) Layout

        ## Create the maptlotlib FigureCanvas for plotting
        self.canvas = MplCanvas(self, width=5, height=4, dpi=100)
        # self.canvas.axes.set_xlim([min(self.xdata) * 0.98, max(self.xdata) * 1.02])
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
        self.LEskip.setText("0")

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
        '''
        QT button action connections are here.
        '''
        self.send_to_Qthread()
        self.folder = self.LEfolder.text()
        self.Bfolder.clicked.connect(self.select_folder)
        self.Bpath.clicked.connect(self.automatic_folder)
        self.BsaveM.clicked.connect(self.save_meta)
        self.BloadM.clicked.connect(self.load_meta)
        self.Binttime.clicked.connect(self.set_integration_time)
        self.LEinttime.returnPressed.connect(self.set_integration_time)
        self.SBinttime.sliderReleased.connect(self.scrollbar_action)
        self.BDarkMeas.clicked.connect(self.dark_measurement)
        self.BBrightMeas.clicked.connect(self.bright_measurement)
        self.BStart.clicked.connect(self.press_start)
        self.LEmeatime.textChanged.connect(self.update_number_of_frames)
        self.Brange.stateChanged.connect(self.set_axis_range)
        self.Braw.stateChanged.connect(self.set_axis_range)
        self.Braw.stateChanged.connect(self.refresh_plot)
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

        self.meta_dict["Dark measurement"] = self.is_dark_data
        self.meta_dict["Bright measurement"] = self.is_bright_data

        self.meta_dict[
            "Comments"] = self.com_labels.toPlainText()  ## This field has a diffferent format than the others

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
            # self.yworker.set_intime(inttime)
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
        self.current_inttime_ms = inttime * 1000
        self.process_queue.put(inttime)

    def wait_until_inttime_in_sync(self):
        self.statusBar().showMessage('Waiting for integration times to be in sync.\tDo not click anything.')
        while not abs(self.current_inttime_ms - self.plot_worker.current_mean_frequency_ms) <= 10:  # 10ms tolerance
            QApplication.processEvents()
            pass
        self.statusBar().showMessage('Integration times are synced.')

    def toggle_widgets(self, status):
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

    @pyqtSlot(object, object, object)
    def save_data(self, spectra_raw_array, spectra_meas_array, time_meas_array):
        self.gather_all_metadata()
        metadata = pd.DataFrame.from_dict(self.meta_dict, orient='index')
        wave = pd.DataFrame({"Wavelength (nm)": self.xdata})

        if self.Braw.isChecked():
            PLspecR = pd.DataFrame(spectra_raw_array.T, columns=time_meas_array)
            ## Remove all unused columns
            PLspecR = PLspecR.drop(list(PLspecR.filter(regex='Test')), axis=1, inplace=True)
            if self.is_dark_data:
                dark = pd.DataFrame({"Dark spectra": self.dark_mean})
            if self.is_bright_data:
                bright = pd.DataFrame({"Bright spectra": self.bright_mean})

            if self.is_dark_data and self.is_bright_data:
                spectral_data = pd.concat([wave, dark, bright, PLspecR], axis=1, join="inner")
            elif self.is_dark_data:
                spectral_data = pd.concat([wave, dark, PLspecR], axis=1, join="inner")
            elif self.is_bright_data:
                spectral_data = pd.concat([wave, bright, PLspecR], axis=1, join="inner")
            else:
                spectral_data = pd.concat([wave, PLspecR], axis=1, join="inner")
        else:
            spectra = spectra_meas_array
            PLspec = pd.DataFrame(spectra.T, columns=time_meas_array)
            spectral_data = pd.concat([wave, PLspec], axis=1, join="inner")

        ## Remove all unused columns
        spectral_data = spectral_data.dropna(axis=1, how="all")
        filename = self.folder + self.sample + "_PL_measurement.csv"
        metadata.to_csv(filename, header=False)
        spectral_data.to_csv(filename, mode="a", index=False)
        if self.BSavePlot.isChecked():
            self.make_heatplot(spectra_raw_array, spectra_meas_array, time_meas_array)
        self.statusBar().showMessage("Data saved successfully", 5000)

    @pyqtSlot()
    def dark_measurement(self):
        self.BDarkMeas.setEnabled(False)
        self.wait_until_inttime_in_sync()
        self.average_cycles = int(self.LEcurave.text())  ## Read number in GUI
        self.BDarkMeas.setStyleSheet("color : yellow;")
        self.BDarkMeas.setText("Measuring...")
        self.brightdark_meas_worker = DarkBrightGatherer(self.average_cycles, self.array_size)
        self.emitter.ui_data_available.connect(self.brightdark_meas_worker.gathering_counts)
        self.brightdark_meas_worker.result.connect(self.after_dark_measurement)
        self.brightdark_meas_worker.moveToThread(self.brightdark_meas_thread)
        self.brightdark_meas_thread.start()

    @pyqtSlot(object)
    def after_dark_measurement(self, dark_mean):
        self.emitter.ui_data_available.disconnect(self.brightdark_meas_worker.gathering_counts)
        self.brightdark_meas_thread.quit()
        self.brightdark_meas_thread.wait()
        self.dark_mean = dark_mean
        self.is_dark_data = True
        self.BDarkMeas.setStyleSheet("color : green;")
        self.BDarkMeas.setText("Measured")
        self.statusBar().showMessage('Measurement of dark spectra completed', 5000)
        self.BDarkMeas.setEnabled(True)
        self.set_axis_range()
        self.refresh_plot()

    @pyqtSlot()
    def delete_dark_measurement(self):
        self.dark_mean = np.ones(
            len(self.xdata))  # TODO: None frees memory. Introduce None check if this causes problems --ashis
        self.is_dark_data = False
        self.BDarkMeas.setStyleSheet("color : black;")
        self.BDarkMeas.setText("Measure (deleted)")

    @pyqtSlot()
    def bright_measurement(self):
        self.BBrightMeas.setEnabled(False)
        self.wait_until_inttime_in_sync()
        self.average_cycles = int(self.LEcurave.text())
        self.BBrightMeas.setStyleSheet("color : yellow;")
        self.BBrightMeas.setText("Measuring...")
        self.brightdark_meas_worker = DarkBrightGatherer(self.average_cycles, self.array_size)
        self.emitter.ui_data_available.connect(self.brightdark_meas_worker.gathering_counts)
        self.brightdark_meas_worker.result.connect(self.after_bright_measurement)
        self.brightdark_meas_worker.moveToThread(self.brightdark_meas_thread)
        self.brightdark_meas_thread.start()

    @pyqtSlot(object)
    def after_bright_measurement(self, bright_mean):
        self.emitter.ui_data_available.disconnect(self.brightdark_meas_worker.gathering_counts)
        self.brightdark_meas_thread.quit()
        self.brightdark_meas_thread.wait()
        self.bright_mean = bright_mean
        self.is_bright_data = True
        self.BBrightMeas.setEnabled(True)
        self.BBrightMeas.setStyleSheet("color : green;")
        self.BBrightMeas.setText("Measured")
        self.statusBar().showMessage('Measurement of bright spectra completed', 5000)
        self.set_axis_range()
        self.refresh_plot()

    @pyqtSlot()
    def delete_bright_measurement(self):
        self.bright_mean = np.ones(len(self.xdata))
        self.is_bright_data = False
        self.BBrightMeas.setStyleSheet("color : black;")
        self.BBrightMeas.setText("Measure (deleted)")
        self.set_axis_range()
        self.refresh_plot()

    @pyqtSlot()
    def press_start(self):
        if not self.is_measuring:
            self.delay = float(self.LEdeltime.text())
            self.LEskip.setText(utils.LEskip_positive_number(self.LEskip.text()))
            self.timer = QTimer()
            self.timer_interval = 0.1
            self.timer.setInterval(int(self.timer_interval * 1000))  # TODO: use single shot timer with delay?? --ashis
            self.timer.timeout.connect(self.delayed_start)
            self.timer.start()
        else:
            self.spec_thread.quit()
            self.is_measuring = False
            self.is_spectra_measurement = False  # TODO: Check and remove this variable --ashis
            self.toggle_widgets(False)
            self.save_data(self.meas_worker.spectra_raw_array, self.meas_worker.spectra_meas_array,
                           self.meas_worker.time_meas_array)

    def delayed_start(self):
        self.LAelapse.setStyleSheet("color :red;")
        self.LAelapse.setText("00:{:02.2f}".format(float(round(self.delay, 2))))
        self.delay = self.delay - self.timer_interval
        skip = int(self.LEskip.text())
        if self.delay <= 0:
            self.timer.stop()
            self.LAelapse.setStyleSheet("color :black;")
            self.LAelapse.setText("00:00")
            self.set_integration_time()
            self.wait_until_inttime_in_sync()
            self.start_time = time()
            print("Starting Worker with the parameters:")
            print("total_frames=", self.total_frames)
            print("array_size =", self.array_size)
            print("skip =", skip)
            print("is_dark_data =", self.is_dark_data)
            print("is_bright_data =", self.is_bright_data)
            print("dark_mean =", self.dark_mean)
            print("Bright Mean", self.bright_mean)
            print("timestamp=", self.start_time)
            self.meas_worker = SpectraGatherer(total_frames=self.total_frames,
                                               array_size=self.array_size,
                                               skip=skip,
                                               is_dark_data=self.is_dark_data,
                                               is_bright_data=self.is_bright_data,
                                               dark_mean=self.dark_mean,
                                               bright_mean=self.bright_mean)
            self.emitter.ui_data_available.connect(self.meas_worker.measure)
            self.meas_worker.moveToThread(self.spec_thread)
            self.meas_worker.finished.connect(self.spec_thread.quit)
            self.meas_worker.finished.connect(self.meas_worker.deleteLater)
            self.meas_worker.progress.connect(self.during_measurement)
            self.meas_worker.result.connect(self.save_data)
            self.spec_thread.finished.connect(self.after_measurement)
            self.is_measuring = True
            self.toggle_widgets(True)
            self.create_folder(True)
            self.spec_thread.start(QThread.HighPriority)

    @pyqtSlot()
    def set_axis_range(self):
        self.canvas.axes.set_xlim([min(self.xdata) * 0.98, max(self.xdata) * 1.02])
        if self.Brange.isChecked():
            if self.is_bright_data:
                self.canvas.axes.set_ylim([-10, 10])
            else:
                fix_arr = np.ma.masked_invalid(self.yarray)
                self.canvas.axes.set_ylim([min(fix_arr) * 0.9, max(fix_arr) * 1.1])

        elif self.is_bright_data and not self.Braw.isChecked():
            self.canvas.axes.set_ylim([-0.5, 1.5])
            self.canvas.axes.set_xlim([380, 820])
        elif self.is_bright_data and self.Braw.isChecked():
            glob_min = np.min([np.min(self.bright_mean), np.min(self.dark_mean)])
            glob_max = np.max([np.max(self.bright_mean), np.min(self.dark_mean)])
            self.canvas.axes.set_ylim([glob_min * 0.9, glob_max * 1.1])
            self.canvas.axes.set_xlim([350, 850])
        else:
            self.canvas.axes.set_ylim([0, 68000])
            self.canvas.axes.set_xlim([330, 1030])

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
        self.toggle_widgets(False)
        self.is_measuring = False

    def make_heatplot(self, spectra_raw_array, spectra_meas_array, time_meas_array):  ## Triggered at the End
        matplotlib.use('Agg')
        plt.ioff()
        fig = plt.figure(figsize=[8, 6])
        ax1 = fig.add_subplot(1, 1, 1)
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
            self.folder + "0_preview_" + self.sample + "_heatplot.png")
        plt.close()  # close the figure window

    def send_to_Qthread(self):
        self.plot_worker = PlotWorker(
            is_dark_data=self.is_dark_data,
            is_bright_data=self.is_bright_data,
            dark_mean=self.dark_mean,
            bright_mean=self.bright_mean,
            canvas=self.canvas,
            xdata=self.xdata,
            is_spectrometer=self.is_spectrometer
        )
        self.emitter.ui_data_available.connect(self.plot_worker.plot_spectra)
        self.plot_worker.moveToThread(self.plot_thread)
        self.plot_thread.start()

    @pyqtSlot()
    def refresh_plot(self):
        self.plot_worker.show_raw = self.Braw.isChecked()
        self.plot_worker.is_dark_data = self.is_dark_data
        self.plot_worker.is_bright_data = self.is_bright_data
        self.plot_worker.dark_mean = self.dark_mean
        self.plot_worker.bright_mean = self.bright_mean
        if not self.Braw.isChecked():
            self.plot_worker.reset_axes()

    @pyqtSlot()
    def finished_plotting(self):
        self.statusBar().showMessage("Plotting process finished and images saved", 5000)

    def closeEvent(self, event):
        reply = QMessageBox.question(self, 'Window Close', 'Are you sure you want to close the window?',
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.spec_thread.quit()
            self.spec_thread.wait()
            self.plot_thread.quit()
            self.plot_thread.wait()
            event.accept()
            self.process_queue.put(None)
        else:
            event.ignore()
