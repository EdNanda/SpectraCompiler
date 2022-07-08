# Spectra Compiler
Graphical Interface based on pyqt that allows the user to collect multiple spectra from Ocean Optic spectrometers [link] https://www.oceaninsight.com/products/spectrometers/


## Description
This program allows you to collect data from Ocean Insight spectrometers and other brands. 
One can change the basic controls of the spectrometer, like the integration time and the number of measurements.
Additionally, you can remove background spectra with the "Dark measurement" option and do absorption measurements with the "Bright measurement" button.
Furthermore, one can add a large amount of relevant metadata for future automated analysis.

## Installation
Install the official Ocean Optics [drivers] (https://www.oceaninsight.com/products/software/)

Install the following libraries if using anaconda

```bash
conda install -c anaconda pyqt=5.12.3
conda install -c conda-forge seabreeze
```

## Usage
When running the code, a graphical interface will appear. If a spectrometer is recognized, you will immediatly see the current spectrum. Otherwise, you will see a demo signal in the shape of a gaussian.

To start a measurement, simply press start.

## Support
For help, contact enandayapa@gmail.com

## Roadmap
The program is mostly on a finished state, other than fixing some bugs. 
Please contact us if you find any issues

## Contributing
Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

Please make sure to update tests as appropriate.

## Authors and acknowledgment
Show your appreciation to those who have contributed to the project.

## License
[MIT](https://choosealicense.com/licenses/mit/)

## Known issues
When "Skip # measurements" is other than 1, empty columns appear on the output datafile, creating issues when trying to open it with programs like excel or origin.
