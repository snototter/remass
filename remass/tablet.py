"""Handles connection & device queries."""
import logging
import os
from typing import Callable, Dict, Tuple
import paramiko
import socket
import re
from getpass import getpass
from .filesystem import RCollection, RDirEntry, RDocument, load_remote_filesystem, render_remote


class NotEnoughDiskSpaceError(Exception):
    pass


def format_timedelta(days: int = 0, hours: int = 0, minutes: int = 0,
                     seconds: int = 0) -> str:
    """Returns a simplified string representation of the given timedelta."""
    s = '' if days == 0 else f'{days:d}d'
    if hours > 0:
        if len(s) > 0:
            s += ' '
        s += f'{hours:d}h'
    if minutes > 0:
        if len(s) > 0:
            s += ' '
        s += f'{minutes:d}min'
    if seconds > 0 or len(s) == 0:
        if len(s) > 0:
            s += ' '
        s += f'{seconds:d}sec'
    return s


def format_uptime(uptime: str) -> str:
    """Returns a simplified string representation of the `uptime` output."""
    match = re.search(r"up\s+(\d*.*),\s*load.*$", uptime)
    if match is None:
        logging.getLogger(__name__).warning(f'Invalid uptime string "{uptime}"')
        return '-Invalid uptime-'
    tstr = match.group(1)
    tokens = tstr.split(',')
    days, hours, mins, secs = 0, 0, 0, 0
    for t in tokens:
        if ':' in t:
            # Should be the hours:mins token
            subtokens = t.strip().split(':')
            hours += int(subtokens[0])
            mins += int(subtokens[1])
        else:
            # Should be either mins or days
            subtokens = t.strip().split(' ')
            val = int(subtokens[0])
            if 'day' in subtokens[1]:
                days += val
            elif 'min' in subtokens[1]:
                mins += val
            elif 'sec' in subtokens[1]:
                secs += val
    return format_timedelta(days=days, hours=hours, minutes=mins, seconds=secs)


### The SSH client does not run the shell in login mode - /sbin/ifconfig then only
### returns the loopback and usb interfaces (thus, there's no use in querying
### the device IPs)
# def parse_addresses(output: str):
#     matches = re.findall(r"inet addr:(\d+\.\d+\.\d+\.\d)\s+", output)
#     if matches is None or len(matches) == 0:
#         logging.getLogger(__name__).warning(f'Invalid ifconfig output "{output}"')
#         return '-Invalid address-'
#     # return [m for m in matches if m != '127.0.0.1']
#     return matches


def ssh_cmd_output(client: paramiko.SSHClient, cmd: str) -> str:
    _, out, _ = client.exec_command(cmd)
    return out.read().decode("utf-8").strip()


