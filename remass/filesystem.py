"""
Parses the xochitl files into a file system-like hierarchical data structure.

For details on the tablet's file system, check the comprehensive summary on
https://remarkablewiki.com/tech/filesystem
"""
from dataclasses import dataclass, field
import os
import json
import datetime
from typing import ClassVar, Dict, List, Tuple, Type
from collections import deque
import paramiko
from paramiko import file
from paramiko.util import ClosingContextManager
import stat
from pathlib import PurePosixPath
from rmrl import render


REMOTE_XOCHITL_DIR = '/home/root/.local/share/remarkable/xochitl'


@dataclass
class RDirEntry(object):
    uuid: str
    visible_name: str
    version: int
    last_modified: datetime.datetime
    deleted: bool = False
    metadata_modified: bool = False
    modified: bool = False
    _parent_uuid: str = None
    pinned: bool = False
    synced: bool = True
    parent: Type['RDirEntry'] = None  # This is how we can do 'forward declarations' in dataclasses

    @property
    def parent_uuid(self):
        if self._parent_uuid is None or len(self._parent_uuid) == 0:
            return None
        return self._parent_uuid

    def __lt__(self, other):
        if isinstance(self, RDocument):
            if isinstance(other, RDocument):
                return self.visible_name < other.visible_name
            else:
                return False
        else:
            # self is a _RLink or RCollection
            if isinstance(other, RDocument):
                return True
            else:
                return self.visible_name < other.visible_name

    def __eq__(self, other):
        if other is None:
            return False
        return self.uuid == other.uuid


@dataclass
class RDocument(RDirEntry):
    last_opened_page: int = 0
    dirent_type: ClassVar[str] = 'DocumentType'

    def __eq__(self, other):
        return super().__eq__(other)


@dataclass
class RCollection(RDirEntry):
    children: list = field(init=False)
    dirent_type: ClassVar[str] = 'CollectionType'
    
    def __post_init__(self):
        self.children = list()

    def add(self, content: RDirEntry):
        self.children.append(content)
        content.parent = self
        content._parent_uuid = self.uuid

    def sort(self):
        self.children.sort()
        for child in self.children:
            if isinstance(child, RCollection):
                child.sort()
    
    def __eq__(self, other):
        return super().__eq__(other)

@dataclass
class _RLink(RDirEntry):
    """Should only be used within fileselect to enable traversal up the file hierarchy."""
    dirent_type: ClassVar[str] = 'Link'

    def __eq__(self, other):
        return super().__eq__(other)


def dirent_from_metadata(metadata_filename: str, metadata_file):
    #TODO doc & type file handle, filename without path
    uuid = os.path.splitext(metadata_filename)[0]
    data = json.load(metadata_file)
    visible_name = data['visibleName']
    version = data['version']
    # Timestamp in .metadata is in milliseconds
    last_modified = datetime.datetime.fromtimestamp(int(data['lastModified']) / 1e3)
    deleted = data['deleted']
    pinned = data['pinned']
    synced = data['synced']
    metadata_modified = data['metadatamodified']
    modified = data['modified']
    parent_uuid = data['parent']
    deleted = data['deleted']

    if data['type'] == RDocument.dirent_type:
        last_opened_page = data['lastOpenedPage']
        return RDocument(uuid=uuid, visible_name=visible_name,
                    version=version, last_modified=last_modified,
                    deleted=deleted, pinned=pinned, synced=synced,
                    metadata_modified=metadata_modified, modified=modified,
                    _parent_uuid=parent_uuid, last_opened_page=last_opened_page)
    elif data['type'] == RCollection.dirent_type:
        return RCollection(uuid=uuid, visible_name=visible_name,
                    version=version, last_modified=last_modified,
                    deleted=deleted, pinned=pinned, synced=synced,
                    metadata_modified=metadata_modified, modified=modified,
                    _parent_uuid=parent_uuid)
    else:
        raise NotImplementedError(f"Data type '{data['type']} not yet supported")


def dfs(node, indent=0):
    print(f"{' '*indent}{node.visible_name} {'DIR' if isinstance(node, RCollection) else ''} {node.uuid}")
    if node.dirent_type == RCollection.dirent_type:
        for child in node.children:
            dfs(child, indent+4)


def _load_dirents_local(folder: str) -> List[RDirEntry]:
    """Parses the metadata files within the given folder into a list of dirents."""
    dirents = list()
    for f in os.listdir(folder):
        if not f.endswith('.metadata'):
            continue
        with open(os.path.join(folder, f), 'r') as mfile:
            dirent = dirent_from_metadata(f, mfile)
        dirents.append(dirent)
    return dirents


