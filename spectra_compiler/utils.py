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
