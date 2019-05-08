import distutils.spawn
import sys
from typing import Any, List, Tuple


def program_available(name: str) -> bool:
    """Is this program available on the system?"""
    return distutils.spawn.find_executable(name) is not None


def get(data: dict, key: str, default: Any = None, required: bool = False) -> Any:
    """Nicer dictionary lookups"""
    if key in data:
        return data[key]
    if not required:
        return default
    raise KeyError("The key '%s' is required in dictionary %s" % (key, str(data)))


class ContainerExec:

    def __init__(self, client, id: int, output):
        self.client = client
        self.id = id
        self.output = output

    def inspect(self) -> dict:
        return self.client.api.exec_inspect(self.id)

    def poll(self) -> int:
        return self.inspect()['ExitCode']

    def communicate(self, return_output: bool = False) -> Tuple[int, str]:
        output_parts = []
        for o in self.output:
            o = o.decode()
            if return_output:
                output_parts.append(o)
            else:
                sys.stdout.write(o)
        while self.poll() is None:
            raise RuntimeError('Hm could that really happen?')
        if return_output:
            return self.poll(), ''.join(output_parts)
        else:
            return self.poll(), ''


def container_exec(container,
                   cmd: List[str],
                   stdout: bool = True,
                   stderr: bool = True,
                   stdin: bool = False,
                   tty: bool = False,
                   privileged: bool = False,
                   user: str = '',
                   detach: bool = False,
                   stream: bool = False,
                   socket: bool = False,
                   environment: bool = None,
                   workdir: str = None) -> ContainerExec:
    """
    An enhanced version of #docker.Container.exec_run() which returns an object
    that can be properly inspected for the status of the executed commands.
    """

    exec_id = container.client.api.exec_create(
        container.id, cmd, stdout=stdout, stderr=stderr, stdin=stdin, tty=tty,
        privileged=privileged, user=user, environment=environment,
        workdir=workdir)['Id']

    output = container.client.api.exec_start(
        exec_id, detach=detach, tty=tty, stream=stream, socket=socket)

    return ContainerExec(container.client, exec_id, output)
