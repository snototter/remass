# reMass
TUI (text-based UI) for Unix-like systems which simplifies customizing reMarkable&reg; e-ink tablets (screens &amp; templates) and provides basic PDF &amp; PNG export functionality.  

Why yet another rM assistant? - because I needed a quick solution to export my notes &amp; drawings without internet connection (and I find such a rather simplistic TUI easier to use than point-and-click interfaces).  
If you're unexperienced at using the command line or are afraid of breaking something, you should likely prefer [RCU](http://www.davisr.me/projects/rcu/).

## Disclaimer
This is not an official reMarkable&reg; product, and I am not affiliated with reMarkable AS in any way.  

This utility is offered without any warranty.
I release this utility in the hope that it is helpful to others, but I can make no guarantee that it works as intended.
There might be bugs, you may lose data, your device may crash, etc.

## TUI Demo
After [setup](#setup), you can run `reMass` via `python -m remass`. The following screenshots show its basic functionalities:
#### Start-up Screen
<img src="https://github.com/snototter/remass/blob/master/screenshots/startup.jpg?raw=true" alt="Connection Dialog" width="50%"/>

#### Main Application Screen
<img src="https://github.com/snototter/remass/blob/master/screenshots/main.jpg?raw=true" alt="Main Screen" width="50%"/>

#### PDF/PNG Export
<img src="https://github.com/snototter/remass/blob/master/screenshots/export.jpg?raw=true" alt="PDF/PNG Export" width="50%"/>

#### Template Up-/Download
<img src="https://github.com/snototter/remass/blob/master/screenshots/templates1.jpg?raw=true" alt="PDF/PNG Export" width="50%"/>

#### Template Removal
<img src="https://github.com/snototter/remass/blob/master/screenshots/templates2.jpg?raw=true" alt="PDF/PNG Export" width="50%"/>

#### Customizing Splash Screens
<img src="https://github.com/snototter/remass/blob/master/screenshots/screens.jpg?raw=true" alt="Screen Customization" width="50%"/>

#### Device Settings
<img src="https://github.com/snototter/remass/blob/master/screenshots/settings.jpg?raw=true" alt="Screen Customization" width="50%"/>


## Setup
#### System Prerequisites & Caveats:
* `reMass` requires `curses` and thus, should work on any Unix-like platform. It is only tested on Linux (Ubuntu 18.04 &amp; 20.04 LTS).
* `reMass` uses a [fork]([`rmrl`](https://github.com/snototter/rmrl)) of [`rmrl`](https://github.com/rschroll/rmrl) to export PDFs. `rmrl` requires Python 3.7 or later.
  * On Ubuntu 20.04, Python 3.8 is the default version (at the time of writing).  
  * On Ubuntu 18.04, Python 3.6 is the default version, thus you have to install a newer version, e.g.  
    `sudo apt install python3.8 python3.8-venv`
* `reMass` uses [`pdf2image`](https://pypi.org/project/pdf2image/) for PNG export which requires [`poppler`](https://poppler.freedesktop.org/). On most Linux distributions, you just need to:  
  `sudo apt install poppler-utils`
* **Limitations:** Currently, `rmrl` doesn't support fine-grained textures for pencils and paintbrushes (all other pen styles render nicely).

#### Install reMass
* The easiest way is to install `reMass` directly from github into a `virtualenv`:
  ```bash
  # Set up & activate a virtual environment
  python3 -m venv venv
  source venv/bin/activate

  # Install reMass
  python -m pip install https://github.com/snototter/remass/tarball/master

  # Now use it
  python -m remass
  ```
* Optionally, adjust and install `./standalone/remass.desktop`:
  ```bash
  # Verify .desktop file before installation:
  desktop-file-validate standalone/remass.desktop

  # Install for current user only:
  desktop-file-install standalone/remass.desktop --dir ~/.local/share/applications/
  ```

#### First Steps
* **Paths:** by default, `reMass` uses `$XDG_CONFIG_HOME/remass/` (refer to the [XDG base directory specification](https://specifications.freedesktop.org/basedir-spec/latest/ar01s03.html)) to store its configuration and `$XDG_DATA_HOME/remass` to store data.  
  You can change these paths via command line arguments, see the provided help:
  ```bash
  python -m remass -h
  ```
* **Configuration:** The starting screen offers all connection options. If you adjust these, you can save this configuration to disk (as TOML) to avoid re-configuration upon the next program start.  
  Available options:  
  ```toml
  [connection]
  # Default hostname/IP
  host = "10.11.99.1"

  # If connection to 'host' cannot be established, reMass tries the fallback:
  host_fallback = ""

  # If you have set up authentication via your private key, specify
  keyfile = "~/.ssh/my_private_key"

  # If keyfile is set, this password will be used to unlock the key. Otherwise,
  # reMass assumes it is the tablet's root password.
  password = "password"

  # SSH connection timeout in seconds
  timeout = 1
  ```
* **Templates:** Notebook templates can optionally be used as background when rendering PDFs from notebooks. You have to check first if you are allowed to copy them from your reMarkable device to your computer for personal use. If this is legal in your jurisdiction, you may `Download Templates From Tablet` within the template section of `reMass`.  
  To get started, you can also try [these custom templates](https://github.com/snototter/retweaks/tree/master/templates).
* **Screens:** For ease of use, copy your custom splash screens to `XDG_DATA_HOME/remass/screens`. Refer to the [reMarkableWiki](https://remarkablewiki.com/tips/splashscreens) on how to make your own.  
  To get started, you can also try [these custom screens](https://github.com/snototter/retweaks/tree/master/splash-screens).

#### Miscellaneous (Linux)
* To change the system-wide default applications to open PDF files/directories, you can use `xdg`:
  ```bash
  # Show known MIME associations
  cat ~/.config/mimeapps.list 

  # Change via xdg-mime, e.g. use 'nemo' as default file browser
  xdg-mime default nemo.desktop inode/directory
  ```
