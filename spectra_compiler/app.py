# SPDX-FileCopyrightText: 2023 Edgar Nandayapa (Helmholtz-Zentrum Berlin) & Ashis Ravindran (DKFZ, Heidelberg)
#
# SPDX-License-Identifier: MIT

import os
from PyQt5 import QtWidgets, QtGui
from PyQt5.QtWidgets import QWidget, QLineEdit, QFormLayout, QHBoxLayout, QSpacerItem, QGridLayout, QApplication
from PyQt5.QtWidgets import QFrame, QPushButton, QCheckBox, QLabel, QToolButton, QTextEdit, QScrollBar
from PyQt5.QtWidgets import QSizePolicy, QMessageBox, QDialog, QVBoxLayout,QTextBrowser
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
from spectra_compiler import utils
import pathlib
from spectra_compiler.workers import PlotWorker, SpectraGatherer, DarkBrightGatherer

class InfoDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        info_browser = QTextBrowser()
        info_browser.setOpenExternalLinks(True)
        info_text = (
            "<p>Software tested with OceanInsights spectrometers.</p>"
            "<p>Created by Edgar Nandayapa (Helmholtz-Zentrum Berlin) with support of Ashis Ravindran (Deutsches Krebsforschungszentrum).</p>"
            "<p>If you find this software useful, please cite it <a href='https://codebase.helmholtz.cloud/hyd/spectra-compiler/-/blob/main/CITATION.bib'>DOI:10.5281/zenodo.7639465</a>.</p>"
            "<p>The latest version of the program can be found at <a href='https://codebase.helmholtz.cloud/hyd/spectra-compiler'>https://codebase.helmholtz.cloud/hyd/spectra-compiler</a>.</p>"

        )
        info_browser.setHtml(info_text)
        layout.addWidget(info_browser)

class MplCanvas(FigureCanvasQTAgg):
    '''
    Initial setup and placeholder for GUI plot
    '''

    def __init__(self, parent=None, width=5, height=4, dpi=300, tight_layout=True):
        fig = Figure(figsize=(width, height), dpi=dpi)
        self.axes = fig.add_subplot(111)
        self.axes.set_xlabel('Wavelength (nm)')
        self.axes.set_ylabel('Intensity (a.u.)')
        self.axes.grid(True, linestyle='--')
        self.axes.set_xlim([330, 1030])
        self.axes.set_ylim([0, 68000])
        fig.tight_layout()
        super(MplCanvas, self).__init__(fig)


