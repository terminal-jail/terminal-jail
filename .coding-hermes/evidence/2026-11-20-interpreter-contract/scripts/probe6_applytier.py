import os
import sys

sys.path.insert(0, "/home/kara/terminal-jail/plugin")
os.chdir("/tmp/tj-df-1120/mk")
os.environ["HOME"] = "/tmp/tj-df-1120/home-a"
from terminal_jail.interruptor import landlock  # noqa: E402 - path bootstrapped above

applied, cause = landlock.apply_tier()
print("apply_tier:", applied, "|", cause)
