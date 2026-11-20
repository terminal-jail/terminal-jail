import os
import sys

sys.path.insert(0, "/home/kara/terminal-jail/plugin")

from terminal_jail.interruptor import (  # noqa: E402 - path bootstrapped above
    interruptor_bridge,
    landlock,
)

HOME = "/tmp/tj-df-1120/home-a"
WD = "/tmp/tj-df-1120/mk"
HOSTILE = HOME + "/.hermes/bin/python3-real"
LIB = HOME + "/.local/lib/terminal-jail/landlock-loader.py"

shapes = {
    "proof_argv": ("bash", "-c", "script", "terminal-jail", "python3"),
    "launch_tail_argv": ("bash", "-c", f"python3 {LIB} -- make ok"),
}
for name, argv in shapes.items():
    layout = landlock.build_layout(workdir=WD, home=HOME, payload_argv=argv)
    roots = (
        list(layout.write_roots) + list(layout.read_roots) + list(layout.read_dir_roots)
    )
    covered = [
        r
        for r in roots
        if landlock._is_inside(os.path.realpath(HOSTILE), os.path.realpath(r))
        or os.path.realpath(r) in os.path.realpath(HOSTILE)
    ]
    print(f"== {name} ==")
    print("write:", sorted(layout.write_roots))
    print("read:", sorted(layout.read_roots))
    print("read_dir:", sorted(layout.read_dir_roots))
    print("hostile-covered-by:", covered)

# what the bridge actually returns for `make ok`

res = interruptor_bridge.evaluate("make ok")
print("bridge:", res)
mod = res.get("modified", "")
print("modified-head-extract-pattern ' bash -c ' present:", " bash -c " in mod)
print("modified repr:", mod[:200])
