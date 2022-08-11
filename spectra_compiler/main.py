__author__ = "Edgar Nandayapa"
__version__ = "1.07-2021"

import sys
from PyQt5 import QtWidgets
from app import MainWindow
import pathlib


''''
1. Init spectormeter here...
2. Define data generating function here... get_ydata
3. 
'''
if __name__ == "__main__":
    icon_path = 'C:/Users/HYDN02/Seafile/IJPrinting_Edgar-Florian/python'
    icon_path = pathlib.Path(icon_path)
    app = QtWidgets.QApplication(sys.argv)
    w = MainWindow(icon_path)
    app.exec_()
