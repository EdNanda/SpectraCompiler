# Spectra Compiler
Graphical Interface based on pyqt that allows the user to collect multiple spectra from Ocean Optic spectrometers [link](https://www.oceaninsight.com/products/spectrometers/).

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.7639465.svg)](https://doi.org/10.5281/zenodo.7639465)

## Description
This program allows you to collect data from Ocean Insight spectrometers and other brands. 
One can change the basic controls of the spectrometer, like the integration time and the number of measurements.
Additionally, you can remove background spectra with the "Dark measurement" option and do absorption measurements with the "Bright measurement" button.
Furthermore, one can add a large amount of relevant metadata for future automated analysis.

## Installation
Install the official Ocean Optics [drivers](https://www.oceaninsight.com/products/software/)

Install the libraries shown in the requirements.txt

```bash
pip install .\requirements.txt
```

If using anaconda, make sure pyqt is installed through conda

```bash
conda install -c anaconda pyqt=5.12.3
```

## Usage
When running the code, a graphical interface will appear. If a spectrometer is recognized, you will immediately see the current spectrum. Otherwise, you will see a demo signal in the shape of a gaussian.

To start a measurement, simply press start.

## Support
For help, contact enandayapa@gmail.com

## Roadmap
The program is mostly on a finished state, albeit some small bugs that need fixing. 
Please contact us if you find any new issues.

## Contributing
Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

Please make sure to update tests as appropriate.

## Authors and acknowledgment
All programming was done by Edgar Nandayapa (Helmholtz-Zentrum Berlin, Germany) and Ashis Ravindran (Deutsches Krebsforschungszentrum, Heidelberg, Germany).
Field testing has been done by C. Rehermann (Helmholtz-Zentrum Berlin, Germany) and F. Mathies (Helmholtz-Zentrum Berlin, Germany).

## License
[MIT](https://choosealicense.com/licenses/mit/)

## Known issues
No known issues