class MainWindow(QtWidgets.QMainWindow):

    def __init__(self, icon_path: pathlib.Path, is_spectrometer: bool, emitter, child_process_queue, xdata, array_size,
                 *args, **kwargs):
        '''
        QT main window class handling all user interactive widgets and their actions
        :param args:
        :param kwargs:
        '''
        super(MainWindow, self).__init__(*args, **kwargs)
        self.is_dark_measurement = False
        self.is_dark_data = False
        self.is_bright_data = False
        self.is_spectra_data = False
        self.is_show_raw = False
        self.is_measuring = False
        self.current_inttime_ms: float = 0
        self.dark_mean = None
        self.bright_mean = None
        self.setWindowTitle("Spectra Compiler")
        self.setWindowIcon(QtGui.QIcon(str(icon_path)))
        np.seterr(divide='ignore', invalid='ignore')

        self.is_spectrometer = is_spectrometer
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
        self.arr_scrbar = utils.array_for_scrollbar()  # This function makes an array for the scrollbar
        self.set_integration_time()  # This resets the starting integration time value
        self.button_actions()  # Set button actions

    def create_widgets(self):
        '''
        Setups up the GUI widgets and layout
        '''
        widget = QWidget()
        layH1 = QHBoxLayout()  # Main (horizontal) Layout

        #  Create the maptlotlib FigureCanvas for plotting
        self.canvas = MplCanvas(self, width=5, height=4, dpi=100)
        # self.canvas.axes.set_xlim([min(self.xdata) * 0.98, max(self.xdata) * 1.02])
        self.canvas.setMinimumWidth(600)  # Fix width so it doesn't change
        self.canvas.setMinimumHeight(450)
        self.setCentralWidget(self.canvas)
        self._plot_ref = None
        #  Add a toolbar to control plotting area
        toolbar = NavigationToolbar(self.canvas, self)

        self.Braw = QCheckBox("Show Raw Data")  #  Button to select visualization
        self.Brange = QCheckBox("Fix y-axis")  #  Button to select visualization
        self.BSavePlot = QCheckBox("Create heatplot")
        self.BSavePlot.setChecked(True)
        self.info_button = QPushButton("\U0001F6C8")
        self.info_button.setFixedSize(25, 25)
        self.info_button.setStyleSheet("text-align: center; font-size: 18px;")

        # # Place all widgets
        #  First in a grid
        LBgrid = QGridLayout()
        LBgrid.addWidget(QLabel(" "), 0, 0)
        LBgrid.addWidget(QLabel(" "), 0, 1)
        LBgrid.addWidget(self.Braw, 0, 2)
        LBgrid.addWidget(self.Brange, 0, 3)
        LBgrid.addWidget(self.BSavePlot, 0, 4)
        LBgrid.addWidget(QLabel(" "), 0, 5)
        LBgrid.addWidget(self.info_button, 0, 6)
        LBgrid.setAlignment(self.info_button, Qt.AlignRight)
        #  Add to (first) vertical layout
        layV1 = QtWidgets.QVBoxLayout()
        #  Add Widgets to the layout
        layV1.addWidget(toolbar)
        layV1.addWidget(self.canvas)
        layV1.addLayout(LBgrid)

        #  Add first vertical layout to the main horizontal one
        layH1.addLayout(layV1, 8)

        # # Make second vertical layout for measurement settings
        layV2 = QtWidgets.QVBoxLayout()
        verticalSpacerV2 = QSpacerItem(20, 10, QSizePolicy.Minimum, QSizePolicy.Expanding)  #  To center the layout

        #  Relevant fields for sample, user and folder names
        self.LEsample = QLineEdit()
        self.LEuser = QLineEdit()
        self.LEfolder = QLineEdit()

        #  Make a grid layout and add labels and fields to it
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

        #  Set defaults
        self.Bpath.setText("\U0001F4C6")
        self.Bfolder.setText("\U0001F4C1")
        self.LEfolder.setText("C:/Data/")

        #  Second set of setup values
        LTsetup = QGridLayout()
        self.LEinttime = QLineEdit()
        self.LEdeltime = QLineEdit()
        self.LEmeatime = QLineEdit()
        self.LEskip = QLineEdit()

        self.Binttime = QToolButton()
        self.Binttime.setText("SET")
        self.SBinttime = QScrollBar()
        self.SBinttime.setOrientation(Qt.Horizontal)
        self.SBinttime.setStyleSheet("background : white;")

        #  Position labels and field in a grid
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

        #  Set defaults
        self.LEinttime.setText("0.2")
        self.LEdeltime.setText("0")
        self.LEmeatime.setText("10")
        self.LEskip.setText("0")

        #  Third set of setup values
        self.LEcurave = QLineEdit()
        self.LEcurave.setText("5")
        # self.LEcurave.setMaximumWidth(160)
        self.BBrightMeas = QPushButton("(Measure Dark First)")
        self.BBrightMeas.setStyleSheet("color : gray;")
        self.BBrightMeas.setEnabled(False)
        self.BBrightDel = QToolButton()
        self.BBrightDel.setText("\U0001F5D1")
        self.BBrightDel.setToolTip("Delete previous measurement")
        self.BDarkMeas = QPushButton("Measure")
        self.BDarkMeas.setStyleSheet("color : red;")
        self.BDarkDel = QToolButton()
        self.BDarkDel.setText("\U0001F5D1")
        self.BDarkDel.setToolTip("Delete previous measurement")

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

        #  Four set of setup values
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

        #  Position all these sets into the second layout V2
        layV2.addItem(verticalSpacerV2)
        layV2.addLayout(LGsetup)
        layV2.addLayout(LTsetup)
        layV2.addLayout(Lsetup)
        layV2.addLayout(LGlabels)
        layV2.addItem(verticalSpacerV2)

        #  Add to main horizontal layout with a spacer (for good looks)
        horizontalSpacerH1 = QSpacerItem(10, 70, QSizePolicy.Minimum, QSizePolicy.Minimum)
        layH1.addItem(horizontalSpacerH1)
        layH1.addLayout(layV2, 3)

        # # Make third vertical layout for metadata
        layV3 = QtWidgets.QVBoxLayout()

        #  List of relevant values
        self.exp_labels = ["Material", "Additives", "Concentration", "Solvents", "Solvents Ratio", "Substrate"]
        self.exp_vars = []
        self.glv_labels = ["Temperature ('C)", "Water content (ppm)", "Oxygen content (ppm)"]
        self.glv_vars = []
        self.photoLu_labels = ["Long pass filter", "Short pass filter", "Light source"]
        self.photoLu_vars = []
        self.spinCo_labels = ["Speed (rpm)", "Acceleration (rpm/s)", "Antisolvent time (s)", "Antisolvent Chemistry"]
        self.spinCo_vars = []

        self.setup_labs = ["Sample", "User", "Folder", "Integration Time (s)", "Delay time (s)",
                           "Measurement length (s)",
                           "Averaged Curves"]
        self.setup_vals = [self.LEsample, self.LEuser, self.LEfolder, self.LEinttime, self.LEdeltime, self.LEmeatime,
                           self.LEcurave]

        #  Make a new layout and position relevant values
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
        LmDataBox.addRow(" ", QFrame())
        LmDataBox.addRow(QLabel('PL VARIABLES'))
        for eb in self.photoLu_labels:
            Evar = QLineEdit()
            # Evar.setMaximumWidth(120)
            LmDataBox.addRow(eb, Evar)
            self.photoLu_vars.append(Evar)
        LmDataBox.addRow(" ", QFrame())
        LmDataBox.addRow(QLabel('SPIN-COATING VARIABLES'))
        for eb in self.spinCo_labels:
            Evar = QLineEdit()
            # Evar.setMaximumWidth(120)
            LmDataBox.addRow(eb, Evar)
            self.spinCo_vars.append(Evar)
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

        #  Position layouts inside of the third vertical layout V3
        layV3.addItem(verticalSpacerV2)
        layV3.addLayout(LmDataExp)
        layV3.addLayout(LmDataBox)
        layV3.addLayout(LGmeta)
        layV3.addItem(verticalSpacerV2)

        #  Add to main horizontal layout with a spacer (for good looks)
        horizontalSpacerH2 = QSpacerItem(30, 70, QSizePolicy.Minimum, QSizePolicy.Minimum)
        layH1.addItem(horizontalSpacerH2)
        layH1.addLayout(layV3, 2)

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
        self.SBinttime.valueChanged.connect(self.scrollbar_action)
        self.BDarkMeas.clicked.connect(self.dark_measurement)
        self.BBrightMeas.clicked.connect(self.bright_measurement)
        self.BStart.clicked.connect(self.press_start)
        self.LEmeatime.textChanged.connect(self.update_number_of_frames)
        self.Brange.stateChanged.connect(self.refresh_plot)
        self.Braw.stateChanged.connect(self.refresh_plot)
        self.BBrightDel.clicked.connect(self.delete_bright_measurement)
        self.BDarkDel.clicked.connect(self.delete_dark_measurement)
        self.info_button.clicked.connect(self.show_info)

    def show_info(self):
        dialog = InfoDialog(self)
        dialog.setWindowTitle("About the Software")
        dialog.setWindowModality(Qt.ApplicationModal)
        dialog.exec_()

    @pyqtSlot()
    def select_folder(self):
        """
        Allows user to select a folder using windows interface
        """
        old_folder = self.LEfolder.text()  # Read entry line
        if not old_folder:  #  If empty, go to default
            old_folder = "C:/Data/"
        #  Select directory from selection
        directory = QtWidgets.QFileDialog.getExistingDirectory(self, "Where do you want your data saved?", old_folder)
        if not directory:  #  if cancelled, keep the old one
            directory = old_folder
        self.LEfolder.setText(directory)
        self.folder = directory

        #  Arrow function, to create folderpath with User and Date

    @pyqtSlot()
    def automatic_folder(self):
        """
        Sets a folder up, with the date as name, under the selected username
        """
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
        """
        Create folder with specific name. If name exists, add a number to the name
        @param sample: sets folder name with the sample's one
        @param retry: number increases if repeated
        """
        self.folder = self.LEfolder.text()
        if self.folder[-1] != "/":
            self.folder = self.folder + "/"  #  Add "/" if non existent
            self.LEfolder.setText(self.folder)
        else:
            pass
        if sample:
            self.sample = self.LEsample.text()
            self.folder = self.folder + self.sample + "/"
            #  If sample name is duplicated, make a "-d#" folder
            if os.path.exists(self.folder):
                self.folder = self.folder.rsplit("/", 1)[0] + "-d" + str(retry) + "/"
                if os.path.exists(self.folder):
                    retry += 1
                    self.create_folder(True, retry)
                self.statusBar().showMessage("Sample is duplicated", 10000)

        if not os.path.exists(self.folder):  # If folders don't exist, make them
            os.makedirs(self.folder)
            self.statusBar().showMessage("Folder " + self.folder + " created", 5000)
        else:
            pass

    @pyqtSlot()
    def save_meta(self):
        """
        Collects and saves a csv file containing metadata
        """
        self.create_folder(False)
        self.gather_all_metadata()
        metadata = pd.DataFrame.from_dict(self.meta_dict, orient='index')
        metadata.to_csv(self.folder + "metadata.csv", header=False)
        self.statusBar().showMessage("Metadata file saved successfully", 5000)

    @pyqtSlot()
    def load_meta(self):
        """
        Allows you to select a file, and then populates metadata fields with that information
        """
        folder = self.LEfolder.text()
        metafile = QtWidgets.QFileDialog.getOpenFileName(self, "Choose your metadata file", folder)
        metadata = pd.read_csv(metafile[0], header=None, index_col=0).T
        labels = self.setup_labs + self.exp_labels + self.photoLu_labels + self.spinCo_labels
        objects = self.setup_vals + self.exp_vars + self.photoLu_vars + self.spinCo_vars

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
                    oo.setText(str(metadata[labels[cc]].values[0]))
        self.LEfolder.setText(metadata["Folder"].values[0])

        self.statusBar().showMessage("Metadata successfully loaded", 5000)

    def gather_all_metadata(self):
        """
        Creates dictionaries containing all relevant metadata
        """
        self.sample = self.LEsample.text()
        self.meta_dict = {}  #  All variables will be collected here

        all_metaD_labs = self.setup_labs + self.exp_labels + self.glv_labels + self.photoLu_labels + self.spinCo_labels
        all_metaD_vals = self.setup_vals + self.exp_vars + self.glv_vars + self.photoLu_vars + self.spinCo_vars

        try:  # Add data to dictionary
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
            "Comments"] = self.com_labels.toPlainText()  #  This field has a diffferent format than the others

    @pyqtSlot()
    def update_number_of_frames(self):
        """
            To update the field with total number of measurement frames
        """
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
        """
        Re-adjusts plot when slider is clicked
        """
        if not self.SBinttime.isSliderDown():
            bar = self.SBinttime.value()  # Read scrollbar value
            self.LEinttime.setText(str(self.arr_scrbar[bar]))  # Put value on entryline
            self.set_integration_time()

    @pyqtSlot()
    def set_integration_time(self):
        """
        Updates spectrometer's integration time
        """
        try:
            inttime = self.LEinttime.text()
            inttime = float(inttime.replace(',', '.'))  #  Read Entry field
        except:
            inttime = 0.1
        array_sb = np.array(self.arr_scrbar)  # Load array of scrollbar values
        pos = np.abs(array_sb - inttime).argmin()  # Find location of closest value in array

        if array_sb[pos] - inttime == 0:  # Set Scrollbar with respect to value chosen
            self.SBinttime.setValue(pos)
        else:
            self.SBinttime.setValue(pos)
            self.LEinttime.setText(str(inttime))
        self.update_number_of_frames()  # Update frames label
        self.current_inttime_ms = inttime * 1000
        self.process_queue.put(inttime)

    def wait_until_inttime_in_sync(self):
        """
        Delays measurement attempts in case live integration time does not match the chosen one
        """
        self.statusBar().showMessage('Waiting for integration times to be in sync.\tDo not click anything.')
        while not abs(self.current_inttime_ms - self.plot_worker.current_mean_frequency_ms) <= 10:  # 10ms tolerance
            QApplication.processEvents()
            pass
        self.statusBar().showMessage('Integration times are synced.')

    def toggle_widgets(self, status):
        """
        Disables QT widgets and renames buttons if process is running or not
        @param status: 
        """
        # Disable the following buttons and fields
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
        """
        Collects all relevant data & metadata and saves it into a csv file
        @param spectra_raw_array: List containing spectra data as measured
        @param spectra_meas_array: List containing spectra data as calculated
        @param time_meas_array:  List containing measurement times
        """
        self.gather_all_metadata()
        metadata = pd.DataFrame.from_dict(self.meta_dict, orient='index')
        wave = pd.DataFrame({"Wavelength (nm)": self.xdata})

        time_meas_array = np.round(time_meas_array,4)

        if self.Braw.isChecked():
            PLspecR = pd.DataFrame(spectra_raw_array.T, columns=time_meas_array)
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

        #  Remove all unused columns and simplify
        spectral_data = spectral_data.dropna(axis=1, how="all")
        spectral_data = spectral_data.round(1)
        filename = self.folder + self.sample + "_PL_measurement.csv"
        metadata.to_csv(filename, header=False)
        spectral_data.to_csv(filename, mode="a", index=False)
        if self.BSavePlot.isChecked():
            self.make_heatplot(spectra_raw_array, spectra_meas_array, time_meas_array)
        self.statusBar().showMessage("Data saved successfully", 5000)

    @pyqtSlot()
    def dark_measurement(self):
        """
        Tasks when measuring a dark spectra
        """
        self.BDarkMeas.setEnabled(False)
        self.wait_until_inttime_in_sync()
        self.average_cycles = int(self.LEcurave.text())  #  Read number in GUI
        self.BDarkMeas.setStyleSheet("color : yellow;")
        self.BDarkMeas.setText("Measuring...")
        self.brightdark_meas_worker = DarkBrightGatherer(self.average_cycles, self.array_size)
        self.emitter.ui_data_available.connect(self.brightdark_meas_worker.gathering_counts)
        self.brightdark_meas_worker.result.connect(self.after_dark_measurement)
        self.brightdark_meas_worker.moveToThread(self.brightdark_meas_thread)
        self.brightdark_meas_thread.start()
        self.BBrightMeas.setEnabled(True)
        self.BBrightMeas.setText("Measure")
        self.BBrightMeas.setStyleSheet("color : green;")

    @pyqtSlot(object)
    def after_dark_measurement(self, dark_mean):
        """
        Exit tasks after dark spectra has been collected
        @param dark_mean: List containing the dark spectra
        """
        self.emitter.ui_data_available.disconnect(self.brightdark_meas_worker.gathering_counts)
        self.brightdark_meas_thread.quit()
        self.brightdark_meas_thread.wait()
        self.dark_mean = dark_mean
        self.is_dark_data = True
        self.BDarkMeas.setStyleSheet("color : green;")
        self.BDarkMeas.setText("Measured")
        self.statusBar().showMessage('Measurement of dark spectra completed', 5000)
        self.BDarkMeas.setEnabled(True)
        self.refresh_plot()

    @pyqtSlot()
    def delete_dark_measurement(self):
        """
        Action of deleting dark spectra
        """
        self.dark_mean = None
        self.dark_mean = np.ones(len(self.xdata))
        self.is_dark_data = False
        self.BDarkMeas.setStyleSheet("color : black;")
        self.BDarkMeas.setText("Measure (deleted)")

    @pyqtSlot()
    def bright_measurement(self):
        """
        Tasks when measuring a bright spectra
        """
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
        self.Brange.setChecked(True)

    @pyqtSlot(object)
    def after_bright_measurement(self, bright_mean):
        """
        Exit tasks after bright spectra has been collected
        @param bright_mean: List containing the bright spectra
        """
        self.emitter.ui_data_available.disconnect(self.brightdark_meas_worker.gathering_counts)
        self.brightdark_meas_thread.quit()
        self.brightdark_meas_thread.wait()
        self.bright_mean = bright_mean
        self.is_bright_data = True
        self.BBrightMeas.setEnabled(True)
        self.BBrightMeas.setStyleSheet("color : green;")
        self.BBrightMeas.setText("Measured")
        self.statusBar().showMessage('Measurement of bright spectra completed', 5000)
        self.refresh_plot()

    @pyqtSlot()
    def delete_bright_measurement(self):
        """
        Action of deleting bright spectra
        """
        self.bright_mean = np.ones(len(self.xdata))
        self.is_bright_data = False
        self.BBrightMeas.setStyleSheet("color : black;")
        self.BBrightMeas.setText("Measure (deleted)")
        self.refresh_plot()

    @pyqtSlot()
    def press_start(self):
        """
        Actions to start collecting spectra
        """
        if not self.is_measuring:
            self.delay = float(self.LEdeltime.text())
            self.LEskip.setText(utils.LEskip_positive_number(self.LEskip.text()))
            self.timer = QTimer()
            self.timer_interval = 0.1
            self.timer.setInterval(int(self.timer_interval * 1000))
            self.timer.timeout.connect(self.delayed_start)
            self.timer.start()
        else:
            self.spec_thread.quit()
            self.is_measuring = False
            self.toggle_widgets(False)
            self.save_data(self.meas_worker.spectra_raw_array, self.meas_worker.spectra_meas_array,
                           self.meas_worker.time_meas_array)

    def delayed_start(self):
        """
        Delays the measurement start by selected time, displaying a countdown
        """
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

    @pyqtSlot(int)
    def during_measurement(self, counter):
        """
        To update values in GUI
        """
        #  This updates the number of measurements that will be made
        self.LAframes.setText(str(counter) + "/" + str(self.total_frames))
        self.elapsed_time = time() - self.start_time
        minute, second = divmod(self.elapsed_time, 60)
        self.LAelapse.setText("{:02}:{:02}".format(int(minute), int(second)))

    @pyqtSlot()
    def after_measurement(self):
        """
        Exit actions after spectra has been collected
        """
        self.toggle_widgets(False)
        self.is_measuring = False

    def make_heatplot(self, spectra_raw_array, spectra_meas_array, time_meas_array):
        """
        Triggered at the End
        """
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

        #  fix axis ticks so they match the data (else they are array positions)
        ax1.set_yticks(np.linspace(0, waveLen, 8))
        ax1.set_yticklabels(np.linspace(PLmin, PLmax, 8).astype(int))
        ax1.set_xticks(np.linspace(0, len(time), 8))
        ax1.set_xticklabels(np.around(np.linspace(0, np.max(time), 8), decimals=1))
        ax1.pcolorfast(heatplot)
        fig.savefig(
            self.folder + "0_preview_" + self.sample + "_heatplot.png")
        plt.close()  # close the figure window

    def send_to_Qthread(self):
        """
        Starts parallel process for the different spectra collecting actions (raw, dark, bright)
        """
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
        """
        Resets status of plot. Mainly to remove legend and frozen curves after desactivating is_show_raw
        """
        self.plot_worker.is_show_raw = self.Braw.isChecked()
        self.plot_worker.is_dark_data = self.is_dark_data
        self.plot_worker.is_bright_data = self.is_bright_data
        self.plot_worker.dark_mean = self.dark_mean
        self.plot_worker.bright_mean = self.bright_mean
        self.plot_worker.is_fix_y = self.Brange.isChecked()
        self.plot_worker.set_axis_range()
        if not self.Braw.isChecked() and not self.Brange.isChecked():
            self.plot_worker.reset_axes()

    @pyqtSlot()
    def finished_plotting(self):
        """
        Displays end of event in status bar
        """
        self.statusBar().showMessage("Plotting process finished and images saved", 5000)

    def closeEvent(self, event):
        """
        Actions when closing the app
        @param event: 
        """
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
