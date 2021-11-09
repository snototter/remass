# reMass
A text-based user interface which simplifies customizing reMarkable&reg;-ink tablets (screens &amp; templates) and provides PDF &amp; PNG export functionality.  

Why yet another rM assistant? - because I needed a quick solution to export my notes &amp; drawings without internet connection (and I find such a rather simplistic TUI easier to use than point-and-click interfaces).

## Disclaimer
This is not an official reMarkable&reg; product, and I am not affiliated with reMarkable AS in any way.  

This utility is offered without any warranty.
I release this utility in the hope that it is helpful to others, but I can make no guarantee that it works as intended.
There might be bugs, you may lose data, your device may crash, etc.

## TUI Demo
* Start-up screen (provides SSH connection options)
  ![Connection dialog](https://github.com/snototter/remass/blob/master/screenshots/startup.jpg?raw=true "Connection dialog")
* Main application screen showing device status information:
  ![Main form](https://github.com/snototter/remass/blob/master/screenshots/main.jpg?raw=true "Main form")
* PDF/PNG export screen:
  ![Export form](https://github.com/snototter/remass/blob/master/screenshots/export.jpg?raw=true "Export form")
* TODO Customizing splash screens:
* TODO Templates

## Setup
#### System Prerequisites:
This utility should work on any platform (Windows, Mac &amp; Linux). However, I can only test it on Linux (Ubuntu 18.04 &amp; 20.04 LTS) and, sporadically, on Windows 10.  
_If there are prerequisites missing for your platform, please let me know._
* `reMass` uses [`rmrl`](https://github.com/rschroll/rmrl) for PDF export, which requires Python 3.7 or later.  
  * On Ubuntu 20.04, Python 3.8 is the default version (at the time of writing).  
  * On Ubuntu 18.04, Python 3.6 is the default version, thus you have to install a newer one manually:  
    ```
    sudo apt install python3.8 python3.8-venv
    ```
* `reMass` uses [`pdf2image`](https://pypi.org/project/pdf2image/) for PNG export which requires [`poppler`](https://poppler.freedesktop.org/). Please refer to the [install instruction](https://pypi.org/project/pdf2image/) of `pdf2image`  
  (_On most Linux distributions, you just need to `sudo apt install poppler-utils`_)

#### Install reMass
TODO doc venv setup (local + via github)

#### Post-Install Steps
* TODO doc
  * rmrl load templates
  * cp screens to appdir/screens
  * cp templates to appdir/templates (or use submodule/retweaks repo)


#### Miscellaneous (Linux)
* To change the system-wide default applications to open PDF files/directories, you can use `xdg`:
  ```bash
  # Show known MIME associations
  cat ~/.config/mimeapps.list 

  # Change via xdg-mime, e.g. use 'nemo' as default file browser
  xdg-mime default nemo.desktop inode/directory
  ```
