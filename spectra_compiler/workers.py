# SPDX-FileCopyrightText: 2023 Edgar Nandayapa (Helmholtz-Zentrum Berlin) & Ashis Ravindran (DKFZ, Heidelberg)
#
# SPDX-License-Identifier: MIT

import utils
import numpy as np
from PyQt5.QtCore import QTimer
from multiprocessing import Pipe
from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot, QThread
from generator import SpectraReading


class Emitter(QThread):
    ui_data_available = pyqtSignal(object)  # Signal indicating new UI data is available.

    def __init__(self, from_process: Pipe):
        super().__init__()
        self.data_from_process = from_process

    def run(self):
        """
        Emits collected List from spectrometer (ydata)
        """
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
        self.is_spectrometer = is_spectrometer
        self.render_buffer = None
        self.is_show_raw = False
        self.is_fix_y = False
        self._plot_ref = None
        self._plot_re1 = None
        self._plot_re2 = None
        self.timer = QTimer()
        self.timer.start(500)
        self.timer.timeout.connect(self.toggle)
        self.reset_axes()
        self.is_measure_frequency = True
        self.n_measure_cycles = 5
        self.init_frequency_measure()

    def init_frequency_measure(self):
        """
        Clears timestamps List and sets frequency to 0
        """
        self.timestamps = []
        self.current_mean_frequency_ms: float = 0

    def measure_freq_list(self, timestamps: list):
        """
        Populates List containing timestamps
        @param timestamps:
        """
        init_time = timestamps[0]
        _timestamps = [(timestamp - init_time) for timestamp in timestamps]
        self.current_mean_frequency_ms = 1000 * sum(_timestamps) / (2 * self.n_measure_cycles)

    def reset_axes(self):
        """
        Resets plot status to initial conditions (blank)
        """
        self.canvas.axes.cla()
        self.canvas.axes.set_xlabel('Wavelength (nm)')
        self.canvas.axes.set_ylabel('Intensity (a.u.)')
        self.canvas.axes.grid(True, linestyle='--')
        self.canvas.axes.set_xlim([min(self.xdata) * 0.98, max(self.xdata) * 1.02])
        # self.canvas.axes.set_xlim([400,850])
        self.canvas.axes.set_ylim([0, 68000])
        self.is_show_raw = False
        self._plot_re1 = None
        self._plot_re2 = None
        self._plot_ref, = self.canvas.axes.plot(self.xdata, np.ones(len(self.xdata)), 'r')
        if not self.is_spectrometer:
            self._plot_ref.set_label("Spectrometer not found: Demo Data")
            self.canvas.axes.legend()

    @pyqtSlot(object)
    def plot_spectra(self, spect: SpectraReading):
        """
        Fixes timestamps
        @param spect:
        """
        self.render_buffer = spect.data
        if self.is_measure_frequency:
            self.timestamps.append(spect.timestamp)
            if len(self.timestamps) > self.n_measure_cycles:
                self.timestamps.pop(0)
                self.measure_freq_list(self.timestamps)

    def toggle(self):
        """
        Fix displayed curves in plot regarding what has been selected
        """
        if self.is_show_raw:
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

    def set_axis_range(self):
        """
        Fixes plot axis limits with respect to what has been selected (bright and dark spectra / raw and fix_y)
        """
        self.canvas.axes.set_xlim([min(self.xdata) * 0.98, max(self.xdata) * 1.02])
        fix_arr = np.ma.masked_invalid(self.render_buffer)

        if self.is_bright_data:
            glob_min = np.min([np.min(self.bright_mean), np.min(self.dark_mean)])
            glob_max = np.max([np.max(self.bright_mean), np.max(self.dark_mean)])

            if self.is_show_raw:
                self.canvas.axes.set_ylim([glob_min * 0.95, glob_max * 1.05])
            elif self.is_fix_y and not self.is_show_raw:
                self.canvas.axes.set_ylim([-0.1, 1.1])
            else:
                pass  # This boolean combination resets the plot by default
        elif self.is_dark_data and not self.is_bright_data:
            glob_min = np.min([np.min(fix_arr), np.min(self.dark_mean)])
            glob_max = np.max([np.max(fix_arr), np.max(self.dark_mean)])
            if self.is_fix_y or self.is_show_raw:
                self.canvas.axes.set_ylim([glob_min * 0.95, glob_max * 1.05])
            if self.is_fix_y or not self.is_show_raw:
                self.canvas.axes.set_ylim([0, glob_max * 1.05])
            else:
                self.canvas.axes.set_ylim([0, 68000])
        else:
            if self.is_fix_y:
                self.canvas.axes.set_ylim([min(fix_arr) * 0.9, max(fix_arr) * 1.1])
            else:
                self.canvas.axes.set_ylim([0, 68000])


