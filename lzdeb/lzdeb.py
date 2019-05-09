import argparse
import logging
import os
import re
import shutil
import sys
import tarfile
import time
import uuid
from abc import ABC, abstractmethod
from shlex import quote as q
from typing import Callable, List, Optional

import docker  # type: ignore
import yaml

from lzdeb.utils import container_exec, get, program_available


class Source(ABC):
    """Generic type to represent source for source code (E.g. GitSource)"""

    @staticmethod
    @abstractmethod
    def from_data(data: dict) -> 'Source':
        """Construct a source from config data"""

    @abstractmethod
    def retrieve(self, run_cmd: Callable, work_dir: str = '') -> str:
        """retrieve the source code in ready to use form into a subdirectory within work_dir"""


class SourceFactory:
    """Create Source objects"""

    @staticmethod
    def create_source(data: dict) -> Source:
        """Construct a source from config data"""
        source_type = get(data, 'type', required=True)
        if source_type == 'git':
            return GitSource.from_data(data)
        raise ValueError("unsupported source type %s" % source_type)


class GitSource(Source):
    """Pull source code from a git repo."""

    def __init__(self, url: str, ref: str, pull_submodules: bool = False):
        self.url = url
        self.ref = ref
        self.pull_submodules = pull_submodules

    @staticmethod
    def from_data(data: dict) -> 'GitSource':
        assert get(data, 'type', required=True) == 'git'
        return GitSource(url=get(data, 'url', required=True),
                         ref=get(data, 'ref', required=True),
                         pull_submodules=get(data, 'pull_submodules', default=False))

    def retrieve(self, run_cmd: Callable, work_dir: str = '') -> str:
        """Pull a git repo to a local repo dir, return path to the local repo dir"""
        local_repo_dir = os.path.join(work_dir, os.path.basename(self.url))
        if os.path.exists(local_repo_dir):
            local_repo_dir += "_1"

        logging.info("Performing git operations now...")
        run_cmd('git clone %s %s' % (self.url, local_repo_dir), cwd=work_dir)
        run_cmd('git checkout %s' % self.ref, cwd=local_repo_dir)
        if self.pull_submodules:
            run_cmd('git submodule init', cwd=local_repo_dir)
            run_cmd('git submodule update', cwd=local_repo_dir)
        return local_repo_dir


class CommandError(Exception):
    def __init__(self, rc: int, msg: str = ''):
        self.rc = rc
        self.msg = msg


