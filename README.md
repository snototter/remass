# reMarkable Assistant
A curses-based TUI enabling customization (screens &amp; templates) and export (PDF &amp; PNG) for my reMarkable e-ink tablet.

## Disclaimer
This is not an official reMarkable product, and I am not affiliated with reMarkable AS in any way.  
I release this utility in the hope that it is helpful to others, but I can make no guarantee that it works as intended.  
There might be bugs, you may lose data, your device may crash, etc.

## Demo
TODO Screenshots

## Setup
#### System Prerequisites:
* `reMass` uses [`rmrl`](https://github.com/rschroll/rmrl) to render reMarkable documents as PDF, which requires Python 3.7 or later.  
  On Ubuntu 20.04, Python 3.8 is the default version at the time of writing.  
  On Ubuntu 18.04 (and like up to 19.10, but didn't check), you have to install it manually:  
  `sudo apt install python3.8 python3.8-venv`
* `reMass` uses [`pdf2image`](https://pypi.org/project/pdf2image/) to convert PDF pages to images. This relies on the `pdftoppm` and `pdftocairo` utils from [poppler](https://poppler.freedesktop.org/).  
   Refer to the [install instruction](https://pypi.org/project/pdf2image/) of `pdf2image` (on most Linux distributions, you just need to `sudo apt install poppler-utils`)

#### Install reMass
TODO

#### Post-Install Steps
rmrl load templates
