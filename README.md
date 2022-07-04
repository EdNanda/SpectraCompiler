# Spectra Compiler



## Getting started

To make it easy for you to get started with GitLab, here's a list of recommended next steps.

Already a pro? Just edit this README.md and make it your own. Want to make it easy? [Use the template at the bottom](#editing-this-readme)!

## Add your files

- [ ] [Create](https://docs.gitlab.com/ee/user/project/repository/web_editor.html#create-a-file) or [upload](https://docs.gitlab.com/ee/user/project/repository/web_editor.html#upload-a-file) files
- [ ] [Add files using the command line](https://docs.gitlab.com/ee/gitlab-basics/add-file.html#add-a-file-using-the-command-line) or push an existing Git repository with the following command:

```
cd existing_repo
git remote add origin git@gitlab.hzdr.de:hyd/spectra-compiler.git
git branch -M main
git push -uf origin main
```

## Integrate with your tools

- [x] [Set up project integrations](https://gitlab.hzdr.de/hyd/spectra-compiler/-/settings/integrations)

## Collaborate with your team

- [x] [Invite team members and collaborators](https://docs.gitlab.com/ee/user/project/members/)
- [ ] [Create a new merge request](https://docs.gitlab.com/ee/user/project/merge_requests/creating_merge_requests.html)
- [ ] [Automatically close issues from merge requests](https://docs.gitlab.com/ee/user/project/issues/managing_issues.html#closing-issues-automatically)
- [ ] [Enable merge request approvals](https://docs.gitlab.com/ee/user/project/merge_requests/approvals/)
- [ ] [Automatically merge when pipeline succeeds](https://docs.gitlab.com/ee/user/project/merge_requests/merge_when_pipeline_succeeds.html)

## Test and Deploy

Use the built-in continuous integration in GitLab.

- [ ] [Get started with GitLab CI/CD](https://docs.gitlab.com/ee/ci/quick_start/index.html)
- [ ] [Analyze your code for known vulnerabilities with Static Application Security Testing(SAST)](https://docs.gitlab.com/ee/user/application_security/sast/)
- [ ] [Deploy to Kubernetes, Amazon EC2, or Amazon ECS using Auto Deploy](https://docs.gitlab.com/ee/topics/autodevops/requirements.html)
- [ ] [Use pull-based deployments for improved Kubernetes management](https://docs.gitlab.com/ee/user/clusters/agent/)
- [ ] [Set up protected environments](https://docs.gitlab.com/ee/ci/environments/protected_environments.html)

***



# Spectra Compiler
For Ocean Insight spectrometers [link] https://www.oceaninsight.com/products/spectrometers/

## Description
This program allows you to collect data from Ocean Insight spectrometers and other brands. 
It it is possible to change the basic controls of the spectrometer, like the integration time and the number of measurements.
Additionally, you can remove background spectra with the "Dark measurement" option and do absorption measurements with the "Bright measurement" button.
Best of all, you can add all the relevant metadata for future analysis.

## Installation
Install the official Ocean Optics [drivers] (https://www.oceaninsight.com/products/software/)

Install the following libraries if using anaconda

```bash
conda install -c anaconda pyqt=5.12.3
conda install -c conda-forge seabreeze
```

## Usage
The program is a graphical interface. If a spectrometer is recognized, you will immediatly see the current spectrum. Otherwise, you will see a demo signal.

To start a measurement, simply press start.

## Support
For help, contact enandayapa@gmail.com

## Roadmap
If you have ideas for releases in the future, it is a good idea to list them in the README.

## Contributing
Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

Please make sure to update tests as appropriate.

## Authors and acknowledgment
Show your appreciation to those who have contributed to the project.

## License
[MIT](https://choosealicense.com/licenses/mit/)

## Project status
There is a small bug, where by choosing "Skip # measurements" other than 1, empty columns appear on the datafile, creating issues with excel or origin.
