from queue import Empty
import numpy as np
import time
import seabreeze.spectrometers as sp
from multiprocessing import Process, Queue, Pipe


class SpectroProcess(Process):
    def __init__(self, to_emitter: Pipe, from_mother: Queue, daemon=True):
        super().__init__()
        self.daemon = daemon
        self.to_emitter = to_emitter
        self.data_from_mother = from_mother
        self.is_spectrometer = bool(len(sp.list_devices()))
        if self.is_spectrometer:  # TODO: check if this is needed or arbitarty fixing values are enough?
            _spec = sp.Spectrometer.from_first_available()
            self.xdata = _spec.wavelengths()[2:]
            self.array_size = len(self.xdata)
            print("spec found")
        else:
            self.array_size = 2046
            self.xdata = np.linspace(340, 1015, self.array_size)
            print("spec not found")

    def reinit_spectrometer_generator(self):
        try:
            self.spec = sp.Spectrometer.from_first_available()
            self.spec.integration_time_micros(200000)
        except Exception:
            print("Spectrometer couldn't be initialized.")

    def run(self):
        def accurate_delay(delay):
            ''' Function to provide accurate time delay in millisecond
            '''
            _ = time.perf_counter() + delay / 1000
            while time.perf_counter() < _:
                pass

        if self.is_spectrometer:
            self.reinit_spectrometer_generator()
            _DP = 1420  # dead pixel on spectrometer @831.5nm
            is_model_verified: bool = ("FLMS12200" in self.spec.serial_number)
            while True:
                ydata = self.spec.intensities()[2:]
                if is_model_verified:
                    ydata[_DP] = np.mean(ydata[_DP - 2:_DP + 2])
                    self.to_emitter.send(ydata)
                    try:
                        inttime = self.data_from_mother.get_nowait()
                        if inttime:
                            self.spec.integration_time_micros(int(inttime * 1000000))
                        else:
                            self.spec.close()
                            break
                    except Empty:
                        pass
        else:
            xx = np.arange(self.array_size)
            inttime = 0.2
            while True:
                accurate_delay(inttime)  # time.sleep(self.inttime)
                ydata = 50000 * np.exp(-(xx - 900) ** 2 / (2 * 100000)) + np.random.randint(0, 10001)
                self.to_emitter.send(ydata)
                try:
                    inttime = self.data_from_mother.get_nowait()
                    if inttime:
                        inttime *= 1000  # convert to ms
                        print("wait time changed (ms)", inttime)
                    else:
                        break
                except Empty:
                    pass
