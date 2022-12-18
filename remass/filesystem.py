"""
Parses the xochitl files into a file system-like hierarchical data structure.

For details on the tablet's file system, check the comprehensive summary on
https://remarkablewiki.com/tech/filesystem
"""
from dataclasses import dataclass, field
import os
import getpass
import json
import datetime
from typing import Callable, ClassVar, Dict, List, Tuple, Type
from collections import deque
import paramiko
from paramiko import file
from paramiko.util import ClosingContextManager
import stat
from pathlib import PurePosixPath
from pdfrw.objects.pdfdict import IndirectPdfDict
from rmrl import render
from pdfrw import PdfReader, PdfWriter


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
    def parent_uuid(self) -> str:
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

    @property
    def hierarchy_name(self) -> str:
        if self.parent is None:
            return self.visible_name
        else:
            return self.parent.hierarchy_name + '/' + self.visible_name


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
    """Returns a RDirEntry (RDocument or RCollection) from the given metadata.
    :metadata_filename: filename (without path/parent dir) as this will be
                        used to extract the UUID
    :metadata_file: file handle"""
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


def print_tree_structure(node, indent=0):
    """Simple DFS to print the file hierarchy starting at 'node'"""
    print(f"{' '*indent}{node.visible_name} {'[directory]' if isinstance(node, RCollection) else '[file]'}: {node.uuid}")
    if node.dirent_type == RCollection.dirent_type:
        for child in node.children:
            print_tree_structure(child, indent+4)


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
    """Builds the filesystem hierarchy from the given list of parsed RDirEntry objects."""
    # rM v5 has two base parents: None (root) or 'trash' (for deleted files)
    dirent_dict = dict()
    root = RCollection('root', 'My Files', version=-1, last_modified=None)
    dirent_dict['root'] = root
    trash = RCollection('trash', 'Trash', version=-1, last_modified=None)
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
    root = RCollection('root', 'My Files', version=-1, last_modified=None)
    trash = RCollection('trash', 'Trash', version=-1, last_modified=None)
    c1 = RCollection('uuid1', 'Collection 1', 1, None)
    c2 = RDocument('uuid2', 'Document 2', 1, None)
    c3 = RDocument('uuid3', 'Document 3', 1, None)
    gc1 = RDocument('uuid1-1', 'Document 1-1', 1, None)
    gc2 = RDocument('uuid1-2', 'Document 1-2', 1, None)
    gc3 = RDocument('uuid1-3', 'Document 1-3', 1, None)
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


def load_remote_filesystem(client: paramiko.SSHClient) -> Tuple[RCollection, RCollection, Dict[str, RDirEntry]]:
    """Loads the rM filesystem from the given remote connection.
    
    :return: root, trash, and a dict{uuid: entry}
    """
    sftp = client.open_sftp()
    dirent_list = _load_dirents_remote(sftp)
    root, trash, dirent_dict = _filesystem_from_dirents(dirent_list)
    sftp.close()
    return root, trash, dirent_dict


def is_rm_textfile(filename):
    """Returns True if the given filename is a known remarkable-specific textfile."""
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
        # We decode the byte streams only if the remote file is a known
        # (text-based) metadata/config/settings file
        self.decode = is_rm_textfile(filename)
        self.sftp_file = sftp_client.file(filename, mode, bufsize)
        self.prefetch()

    def close(self):
        self.sftp_file.close()

    def flush(self):
        self.sftp_file.flush()

    def prefetch(self, file_size=None):
        self.sftp_file.prefetch(file_size)

    def read(self, size=None):
        # As of v1.0, we only needed to expose the read() interface to enable
        # rendering the notebooks remotely (with correct template backgrounds).
        # For the future, we might want to also override: 
        # readable(), readinto(), readline(size=None), readlines(sizehint=None),
        # readv(chunks) and seekable()
        buf = self.sftp_file.read(size)
        if self.decode:
            return buf.decode('utf-8')
        else:
            return buf


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


def render_remote(
        client: paramiko.SSHClient, rm_file: RDocument, output_filename: str,
        progress_cb: Callable[[float], None], **kwargs) -> bool:
    """Uses the SSH connection to render the given notebook remotely."""
    if progress_cb is None:
        progress_cb = lambda x: None
    sftp = client.open_sftp()
    src = RemoteFileSystemSource(sftp, rm_file.uuid)
    render_output = render(src, progress_cb=progress_cb, **kwargs)
    sftp.close()
    pdf_stream = PdfReader(render_output)
    if pdf_stream is not None:
        pdf_stream.Info = IndirectPdfDict(
            Title=rm_file.visible_name,
            Author=getpass.getuser(),
            Subject='Exported Notes',
            Creator='reMass')
        PdfWriter(output_filename, trailer=pdf_stream).write()
        return True
    else:
        return False


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('backup_path', type=str, help='Path to local backup copy of xochitl files.')
    args = parser.parse_args()
    root, trash, _ = load_local_filesystem(args.backup_path)

    print('Root')
    print_tree_structure(root)
    print()
    print('Trash')
    print_tree_structure(trash)
