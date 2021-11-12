# reMass
TUI (text-based UI) for Unix-like systems which simplifies customizing reMarkable&reg; e-ink tablets (screens &amp; templates) and provides basic PDF &amp; PNG export functionality.  

Why yet another rM assistant? - because I needed a quick solution to export my notes &amp; drawings without internet connection (and I find such a rather simplistic TUI easier to use than point-and-click interfaces).

## Disclaimer
This is not an official reMarkable&reg; product, and I am not affiliated with reMarkable AS in any way.  

This utility is offered without any warranty.
I release this utility in the hope that it is helpful to others, but I can make no guarantee that it works as intended.
There might be bugs, you may lose data, your device may crash, etc.

## TUI Demo
After setup, you can run `reMass` via `python -m remass`:
* Start-up screen  
  ![Connection dialog](https://github.com/snototter/remass/blob/master/screenshots/startup.jpg?raw=true "Connection dialog")
* Main application screen showing device status information:  
  ![Main screen](https://github.com/snototter/remass/blob/master/screenshots/main.jpg?raw=true "Main screen")
* PDF/PNG export screen:  
  ![Export screen](https://github.com/snototter/remass/blob/master/screenshots/export.jpg?raw=true "Export screen")
* TODO Templates
  * https://github.com/rschroll/rmrl#templates (our patched rmrl can be used with custom template paths, thus we can use the "load templates" button if you're allowed)
* Customizing the tablet's splash screens:  
  ![Screen customization](https://github.com/snototter/remass/blob/master/screenshots/screens.jpg?raw=true "Screen customization")

## Setup
#### System Prerequisites:
This utility should work on any Unix-like platform (as it requires `curses`). It is only tested on Linux (Ubuntu 18.04 &amp; 20.04 LTS). _If there are prerequisites missing for your platform, please let me know._
* `reMass` uses [`rmrl`](https://github.com/rschroll/rmrl) for PDF export, which requires Python 3.7 or later.  
  * On Ubuntu 20.04, Python 3.8 is the default version (at the time of writing).  
  * On Ubuntu 18.04, Python 3.6 is the default version, thus you have to install a newer version, e.g.  
    `sudo apt install python3.8 python3.8-venv`
* Since we actually rely on a patched [`rmrl`](https://github.com/snototter/rmrl) fork, you will need `git` to install this dependency automatically using `pip`:  
  `sudo apt install git`
* `reMass` uses [`pdf2image`](https://pypi.org/project/pdf2image/) for PNG export which requires [`poppler`](https://poppler.freedesktop.org/). On most Linux distributions, you just need to:  
  `sudo apt install poppler-utils`

#### Install reMass
The easiest way is to install `reMass` directly from github into a `virtualenv`:
```bash
# Set up & activate a virtual environment
python3 -m venv venv
source venv/bin/activate

# Install reMass
python -m pip install https://github.com/snototter/remass/tarball/master

# Now use it
python -m remass
```

#### First Steps
TODO add documentation
* **Paths:** by default, `reMass` uses `XDG_CONFIG_HOME/remass/` (usually `$HOME/.config/remass`) to store its configuration and `XDG_DATA_HOME/remass` (usually `$HOME/.local/share/remass`) to store data.  
  You can change these paths via command line arguments, see the provided help:
  ```bash
  python -m remass -h
  ```
* **Configuration:** the starting screen offers all connection options. If you adjust these, you can save this configuration to disk (as TOML) to avoid re-configuration upon the next program start.  
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
* **Templates:** TODO load templates for export
* **Screens:** for ease of use, copy your custom splash screens to `XDG_DATA_HOME/remass/screens`. Refer to the [reMarkableWiki](https://remarkablewiki.com/tips/splashscreens) on how to make your own.

#### Miscellaneous (Linux)
* To change the system-wide default applications to open PDF files/directories, you can use `xdg`:
  ```bash
  # Show known MIME associations
  cat ~/.config/mimeapps.list 

  # Change via xdg-mime, e.g. use 'nemo' as default file browser
  xdg-mime default nemo.desktop inode/directory
  ```

## Status
`v1.0` will be considered feature-complete:
* [x] Notebook export
* [x] Screen customization
* [ ] Template management

Nice-to-have features for (very! distant) future updates:
* [ ] Adjust tablet configuration (i.e. xochitl.conf settings)
* [ ] Automatically set the timezone (must be able to query the host's timezone without DST, though)  
  remote: `timedatectl set-timezone (non-DST)TZ`  
  python: `import time; time.tzname[0] # is non-DST`
* [ ] Adjust the hostname
* [ ] Reboot the tablet
* [ ] Remove rm files from the tablet (both, move to trash and delete permanently)
