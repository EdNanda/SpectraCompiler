__author__ = "Edgar Nandayapa"
__version__ = "1.07-2021"

import sys
from multiprocessing import Process, Queue, Pipe
from PyQt5 import QtWidgets
from app import MainWindow
import pathlib
from queue import Empty
import numpy as np
import time
from seabreeze.spectrometers import Spectrometer
from PyQt5.QtCore import pyqtSignal, QThread

''''
1. Init spectormeter here...
2. Define data generating function here... get_ydata
3. 
'''

class Emitter(QThread):
    """ Emitter waits for data from the capitalization process and emits a signal for the UI to update its text. """
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


class SpectroProcess(Process):
    """ Process to capitalize a received string and return this over the pipe. """

    def __init__(self, to_emitter: Pipe, from_mother: Queue, inittime: str = "0.2", daemon=True):
        super().__init__()
        self.daemon = daemon
        self.to_emitter = to_emitter
        self.data_from_mother = from_mother
        self.inttime = float(inittime)
        try:
            self.spec = Spectrometer.from_first_available()
            self.spec.integration_time_micros(200000)
            self.xdata = self.spec.wavelengths()[2:]
            self.array_size = len(self.xdata)
            self.spec_counts = []
            self.spectrometer = True
            print("spec found")
        except:
            print("spec not found")
            self.array_size = 2046
            self.xdata = np.linspace(340, 1015, self.array_size)
            self.spectrometer = False

    def run(self):
        def accurate_delay(delay):
            ''' Function to provide accurate time delay in millisecond
            '''
            _ = time.perf_counter() + delay / 1000
            while time.perf_counter() < _:
                pass

        if self.spectrometer:
            _DP = 1420  ##dead pixel on spectrometer @831.5nm
            while True:
                ydata = self.spec.intensities()[2:]
                if "FLMS12200" in self.spec.serial_number:
                    ydata[_DP] = np.mean(ydata[_DP - 2:_DP + 2])
                    self.to_emitter.send(ydata)
                    try:
                        inttime = self.data_from_mother.get_nowait() # TODO check overhead of this call - super important!!
                        self.spec.integration_time_micros(int(inttime * 1000000))
                    except Empty:
                        pass
        else:
            xx = np.arange(self.array_size)
            while True:
                accurate_delay(self.inttime)  # time.sleep(self.inttime)
                ydata = 50000 * np.exp(-(xx - 900) ** 2 / (2 * 100000)) + np.random.randint(0, 10001)  # result is in [start, end). hence 10001 instead of 10000
                self.to_emitter.send(ydata)
                try:
                    self.inttime = self.data_from_mother.get_nowait()
                    self.inttime *= 1000 #convert to ms
                    print("wait time changed (ms)", self.inttime)
                except Empty:
                    pass

    def set_spec(self, spec):
        self.spec = spec

    def set_intime(self, inttime):
        self.inttime = float(inttime)

    def close(self):
        if self.spectrometer:
            self.spec.close()



if __name__ == "__main__":
    icon_path = 'C:/Users/HYDN02/Seafile/IJPrinting_Edgar-Florian/python'
    icon_path = pathlib.Path(icon_path)
    app = QtWidgets.QApplication(sys.argv)

    mother_pipe, child_pipe = Pipe()
    queue = Queue()
    # Instantiate (i.e. create instances of) our classes.
    emitter = Emitter(mother_pipe)
    child_process = SpectroProcess(child_pipe, queue)

    w = MainWindow(icon_path, False, emitter, queue, child_process.xdata, child_process.array_size) #TODO: send queue as well
    child_process.start()

    w.show()
    app.exec()

    child_process.close()
    child_process.terminate()


