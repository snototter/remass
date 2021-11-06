import npyscreen as nps
import platform
import os
import subprocess


###############################################################################
# TUI Utilities
###############################################################################
def add_empty_row(form: nps.Form) -> None:
    """Adds an empty row to the given form."""
    form.add(nps.FixedText, value='', hidden=True)


def full_class_name(o: object):
    """Returns the fully qualified class name of the given object.
    Taken from MB's answer: https://stackoverflow.com/a/13653312
    """
    module = o.__class__.__module__
    if module is None or module == str.__class__.__module__:
        return o.__class__.__name__
    return module + '.' + o.__class__.__name__


def safe_filename(fname: str) -> str:
    """
    Replaces all special (ASCII-only) characters in the given filename.
    Note that this will also replace path separators if present.
    """
    replacements = {
        '/': '_',
        '\\': '_',
        ':': '_',
        '?': '-',
        '!': '-',
        '*': '-',
        ' ': '-',
        '%': '_',
        '$': '_',
        '|': '',
        '"': '',
        '<': '',
        '>': ''
    }
    for needle, rep in replacements.items():
        fname = fname.replace(needle, rep)
    
    if platform.system() == 'Windows':
        # Filenames mustn't end with a dot on windows
        if fname[-1] == '.':
            return fname[:-1]
    return fname


def open_with_default_application(filename: str) -> None:
    if platform.system() == 'Darwin':
        subprocess.call(('open', filename),
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    elif platform.system() == 'Windows':
        os.startfile(filename)
    else:
        subprocess.call(('xdg-open', filename),
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
# if platform.system() == "Darwin":
#     subprocess.Popen(["open", folder])
# if platform.system() == "Windows":
#     os.startfile(folder)
# else:
#     subprocess.Popen(["xdg-open", folder])