__author__ = "Edgar Nandayapa"
__version__ = "1.07-2021"

import sys
from multiprocessing import Queue, Pipe
from PyQt5 import QtWidgets
from app import MainWindow
import pathlib
from generator import SpectroProcess
from workers import Emitter

#TODO:
# gathering_dark_counts and bright counts have the same logic??


if __name__ == "__main__":
    icon_path = 'C:/Users/HYDN02/Seafile/IJPrinting_Edgar-Florian/python'
    icon_path = pathlib.Path(icon_path)
    app = QtWidgets.QApplication(sys.argv)

    mother_pipe, child_pipe = Pipe()
    queue = Queue()
    emitter = Emitter(mother_pipe)
    spectro_process = SpectroProcess(child_pipe, queue)

    w = MainWindow(icon_path, spectro_process.is_spectrometer, emitter, queue, spectro_process.xdata, spectro_process.array_size)
    spectro_process.start()

    w.show()
    app.exec()
    spectro_process.join()
    spectro_process.terminate()


