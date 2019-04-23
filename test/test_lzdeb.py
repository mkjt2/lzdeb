import os
import shutil
import subprocess
import unittest
import uuid

from lzdeb import GitSource


def run_cmd(cmd: str, cwd=None) -> None:
    _ = subprocess.check_call(cmd, shell=True, cwd=cwd)
    return


class TestGitSource(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = '/tmp/' + str(uuid.uuid4())
        self.remote_repo_dir = os.path.join(self.tmp_dir, 'remote_repo')
        os.makedirs(self.remote_repo_dir)
        subprocess.check_call(['git', 'init'], cwd=self.remote_repo_dir)
        dummy_file = os.path.join(self.remote_repo_dir, 'dummy')
        with open(dummy_file, 'w') as f:
            f.write("dummy!")
        subprocess.check_call(['git', 'add', 'dummy'], cwd=self.remote_repo_dir)
        subprocess.check_call(['git', 'commit', '-m', 'add dummy file'], cwd=self.remote_repo_dir)

    def test_end_to_end(self):
        git_source = GitSource.from_data({
            'type': 'git',
            'url': self.remote_repo_dir,
            'ref': 'master',
            'pull_submodules': True
        })
        os.makedirs(self.tmp_dir, exist_ok=True)
        local_repo_dir = git_source.retrieve(run_cmd, work_dir=self.tmp_dir)
        self.assertNotEqual(local_repo_dir, self.remote_repo_dir)
        lines = subprocess.check_output(['git', 'remote', '-v'],
                                        cwd=local_repo_dir).decode().splitlines()
        self.assertTrue(any(self.remote_repo_dir in x for x in lines))

    def tearDown(self):
        shutil.rmtree(self.tmp_dir)


class TestBuilder(unittest.TestCase):
    """ TODO """


if __name__ == '__main__':
    unittest.main()
