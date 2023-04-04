# SPDX-FileCopyrightText: 2023 Edgar Nandayapa (Helmholtz-Zentrum Berlin) & Ashis Ravindran (DKFZ, Heidelberg)
#
# SPDX-License-Identifier: MIT

import math
import numpy as np
import socket


def get_host_name() -> str:
    """

    @return: pc name
    """
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
    arr_scrbar = [round(math.exp(i * (factor + math.log(max_val)) / max_bar) - 1 + min_val, 2) for i in range(100)]
    return arr_scrbar


def LEskip_positive_number(string_val: str) -> str:
    """
    #  Makes sure that number of skipped measurements is a positive integer
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


def spectra_math(ydata: np.ndarray, is_dark_data, is_bright_data, dark_mean, bright_mean) -> np.ndarray:
    """
    Do necessary math to spectra with respect to what has been selected:
    Using bright_data as a top limit, spectra is normalized to 1
    dark_data is subtracted from raw spectra
    @param ydata: list of raw spectra data
    @param is_dark_data: boolean for dark data
    @param is_bright_data: boolean for bright data
    @param dark_mean: list of dark data
    @param bright_mean: list of bright data
    @return: list of calculated spectra
    """
    if is_dark_data and not is_bright_data:
        yarray = (ydata - dark_mean)
    elif is_bright_data and not is_dark_data:
        yarray = ydata / bright_mean
    elif is_bright_data and is_dark_data:
        # yarray = 1 - np.divide((ydata - dark_mean), (bright_mean - dark_mean) + 1e-6) # Transmittance
        yarray = -1 * np.log(np.divide((ydata - dark_mean), (bright_mean - dark_mean))) # Absorbance
    else:
        return ydata
    return yarray