class SpectraGatherer(QObject):
    finished = pyqtSignal()
    progress = pyqtSignal(int)
    result = pyqtSignal(object, object, object)

    def __init__(self, total_frames, array_size, skip, is_dark_data, is_bright_data, dark_mean, bright_mean):
        super(SpectraGatherer, self).__init__()
        self.total_frames = total_frames
        self.array_size = array_size
        self.skip = skip + 1
        self.is_dark_data = is_dark_data
        self.is_bright_data = is_bright_data
        self.dark_mean = dark_mean
        self.bright_mean = bright_mean
        self.spectra_meas_array = np.ones((self.total_frames, self.array_size))
        self.spectra_raw_array = np.ones((self.total_frames, self.array_size))
        self.time_meas_array = np.ones(self.total_frames)
        self.spectra_counter = 0
        self.array_count = 0
        self.init_spectra_measurement()

    @pyqtSlot(object)
    def measure(self, reading: SpectraReading):
        """
        Collect measured spectra and do necessary math to it
        @param reading:
        """
        spect = reading.data
        yarray = utils.spectra_math(spect, self.is_dark_data, self.is_bright_data, self.dark_mean, self.bright_mean)
        self.gathering_spectra_counts(spect, yarray, reading.timestamp)

    def init_spectra_measurement(self):
        """
        Resets lists and counters to begin new measurement
        """
        self.spectra_meas_array[:] = np.nan
        self.spectra_raw_array[:] = np.nan
        self.time_meas_array[:] = np.nan
        self.spectra_counter = 0
        self.array_count = 0

    def gathering_spectra_counts(self, ydata, yarray, timestamp):
        """
        Collect lists of spectra into a predefined matrix
        @param ydata: list of measured spectra
        @param yarray: list of calculated data from spectra
        @param timestamp: float of elapsed time
        """
        if self.spectra_counter < self.total_frames:
            if self.spectra_counter == 0 or (self.spectra_counter % self.skip) == 0:
                self.spectra_raw_array[self.array_count] = ydata
                self.spectra_meas_array[self.array_count] = yarray
                self.time_meas_array[self.array_count] = timestamp
                self.array_count += 1
            self.spectra_counter += 1
            self.progress.emit(self.spectra_counter)
        else:
            self.time_meas_array = self.time_meas_array - self.time_meas_array[0]
            self.result.emit(self.spectra_raw_array, self.spectra_meas_array, self.time_meas_array)
            self.finished.emit()


class DarkBrightGatherer(QObject):
    result = pyqtSignal(object)

    def __init__(self, average_cycles, array_size):
        super(DarkBrightGatherer, self).__init__()
        self.counter = 0
        self.average_cycles = average_cycles
        self.measured_array = np.ones((self.average_cycles, array_size))

    @pyqtSlot(object)
    def gathering_counts(self, reading: SpectraReading):
        """
        Collects data specifically for dark and bright conditions
        @param reading: list of spectra data
        """
        if self.counter < self.average_cycles:
            self.measured_array[self.counter] = reading.data
            self.counter += 1
        else:
            _mean = np.mean(self.measured_array, axis=0)
            self.result.emit(_mean)