class DockerContainer:
    """Wrapper around a docker container p"""

    def __init__(self, image: str = '', bootstrap_cmds: List[str] = []):
        if not program_available('docker'):
            raise EnvironmentError("docker CLI not found.")
        self.bootstrap_cmds = bootstrap_cmds
        self.image = image
        self.docker_client = docker.from_env()
        self.container = None

    def bootstrap_container(self) -> None:
        """Run bootstrap commands"""
        if not self.bootstrap_cmds:
            return
        logging.info("Running %d bootstrapping commands...", len(self.bootstrap_cmds))
        for c in self.bootstrap_cmds:
            self.run_cmd(c)

    def program_available(self, program) -> bool:
        try:
            self.run_cmd('which %s' % program)
            logging.info("Program '%s' is available.", program)
            return True
        except CommandError as ce:
            if ce.rc != 1:
                msg = "Unexpected return code (%d) when checking for program (%s) presence"
                raise RuntimeError(msg % (ce.rc, program))
            logging.warning("Program '%s' is missing.", program)
            return False

    def start(self, label: str = '') -> None:
        if self.container is not None:
            logging.warning("Cannot start container again - already started!")
            return
        name = None
        if label:
            name = '%s_%d' % (label, int(time.time()))
        logging.info("Starting docker container (%s)", name)
        self.container = self.docker_client.containers.run(
            image=self.image,
            name=name,
            command=['sleep', '100000'],  # TODO hack! can we do better?
            detach=True,
            auto_remove=True)
        logging.info("Started %s", str(self.container))

    def stop(self) -> None:
        """Stop the container"""
        if self.container is None:
            logging.warning("Container never started... nothing to stop")
            return
        logging.debug("Stopping container %s", self.container)
        self.container.stop()

    @staticmethod
    def from_data(data: dict) -> 'DockerContainer':
        if data is None:
            return None
        return DockerContainer(image=get(data, 'image', required=True),
                               bootstrap_cmds=get(data, 'bootstrap_cmds', default=[]))

    def run_cmd(self, cmd: str, cwd: str = None, return_output=False) -> Optional[str]:
        """Run a command inside the container (docker exec)"""
        logging.info(cmd)
        # TODO circleci docker cannot set exec_run(workdir)
        exec_cmd = ['/bin/bash', '-c']
        if cwd:
            exec_cmd.append(('cd %s && ' % cwd) + cmd)
        else:
            exec_cmd.append(cmd)

        exec_result = container_exec(container=self.container, cmd=exec_cmd, stream=True)
        res, output_str = exec_result.communicate(return_output=return_output)
        if res != 0:
            raise CommandError(rc=res, msg="Bad return code!")
        if return_output:
            return output_str
        return None

    def import_file(self, src_path: str, dest_path: str) -> None:
        """cp a file into the container"""
        if self.container is None:
            raise RuntimeError("Container not started - cannot import file into it")
        src_path_tar = '/tmp/' + str(uuid.uuid4())
        try:
            with tarfile.open(name=src_path_tar, mode='w') as tf:
                tf.add(src_path, arcname=dest_path)
            with open(src_path_tar, mode='rb') as f:
                self.container.put_archive(path='/', data=f.read())
        finally:
            if os.path.exists(src_path_tar):
                os.remove(src_path_tar)

    def list_files(self, pattern: str) -> List[str]:
        output = self.run_cmd('ls -1 ' + pattern, return_output=True)
        if output is not None:
            return output.splitlines()
        raise RuntimeError("output is always a string")

    def export_file(self, src_path, dest_dir) -> str:
        """cp a file out of the container"""
        if self.container is None:
            raise RuntimeError("Container not started - cannot export file from it")
        os.makedirs(dest_dir, exist_ok=True)
        data_chunks, st_info = self.container.get_archive(src_path)
        try:
            collected_archive = os.path.join(dest_dir, 'collected.tar')
            with open(collected_archive, mode='wb') as f:
                for chunk in data_chunks:
                    f.write(chunk)
            with tarfile.open(collected_archive, mode='r') as tf:
                tf.extractall(path=dest_dir)
            return os.path.join(dest_dir, os.path.basename(src_path))
        finally:
            if os.path.exists(collected_archive):
                os.remove(collected_archive)


