__author__ = "Edgar Nandayapa"
__version__ = "1.13 (2022)"


import sys
import os
import csv
import traceback
import matplotlib
matplotlib.use('Qt5Agg')

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg, NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
from collections import OrderedDict
import matplotlib.pyplot as plt
# from matplotlib.ticker import MaxNLocator

from PyQt5 import QtWidgets
from PyQt5.QtWidgets import QGridLayout, QVBoxLayout, QHBoxLayout, QSpacerItem, QSizePolicy
from PyQt5.QtWidgets import QScrollBar,QToolButton,QLabel,QComboBox,QLineEdit,QMenu
from PyQt5.QtWidgets import QDialog,QFormLayout,QDialogButtonBox,QAction,QCheckBox,QMessageBox
from PyQt5.QtCore import Qt,QObject,pyqtSignal,QRunnable,pyqtSlot,QThreadPool
from PyQt5.QtGui import QFont, QIcon
from qtrangeslider import QLabeledRangeSlider

from lmfit.models import LinearModel,PolynomialModel
from lmfit.models import ExponentialModel,GaussianModel,LorentzianModel,VoigtModel
from lmfit.models import PseudoVoigtModel,ExponentialGaussianModel,SkewedGaussianModel,SkewedVoigtModel

import pandas as pd
import numpy as np
from time import time
from datetime import datetime
from glob import glob


from functools import partial

from matplotlib import rcParams
rcParams.update({'figure.autolayout': True})
cmaps = OrderedDict()


class WorkerSignals(QObject):
    finished = pyqtSignal()
    error = pyqtSignal(tuple)
    result = pyqtSignal(object)
    progress = pyqtSignal(object)


class Worker(QRunnable):
    def __init__(self, fn, *args, **kwargs):
        super(Worker, self).__init__()

        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()

        self.kwargs['progress_callback'] = self.signals.progress

    
    @pyqtSlot()
    def run(self):
        try:
            result = self.fn(*self.args, **self.kwargs)
        except:
            traceback.print_exc()
            exctype, value = sys.exc_info()[:2]
            self.signals.error.emit((exctype, value, traceback.format_exc()))
        else:
            self.signals.result.emit(result)  # Return the result of the processing
        finally:
            self.signals.finished.emit()  # Done


class MplCanvas_heatplot(FigureCanvasQTAgg):
    def __init__(self, parent=None, width=5, height=4, dpi=100):
        self.figh = Figure(figsize=(width, height), dpi=dpi)
        self.axes = self.figh.add_subplot(111)
        self.axes.set_xlabel('Time (s)')
        self.axes.set_ylabel('Wavelength (nm)')

        super(MplCanvas_heatplot, self).__init__(self.figh)
        
        
        
