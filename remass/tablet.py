"""Handles connection & device queries."""
import logging
import os
import paramiko
from getpass import getpass


class RAConnection(object):
    def __init__(self, config):
        self._cfg = config['connection']
        self._client = None
    
    def open(self):
        self._client = paramiko.SSHClient()
        self._client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        pkey = self._check_key()
        password = None if pkey is not None else self._cfg['password']
        user = self._cfg['user']

        self._client.connect(self._cfg['host'], username=user,
                            password=password, pkey=pkey,
                            timeout=self._cfg['timeout'],
                            port=self._cfg['port'],
                            look_for_keys=False)
        logging.getLogger(__name__).info(f'Connected to {self.get_tablet_version()}')
    
    def close(self):
        if self._client is not None:
            self._client.close()
    
    def get_tablet_version(self):
        _, out, _ = self._client.exec_command("cat /sys/devices/soc0/machine")
        return out.read().decode("utf-8").strip()

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