def _load_dirents_remote(sftp: paramiko.SFTPClient) -> List[RDirEntry]:
    """Parses the metadata files from the SFTP connection into a list of dirents."""
    dirents = list()
    # We're only interested in the .metadata files
    metadata_nodes = [de for de in sftp.listdir_attr(REMOTE_XOCHITL_DIR)
                      if stat.S_ISREG(de.st_mode) and de.filename.endswith('.metadata')]
    # print('METADATA NODES:', '\n'.join([n.filename for n in metadata_nodes]))
    for fnode in metadata_nodes:
        pth = PurePosixPath(REMOTE_XOCHITL_DIR, fnode.filename)
        with sftp.file(str(pth), 'r') as mfile:
            dirent = dirent_from_metadata(fnode.filename, mfile)
        dirents.append(dirent)
    return dirents

def _filesystem_from_dirents(dirent_list: List[RDirEntry]) -> Tuple[RCollection, RCollection, Dict[str, RDirEntry]]:
    # rM v5 has two base parents: None (root) or 'trash' (for deleted files)
    dirent_dict = dict()
    root = RCollection('root', '/TODO', version=-1, last_modified=None)
    dirent_dict['root'] = root
    trash = RCollection('trash', 'trash', version=-1, last_modified=None)
    dirent_dict['trash'] = trash

    # First pass, separate (direct) children from grandchildren
    grandchildren = list()
    for dirent in dirent_list:
        if dirent.parent_uuid is None:
            root.add(dirent)
        elif dirent.parent_uuid == 'trash':
            trash.add(dirent)
        else:
            grandchildren.append(dirent)
        dirent_dict[dirent.uuid] = dirent
    # Second pass, now all entries are known & we just need to finish the hierarchy
    for gc in grandchildren:
        if gc.parent_uuid not in dirent_dict:
            raise RuntimeError(f"Parent '{gc.parent_uuid}' of grandchild entry '{gc.uuid}' is not in dict - this should not happen (first check if filesystem specs have changed)")
        else:
            dirent_dict[gc.parent_uuid].add(gc)
    # Finally, sort the base parents (this will sort all child/grandchild collections, too)
    root.sort()
    trash.sort()
    return root, trash, dirent_dict


def dummy_filesystem() -> Tuple[RCollection, RCollection, Dict[str, RDirEntry]]:
    """Returns a dummy hierarchy used for offline development"""
    root = RCollection('root', 'My Documents/Notebooks TODO', version=-1, last_modified=None)
    trash = RCollection('trash', 'trash', version=-1, last_modified=None)
    c1 = RCollection('uuid1', 'First Child', 1, None)
    c2 = RDocument('uuid2', 'Second Child', 1, None)
    c3 = RDocument('uuid3', 'Third Child', 1, None)
    gc1 = RDocument('uuid1-1', 'First Grandchild', 1, None)
    gc2 = RDocument('uuid1-2', 'Second Grandchild', 1, None)
    gc3 = RDocument('uuid1-3', 'Third Grandchild', 1, None)
    root.add(c1)
    root.add(c2)
    trash.add(c3)
    c1.add(gc1)
    c1.add(gc2)
    c1.add(gc3)
    root.sort()
    trash.sort()
    dirents = {'root':root, 'trash':trash}
    dirents[c1.uuid] = c1
    dirents[c2.uuid] = c2
    dirents[c3.uuid] = c3
    dirents[gc1.uuid] = gc1
    dirents[gc2.uuid] = gc2
    dirents[gc3.uuid] = gc3
    return root, trash, dirents

    


def load_local_filesystem(folder: str) -> Tuple[RCollection, RCollection, Dict[str, RDirEntry]]:
    """Builds a filesystem representation from the given xochitl backup folder.
    
    :return: root, trash, and a dict{uuid: entry}
    """
    dirent_list = _load_dirents_local(folder)
    return _filesystem_from_dirents(dirent_list)


# def render_test():
#     from rmrl import render
#     # import shutil
#     render_output = render(os.path.join(os.path.dirname(__file__), 'dev-files', 'xochitl', '18cc3ec7-6e38-49ec-8de4-a28ca9530e02'))
#     # render_output = render(os.path.join(os.path.dirname(__file__), 'dev-files', 'xochitl', '53d9369c-7f2c-4b6d-b377-0fc5e71135cc'))
    
#     print('RENDER OUTPUT: ', type(render_output))
#     #render_output.seek(0)
#     from pdfrw import PdfReader, PdfWriter
#     pdf_stream = PdfReader(render_output)
#     print('DUMP INFO:', pdf_stream.Info)
#     pdf_stream.Info.Title = 'Notebook Title'
#     PdfWriter('render-test.pdf', trailer=pdf_stream).write()
#     # with open('render-test.pdf', "wb") as outfile:
#     #     shutil.copyfileobj(output, outfile)


