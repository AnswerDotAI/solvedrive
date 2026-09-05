import subprocess, sys


def test_skill_import(): subprocess.run([sys.executable, '-c', 'from solvedrive.skill import *'], check=True)

