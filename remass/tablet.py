"""Handles connection & device queries."""
import logging
import os
import paramiko
import socket
from getpass import getpass


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
        _, out, _ = self._client.exec_command("cat /sys/devices/soc0/machine")
        return out.read().decode("utf-8").strip()
    
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
        _, out, _ = self._client.exec_command("cat /etc/version")
        vstr = out.read().decode("utf-8").strip()
        return version_map.get(vstr, vstr)

    def get_free_space(self, mount_point: str = '/'):
        _, out, _ = self._client.exec_command("df -h " + mount_point + " | tail -n1 | awk '{print $4 \" / \" $2}'")
        return out.read().decode("utf-8").strip()
    
    def is_connected(self):
        # Returns True if the client is still connected and the session is
        # still active (see comment to https://stackoverflow.com/a/33383984)
        if self._client is not None:
            try:
                transport = self._client.get_transport()
                if transport.is_active():
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