class DebInfo:
    def __init__(self,
                 pkgname: str = '',
                 pkgversion: str = '',
                 pkgrelease: str = '',
                 pkglicense: str = '',
                 pkggroup: str = '',
                 maintainer: str = '',
                 description: str = '',
                 requires: List[str] = []):
        self.pkgname = pkgname
        self.pkgversion = str(pkgversion)
        self.pkgrelease = str(pkgrelease)
        self.pkglicense = pkglicense
        self.pkggroup = pkggroup
        self.maintainer = maintainer
        self.description = description
        self.requires = requires
        self.tmp_pak_dir = os.path.join('/tmp/' + str(uuid.uuid4()))

    @staticmethod
    def from_data(data: dict) -> 'DebInfo':
        return DebInfo(
            pkgname=get(data, 'pkgname', required=True),
            pkgversion=get(data, 'pkgversion', required=True),
            pkgrelease=get(data, 'pkgrelease', required=True),
            pkglicense=get(data, 'pkglicense', required=True),
            pkggroup=get(data, 'pkggroup', required=True),
            maintainer=get(data, 'maintainer', required=True),
            description=get(data, 'description', required=True),
            requires=get(data, 'requires', required=False),
        )

    def prepare(self, builder: DockerContainer, work_dir: str):
        src_descript_pak_file = os.path.join(self.tmp_pak_dir, 'description-pak')
        os.makedirs(self.tmp_pak_dir)
        dest_descript_pak_file = os.path.join(work_dir, 'description-pak')
        with open(src_descript_pak_file, mode='w') as f:
            f.write(self.description)
        builder.import_file(src_descript_pak_file, dest_descript_pak_file)

    def cleanup(self):
        if os.path.exists(self.tmp_pak_dir):
            shutil.rmtree(self.tmp_pak_dir)

    def _get_checkinstall_requires_opt(self) -> str:
        parts = []
        for r in self.requires:
            m = re.search(r'^([^><=]+)(([><]?=)([^><=]+))$', r)
            if not m:
                raise ValueError("requirement %s is bad." % r)
            pkg_name, vers_constraint, pkg_version = m.group(1), m.group(3), m.group(4)
            final_fmt = '%s (%s%s)' % (pkg_name, vers_constraint, pkg_version)
            parts.append(final_fmt)
        opt_str = '--requires=' + (','.join(parts))
        for c in ['(', ')', '>', '<']:
            opt_str = opt_str.replace(c, '\\' + c)
        return opt_str

    def debianize_cmd(self, cmd: str) -> str:
        checkinstall_cmd = "checkinstall -D -y --install=no --backup=no --fstrans=no"
        checkinstall_cmd += ' ' + q("--maintainer=" + self.maintainer)
        checkinstall_cmd += ' ' + q("--pkgname=" + self.pkgname)
        checkinstall_cmd += ' ' + q("--pkgrelease=" + self.pkgrelease)
        checkinstall_cmd += ' ' + q("--pkggroup=" + self.pkggroup)
        checkinstall_cmd += ' ' + q("--pakdir=" + self.tmp_pak_dir)
        checkinstall_cmd += ' ' + q("--pkgversion=" + self.pkgversion)
        checkinstall_cmd += ' ' + q("--pkglicense=" + self.pkglicense)
        if self.requires:
            checkinstall_cmd += " " + q(self._get_checkinstall_requires_opt())
        checkinstall_cmd += " " + cmd
        return checkinstall_cmd


