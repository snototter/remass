"""Handles connection & device queries."""
import logging
import os
from typing import Callable, Dict, Tuple
import paramiko
import socket
import re
from getpass import getpass
from .filesystem import RCollection, RDirEntry, load_remote_filesystem, render_remote


def format_timedelta(days: int = 0, hours: int = 0, minutes: int = 0,
                     seconds: int = 0):
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


def format_uptime(uptime: str):
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


def ssh_cmd_output(client: paramiko.SSHClient, cmd: str):
    _, out, _ = client.exec_command(cmd)
    return out.read().decode("utf-8").strip()


class RAConnection(object):
    def __init__(self, config):
        self._cfg = config['connection']
        self._client = None
    
    def _connect(self, host):
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

    def open(self):
        if self._client is not None:
            return
        try:
            self._connect(self._cfg['host'])
        except socket.timeout as e:
            if self._cfg['host_fallback'] is not None:
                self._connect(self._cfg['host_fallback'])
            else:
                raise e
    
    def close(self):
        if self._client is not None:
            self._client.close()
    
    def get_tablet_model(self):
        return ssh_cmd_output(self._client, "cat /sys/devices/soc0/machine")
    
    def get_firmware_version(self):
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

    def get_free_space(self, mount_point: str = '/'):
        return ssh_cmd_output(self._client, "df -h " + mount_point + " | tail -n1 | awk '{print $4 \" / \" $2}'")
    
    def get_uptime(self):
        return format_uptime(ssh_cmd_output(self._client, 'uptime'))

    def get_battery_info(self):
        capacity = int(ssh_cmd_output(self._client, "cat /sys/class/power_supply/*_battery/capacity"))
        health = ssh_cmd_output(self._client, "cat /sys/class/power_supply/*_battery/health")
        temp = int(ssh_cmd_output(self._client, "cat /sys/class/power_supply/*_battery/temp"))/10
        return (f'{capacity:d}%', health, f'{temp:.1f}°C')

    def get_filesystem(self) -> Tuple[RCollection, RCollection, Dict[str, RDirEntry]]:
        return load_remote_filesystem(self._client)
    
    def render_document(self, uuid: str, output_filename: str,
                        progress_cb: Callable[[float], None], **kwargs):
        """kwargs will be passed to rmrl.render()"""
        render_remote(self._client, uuid, output_filename, progress_cb, **kwargs)

    def is_connected(self):
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

    def _check_key(self):
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
