import numpy as np
import socket


def get_host_name() -> str:
    return socket.gethostname()


def array_for_scrollbar(min_val=0.06, max_val=2, factor=0.385, max_bar=99) -> list:
    """
    Create an array of values for the scrollbar
    :param min_val:
    :param max_val:
    :param factor:
    :param max_bar:
    :return: (list)
    """
    arr_scrbar = []
    for i in range(100):  # TODO: convert to list comprehension --ashis
        arr_scrbar.append(round(np.exp(i * (factor + np.log(max_val)) / max_bar) - 1 + min_val, 2))
    return arr_scrbar


def LEskip_positive_number(string_val: str) -> str:
    """
    ## Makes sure that number of skipped measurements is a positive integer
    :param self:
    :return:
    """
    try:
        num = int(string_val)
        if num < 0:
            return "1"
    except:
        return "1"
    else:
        return string_val


def spectra_math(ydata, is_dark_data, is_bright_data, dark_mean, bright_mean):
    if is_dark_data and not is_bright_data:
        yarray = (ydata - dark_mean)
    elif is_bright_data and not is_dark_data:
        yarray = ydata / bright_mean
    elif is_bright_data and is_dark_data:
        yarray = 1 - np.divide((ydata - dark_mean), (bright_mean - dark_mean))
    else:
        return ydata
    return yarray

"""
Maybe start a class called "SpectraAlgorithms" with all algorithm functions and state variables eg- ydata, bright_mean
"""