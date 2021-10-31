"""
Parses the xochitl files into a file system-like hierarchical data structure.

For details on the tablet's file system, check the comprehensive summary on
https://remarkablewiki.com/tech/filesystem
"""
from dataclasses import dataclass, field
import os
import json
import datetime
from typing import ClassVar, Dict, Tuple, Type
from collections import deque


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
        return self.visible_name < other.visible_name


@dataclass
class RDocument(RDirEntry):
    last_opened_page: int = 0
    dirent_type: ClassVar[str] = 'DocumentType'


@dataclass
class RCollection(RDirEntry):
    children: list = field(init=False)
    dirent_type: ClassVar[str] = 'CollectionType'
    
    def __post_init__(self):
        self.children = list()

    def add(self, content: RDirEntry):
        self.children.append(content)

    def sort(self):
        self.children.sort()
        for child in self.children:
            if isinstance(child, RCollection):
                child.sort()


def dirent_from_metadata(metadata_filename):
    uuid = os.path.splitext(os.path.basename(metadata_filename))[0]
    with open(metadata_filename, 'r') as mdf:
        data = json.load(mdf)
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


def _load_dirents(folder):
    """Parses the metadata files within the given folder into a list of dirents."""
    dirents = list()
    for f in os.listdir(folder):
        if not f.endswith('.metadata'):
            continue
        dirent = dirent_from_metadata(os.path.join(folder, f))
        dirents.append(dirent)
    return dirents


def build_rm_filesystem(folder: str) -> Tuple[RCollection, RCollection, Dict[str, RDirEntry]]:
    """Builds a filesystem representation from the given xochitl backup folder.
    
    :return: root, trash, and a dict{uuid: entry}
    """
    # Collect all file nodes
    dirent_list = _load_dirents(folder)

    # rM v5 has two base parents: None (root) or 'trash' (for deleted files)
    dirent_dict = dict()
    root = RCollection('root', '/', version=-1, last_modified=None)
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


#TODO sort collection
#TODO


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('backup_path', type=str, help='Path to local backup copy of xochitl files.')
    args = parser.parse_args()
    root, trash, _ = build_rm_filesystem(args.backup_path)

    print('Root')
    dfs(root)
    print()
    print('Trash')
    dfs(trash)