class MplCanvas(FigureCanvasQTAgg):
    def __init__(self, parent=None, width=5, height=4, dpi=100):
        fig = Figure(figsize=(width, height), dpi=dpi)
        self.axes = fig.add_subplot(111)
        self.axes.set_xlabel('Wavelength (nm)')
        self.axes.set_ylabel('Intensity (a.u.)')
        self.axes.grid(True,linestyle='--')

        super(MplCanvas, self).__init__(fig)
        


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, *args, **kwargs):
        super(MainWindow, self).__init__(*args, **kwargs)
        
        self.menu = QMenu(self)
        self.menu.setToolTipsVisible(True)
        mainMenu = self.menuBar()
        
        infoMenu = QAction("&About", self)
        
        open_PL = QAction("Open single file (&Automatic)",self) ##"Open File"
        open_Manu=QAction("Open single file (&Manual)",self) ## "Open (Manual)"
        open_xrd =QAction("Open folder w/ &Log files",self) ## "Open GIWAXS"
        open_plf =QAction("Open folder (Multiple &files)",self) ## "Open PL folder"
        open_vin =QAction("Open folder (Multiple f&iles)",self) ## "Vincent mode"
        open_PL.setShortcut("Ctrl+O")
        open_Manu.setShortcut("Ctrl+M")
        open_xrd.setShortcut("Ctrl+P")
        open_plf.setShortcut("Ctrl+U")
        open_PL.setToolTip("This will open most files automatically")
        open_Manu.setToolTip("Use this if automatic function\n   is not showing what you expect")
        open_xrd.setToolTip("Use this if there is a log file\n   containing temperature information")
        open_plf.setToolTip("Use this in case the data is\n   is in individual spectra or files")
        open_vin.setToolTip("Use this in case the data is\n   is in individual spectra or files")
        open_PL.triggered.connect(self.renew_plot_direct)
        open_Manu.triggered.connect(self.renew_plot_manual)
        open_xrd.triggered.connect(self.renew_plot_giwaxs)
        open_plf.triggered.connect(self.renew_plot_PL_folder)
        open_vin.triggered.connect(self.renew_vincent_mode)
        
        add_model = QAction("Add &model line",self)
        fid_save = QAction("&Save fit parameters",self)
        fit_load = QAction("&Load fit parameters",self)
        fit_single = QAction("Fit &current spectra",self)
        fit_multip =QAction("&Fit selected range",self)
        fid_save.setShortcut("Ctrl+S")
        fit_load.setShortcut("Ctrl+L")
        add_model.setShortcut("Ctrl+A")
        fit_single.setShortcut("Ctrl+D")
        fit_multip.setShortcut("Ctrl+Alt+F")
        add_model.setToolTip("This will add one more model line to the interface\n  up to 14 times")
        fid_save.setToolTip("This will save the model configuration values")
        fit_load.setToolTip("This will load the model configuration values")
        fit_single.setToolTip("This will fit the data at the current view point")
        fit_multip.setToolTip("This will fit the data within the chosen range")
        fid_save.triggered.connect(self.get_all_fit_fields)
        fit_load.triggered.connect(self.populate_fit_fields)
        add_model.triggered.connect(self.add_model_row)
        fit_single.triggered.connect(self.fitmodel_process)
        fit_multip.triggered.connect(self.start_parallel_calculation)
        
        other_clean = QAction("Clean &dead Pixel (831nm)",self)
        other_eV = QAction("Convert to &Energy (eV)",self)
        other_subtract = QAction("Subtract &background",self)
        other_save = QAction("&Save current dataset",self)
        other_color = QAction("Set heatplot &color range",self)
        other_clean.setToolTip("This will remove a spike at 831 nm (from a dead pixel in detector)")
        other_eV.setToolTip("This will convert wavelength into energy and viceversa")
        other_subtract.setToolTip("This will substract the background, in case there was no dark measurement")
        other_save.setToolTip("This will save a data file and the heatplot of the current dataset")
        other_color.setToolTip("You can select a better color range for the heatplot here")
        other_clean.triggered.connect(self.clean_dead_pixel)
        other_eV.triggered.connect(self.convert_to_eV)
        other_subtract.triggered.connect(self.popup_subtract_bkgd)
        other_save.triggered.connect(self.save_current_state)
        other_color.triggered.connect(self.popup_heatplot_color_range)
 
        
        ##Create menues
        fileMenu = mainMenu.addMenu("&File")
        fitMenu = mainMenu.addMenu("Fi&t")
        otherMenu = mainMenu.addMenu("&Other")

        a =fileMenu.addAction("Photoluminescence")
        a.setDisabled(True)
        fileMenu.addAction(open_PL)
        fileMenu.addAction(open_Manu)
        fileMenu.addAction(open_plf)
        fileMenu.addSeparator()
        b =fileMenu.addAction("GIWAXS")
        b.setDisabled(True)
        fileMenu.addAction(open_xrd)
        fileMenu.addAction(open_vin)
        fitMenu.addAction(add_model)
        fitMenu.addAction(fid_save)
        fitMenu.addAction(fit_load)
        fitMenu.addSeparator()
        fitMenu.addAction(fit_single)
        fitMenu.addAction(fit_multip)
        otherMenu.addAction(other_eV)
        otherMenu.addSeparator()
        otherMenu.addAction(other_clean)
        otherMenu.addAction(other_subtract)
        otherMenu.addAction(other_color)
        otherMenu.addSeparator()
        otherMenu.addAction(other_save)
        mainMenu.addAction(infoMenu)
        
        
        Lmain = QHBoxLayout()
        
        self.setWindowTitle("Spectra Analyzer")
        self.setWindowIcon(QIcon("./graph.ico"))
        
        self.L1fit = QHBoxLayout()
        self.LGfit = QGridLayout()
        self.Badd= QToolButton()
        self.Badd.setText("+")
        self.Bsubtract= QToolButton()
        self.Bsubtract.setText("-")
        self.Bfit= QToolButton()
        self.Bfit.setText("Fit")
        self.LR = QLabel()
        self.Lvalue = QLabel()
        self.L1 = QLabel("Start:")
        self.L1.setAlignment(Qt.AlignRight)
        self.L1.setFixedWidth(60)
        self.L2 = QLabel("End:")
        self.L2.setFixedWidth(60)
        self.L2.setAlignment(Qt.AlignRight)
        self.LEstart = QLineEdit()
        self.LEend = QLineEdit()
        self.LEstart.setFixedWidth(60)
        self.LEend.setFixedWidth(60)
        self.BMulti = QToolButton()
        self.BMulti.setText("Fit range")
        self.BMulti.setFixedWidth(120)
        self.Btest = QToolButton()
        self.Btest.setText("test")
        
        self.mnm = 14 ##Max number of models
        
        verticalSpacer = QSpacerItem(20, 10, QSizePolicy.Minimum, QSizePolicy.Expanding)
        horizontSpacer = QSpacerItem(10, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)
        
        self.L1fit.addWidget(self.Badd)
        self.L1fit.addWidget(self.Bsubtract)
        self.L1fit.addWidget(self.LR)
        self.L1fit.addWidget(self.Lvalue)
        self.L1fit.addItem(horizontSpacer)
        self.L1fit.addWidget(self.Bfit)
        
        Lmulti = QGridLayout()
        Lmulti.addWidget(self.L1,0,0)
        Lmulti.addWidget(self.LEstart,0,1)
        Lmulti.addWidget(self.L2,0,2)
        Lmulti.addWidget(self.LEend,0,3)
        Lmulti.addWidget(self.BMulti,1,1,1,2)
        Lmulti.addWidget(self.Btest,2,0)

        Lend = QHBoxLayout()
        Lend.addLayout(Lmulti)
        Lend.addItem(horizontSpacer)
        
        Lfit = QVBoxLayout()
        Lfit.addLayout(self.L1fit)
        Lfit.addLayout(self.LGfit)
        Lfit.addItem(verticalSpacer)
        Lfit.addItem(Lend)
        # Create the maptlotlib FigureCanvas object
        self.canvas = MplCanvas(self)
        self.savnac = MplCanvas_heatplot(self)
        
        self.threadpool = QThreadPool.globalInstance()

        self.SBtime = QScrollBar()
        self.SBtime.setOrientation(Qt.Horizontal)
        self.SBtime.setMaximum(0)
        self.SBtime.setStyleSheet("background : gray;")
        
        # Create toolbar, passing canvas as first parament, parent (self, the MainWindow) as second.
        toolbar = NavigationToolbar(self.canvas, self)

        Lgraph = QVBoxLayout()
        self.canvas.setMinimumWidth(500)##Fix width so it doesn't change
        self.range_slider = QLabeledRangeSlider()
        self.range_slider.setFixedWidth(70)
        self.range_slider.setMinimum(0)
        self.range_slider.setMaximum(1)
        self.range_slider.setValue((0,1))
        self.range_slider.EdgeLabelMode.NoLabel
        self.range_slider.EdgeLabelMode.LabelIsValue

        Lgraph.addWidget(toolbar)
        Lgraph.addWidget(self.canvas)
        Lgraph.addWidget(self.SBtime)
        LHgra = QHBoxLayout()
        LHgra.addWidget(self.range_slider)
        LHgra.addWidget(self.savnac)
        Lgraph.addLayout(LHgra)

        Lmain.addLayout(Lfit,3)
        Lmain.addLayout(Lgraph,6)
        
        widget = QtWidgets.QWidget()
        widget.setLayout(Lmain)
        self.setCentralWidget(widget)
        self.show()
        
        # Create a placeholder widget to hold our toolbar and canvas.
        self.grid_count = 0
        self.combo_mod = []
        self.plots = []
        self.models = ["","Linear","Polynomial","Exponential","Gaussian",
                       "Lorentzian","Voigt","PseudoVoigt","SkewedVoigt",
                       "ExpGaussian","SkewedGaussian",]
        self.giwaxs_bool = False
        self.pero_peak = False
        self.selected_f = False

        self.add_fit_setup()
        
        self.constraints = []
        for i in range(self.mnm):
            self.constraints.append([])
            
        self.fw =46 ##width of QLineEdit fields
        for nn,cb in enumerate(self.combo_mod):
            try:
                cb[1].currentTextChanged.connect(partial(self.make_ComboBox_fields,cb,nn))
                cb[1].setFixedWidth(100)
            except:
                pass

        self.Bfit.pressed.connect(self.fitmodel_process)
        self.BMulti.pressed.connect(self.start_parallel_calculation)
        self.SBtime.valueChanged.connect(self.scrollbar_action)
        self.range_slider.valueChanged.connect(self.slider_action)
        self.Badd.pressed.connect(self.add_model_row)
        self.Bsubtract.pressed.connect(self.remove_model_row)
        infoMenu.triggered.connect(self.popup_info)
        # self.Btest.pressed.connect(self.clean_dead_pixel)

        
    def renew_plot_direct(self):
        self.select_file()
        self.giwaxs_bool = False
        if self.selected_f:
            self.popup_test_file_fast()
            self.extract_data()
            self.renew_plot_continued()
        else:
            self.statusBar().showMessage("File not selected", 5000)
            
        
    def renew_plot_manual(self):
        ##TODO add a description to manual menu
        self.select_file()
        self.giwaxs_bool = False
        if self.selected_f:
            self.popup_read_file()
            self.popup_test_file_slow()
            try:
                self.extract_data()
                self.renew_plot_continued()
            except:
                self.statusBar().showMessage("ERROR: All column names should be numbers in manual mode!!",5000)
                print(self.mdata)
        else:
            self.statusBar().showMessage("File not selected", 5000)
        
    def renew_plot_PL_folder(self):
        self.select_folder()
        self.giwaxs_bool = False
        if self.selected_f:
            self.pl_folder_gather_data()
            self.extract_data()
            self.save_data_2DMatrix()
            self.save_heatplot_giwaxs()
            self.renew_plot_continued()
        else:
            self.statusBar().showMessage("Folder not selected", 5000)
        
    def renew_plot_giwaxs(self):
        self.giwaxs_bool = True
        self.select_folder()
        if self.selected_f:
            self.giwaxs_popup()
            self.extract_giwaxs()
            self.save_data_2DMatrix()
            self.save_heatplot_giwaxs()
            self.renew_plot_continued()
        else:
            self.statusBar().showMessage("Folder not selected", 5000)
        
    def renew_vincent_mode(self):
        self.select_folder()
        self.giwaxs_bool = False
        if self.selected_f:
            self.vincent_gather_data()
            self.extract_data()
            self.save_data_2DMatrix()
            self.save_heatplot_giwaxs()
            self.renew_plot_continued()
        else:
            self.statusBar().showMessage("Folder not selected", 5000)
        
    def renew_plot_continued(self):
        # self.giwaxs_bool = False
        self.statusBar().showMessage("Loading files, please wait...")
        self.plot_setup()
        self.set_default_fitting_range()
        self.SBtime.setMaximum(self.xsize)
        self.bar_update_plots(0)
        self.statusBar().showMessage("")    
        
        
    def save_data_2DMatrix(self):
        fi,le = self.gfile.rsplit("/",1)
        self.mdata.to_excel(fi+"/0_collected_"+le+".xlsx")

    def clean_dead_pixel(self):
        self.mdata.iloc[1421] = self.mdata.iloc[1419:1421].mean()
        self.mdata.iloc[1423] = self.mdata.iloc[1425:1427].mean()
        self.mdata.iloc[1422] = self.mdata.iloc[np.r_[1419:1421,1425:1427]].mean()
        self.scrollbar_action()

    def add_model_row(self):
        try:
            for gc in self.combo_mod[self.grid_count][1:]:
                gc.setVisible(True)
            self.grid_count += 1
        except:
            ##TODO: add true/false to avoid overwritting the message
            self.LGfit.addWidget(QLabel("Reached Maximum"),100,0)
    
    def remove_model_row(self):
        if self.grid_count > 0:
            self.grid_count -= 1
            self.combo_mod[self.grid_count][1].setCurrentIndex(0)
            for gc in self.combo_mod[self.grid_count][1:]:
                gc.setVisible(False)

            self.clean_all_fit_fields()
        else:
            pass
        
    def clean_all_fit_fields(self):
        rows = list(range(self.LGfit.rowCount()))[1:]
        x_arr = [1,2,4,6,8]## usable grid coordinates
        y_arr = [h for h in rows if h%2==0] ## odd rows
        
        # print(self.grid_count)
        
        for yd in y_arr:
            for xd in x_arr:
                testmod = self.LGfit.itemAtPosition(yd,xd)
                try: ## if widget found
                    fieldwid = testmod.widget()
                    if isinstance(fieldwid, QLabel):
                        # print(fieldwid.text())
                        fieldwid.setText("") ##remove text
                except:
                    pass
        self.LR.setText("")
        self.Lvalue.setText("")
        
    def get_all_fit_fields(self):
        x_arr = [1,2,4,6,8]## usable grid coordinates
        rows = list(range(self.LGfit.rowCount()))
        y_arr = [h for h in rows if h%2==1]
        
        all_mods = []
        for yd in y_arr:
            row_mod = []
            for xd in x_arr:
                testmod =self.LGfit.itemAtPosition(yd,2)

                testwid = testmod.widget()
                if len(testwid.currentText()):
                    field = self.LGfit.itemAtPosition(yd,xd)
                    try:
                        fieldwid = field.widget()
                        try:
                            row_mod.append(fieldwid.text())
                        except:
                            row_mod.append(fieldwid.currentText())
                    except:
                        pass
            all_mods.append(row_mod)
        
        filename = QtWidgets.QFileDialog.getSaveFileName(self, 'Save Fit Parameters File', "", "fit (*.fit)")

        if filename[0] != "":
            textfile = open(filename[0], "w")
            for col_dat in all_mods:
                for row_dat in col_dat:
                    textfile.write(row_dat+"\t")
                textfile.write("\n")
            textfile.close()
        else:
            self.statusBar().showMessage("Fit parameter file not saved", 5000)
            # raise Exception("Fit parameter file not saved")
            # return
    
    def populate_fit_fields(self):
        filename = QtWidgets.QFileDialog.getOpenFileName(self, "Select file with fitting parameters?", "", "fit (*.fit)") 
        
        if filename[0] != "":
            x_arr = [1,2,4,6,8]## usable grid coordinates
            with open(filename[0], "r") as fd:
                reader = csv.reader(fd, delimiter="\t")
                for cr,row in enumerate(reader):
                    if len(row)>1:
                        self.grid_count += 1
                        for gc in self.combo_mod[cr][1:]:
                            gc.setVisible(True)
                        for ce,ele in enumerate(row[:-1]):
                            field = self.LGfit.itemAtPosition(cr*2+1,x_arr[ce])
                            try:
                                fieldwid = field.widget()
                                try:
                                    fieldwid.setText(ele)
                                except:
                                    fieldwid.setCurrentText(ele)
                            except:
                                pass
        else:
            self.statusBar().showMessage("Fit parameter file not loaded", 5000)
            # raise Exception("Fit parameter file not loaded")
            # return
            
    def save_heatplot_giwaxs(self):
        fi,le = self.gfile.rsplit("/",1)
        
        ticks_n = 10
        
        try:
            sets = len(self.separated)
    
            if "Time" in self.separated[0].keys():
                total_size = self.separated[-1]["Time"].iloc[-1]
            else:
                total_size = self.separated[-1]["eta"].iloc[-1]
            
            ind_sizes = []
            last_time=0
            
            mnT = 100 ##dummy values to find the temperature range
            mxT = 0
            step = 0
            for cg, gs in enumerate(self.separated):
                if cg == 0:
                    step = gs["Time"].iloc[1]
                    dist = gs["Time"].iloc[-1] + step
                    total_size += step
                    last_time = dist
                else:
                    dist = gs["Time"].iloc[-1]+step-last_time
                    # print(gs["Time"].iloc[0],gs["Time"].iloc[-1],dist)
                    last_time = dist
                    
                ind_sizes.append(dist/total_size) ##To find the ratio of the frames
            
                if mnT > np.min(gs.DegC):
                    mnT = np.min(gs.DegC)
                
                if mxT < np.max(gs.DegC):
                    mxT = np.max(gs.DegC)

            fig, axs = plt.subplots(1,sets,figsize=(12,9), gridspec_kw={'width_ratios': ind_sizes,'wspace':0.02,
                                                                        'hspace':0.02},sharex=False,sharey=True)
            fig.set_tight_layout(False)
            
            srt = 0
            for c, ks in enumerate(self.separated):
                end = srt+ks.shape[0]-1
                mat = self.mdata.iloc[:,srt:end]
                leng= ks.shape[0]
                temp = ks.DegC

                axs[c].pcolorfast(mat, vmin = min(self.mdata.min())*0.9, vmax = max(self.mdata.max())*1.1 )
                axt = axs[c].twinx()
                axt.plot(temp, "--m")
                axt.set_ylim([mnT*0.9,mxT*1.05])
                
                tn = int(ticks_n*ind_sizes[c])
                if tn <= 1:
                    tn = 2
                axs[c].set_xticks(np.linspace(0,leng-1,tn))
                axs[c].set_xticklabels(np.around(np.linspace(self.xtime[srt], self.xtime[end], tn),decimals=1).astype(int))                    
                                   
                if c == 0:
                    axs[0].set_ylabel(r"2$\theta$ (Degree)")
                    axs[0].set_yticks(np.linspace(0,len(self.wave),8))
                    axs[0].set_yticklabels(np.linspace(self.wave[0],self.wave[-1],8).astype(int))
                
                else:
                    pass
                
                if c%2 == 0:
                    axs[c].xaxis.tick_bottom()
                else:
                    axs[c].xaxis.tick_top()
                    
                if c == sets-1:
                    ##this uses the secondary axis (axt)
                    axt.set_ylabel("Temperature (°C)",color="m")
                    axt.tick_params(axis='y', colors='m')
                    
                else:
                    axt.yaxis.set_major_locator(plt.NullLocator())
               
                srt = srt+leng
                
            if "eta" in self.gname:
                fig.text(0.5, 0.08, 'Eta (degrees)', ha='center')
            else:
                fig.text(0.5, 0.08, 'Time (seconds)', ha='center')
            
            fig.savefig(fi+"/0_heatplot_"+le+".png", dpi=300)
            plt.close()
        except:
            self.savnac.figh.savefig(fi+"/0_heatplot_"+le+".png", dpi=300)
        
        # plt.close()
        
    def select_file(self):
        # old_folder = self.LEfolder.text() ##Read entry line
        self.selected_f = True
        old_folder = "C:\\Data\\test\\"
        
        if not old_folder: ## If empty, go to default
            old_folder = "C:\\Data\\"
        
        ## Select directory from selection
        directory = QtWidgets.QFileDialog.getOpenFileName(self, "Select a file", old_folder) 
        # print(directory)
        
        if directory[0] !="": ## if cancelled, keep the old one
            self.folder = directory[0]
        else:
            self.selected_f = False
            # return
            
        
    def select_folder(self):
        self.selected_f = True
        self.giw_dir= QtWidgets.QFileDialog.getExistingDirectory(self, 'Select a directory')
        # self.folder = self.giw_dir
        

        if self.giw_dir != "":## If folder selected, then
            file_list = glob(self.giw_dir+"\\*")## Get all files
            input_file = []
            
            for p in file_list: ## Keep only log files (for giwaxs)
                if "." not in p[-5:] and "Fitting" not in p:
                    input_file.append(p)
                else:
                    pass
            
            self.giw_names = []
            for f in input_file:
                self.giw_names.append(f.split("\\")[-1])
                
            
        else:
            self.selected_f = False

    
    ##TODO always show open file/exp name on title bar    
    def giwaxs_popup(self):
        self.dgiw = QDialog()
        Lopt = QVBoxLayout()
        Lopt.setAlignment(Qt.AlignCenter)
        
        Tdats = QLabel("The following datasets were found,\nplease select one number:\n")
        Lopt.addWidget(Tdats)
        
        for cs, ds in enumerate(self.giw_names):
            Tlab = QLabel("\t"+str(cs+1)+":\t"+ds)
            Lopt.addWidget(Tlab)
            
        Tempt = QLabel("\n")
        Lopt.addWidget(Tempt)
        
        self.sel_ds = QLineEdit()
        self.sel_ds.setFixedWidth(50)
        self.sel_ds.setAlignment(Qt.AlignCenter)
        self.sel_ds.setText("1")
        Lopt.addWidget(self.sel_ds)
        
        Bok = QDialogButtonBox(QDialogButtonBox.Ok)
        Lopt.addWidget(Bok)
        Bok.accepted.connect(self.popup_giwaxs_ok)
        
        self.dgiw.setLayout(Lopt)
        self.dgiw.setWindowTitle("Select data")
        self.dgiw.setWindowModality(Qt.ApplicationModal)
        self.dgiw.exec_()
        
        
    def popup_giwaxs_ok(self):
        self.dgiw.close()
        self.giwaxs_gather_data()

    def vincent_gather_data(self):
        pl_files = sorted(glob(self.giw_dir+"\\*.dat"))

        self.gfile = self.giw_dir+"/"+self.giw_dir.split("/")[-1]
        ##TODO clean this folder gfile
        self.folder = self.gfile
        
        for counter, file in enumerate(pl_files):
            data = pd.read_csv(file, delimiter="\t", skiprows=4, header=None,names=["2Theta",counter],index_col=False)
            
            if counter == 0:
                self.mdata = data
                
            else:
                self.mdata = self.mdata.join(data.set_index("2Theta"), on="2Theta")
                
        self.mdata.set_index("2Theta", inplace=True)

    def pl_folder_gather_data(self):
        # pl_files = glob(self.giw_dir+"\\*.txt")
        pl_files = sorted(glob(self.giw_dir+"\\*.txt"),key=os.path.getmtime)

        self.gfile = self.giw_dir+"/"+self.giw_dir.split("/")[-1]
        ##TODO clean this folder gfile
        self.folder = self.gfile
        
        for counter, file in enumerate(pl_files):
            data = pd.read_csv(file, delimiter="\t", skiprows=14, header=None,names=["Wavelength",counter],index_col=False)
            meta = pd.read_csv(file, delimiter=": ", skiprows=2, nrows=10,index_col=0, header=None,engine="python")
            time = str(meta.T.Date.values[0])
            time = time.replace("CEST ","")
            delta = datetime.strptime(time, '%a %b %d %H:%M:%S %Y')
            # print(delta)
            
            if counter == 0:
                start_t = delta
                # print(data)
                self.mdata = data
                
            else:
                curr_t = delta - start_t
                curr_t = curr_t.total_seconds()
                self.mdata = self.mdata.join(data.set_index("Wavelength"), on="Wavelength")
                self.mdata.rename(columns={counter:curr_t})

        self.mdata.set_index("Wavelength", inplace=True)


    def giwaxs_gather_data(self):
        ## This part pre-reads files to find where data start and end
        
        ## read number from popup and fix it if its not there
        fnum = self.sel_ds.text()
        if int(fnum)-1 in range(len(self.giw_names)):
            fnum = int(fnum)-1
        else:
            fnum = 0
        
        self.gname = self.giw_names[fnum]
        self.gfile = self.giw_dir+"/"+self.gname
        input1 = open(self.gfile, 'rb')
        with input1 as f:
            lines = f.readlines()
        
        ## Analyze file and gather positions of relevant information (time, eta, degC)
        count = 0
        elapsed = 0
        data1 = False
        datetime_object = 0
        combined = 0
        
        times = []
        starts= []
        ends  = []
        line = 1
        # datasets = 0
        for line in lines:
            if "#S" in str(line):
                data1 = True
        
            if "#D" in str(line) and data1:
                time = str(line[3:-1])[2:-1]
                delta = datetime.strptime(time, '%a %b %d %H:%M:%S %Y')
                if datetime_object == 0:
                    elapsed = 0
                    delta_start = delta
                else:
                    elapsed = delta - delta_start
                    elapsed = elapsed.total_seconds()
                datetime_object = delta
                times.append(elapsed)
                
            if "#L" in str(line) and data1:
                head = str(line[3:-1])[2:-1].split("  ")
                starts.append(count)
        
            if "#C results" in str(line) and data1:
                ends.append(count)
                
            count += 1
        input1.close()
        
        ## Gather relevant information from step above with pandas
        end_times = []
        self.separated = []
        for c,t in enumerate(times):
            data = pd.read_csv(self.gfile, delimiter=" ", skiprows=starts[c]+1, header=None, nrows=ends[c]-starts[c]-1 )
            data.columns = head
            

            if c == 0:
                combined = data
            else:
                if "eta" in self.gfile:
                    pass
                else:
                    end_times.append(data.Time.iloc[-1])
                    data.Time = data.Time+t
                    
                    combined = pd.concat([combined,data])
            # print(combined)
            self.separated.append(data)
        combined = combined.reset_index(drop=True)
        
        ## Gather measurement data using pandas
        pd.set_option('mode.chained_assignment',None)## ignores an error message
        for counter,gf in enumerate(glob(self.gfile+"_[0-9]*.dat")):
            ## Read data from file
            Mdata = pd.read_csv(gf, index_col=None, skiprows=15, header=None, delimiter="\t")
            raw_dat = Mdata[[0,1]]
            raw_dat.rename(columns={0:"TTh",1:"m_"+str(counter)},inplace = True)
            
            if counter == 0:
                self.mdata = raw_dat
            else:
                self.mdata = self.mdata.join(raw_dat.set_index("TTh"), on="TTh")
                
        self.mdata = self.mdata.set_index("TTh")  
        # print(self.mdata)
        
        if "eta" in self.gfile:        
            self.mdata.columns=[combined.eta, combined.DegC]
            self.comb_data = combined[["eta","DegC"]]
        else: 
            self.mdata.columns=[combined.Time,combined.DegC]
            self.comb_data = combined[["Time","DegC"]]
            
        
    def extract_giwaxs(self):
        try:
            self.xtime = [ik[0] for ik in self.mdata.keys()]
        except:
            self.xtime=self.mdata.keys().values.astype(float)
        self.xsize = len(self.xtime)-1
        
        self.max_int = self.mdata.to_numpy().max()
        self.min_int = self.mdata.to_numpy().min()
        
        self.wave = self.mdata.index
        self.ysize = len(self.wave)
        
        self.range_slider.setMaximum(self.ysize)
        self.range_slider.setValue((0,self.ysize))
        self.set_default_fitting_range()
        
    def extract_data(self):
        ## Extract relevant data
        self.xtime = self.mdata.keys().astype(float)
        self.xsize = len(self.xtime)-1
        
        fix_arr = np.ma.masked_invalid(self.mdata.to_numpy())
        self.max_int = fix_arr.max()
        self.min_int = fix_arr.min()
        
        self.wave = self.mdata.index
        self.ysize = len(self.wave)
        self.range_slider.setMaximum(self.ysize)
        self.range_slider.setValue((0,self.ysize))
       
        
    def popup_info(self):
        dinf = QDialog()
        Ltext = QVBoxLayout()
        
        Tlibra = QLabel("Fitting is done using \nthe python library \"lmfit\"")
        Tlibra.setAlignment(Qt.AlignCenter)
        Tlibra.setFont(QFont('Arial', 12))
        
        Tmodel = QLabel("More information about the models can be found at")
        Tmodel.setAlignment(Qt.AlignCenter)
        Tmodel.setFont(QFont('Arial', 12))
        Tmodel.setOpenExternalLinks(True)
        
        urlLink="<a href=\"https://lmfit.github.io/lmfit-py/builtin_models.html\">lmfit.github.io</a>"
        Tlink = QLabel()
        Tlink.setOpenExternalLinks(True)
        Tlink.setText(urlLink)
        Tlink.setAlignment(Qt.AlignCenter)
        Tlink.setFont(QFont('Arial', 12))
        
        Tempty = QLabel("")
        Tauthor = QLabel("Program created by Edgar Nandayapa (2021)\nHelmholtz-Zentrum Berlin")
        Tauthor.setAlignment(Qt.AlignCenter)
        Tauthor.setFont(QFont('Arial', 8))
        
        Ltext.addWidget(Tlibra)
        Ltext.addWidget(Tempty)
        Ltext.addWidget(Tmodel)
        Ltext.addWidget(Tlink)
        Ltext.addWidget(Tempty)
        Ltext.addWidget(Tauthor)
        
        dinf.setLayout(Ltext)
        dinf.setWindowTitle("About")
        dinf.setWindowModality(Qt.ApplicationModal)
        dinf.exec_()
        
        
    def popup_read_file(self):
        self.dlg = QDialog()
        self.ind_col = QLineEdit()
        self.skiprow = QLineEdit()
        self.headers = QLineEdit()
        self.delimit = QLineEdit()
        self.decimal =QLineEdit()
        self.remove = QLineEdit()
        self.clean = QCheckBox()
        
        self.ind_col.setText("0")
        self.skiprow.setText("22")
        self.headers.setText("0")
        self.remove.setText("None")
        self.decimal.setText(".")
        if "csv" in self.folder[-4:]:
            self.delimit.setText(",")
        else:
            self.delimit.setText("\\t")
        
        bok = QDialogButtonBox(QDialogButtonBox.Ok)
        btest = QToolButton()
        btest.setText("Test")
        
        self.QFL = QFormLayout()
        
        skrs = QLabel("Skip rows")
        skrs.setToolTip("Number of rows to skip\n   e.g.where metadata is\n   None if no not needed")
        self.QFL.addRow(skrs,self.skiprow)
        
        pohr = QLabel("Position of header")
        pohr.setToolTip("Row where header is\n   (Remember first row is 0)")
        self.QFL.addRow(pohr,self.headers)
        
        ixcn = QLabel("Index column")
        ixcn.setToolTip("Number of column where index is, usually Wavelength\n   (Remember first column is 0)")
        self.QFL.addRow(ixcn,self.ind_col)
        
        dlsl = QLabel("Delimiting symbol")
        dlsl.setToolTip("e.g. tab = \\t, comma = ,")
        self.QFL.addRow(dlsl,self.delimit)
        
        # dlcr = QLabel("Clean File")
        # dlcr.setToolTip("Check this if the file comes with empty columns")
        # self.QFL.addRow(dlcr,self.clean)
        
        # dlsp = QLabel("Decimal separator")
        # dlsp.setToolTip("e.g. dot = ., comma = ,")
        # self.QFL.addRow(dlsp,self.decimal)
        
        rvcl = QLabel("Remove columns")
        rvcl.setToolTip("Separated by a comma\n   or None if not needed\n   e.g. 1,2,3")
        self.QFL.addRow(rvcl,self.remove)
        self.QFL.addRow(btest,bok)
        
        bok.accepted.connect(self.popup_ok)
        btest.clicked.connect(self.popup_test_file_slow)
        
        self.dlg.setLayout(self.QFL)
        self.dlg.setWindowTitle("Setup up file characteristics")
        self.dlg.setWindowModality(Qt.ApplicationModal)
        self.dlg.exec_()
        
        
    def popup_test_file_fast(self):
        if "xlsx" in self.folder[-5:]:
            self.mdata = pd.read_excel(self.folder, index_col=0, header=0)
        else:
            try:
                self.mdata = pd.read_csv(self.folder, index_col=0, skiprows=None, header=0,delimiter ="\t",engine="python")
                if self.mdata.shape[1] != 0:
                    pass
                else:
                    try:
                        self.mdata = pd.read_csv(self.folder, index_col=0, skiprows=21, header=0,delimiter=",", engine="python")
                    except:
                        self.mdata = pd.read_csv(self.folder, index_col=0, skiprows=22, header=0,delimiter=",", engine="python")
                    ## When Dark&Bright, do the math to display the raw data properly
                    if self.mdata.keys()[1] == "Bright spectra": 
                        sd = self.mdata.iloc[:,2:].subtract(self.mdata["Dark spectra"], axis="index")
                        bd = self.mdata["Bright spectra"]-self.mdata["Dark spectra"]
                        fn = 1-sd.divide(bd, axis="index")
                        ## filter extreme values
                        val = 10##This is the extreme value
                        fn.values[fn.values > val] = val
                        fn.values[fn.values < -val] = -val
                        self.mdata = fn
                    elif self.mdata.keys()[0] == "Dark spectra": 
                        sd = self.mdata.iloc[:,2:].subtract(self.mdata["Dark spectra"], axis="index")
                        self.mdata = bd
                    else:
                        pass
                        
            except:
                self.popup_read_file()
            
    def set_default_fitting_range(self):
        self.LEstart.setText("0")
        self.LEend.setText(str(self.mdata.shape[1]-1))
        
    def read_fitting_range(self):
        self.start = int(self.LEstart.text())
        self.end = int(self.LEend.text())
        
    def remove_dummy_columns(self):
        non_floats = []
        for col in self.mdata.columns:
            try:
                float(col)
            except:
                non_floats.append(col)
        self.mdata = self.mdata.drop(columns=non_floats)
        self.mdata = self.mdata.drop(columns=self.mdata.columns[-1], axis=1) #remove last also
        # self.mdata = self.mdata.reindex(sorted(self.mdata.columns), axis=1)
        # print(non_floats)
        # print(self.mdata)

    
    def popup_test_file_slow(self):
        self.success = False
        h = int(self.headers.text())
        l = self.delimit.text()
        # dc = self.decimal.text()
        rem = self.remove.text().split(",")
        # cleanf = self.clean.
        remove = False
        if "None" not in rem:
            rem = [int(r)-1 for r in rem]
            remove = True
        if self.skiprow.text() == "None":
            sr = None
        else:
            sr = int(self.skiprow.text())
            
        if self.ind_col.text() == "None":
            ic = None
        else:
            ic = int(self.ind_col.text())

        try:
            try:
                self.mdata = pd.read_csv(self.folder, index_col=ic, skiprows=sr, header=h, delimiter=l, engine="python")
            except:
                self.mdata = pd.read_excel(self.folder, index_col=ic, skiprows=sr, header=h)
            
            if remove:
                self.mdata.drop(self.mdata.columns[rem], axis=1, inplace=True)
                
            self.remove_dummy_columns()
    
            self.QFL.addRow(QLabel("Headers:"),QLabel(str("  ".join(self.mdata.keys().values[:5]))))
            self.QFL.addRow(QLabel("First line:"),QLabel(str("  ".join(self.mdata.head(1).values[0][:5].astype(str)))))
            self.success = True
        except:
            self.QFL.addRow(QLabel("Something went wrong, please try again."))
            self.success = False
        
    def popup_ok(self):
        self.popup_test_file_slow()
        if self.success:
            self.dlg.close()
            self.extract_data()  
        else:
            self.QFL.addRow(QLabel("Something went wrong, please try again."))
        
    def add_fit_setup(self):
        for ii in range(self.mnm):
            combobool = False
            
            combobox = QComboBox()
            combobox.addItems(self.models)
            combobox.setVisible(False)
            
            comboName = QLineEdit()
            comboName.setFixedWidth(80)
            comboName.setVisible(False)
            
            comboNumber = QLabel(str(ii+1))
            comboNumber.setFixedWidth(14)
            comboNumber.setVisible(False)
            
            if ii == 0:
                self.LGfit.addWidget(QLabel("Name"),0,1)
                self.LGfit.addWidget(QLabel("Model"),0,2)
                self.LGfit.addWidget(QLabel("Parameters"),0,3)
                self.LGfit.addWidget(QLabel("  fix\ncenter"),0,9)

            self.LGfit.addWidget(comboNumber,ii*2+1,0)
            self.LGfit.addWidget(comboName,ii*2+1,1)
            self.LGfit.addWidget(combobox,ii*2+1,2)
            self.combo_mod.append([combobool,combobox,comboName,comboNumber])

        
    def make_ComboBox_fields(self, cb, ii):
        single_cnst = []
        if cb[0]:
            for i in reversed(range(1,self.mnm)):
                try:
                    self.LGfit.itemAtPosition(ii*2+1,i+2).widget().deleteLater()
                except:
                    pass
            cb[0]=False
        else:
            pass

        if cb[1].currentText() == "":
            cb[0] = False
            QLE_array = [QLabel("0"),QLabel("0"),QLabel("0")]
        
        elif cb[1].currentText() == "Linear":
            slope = QLineEdit()
            inter = QLineEdit()
            
            QLE_array = [slope,inter]
            for ql in QLE_array:
                ql.setFixedWidth(self.fw)
            single_cnst.append(QLE_array)
            
            self.LGfit.addWidget(QLabel("Slope:"),ii*2+1,3)
            self.LGfit.addWidget(slope,ii*2+1,4)
            self.LGfit.addWidget(QLabel("Y-int:"),ii*2+1,5)
            self.LGfit.addWidget(inter,ii*2+1,6)
            cb[0] = True
            
        elif cb[1].currentText() == "Polynomial":
            degree = QLineEdit()

            QLE_array = [degree]
            for ql in QLE_array:
                ql.setFixedWidth(self.fw)
                ql.setText("7")
            single_cnst.append(QLE_array)
            
            self.LGfit.addWidget(QLabel("Degree:"),ii*2+1,3)
            self.LGfit.addWidget(degree,ii*2+1,4)
            cb[0] = True
            
        elif cb[1].currentText() == "Exponential":
            amp = QLineEdit()
            exp = QLineEdit()
            
            QLE_array = [amp,exp]
            for ql in QLE_array:
                ql.setFixedWidth(self.fw)
            single_cnst.append(QLE_array)
            
            self.LGfit.addWidget(QLabel("Amplitude:"),ii*2+1,3)
            self.LGfit.addWidget(amp,ii*2+1,4)
            self.LGfit.addWidget(QLabel("Exponent:"),ii*2+1,5)
            self.LGfit.addWidget(exp,ii*2+1,6)
            cb[0] = True
            
        else:
            amp = QLineEdit()
            center = QLineEdit()
            sigma = QLineEdit()
            fix_button = QCheckBox()
            
            QLE_array = [amp,center,sigma]
            for ql in QLE_array:
                ql.setFixedWidth(self.fw)
            single_cnst.append(QLE_array)
            
            self.LGfit.addWidget(QLabel("Amplitude:"),ii*2+1,3)
            self.LGfit.addWidget(amp,ii*2+1,4)
            self.LGfit.addWidget(QLabel("Center:"),ii*2+1,5)
            self.LGfit.addWidget(center,ii*2+1,6)
            self.LGfit.addWidget(QLabel("Sigma:"),ii*2+1,7)
            self.LGfit.addWidget(sigma,ii*2+1,8)
            self.LGfit.addWidget(fix_button,ii*2+1,9)
            cb[0] = True


        self.constraints[ii] = single_cnst
                    
                    
    def start_parallel_calculation(self):
        # self.fitting_parameters_to_plot()
        self.read_fitting_range()
        self.fitmodel_setup()
        self.start_time = time()
        try:
            del self.res_df
        except:
            pass
        
        self.calc_length = self.end-self.start+1
        
        self.threadpool.clear()
        self.statusBar().showMessage("Fitting multiprocess started with "+str(self.threadpool.maxThreadCount())+" threads...")
        for ww in range(self.start,self.end+1):
            self.send_to_Qthread(ww)
                    
    def send_to_Qthread(self, w):
        ## Create a worker object and send function to it
        self.worker = Worker(self.parallel_calculation, w)
        
        ## Whenever signal exists, send it to plot
        self.worker.signals.progress.connect(self.fitting_progress)
        
        self.threadpool.start(self.worker)
        self.threadpool.releaseThread() ##I think this makes it faster over time
        
    def fitting_end(self):
        self.res_df = self.res_df.reindex(sorted(self.res_df.columns), axis=1)
        # self.res_df["Best Fit"] = self.result.best_fit
        # print(self.res_df)
        self.save_fitting_data()
        
    def fitting_progress(self, res):
        try:
            self.res_df = pd.concat([self.res_df,res], axis=1, join="inner")
        except:
            self.res_df = res
        
        current = self.res_df.shape[1]
        total = self.calc_length
        
        perc = current/total*100
        
        self.statusBar().showMessage(f"{perc:0.1f}% completed ({current:2d})")
        if current == total:
            self.statusBar().showMessage("Finished in "+str(round(time()-self.start_time,1))+" seconds")
            self.fitting_end()
            
    def get_peak_ratios(self):
        df = self.res_df.T
        
        Akeys = []
        sk = "amplitude"
        for k in df.keys():
            if sk in k:
                Akeys.append(k)
            if "center" in k:
                if np.mean(df[k])-14.2 < 0.2:
                    the_key = k
                    # print(the_key)
                    self.pero_peak = True
        m_key = the_key.rsplit("_",1)[0]
        
        self.norm_df = None
        for ak in Akeys:
            if m_key in ak:
                # print(m_key)
                continue
            else:
                # print(ak)
                norm = pd.DataFrame({ak:df[ak]/df[m_key+"_"+sk].values})
                try:
                    self.norm_df = pd.concat([self.norm_df,norm], axis=1, join="inner")
                except:
                    self.norm_df = norm



    def save_fitting_data(self):
        ## Get folder names
        if self.giwaxs_bool:
            fi,le = self.gfile.rsplit("/",1)
            if self.start != 0 or self.end != self.xsize:
                folder = self.gfile.rsplit("/",1)[0] + "/Fitting_"+le+"["+str(self.start)+"-"+str(self.end)+"]/"
            else:
                folder = fi+"/Fitting_"+le+"/"
            name = le
        else:
            if self.start != 0 or self.end != self.xsize:
                folder = self.folder.rsplit("/",1)[0] + "/Fitting["+str(self.start)+"-"+str(self.end)+"]/"
            else:
                folder = self.folder.rsplit("/",1)[0] + "/Fitting/"
            name = self.folder.rsplit("/",2)[1]
        # print(folder)
        
        if not os.path.exists(folder):
            os.makedirs(folder)
        
        ## Start an excel file
        writer = pd.ExcelWriter(folder+"0_"+name+"_fitting_parameters.xlsx")
        dataF = self.res_df.T

        ## Add data to excel file, making a new worksheet per dataset
        if self.giwaxs_bool:
            self.get_peak_ratios()
            normF = pd.concat([self.comb_data,self.norm_df],axis=1,join="inner")
            dataF = pd.concat([self.comb_data,dataF],axis=1,join="inner")
            
            normF.to_excel(writer,index=True, sheet_name = "Normalized")
            
        dataF.to_excel(writer,index=True, sheet_name = "Fitting")
        
        writer.save()
        self.plot_fitting_previews(folder)
       
    def plot_fitting_previews(self, folder):
        plt.ioff()
        df = self.res_df.T
        variables = []
        ##This part cleans the model labels so it can use them generally
        for ke in df.keys():
            for mn in self.mod_names:
                if mn in ke:
                    variables.append(ke.replace(mn,""))
        variables = list(set(variables))
        
        for va in variables:
            for ke in df.keys():
                name = ke.replace(va,"")
                plt.title(va)
                if va in ke:
                    plt.plot(self.xtime[self.start:self.end+1], df[ke], label = name[:-1])
            self.plot_preview_fitting(folder,va)
                    
        plt.plot(self.xtime[self.start:self.end+1], df["r-squared"], label = "R²")  
        plt.title("R-squared") 
        self.plot_preview_fitting(folder,"r-squared")     

        if self.pero_peak:
            try:
                for ndf in self.norm_df.keys():
                    plt.plot(self.xtime[self.start:self.end+1],self.norm_df[ndf], label = ndf.rsplit("_",1)[0])
                plt.title("Amplitude ratio with Perovskite peak")
                self.plot_preview_fitting(folder,"ratio") 
            except:
                pass

    def plot_preview_fitting(self,folder,fn):
        plt.legend(bbox_to_anchor=(1,1), loc="best")
        plt.xlabel("Time (seconds)")
        plt.ylabel("")
        plt.grid(True,linestyle='--')
        if fn == "r-squared":
            plt.savefig(folder+"0_preview_fit_0_"+fn+".png", dpi=300, bbox_inches='tight')
        else:
            plt.savefig(folder+"0_preview_fit_"+fn+".png", dpi=300, bbox_inches='tight')
        # plt.show()
        plt.close()
                    
    def parallel_calculation(self, w, progress_callback):
        
        try:
            # self._plot_ref.set_xdata(self.pdata.index.values)
            # self._plot_ref.set_ydata(self.pdata.iloc[:,[bar]].T.values[0])
            ydata = np.array(self.pdata.iloc[:,w].values)
            xdata = np.array(self.pdata.index.values)
            # print("hello")
        except:
            # self._plot_ref.set_ydata(self.mdata.iloc[:,[bar]].T.values[0])
            xdata = np.array(self.wave)
            ydata = np.array(self.mdata.iloc[:,w].values)
        
        result = self.model_mix.fit(ydata, self.pars, x=xdata)
        rsqrd = 1 - result.redchi / np.var(ydata, ddof=2)
        
        res = pd.DataFrame.from_dict(result.values, orient="index", columns=[w])
        
        rsq = pd.DataFrame([rsqrd], columns = [w], index =["r-squared"])
        
        new = pd.concat([res,rsq])

        progress_callback.emit(new)
        
    def fitmodel_process(self):
        self.clean_all_fit_fields()
        # self.read_fitting_range()
        self.fitmodel_setup()
        if self.fit_model_bool:
            self.fitmodel_plot()
        else:
            pass
        
        
    def fitmodel_setup(self):
        self.pero_peak = False ##Reset value to False 
        bar = int(self.SBtime.value()) ##Read scrollbar value
        
        try:
            # self._plot_ref.set_xdata(self.pdata.index.values)
            # self._plot_ref.set_ydata(self.pdata.iloc[:,[bar]].T.values[0])
            y_data = np.array(self.pdata.iloc[:,[bar]].T.values[0])
            x_data = np.array(self.pdata.index.values)
            # print("hello")
        except:
            # self._plot_ref.set_ydata(self.mdata.iloc[:,[bar]].T.values[0])
            y_data = np.array(self.mdata.iloc[:,[bar]].T.values[0])
            x_data = np.array(self.wave)
        
        # mod_number = 0
        self.model_mix=[]
        self.pars=[]
        self.mod_names = []
        self.fit_vals = []
        mod_name = None
        
        for nn,cb in enumerate(self.combo_mod):
            if nn == 0:
                try:
                    del self.model_mix
                    del self.pars
                except:
                    pass
            else:
                pass
            
            cb = cb[1]
            if cb.currentText() == "":
                pass
            
            elif cb.currentText() == "Linear":
                if len(self.combo_mod[nn][2].text()) > 0:
                    mod_name = self.combo_mod[nn][2].text()+"_"
                else:
                    # cur_name = "Linear"
                    mod_name = "Linear_"+str(nn+1)+"_"
                
                # mod_name = cur_name+"_"+str(nn+1)+"_"
                curv_mod = LinearModel(prefix=mod_name) 
                
                try:
                    self.model_mix = self.model_mix + curv_mod
                    self.pars.update(curv_mod.make_params())
                    
                except:
                    self.model_mix = curv_mod
                    self.pars = curv_mod.guess(y_data, x=x_data)
                
                slope  = self.constraints[nn][0][0].text().replace(",",".")
                interc = self.constraints[nn][0][1].text().replace(",",".")
                
                if len(slope) >= 1:
                    self.pars[mod_name+"slope"].set(value=float(slope))
                else:
                    pass
                if len(interc) >= 1:
                    self.pars[mod_name+"intercept"].set(value=float(interc))
                else:
                    pass
                
                # mod_number += 1

            elif cb.currentText() == "Polynomial":
                if len(self.combo_mod[nn][2].text()) > 0:
                    mod_name = self.combo_mod[nn][2].text()+"_"
                else:
                    mod_name = "Polynomial_"+str(nn+1)+"_"
                
                # mod_name = cur_name+"_"+str(nn+1)+"_"
                
                deg  = self.constraints[nn][0][0].text()
                if int(deg) > 7:
                    deg = 7
                    self.constraints[nn][0][0].setText("7")
                
                curv_mod = PolynomialModel(prefix=mod_name, degree=int(deg))
                
                try:
                    self.model_mix = self.model_mix + curv_mod
                    self.pars.update(curv_mod.make_params())
                except:
                    self.model_mix = curv_mod
                    self.pars = curv_mod.guess(y_data, x=x_data)
                    


            elif cb.currentText() == "Exponential":
                if len(self.combo_mod[nn][2].text()) > 0:
                    mod_name = self.combo_mod[nn][2].text()+"_"
                else:
                    mod_name = "Exponential_"+str(nn+1)+"_"
                
                # mod_name = cur_name+"_"+str(nn+1)+"_"
                curv_mod = ExponentialModel(prefix=mod_name) 
                
                try:
                    self.model_mix = self.model_mix + curv_mod
                    self.pars.update(curv_mod.make_params())
                except:
                    self.model_mix = curv_mod
                    self.pars = curv_mod.guess(y_data, x=x_data)
                    
                amp = self.constraints[nn][0][0].text().replace(",",".")
                dec = self.constraints[nn][0][1].text().replace(",",".")

                if len(amp) >= 1:
                    self.pars[mod_name+"amplitude"].set(value=float(amp))
                else:
                    pass
                if len(dec) >= 1:
                    self.pars[mod_name+"decay"].set(value=float(dec))
                else:
                    pass
                
                # mod_number += 1
                    
            # elif cb.currentText() == "Gaussian":
            else:
                if len(self.combo_mod[nn][2].text()) > 0:
                    mod_name = self.combo_mod[nn][2].text()+"_"
                else:
                    mod_name = cb.currentText()+"_"+str(nn+1)+"_"
                
                if "Lorentzian" in cb.currentText():
                    curv_mod = LorentzianModel(prefix=mod_name)
                elif "PseudoVoigt" in cb.currentText():
                    curv_mod = PseudoVoigtModel(prefix=mod_name)
                elif "ExpGaussian" in cb.currentText():
                    curv_mod = ExponentialGaussianModel(prefix=mod_name) 
                elif "SkewedGaussian" in cb.currentText():
                    curv_mod = SkewedGaussianModel(prefix=mod_name) 
                elif "SkewedVoigt" in cb.currentText():
                    curv_mod = SkewedVoigtModel(prefix=mod_name) 
                elif "Voigt" in cb.currentText():
                    curv_mod = VoigtModel(prefix=mod_name) 
                elif "Gaussian" in cb.currentText():
                    curv_mod = GaussianModel(prefix=mod_name)
                else:
                    print("model error")
                
                try:
                    self.model_mix = self.model_mix + curv_mod
                    self.pars.update(curv_mod.make_params())
                except:
                    self.model_mix = curv_mod
                    self.pars = curv_mod.guess(y_data, x=x_data)
                    
                amp = self.constraints[nn][0][0].text().replace(",",".")
                cen = self.constraints[nn][0][1].text().replace(",",".")
                sig = self.constraints[nn][0][2].text().replace(",",".")

                if len(amp) >= 1:
                    va = float(amp)
                    self.pars[mod_name+"amplitude"].set(value=va, min=0)
                    self.pars[mod_name+"height"].set(max =self.max_int)
                else:
                    self.pars[mod_name+"amplitude"].set(min=0)
                if len(cen) >= 1:
                    vv = float(cen)
                    if self.LGfit.itemAtPosition(nn*2+1,9).widget().isChecked():
                        self.pars[mod_name+"center"].set(value=vv,vary=False)
                    else:
                        self.pars[mod_name+"center"].set(value=vv,min=vv/3,max=vv*3)
                else:
                    pass
                if len(sig) >= 1:
                    vs = float(sig)
                    self.pars[mod_name+"sigma"].set(value=vs, min=vs/3, max=vs*3)
                else:
                    pass
            
            if mod_name is not None:
                self.mod_names.append(mod_name)
                self.fit_model_bool = True
            else:
                self.statusBar().showMessage("No fitting models selected",5000)
                self.fit_model_bool = False
                # raise Exception("No fitting models")
                # return
        
    def fitmodel_plot(self):
        self.statusBar().showMessage("Fitting...   This might take some time")
        
        bar = int(self.SBtime.value()) ##Read scrollbar value
        
        try:
            # self._plot_ref.set_xdata(self.pdata.index.values)
            # self._plot_ref.set_ydata(self.pdata.iloc[:,[bar]].T.values[0])
            y_data = np.array(self.pdata.iloc[:,[bar]].T.values[0])
            x_data = np.array(self.pdata.index.values)
            # print("hello")
        except:
            # self._plot_ref.set_ydata(self.mdata.iloc[:,[bar]].T.values[0])
            y_data = np.array(self.mdata.iloc[:,[bar]].T.values[0])
            x_data = np.array(self.wave)
        
        try:
            self.result = self.model_mix.fit(y_data, self.pars, x=x_data)
            comps = self.result.eval_components(x=x_data)
        except ValueError:
            self.statusBar().showMessage("### One of the models shows an error ###",5000)
            
        
        self.fit_vals = self.result.values
        self.add_fitting_data_to_gui()
        
        ##This can be separated into new function (if needed)
        if self.plots:
            try:
                for sp in self.plots:
                    sp.pop(0).remove()
                self.best_fit.pop(0).remove()
                self.plots = []
            except:
                pass   
        else:
            pass
        
        plt.rcParams["axes.prop_cycle"] = plt.cycler("color", plt.cm.tab20(np.linspace(0,1,10)))
        
        for cc, mc in enumerate(self.model_mix.components):
            plot  = self.canvas.axes.plot(x_data,comps[mc.prefix], '--', label = mc.prefix[:-1])
            self.plots.append(plot)
        self.best_fit = self.canvas.axes.plot(x_data, self.result.best_fit, '-.b', label='Best fit')
        
        try:
            # self.LGfit.itemAtPosition(0,1).widget().deleteLater()
            # self.LGfit.itemAtPosition(0,2).widget().deleteLater()
            self.LR.setText("")
            self.Lvalue.setText("")
        except:
            pass
        
        self.rsquared = 1 - self.result.redchi / np.var(y_data, ddof=2)
        
        r2_label = str(np.round(self.rsquared,4))
        
        # self.LGfit.addWidget(QLabel(" R² = "),0,1)
        # self.LGfit.addWidget(QLabel(r2_label),0,2)
        self.LR.setText(" R² = ")
        self.Lvalue.setText(r2_label)
            
        self.canvas.axes.legend(loc = "best")    
        self.canvas.draw_idle()
        self.statusBar().showMessage("Initial fitting is done", 5000)
    
    def convert_to_eV(self):
        ## set variables
        hc = (4.135667696E-15)*(2.999792E8)*1E9
        eV_conv=hc/self.mdata.index
        
        ## Make conversion of database and index
        ev_df = self.mdata.multiply(self.mdata.index.values**2, axis="index")/hc
        
        ev_df = ev_df.set_index(eV_conv)
        ev_df.index.names=["Energy"]
        
        ## This is for plotting later
        axis=np.around(np.linspace(self.wave[0],self.wave[-1],8),decimals=1)
        self.eV_axis=np.round(hc/axis,1)
        
        ## Rename mdata (this is what is always plotted)
        self.pdata = ev_df
        self.mdata = ev_df
        
        ## Update plot
        self.extract_data()
        self.plot_setup()
        self.bar_update_plots(0)
        # self.scrollbar_action()

    def popup_subtract_bkgd(self):
        self.dgiw = QDialog()
        Lopt = QVBoxLayout()
        Lopt.setAlignment(Qt.AlignCenter)
        
        Tdats = QLabel("Select the starting position\nand the number of spectra curves to average")
        Lopt.addWidget(Tdats)
        
            
        Tempt = QLabel("\n")
        Lopt.addWidget(Tempt)
        
        layout = QFormLayout()
        
        self.left_b = QLineEdit()
        self.left_b.setFixedWidth(50)
        self.left_b.setAlignment(Qt.AlignCenter)
        self.left_b.setText("0")
        self.len_range = QLineEdit()
        self.len_range.setFixedWidth(50)
        self.len_range.setAlignment(Qt.AlignCenter)
        self.len_range.setText("5")
        layout.addRow("Start pos.",self.left_b)
        layout.addRow("Mean length",self.len_range)
        
        Lopt.addLayout(layout)
        
        Bok = QDialogButtonBox(QDialogButtonBox.Ok)
        Lopt.addWidget(Bok)
        Bok.accepted.connect(self.subtract_background)
        
        self.dgiw.setLayout(Lopt)
        self.dgiw.setWindowTitle("Select range to subtract")
        self.dgiw.setWindowModality(Qt.ApplicationModal)
        self.dgiw.exec_()

    def subtract_background(self):
        left_b = int(self.left_b.text())
        right_b= left_b + int(self.len_range.text())
        
        ## Calculate mean of selected range of columns
        col_mean = self.mdata.iloc[:,left_b:right_b].mean(axis=1)
        ## Subtract mean to all dataset
        clean_data = self.mdata.subtract(col_mean, "index")
                
        ## Rename mdata (this is what is always plotted)
        self.pdata = clean_data
        self.mdata = clean_data
        
        ## Update plot
        self.extract_data()
        self.plot_setup()
        self.bar_update_plots(0)
        # self.scrollbar_action()    
            
    def plot_restart(self):
        self.canvas.axes.set_xlabel('Time (s)')
        self.canvas.axes.set_ylabel('Wavelength (nm)')

        self.canvas.axes.set_xlabel('Wavelength (nm)')
        self.canvas.axes.set_ylabel('Intensity (a.u.)')
        self.canvas.axes.grid(True,linestyle='--')
        
    def plot_setup(self):
        try:
            fi,le = self.gfile.rsplit("/",1)
            self.setWindowTitle("Spectra Fitter ("+le+")")
        except:
            pass
        try:
            self.canvas.axes.cla()
            self.savnac.axes.cla()
            self.plot_restart()
            self.ax2.remove()
        except:
            pass
        ## First plot
        self._plot_ref,  = self.canvas.axes.plot(self.wave, self.mdata.iloc[:,[0]], 'r', label = "Experiment")
        # print(self.wave)
        index_name = self.mdata.index.name
        
        if "0.000" in index_name:
            axis_name = "Wavelength (nm)"
        elif "Wavelength" in index_name:
            axis_name = index_name+" (nm)"
        elif "Energy" in index_name:
            axis_name = index_name+" (eV)"
        elif "TTh" in index_name:
            axis_name = r"2$\theta$ (Degree)"
        else:
            axis_name = index_name
        
        if self.giwaxs_bool:
            self.canvas.axes.set_xlabel(axis_name)
            if "eta" in self.gname:
                self.t_label = "Degree"
            else:
                self.t_label = "Time"
        else:
            
            self.canvas.axes.set_xlabel(axis_name)
            self.t_label = "Time"
            
        
        ## Set text fields for time and position
        self.text_time = self.canvas.axes.text(0.4,0.9, self.t_label+" 0.0",
                        horizontalalignment='left',verticalalignment='center', transform=self.canvas.axes.transAxes)
        self.text_pos = self.canvas.axes.text(0.4,0.83, "Position 0",
                        horizontalalignment='left',verticalalignment='center', transform=self.canvas.axes.transAxes)

        self.canvas.axes.set_ylim([self.min_int*0.9,self.max_int*1.1]) ## Set y-axis range
        self.canvas.axes.legend(loc = "best") ## Position legend smartly
        
        ## Second plot
        if self.giwaxs_bool:
            self.ax2 = self.savnac.axes.twinx()
        
        self._plot_heat = self.savnac.axes.pcolorfast(self.mdata)  ## 2D heatplot
        self._plot_vline,  = self.savnac.axes.plot([0,0], [0,self.ysize], 'r') ##Horizontal line
        self._plot_hline1,  = self.savnac.axes.plot([0,self.xsize],[0,0], 'b') ##Horizontal line
        self._plot_hline2,  = self.savnac.axes.plot([0,self.xsize],[0,0], 'b') ##Horizontal line
        
        if self.giwaxs_bool:
            if "eta" in self.gname:
                self.savnac.axes.set_xlabel("Eta (degrees)")
            else:
                self.savnac.axes.set_xlabel("Time (seconds)")
            self.savnac.axes.set_ylabel(axis_name)
            tempe = [ik[1] for ik in self.mdata.keys()]
            self.ax2.plot(range(len(self.xtime)),tempe,"--m")
            self.ax2.set_ylabel("Temperature (°C)",color="m")#
            self.ax2.set_ylim([min(tempe)*0.9,max(tempe)*1.1])
            self.ax2.tick_params(axis='y', colors='m')
        else:
            self.savnac.axes.set_xlabel("Time (seconds)")
            self.savnac.axes.set_ylabel(axis_name)
            
        # Reset ticks to match data
        ## Y-axis
        if "Energy" in axis_name:
            # self.savnac.axes.set_yscale("log")
            # axis = self.savnac.axes.get_yticklabels()
            # print(axis)
            # axis = [1240/a for a in axis]
            self.savnac.axes.set_yticks(np.linspace(0,len(self.wave),8))
            self.savnac.axes.set_yticklabels(self.eV_axis)
        else:
            # self.savnac.axes.set_yscale("linear")
            self.savnac.axes.set_yticks(np.linspace(0,len(self.wave),8))
            self.savnac.axes.set_yticklabels(np.around(np.linspace(self.wave[0],self.wave[-1],8),decimals=1))
        ## X-axis
        self.savnac.axes.set_xticks(np.linspace(0,len(self.xtime),8))
        try:## In case index is not made of numbers but strings
            if "eta" in self.gname:
                self.savnac.axes.set_xticklabels(np.around(np.linspace(0, self.xtime[-1], 8),decimals=1))
            else:
                self.savnac.axes.set_xticklabels(np.around(np.linspace(0, self.xtime[-1], 8),decimals=0).astype(int))
        except:
            pass

        
    def simplify_number(self, number):
        if number < 0:
            number = np.round(number,4)
        elif number < 20:
            number = np.round(number,2)
        else:
            number = int(number)
        
        return number
    
    ## Allow to keep center fixed (with checkbox)
    def add_fitting_data_to_gui(self):
        fv = self.fit_vals
        ke = fv.keys()
        # print(ke)
        
        row = 1
        cou = 1
        col = 0
        extra = 0
        for cc, key in enumerate(ke):
            box_name = self.combo_mod[row-1][1].currentText()
            # print(box_name)
            
            ## This part sets the lenght of parameters and the number of skipped ones
            if box_name == "":
                mod = 1
                extra = 0
            elif box_name == "Polynomial":
                # print(self.constraints[row-1][0][0].text())
                mod = int(self.constraints[row-1][0][0].text())+2
                extra = int(self.constraints[row-1][0][0].text())+2
            elif box_name in ["Linear","Exponential"]:
                mod = 3
                extra = 0
            elif box_name in ["Gaussian","Lorentzian"]:
                mod = 6
                extra = 2
            elif box_name in ["PseudoVoigt","ExpGaussian","SkewedGaussian","SkewedVoigt","Voigt"]:
                mod = 7
                extra = 3
            else:
                pass
                
            if cou % mod == 0:
                col = 0
                cou = 1
                row += 1
                extra = 0
            else:
                pass
            
            try:##  To remove old fitting value on GUI
                self.LGfit.itemAtPosition(row*2,col*2+4).widget().deleteLater()
            except:
                pass
            
            if mod-col-1 <= extra:
                pass
            else:
                val = str(self.simplify_number(fv[key]))
                labl = QLabel(val)
                labl.setAlignment(Qt.AlignCenter)
                self.LGfit.addWidget(labl,row*2,col*2+4)
            col += 1
            cou += 1
          
    def popup_heatplot_color_range(self):
        dgiw = QDialog()
        Lopt = QVBoxLayout()
        Lopt.setAlignment(Qt.AlignCenter)
        
        Tdats = QLabel("Select a new color range for the heaplot")
        Lopt.addWidget(Tdats)
            
        Tempt = QLabel("\n")
        Lopt.addWidget(Tempt)
        
        max_val = round(self.mdata.to_numpy().max(),2)
        min_val = round(self.mdata.to_numpy().min(),2)
        
        self.cb_max = QLineEdit()
        self.cb_max.setFixedWidth(100)
        self.cb_max.setAlignment(Qt.AlignCenter)
        self.cb_max.setText(str(max_val))
        self.cb_min = QLineEdit()
        self.cb_min.setFixedWidth(100)
        self.cb_min.setAlignment(Qt.AlignCenter)
        self.cb_min.setText(str(min_val))
        
        Lvalues = QFormLayout()
        Lvalues.addRow("Upper Boundary: ", self.cb_max)
        Lvalues.addRow("Lower Boundary: ", self.cb_min)
        
        Lopt.addLayout(Lvalues)
        Bok = QDialogButtonBox(QDialogButtonBox.Ok)
        Lopt.addWidget(Bok)
        Bok.accepted.connect(self.set_heaplot_color_range)
        
        dgiw.setLayout(Lopt)
        dgiw.setWindowTitle("Select boundaries")
        dgiw.setWindowModality(Qt.ApplicationModal)
        dgiw.exec_()
        
    def set_heaplot_color_range(self):
        min_val = float(self.cb_min.text())
        max_val = float(self.cb_max.text())
        self._plot_heat.set_clim(min_val,max_val)
        self.scrollbar_action()
    
    def slider_action(self):
        sli1,sli2 = self.range_slider.value()

        try:
            self._plot_hline1.set_ydata([sli1,sli1])
            self._plot_hline2.set_ydata([sli2,sli2])
            
            self.pdata = self.mdata.iloc[sli1:sli2+1]
            
            
            # self._plot_heat.set_clim(np.min(self.pdata), np.max(self.pdata))
            # self.savnac.draw_idle()
            
            self.scrollbar_action()
        except:
            pass
        
    def save_current_state(self):
        # try:
        try:
            fi,le = self.gfile.rsplit("/",1)
        except:
            fi,le = self.folder.rsplit("/",1)
        
        filename = QtWidgets.QFileDialog.getSaveFileName(self, 'Save File',directory=fi,filter="CSV (*.csv) ;; Excel (*.xlsx)")[0]

        self.statusBar().showMessage("Saving file, please wait...")
        
        if ".xlsx" in filename:
            self.pdata.to_excel(filename)
        else:
            self.pdata.to_csv(filename)
        
        self.statusBar().showMessage("File saved!",5000)
        # except:
        #     ##File not modified
        #     self.popup_error_msg()
        
    def popup_error_msg(self):
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Critical)
        msg.setText("There are no changes")
        msg.setInformativeText('The dataset has not been modified')
        msg.setWindowTitle("Error")
        msg.exec_()
    
    def scrollbar_action(self):
        bar = int(self.SBtime.value()) ##Read scrollbar value
        self.bar_update_plots(bar)
        
    def bar_update_plots(self,bar):
        try:
            self._plot_ref.set_xdata(self.pdata.index.values)
            self._plot_ref.set_ydata(self.pdata.iloc[:,[bar]].T.values[0])
            # print("hello")
        except:
            self._plot_ref.set_ydata(self.mdata.iloc[:,[bar]].T.values[0])
        try:
            time = str(round(float(self.xtime[bar]),1))
        except:
            time = str(self.xtime[bar])
        self.text_time.set_text(self.t_label+" "+time)
        self.text_pos.set_text("Position "+str(bar))

        self._plot_vline.set_xdata([bar,bar])
        self.canvas.draw_idle()
        self.savnac.draw_idle()



app = QtWidgets.QApplication(sys.argv)
w = MainWindow()
app.exec_()