class RAConnection(object):
    def __init__(self, config):
        self._cfg = config['connection']
        self._client = None
    
    def _connect(self, host) -> None:
        self._client = paramiko.SSHClient()
        self._client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        pkey = self._check_key()
        password = None if pkey is not None else self._cfg['password']
        user = self._cfg['user']
        self._client.connect(host, username=user,
                            password=password, pkey=pkey,
                            timeout=self._cfg['timeout'],
                            port=self._cfg['port'],
                            look_for_keys=False)
        logging.getLogger(__name__).info(f'Connected to {self.get_tablet_model()}')

    def open(self) -> None:
        if self._client is not None:
            return
        try:
            self._connect(self._cfg['host'])
        except socket.timeout as e:
            if self._cfg['host_fallback'] is not None:
                self._connect(self._cfg['host_fallback'])
            else:
                raise e
    
    def close(self) -> None:
        if self._client is not None:
            self._client.close()
    
    def get_tablet_model(self) -> str:
        return ssh_cmd_output(self._client, "cat /sys/devices/soc0/machine")
    
    def get_firmware_version(self) -> str:
        version_map = {
            "20211014151303": "rM2 v2.10.2.356",
            "20211014150444": "rM1 v2.10.2.356",
            "20210929140057": "rM2 v2.10.1.332",
            "20210923144714": "rM2 v2.10.0.324",
            "20210923152158": "rM1 v2.10.0.324",
            "20210812195523": "rM2 v2.9.1.217",
            "20210820111232": "rM1 v2.9.1.236",
            "20210611153600": "rM2 v2.8.0.98",
            "20210611154039": "rM1 v2.8.0.98",
            "20210511153632": "rM2 v2.7.1.53",
            "20210504114631": "rM2 v2.7.0.51",
            "20210504114855": "rM1 v2.7.0.51",
            "20210322075357": "rM2 v2.6.2.75",
            "20210322075617": "rM1 v2.6.2.75",
            "20210311194323": "rM2 v2.6.1.71",
            "20210311193614": "rM1 v2.6.1.71"
        }
        vstr = ssh_cmd_output(self._client, "cat /etc/version")
        return version_map.get(vstr, vstr)

    def get_hostname(self) -> str:
        return ssh_cmd_output(self._client, "cat /etc/hostname")

    def get_free_space_str(self, location: str = '/') -> str:
        return ssh_cmd_output(self._client, 'df -h ' + f'"{location}"' + " | tail -n1 | awk '{print $4 \" / \" $2}'")

    def get_free_space_kb(self, location: str) -> int:
        try:
            # Use dirname on the remote (because the target file location may
            # not exist, which would cause df to not find the corresponding
            # mounting point)
            return int(ssh_cmd_output(self._client, f"df $(dirname \"{location}\") | tail -n1 | awk '{{print $4}}'"))
        except ValueError:
            raise NotEnoughDiskSpaceError(f'Cannot determine free space for location "{location}"')

    def get_uptime(self) -> str:
        return format_uptime(ssh_cmd_output(self._client, 'uptime'))

    def get_battery_info(self) -> Tuple[str, str, str]:
        capacity = int(ssh_cmd_output(self._client, "cat /sys/class/power_supply/*_battery/capacity"))
        health = ssh_cmd_output(self._client, "cat /sys/class/power_supply/*_battery/health")
        temp = int(ssh_cmd_output(self._client, "cat /sys/class/power_supply/*_battery/temp"))/10
        return (f'{capacity:d}%', health, f'{temp:.1f}°C')

    def get_filesystem(self) -> Tuple[RCollection, RCollection, Dict[str, RDirEntry]]:
        return load_remote_filesystem(self._client)

    def render_document_by_uuid(self, uuid: str, output_filename: str,
                        progress_cb: Callable[[float], None], **kwargs) -> None:
        _, _, dirents = load_remote_filesystem(self._client)
        self.render_document(dirents[uuid], output_filename, progress_cb, **kwargs)

    def render_document(self, rm_file: RDocument, output_filename: str,
                        progress_cb: Callable[[float], None], **kwargs) -> None:
        """kwargs will be passed to rmrl.render()"""
        render_remote(self._client, rm_file, output_filename, progress_cb, **kwargs)

    def download_file(self, remote_filename: str, local_filename: str):
        sftp = self._client.open_sftp()
        sftp.get(remote_filename, local_filename)
        sftp.close()

    def upload_file(self, local_filename: str, remote_filename: str):
        """We allow uploading only if there are is at least 1MB free space available."""
        min_free_space = 1024  # Size in KB
        # First, check available space (as rM's root partition is quite limited)
        upload_bytes = os.path.getsize(local_filename)
        free_space = self.get_free_space_kb(remote_filename)
        if upload_bytes + min_free_space >= free_space:
            raise NotEnoughDiskSpaceError(f'Upload of "{local_filename}" ({upload_bytes} KB) '
                                          f'to "{remote_filename}" '
                                          f'would lead to less than {min_free_space} KB on '
                                          f'partition (free: {free_space} KB).')
        # Now it's safe to upload the file
        sftp = self._client.open_sftp()
        sftp.put(local_filename, remote_filename)
        sftp.close()

    def is_connected(self) -> bool:
        # Returns True if the client is still connected and the session is
        # still active (see comment to https://stackoverflow.com/a/33383984)
        if self._client is not None:
            try:
                transport = self._client.get_transport()
                if transport is not None and transport.is_active():
                    transport.send_ignore()
                    return True
            except EOFError:
                # connection is closed
                pass
        return False

    def _check_key(self) -> paramiko.RSAKey:
        if self._cfg['keyfile'] is None:
            return None
        try:
            pkey = paramiko.RSAKey.from_private_key_file(os.path.expanduser(self._cfg['keyfile']),
                                                         password=self._cfg['password'])
        except paramiko.ssh_exception.PasswordRequiredException:
            passphrase = getpass(f"Enter passphrase for private key \"{self._cfg['keyfile']}\": ")
            pkey = paramiko.RSAKey.from_private_key_file(os.path.expanduser(self._cfg['keyfile']),
                                                         password=passphrase)
        return pkey
