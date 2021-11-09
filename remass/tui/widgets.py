import curses
import npyscreen as nps
import os
import re
from typing import Tuple
from ..config import abbreviate_user


class CustomPasswordEntry(nps.Textfield):
    """Extension to npyscreen's PasswordEntry which allows overriding the
    password replacement character."""
    def __init__(self, *args, pwd_char: str='*', **kwargs):
        super().__init__(*args, **kwargs)
        self.pwd_char = pwd_char

    def _print(self):
        strlen = len(self.value)
        tmp_x = self.relx
        if self.maximum_string_length < strlen:
            n = self.maximum_string_length
            fx = self.parent.curses_pad.addch
        else:
            n = strlen
            fx = self.parent.curses_pad.addstr
        for i in range(n):
            fx(self.rely, tmp_x, self.pwd_char)
            tmp_x += 1


class TitleCustomPassword(nps.TitleText):
    _entry_type = CustomPasswordEntry


class CustomFilenameCombo(nps.FilenameCombo):
    """Customizes the filename display of the default FilenameCombo"""
    def __init__(self, screen, *args, when_value_edited_cb=None, initial_folder=None, **kwargs):
        self.initial_folder = initial_folder
        super().__init__(screen, *args, **kwargs)
        self.when_value_edited_cb = when_value_edited_cb
        # self.add_handlers({
        #     curses.ascii.ESC:  self.h_exit_escape
        # })#TODO check how we can abort the file selection by ESC (this likely needs a custom selector form :-/ )

    def when_value_edited(self):
        if self.when_value_edited_cb is not None:
            self.when_value_edited_cb()

    def display_value(self, vl):
        return abbreviate_user(str(vl))

    def _print(self):  # override (because I didn't like the "-Unset-" display)
        if self.value == None:
            printme = '- Not set -'
        else:
            try:
                printme = self.display_value(self.value)
            except IndexError:
                printme = '- Error -'
        if self.do_colors():
            self.parent.curses_pad.addnstr(self.rely, self.relx, printme, self.width, self.parent.theme_manager.findPair(self))
        else:
            self.parent.curses_pad.addnstr(self.rely, self.relx, printme, self.width)

    def h_change_value(self, *args, **keywords): # override
        self.value = nps.selectFile(
            starting_value = self.initial_folder if self.value is None or self.value == '' else self.value,
            select_dir = self.select_dir,
            must_exist = self.must_exist,
            confirm_if_exists = self.confirm_if_exists,
            sort_by_extension = self.sort_by_extension
        )
        if self.value == '':
            self.value = None
        self.display()

    @property
    def filename(self):
        if self.value is None:
            return None
        else:
            return os.path.expanduser(self.value)


class TitleCustomFilenameCombo(nps.TitleCombo):
    _entry_type = CustomFilenameCombo

    @property
    def filename(self):
        return self.entry_widget.filename


def _parse_range_token(token: str) -> Tuple[int, int]:
    """Parses an input range token:
    '*' or '-': (1, -1), i.e. representing the whole range
    X-Y: (X, Y)
    -Y:  (1, Y)
    X-:  (X, -1)
    """
    try:
        token = token.strip()
        if token == '*' or token == '-':
            return (1, -1)
        elif '-' in token:
            match = re.match(r"([-+]?\d+)?-([-+]?\d+)?", token)
            if match is None:
                return None
            return (int(match[1]) if match[1] is not None else 1,
                    int(match[2]) if match[2] is not None else -1)
        else:
            return (int(token), int(token))
    except:
        return None


class PageRange(nps.Textfield):
    """
    Allows parsing page range inputs, e.g. 1,2-5,17

    User inputs are exptected to be 1-based; start and end are inclusive.
    Its .page attribute parses the input into a list of tuple[start, end]
    Special:
    '*' denotes 'all', parsed as:       (1, -1)
    '-X' denotes '1 to X', parsed as:   (1,  X)
    'X-' denotes 'X to end', parsed as: (X, -1) 
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_handlers({ curses.ascii.ESC: self._reset })

    def _reset(self, *args, **kwargs):
        self.value = '*'
        self.display()

    @property
    def pages(self):
        if self.value is None:
            return None
        self.value = self.value.strip()
        if len(self.value) == 0:
            return None
        tokens = self.value.replace(';', ',').split(',')
        return [_parse_range_token(token) for token in tokens]


class TitlePageRange(nps.TitleText):
    _entry_type = PageRange

    @property
    def pages(self):
        return self.entry_widget.pages


class AlphaSlider(nps.Slider):
    """Slider widget to select a transparency/alpha value in [0,1] with increments of 0.1"""
    def translate_value(self):
        assert self.step == 1
        assert self.out_of == 10
        return f'{self.alpha:.1f}'.rjust(8)

    @property
    def alpha(self):
        return self.value / self.out_of


class TitleAlphaSlider(nps.TitleText):
    _entry_type = AlphaSlider
    def __init__(self, screen, *args, **kwargs):
        super().__init__(screen, *args, lowest=0, step=1, out_of=10, label=True, color='STANDOUT', **kwargs)

    @property
    def alpha(self):
        return self.entry_widget.alpha


class ProgressBar(nps.Slider):
    def __init__(self, *args, **keywords):
        super().__init__(*args, **keywords)
        self.editable = False

    def translate_value(self):
        assert self.out_of == 100
        percent = int(self.value)
        return f'{percent:d} %'.rjust(8)


class ProgressBarBox(nps.BoxTitle):   
    _contained_widget = ProgressBar