class LzDeb:
    """Manages the full lzdeb building process."""

    def __init__(self,
                 config_dir: str,
                 builder: DockerContainer,
                 validator: DockerContainer,
                 source: Source,
                 deb_info: DebInfo,
                 collect_path: str = '',
                 artifact_type: str = ''):
        self.config_dir = config_dir
        self.builder = builder
        self.validator = validator
        self.source = source
        self.deb_info = deb_info
        self.collect_path = collect_path
        self.artifact_type = artifact_type
        self.work_dir = '/var/tmp/' + str(uuid.uuid4())
        self._deb_file = None

    @property
    def build_script(self) -> str:
        """Location of the build script for this package."""
        return os.path.join(self.config_dir, 'build')

    @property
    def install_script(self) -> str:
        """Location of the install script for this package"""
        return os.path.join(self.config_dir, 'install')

    @property
    def validate_script(self) -> str:
        """Location of the validate script for this package"""
        return os.path.join(self.config_dir, 'validate')

    @staticmethod
    def from_data(config_dir: str, data: dict) -> 'LzDeb':
        """Create a LzDeb object based on a config directory and yaml config dict."""
        return LzDeb(config_dir=config_dir,
                     builder=DockerContainer.from_data(get(data, 'builder', required=True)),
                     validator=DockerContainer.from_data(get(data, 'validator')),
                     source=SourceFactory.create_source(get(data, 'source', required=True)),
                     deb_info=DebInfo.from_data(get(data, 'deb_info')))

    @staticmethod
    def from_config_dir(config_dir: str) -> 'LzDeb':
        """Create a LzDeb object based the lzdeb's config directory.
           The directory should contain:
           - ./install
           - ./build (optional)
           - ./config.yml
        """
        yaml_path = os.path.join(config_dir, 'lzdeb.yml')
        with open(yaml_path) as f:
            data = yaml.safe_load(f)
            return LzDeb.from_data(config_dir, data)

    def inject_file(self, container: DockerContainer, file_path: str) -> str:
        """Copy the build script into the DockerContainer container."""
        dest_path = os.path.join(self.work_dir, os.path.basename(file_path))
        container.import_file(src_path=file_path, dest_path=dest_path)
        return dest_path

    def build(self) -> str:
        """Build the debian package!
           - retrieve the source code
           - run the build script on it
           - collect the .deb file
        """
        try:
            self.builder.start('lzdeb_build')
            self.builder.bootstrap_container()
            for p in ['apt', 'apt-get', 'git']:
                if not self.builder.program_available(p):
                    raise EnvironmentError("Program '%s' must be available!" % p)
            run_cmd = self.builder.run_cmd

            run_cmd('mkdir -p ' + self.work_dir)
            local_repo_dir = self.source.retrieve(run_cmd=run_cmd, work_dir=self.work_dir)
            logging.info("Got the source at %s" % local_repo_dir)
            run_cmd(self.inject_file(container=self.builder, file_path=self.build_script),
                    cwd=self.work_dir)
            logging.info("Finished running build script")

            try:
                self.deb_info.prepare(builder=self.builder, work_dir=self.work_dir)
                # TODO let's do better than this
                run_cmd('apt update && apt-get install -y checkinstall')
                debianized_cmd = self.deb_info.debianize_cmd(
                    cmd=self.inject_file(container=self.builder, file_path=self.install_script))
                run_cmd(cmd=debianized_cmd, cwd=self.work_dir)

                deb_files = self.builder.list_files(
                    pattern=os.path.join(self.deb_info.tmp_pak_dir, '*.deb'))
                assert len(deb_files) == 1, "Expected exactly %d deb files, saw %s" + str(deb_files)
                deb_file = deb_files[0]
                run_cmd("ls -l " + deb_file)
                return self.builder.export_file(deb_file, os.getcwd())
            finally:
                self.deb_info.cleanup()

            logging.info("Finished running install script")
        finally:
            self.builder.stop()

    def validate(self, deb_file: str) -> None:
        if not os.path.exists(self.validate_script):
            return
        try:
            logging.info("Validating deb file %s", deb_file)
            self.validator.start('lzdeb_validate')
            self.validator.bootstrap_container()
            run_cmd = self.validator.run_cmd
            run_cmd('mkdir -p ' + self.work_dir)
            validate_script = self.inject_file(container=self.validator,
                                               file_path=self.validate_script)
            self.inject_file(container=self.validator, file_path=deb_file)
            run_cmd(cmd=validate_script, cwd=self.work_dir)
        finally:
            self.validator.stop()


def handle_build(args) -> int:
    """lzdeb build"""
    handle_common(args)
    r = LzDeb.from_config_dir(args.config_dir)
    deb_file = r.build()
    r.validate(deb_file)
    return 0


def handle_common(args) -> None:
    """logic common to all sub-commands.  E.g. logger setup"""
    logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s',
                        stream=sys.stdout,
                        level=logging.INFO)


def main() -> int:
    parser = argparse.ArgumentParser(description="lzdeb - build debian packages the lazy way.")
    subparsers = parser.add_subparsers(title="subcommand")
    build_parser = subparsers.add_parser('build')
    build_parser.add_argument('config_dir', help="lzdeb build config dir")
    build_parser.set_defaults(func=handle_build)

    args = parser.parse_args()
    try:
        return args.func(args)
    except KeyboardInterrupt:
        return 1
