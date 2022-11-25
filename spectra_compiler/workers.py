import utils
import numpy as np
from PyQt5.QtCore import QTimer
from multiprocessing import Pipe
from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot, QThread
import time


class Emitter(QThread):
    ui_data_available = pyqtSignal(object)  # Signal indicating new UI data is available.

    def __init__(self, from_process: Pipe):
        super().__init__()
        self.data_from_process = from_process

    def run(self):
        while True:
            try:
                ydata = self.data_from_process.recv()
            except EOFError:
                break
            else:
                self.ui_data_available.emit(ydata)


class PlotWorker(QObject):

    def __init__(self, canvas, xdata, is_dark_data, is_bright_data, dark_mean, bright_mean, is_spectrometer=False):
        super(PlotWorker, self).__init__()
        self.canvas = canvas
        self.xdata = xdata
        self.is_dark_data = is_dark_data
        self.is_bright_data = is_bright_data
        self.dark_mean = dark_mean
        self.bright_mean = bright_mean
        self._plot_ref = None
        self.is_spectrometer = is_spectrometer
        self.render_buffer = None
        self.show_raw = False
        self._plot_re1 = None
        self._plot_re2 = None
        self.timer = QTimer()
        self.timer.start(500)
        self.timer.timeout.connect(self.toggle)
        self.reset_axes()

    def reset_axes(self):
        self.canvas.axes.cla()
        self.canvas.axes.set_xlabel('Wavelength (nm)')
        self.canvas.axes.set_ylabel('Intensity (a.u.)')
        self.canvas.axes.grid(True, linestyle='--')
        self.canvas.axes.set_xlim([min(self.xdata) * 0.98, max(self.xdata) * 1.02])
        # self.canvas.axes.set_xlim([400,850])
        self.canvas.axes.set_ylim([0, 68000])
        self.show_raw = False
        self._plot_re1 = None
        self._plot_re2 = None
        self._plot_ref, = self.canvas.axes.plot(self.xdata, np.ones(len(self.xdata)), 'r')
        if not self.is_spectrometer:
            self._plot_ref.set_label("Spectrometer not found: Demo Data")
            self.canvas.axes.legend()

    @pyqtSlot(object)
    def plot_spectra(self, spect):
        self.render_buffer = spect

    def toggle(self):
        if self.show_raw:
            if self.is_dark_data and self._plot_re1 is None:
                self._plot_re1 = self.canvas.axes.plot(self.xdata, self.dark_mean, 'b', label="Dark")
            if self.is_bright_data and self._plot_re2 is None:
                self._plot_re2 = self.canvas.axes.plot(self.xdata, self.bright_mean, 'y', label="Bright")
            self._plot_ref.set_ydata(self.render_buffer)  # TODO: check its yarray or render_buffer?
            self._plot_ref.set_label("Spectra")
            self.canvas.axes.legend()
        else:
            yarray = utils.spectra_math(self.render_buffer, self.is_dark_data, self.is_bright_data, self.dark_mean,
                                        self.bright_mean)
            self._plot_ref.set_ydata(yarray)
        self.canvas.draw_idle()


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
    def run(self, spect):  # TODO: rename
        # print("Run start", spect.shape)
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
        self.array_count = 0  # TODO: REMOVE variable

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
                self.time_meas_array[self.array_count] = np.round(time.time() - self.start_time, 4)
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


class Worker3(QObject):
    result = pyqtSignal(object)

    def __init__(self, average_cycles, array_size):
        super(Worker3, self).__init__()
        self.counter = 0
        self.average_cycles = average_cycles
        self.measured_array = np.ones((self.average_cycles, array_size))

    @pyqtSlot(object)
    def gathering_counts(self, spect):
        if self.counter < self.average_cycles:
            self.measured_array[self.counter] = np.array(spect)
            self.counter += 1
        else:
            _mean = np.mean(self.measured_array, axis=0)
            self.result.emit(_mean)
            print('finished thread.....')
