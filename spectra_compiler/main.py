__author__ = "Edgar Nandayapa (HZB), Ashis Ravindran (DKFZ)"
__version__ = "20.01.2023"
__status__ = "Production"
__maintainer__ = "place holder"

import sys
from multiprocessing import Queue, Pipe
from PyQt5 import QtWidgets
from app import MainWindow
import pathlib
from generator import SpectroProcess
from workers import Emitter

if __name__ == "__main__":
    icon_path = '../resources/rainbow.ico'
    icon_path = pathlib.Path(icon_path)
    app = QtWidgets.QApplication(sys.argv)

    mother_pipe, child_pipe = Pipe()
    queue = Queue()
    emitter = Emitter(mother_pipe)
    spectro_process = SpectroProcess(child_pipe, queue)

    w = MainWindow(icon_path, spectro_process.is_spectrometer, emitter, queue, spectro_process.xdata,
                   spectro_process.array_size)
    spectro_process.start()

    w.show()
    app.exec()
    spectro_process.join()
    spectro_process.terminate()
