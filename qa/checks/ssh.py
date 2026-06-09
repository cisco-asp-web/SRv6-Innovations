"""Shared SSH session used by every layer module."""

from typing import Optional, Tuple
import paramiko


class SSHSession:
    """
    SSH client with optional jump-host forwarding. Use as a context manager.

    Both the main client and the proxy (jump host) are stored as instance
    attributes so the proxy is never garbage-collected while the forwarded
    channel is still in use.
    """

    def __init__(self) -> None:
        self._main: Optional[paramiko.SSHClient] = None
        self._proxy: Optional[paramiko.SSHClient] = None

    def connect(
        self,
        host: str,
        user: str,
        password: str,
        jump_host: Optional[str] = None,
        jump_user: Optional[str] = None,
        jump_password: Optional[str] = None,
        timeout: int = 15,
    ) -> None:
        if jump_host:
            self._proxy = paramiko.SSHClient()
            self._proxy.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self._proxy.connect(
                jump_host, username=jump_user, password=jump_password, timeout=timeout
            )
            sock = self._proxy.get_transport().open_channel(
                "direct-tcpip", (host, 22), ("127.0.0.1", 0)
            )
        else:
            sock = None

        self._main = paramiko.SSHClient()
        self._main.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self._main.connect(
            host, username=user, password=password, sock=sock, timeout=timeout
        )

    def run(self, command: str, timeout: int = 30) -> Tuple[str, str, int]:
        """Execute a command; return (stdout, stderr, exit_code)."""
        stdin, stdout, stderr = self._main.exec_command(command, timeout=timeout)
        out = stdout.read().decode().strip()
        err = stderr.read().decode().strip()
        code = stdout.channel.recv_exit_status()
        return out, err, code

    def sudo_run(self, command: str, password: str, timeout: int = 30) -> Tuple[str, str, int]:
        """Execute a command with sudo, providing password via stdin."""
        stdin, stdout, stderr = self._main.exec_command(
            f"sudo -S {command}", timeout=timeout
        )
        stdin.write(password + "\n")
        stdin.flush()
        out = stdout.read().decode().strip()
        stderr.read()  # drain to prevent buffer deadlock; sudo prompt goes here
        code = stdout.channel.recv_exit_status()
        return out, "", code

    def close(self) -> None:
        if self._main:
            self._main.close()
            self._main = None
        if self._proxy:
            self._proxy.close()
            self._proxy = None

    def __enter__(self) -> "SSHSession":
        return self

    def __exit__(self, *_) -> None:
        self.close()