# def list_types(folder):
#     counter = dict()
#     for f in os.listdir(folder):
#         if not f.endswith('.metadata'):
#             continue
#         with open(os.path.join(folder, f), 'r') as mdf:
#             metadata = json.load(mdf)
#             type_ = metadata['type']
#             if os.path.basename(f).startswith('e7fe9444-9e3a-4bfb-9e3d-3713d7a05d45'):
#                 print('BINGO', metadata)
#             # print(type_, metadata['visibleName'])
#             if type_ in counter:
#                 counter[type_] += 1
#             else:
#                 counter[type_] = 0
#             # print(metadata)
#     print(counter)


def load_remote_filesystem(client: paramiko.SSHClient) -> Tuple[RCollection, RCollection, Dict[str, RDirEntry]]:
    """Loads the rM filesystem from the given remote connection.
    
    :return: root, trash, and a dict{uuid: entry}
    """
    sftp = client.open_sftp()
    dirent_list = _load_dirents_remote(sftp)
    root, trash, dirent_dict = _filesystem_from_dirents(dirent_list)
    print('Root')
    dfs(root)
    print()
    print('Trash')
    dfs(trash) #TODO rm output
    return root, trash, dirent_dict


def is_rm_textfile(filename):
    if filename.endswith('.json'):
        return True
    if filename.endswith('.content'):
        return True
    if filename.endswith('.pagedata'):
        return True
    if filename.endswith('.bookm'):
        return True
    return False


class RemoteFile(ClosingContextManager):
    def __init__(self, sftp_client, filename, mode, bufsize):
        # self.sftp_client = sftp_client
        # self.filename = filename
        self.decode = is_rm_textfile(filename)
        self.sftp_file = sftp_client.file(filename, mode, bufsize)
    
    def close(self):
        self.sftp_file.close()
    
    def flush(self):
        self.sftp_file.flush()

    def prefetch(self, file_size=None):
        self.sftp_file.prefetch(file_size)
    
    def read(self, size=None):
        buf = self.sftp_file.read(size)
        if self.decode:
            return buf.decode('utf-8')
        else:
            return buf
        #TODO as of now, it seems we only need to expose the read() interface
        #  readable, readinto, readline(size=None), readlines(sizehint=None), readv(chunks)
        #TODO seekable()
        

class RemoteFileSystemSource(object):
    def __init__(self, sftp_client, doc_id):
        self.base_dir = PurePosixPath(REMOTE_XOCHITL_DIR)
        self.sftp_client = sftp_client
        self.doc_id = doc_id

    def format_name(self, name):
        return str(self.base_dir / name.format(ID=self.doc_id))

    def open(self, fn, mode='r', bufsize=-1):
        # Paramiko SFTPFile only returns bytes but rmrl requires strings for
        # text files. Thus, we use our RemoteFile wrapper
        # return self.sftp_client.file(self.format_name(fn), mode, bufsize)
        return RemoteFile(self.sftp_client, self.format_name(fn), mode, bufsize)

    def exists(self, fn):
        try:
            self.sftp_client.stat(self.format_name(fn))
            return True
        except IOError:
            return False


#TODO the user will likely have to preload the templates for rmrl, see rmrl doc (~/.local/share/rmrl/templates)
#     - but this currently doesn't work for me... (no templates loaded when file is remote...)
#     - the problem is strings vs bytes (sftpfile: b'GridRulerP' versus local file: 'GridRuleP' for template name...)
      #TODO check whether we can easily change the template name type: https://github.com/rschroll/rmrl/blob/89b5cc38ef45251b96bd3d1c3618429b6b46db92/rmrl/document.py#L51
      # or if we can adjust an sftpfile setting
      # or :( if we have to override sftpfile
      # or ... if we have to copy all the files over...
#TODO rendering (especially REMOTE!) must be done in a separate thread (and use the progress callback)
def render_remote(client: paramiko.SSHClient, uuid: str):
    #     from rmrl import render
    # # import shutil
    sftp = client.open_sftp()
    src = RemoteFileSystemSource(sftp, uuid)
    render_output = render(src)
    # # render_output = render(os.path.join(os.path.dirname(__file__), 'dev-files', 'xochitl', '53d9369c-7f2c-4b6d-b377-0fc5e71135cc'))
    print('RENDER OUTPUT: ', type(render_output))
    #render_output.seek(0)
    from pdfrw import PdfReader, PdfWriter
    pdf_stream = PdfReader(render_output)
    print('DUMP INFO:', pdf_stream.Info)
    pdf_stream.Info.Title = 'Notebook Title'
    PdfWriter('render-test.pdf', trailer=pdf_stream).write()
    # with open('render-test.pdf', "wb") as outfile:
    #     shutil.copyfileobj(output, outfile)
    

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('backup_path', type=str, help='Path to local backup copy of xochitl files.')
    args = parser.parse_args()
    root, trash, _ = load_local_filesystem(args.backup_path)

    print('Root')
    dfs(root)
    print()
    print('Trash')
    dfs(trash)
