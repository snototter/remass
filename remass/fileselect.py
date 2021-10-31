#!/usr/bin/env python
from typing import List
import npyscreen as nps
import os
import curses
from .filesystem import RCollection, RDirEntry, RDocument, _RBackRef, dummy_filesystem


class RFileGrid(nps.SimpleGrid):
    default_column_number = 3
    
    def set_up_handlers(self):
        super(RFileGrid, self).set_up_handlers()
        self.handlers.update ({
            curses.ascii.NL:    self.h_select_file,
            curses.ascii.CR:    self.h_select_file,
            curses.ascii.SP:    self.h_select_file,
        })
    
    def display_value(self, vl):
        s = ''
        if vl.dirent_type == RDocument.dirent_type:
            s += '[f] '
        elif vl.dirent_type == RCollection.dirent_type:
            s += '[d] '
        return s + vl.visible_name
    
    def change_dir(self, select_file):
        self.parent.selected_folder = select_file
        self.parent.update_grid()
        self.edit_cell = [0, 0]
        self.begin_row_display_at = 0
        self.begin_col_display_at = 0
        return True
        
    def set_grid_values(self, new_values, max_cols=None, reset_cursor=True):
        if not max_cols:
            max_cols = self.columns
        grid_values = [ [], ]
        col_number        = 0
        row_number        = 0
        for f in new_values:
            if col_number >= max_cols:
                col_number = 0
                grid_values.append([])
                row_number += 1
            grid_values[row_number].append(f)
            # if f == selected_file:  # if we set the edit_cell, we cannot navigate the grid anymore (too lazy to debug the nps widget)
            #     self.edit_cell = [row_number, col_number]
            col_number += 1
        self.values = grid_values
        if reset_cursor:
            self.edit_cell = [0,0]
    
    def h_select_file(self, *args, **keywrods):
        dirent = self.values[self.edit_cell[0]][self.edit_cell[1]]
        if dirent.dirent_type == RDocument.dirent_type:
            # self.parent.wCommand.value = dirent
            self.parent.selected_file = dirent
            self.h_exit_down(None)
            self.parent.try_exit()
        else:
            self.change_dir(dirent)
#TODO we don't have '..'

class RFileSelector(nps.FormBaseNew):
    def __init__(self,
                 rm_dirents, 
                 starting_value: RDirEntry = None,  # Pre-select the starting file node (will switch to the parent container if it's a document)
                 select_dir: bool = True,  # Select a directory if True, otherwise select a file
                 *args, **keywords):
        self.rm_dirents = rm_dirents
        self.select_dir = select_dir
        self.selected_folder = None
        self.selected_file = None

        if starting_value is not None:
            if starting_value.dirent_type == RDocument.dirent_type:
                self.selected_file = starting_value
                self.selected_folder = starting_value.parent
            else:
                self.selected_folder = starting_value

        super(RFileSelector, self).__init__(*args, **keywords)
    
    def try_exit(self):
        if self.select_dir and self.selected_folder is None:
            self.exit_editing()
            return False

        if not self.select_dir and self.selected_file is None:
            self.exit_editing()
            return False

        self.exit_editing()
        return True
        
    def create(self):
        self.wMain = self.add(RFileGrid)

    def beforeEditing(self,):
        self.adjust_widgets()

    def update_grid(self,):
        if isinstance(self.selected_folder, _RBackRef) and self.selected_folder.uuid is None:
            self.selected_folder = None
        if self.selected_folder is None:
            file_list = [self.rm_dirents['root'], self.rm_dirents['trash']]
        else:
            dirent = self.rm_dirents[self.selected_folder.uuid]
            file_list = [_RBackRef(dirent.parent_uuid, '..', dirent.version, None)] + dirent.children
        self.wMain.set_grid_values(file_list, reset_cursor=False, max_cols=3)
        self.display()

    def adjust_widgets(self):
        self.update_grid()
        
def selectRFile(rm_dirents, starting_value=None, select_dir=False, *args, **keywords):
    F = RFileSelector(rm_dirents, starting_value, *args, **keywords)
    F.update_grid()
    F.display()
    F.edit()    
    return F.selected_folder if select_dir else F.selected_file


class RFilenameCombo(nps.ComboBox):
    """You can EITHER select a notebook/document OR a folder, depending on how
    you set select_dir"""
    def __init__(self, screen, rm_dirents: List[RDirEntry], select_dir: bool, *args, **keywords):
        self.select_dir = select_dir
        self.rm_dirents = rm_dirents
        super(RFilenameCombo, self).__init__(screen, *args, **keywords)

    def _print(self):
        if isinstance(self.value, RDirEntry):
            printme = self.value.visible_name
        else:
            self.value = None
            printme = '- Unset -'

        if self.do_colors():
            self.parent.curses_pad.addnstr(self.rely, self.relx, printme, self.width, self.parent.theme_manager.findPair(self))
        else:
            self.parent.curses_pad.addnstr(self.rely, self.relx, printme, self.width)

    def h_change_value(self, *args, **keywords):
        self.value = selectRFile(
            rm_dirents = self.rm_dirents,
            starting_value = self.value,
            select_dir = self.select_dir)
        self.display()


class TitleRFilenameCombo(nps.TitleCombo):
    _entry_type = RFilenameCombo


class MainForm(nps.ActionFormMinimal):
    OK_BUTTON_TEXT = 'Exit'

    def __init__(self, dirents, *args, **kwargs):
        self.dirents = dirents
        super().__init__(*args, **kwargs)

    def on_ok(self):
        self.exit_application()

    def create(self):
        self.add_handlers({
            "^X": self.exit_application
        })
        self.select_file = self.add(TitleRFilenameCombo, name="RM File", label=True,
                                    rm_dirents=self.dirents, select_dir=False)

    def exit_application(self, *args, **kwargs):
        self.parentApp.setNextForm(None)
        self.editing = False
        self.parentApp.switchFormNow()


class TestApp(nps.NPSAppManaged):
    def __init__(self, dirents, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.dirents = dirents

    def onStart(self):
        self.addFormClass('MAIN', MainForm, dirents=self.dirents, name='reMass')


if __name__ == "__main__":
    from .filesystem import load_local_filesystem, dummy_filesystem
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--bp', type=str, help='Path to local backup copy of xochitl files.', default=None)
    args = parser.parse_args()
    if args.bp is None:
        root, trash, dirents = dummy_filesystem()
    else:
        root, trash, dirents = load_local_filesystem(args.bp)
    # dfs(root)
    # dfs(trash)
    App = TestApp(dirents)
    App.run()
