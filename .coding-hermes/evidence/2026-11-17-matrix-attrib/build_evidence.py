import gzip
import os
import re
import shutil
from pathlib import Path

BASE = Path("/home/kara/.hermes/cache/scratch/tj-1117f")
DEST = Path("/home/kara/terminal-jail/.coding-hermes/evidence/2026-11-17-matrix-attrib")
DEST.mkdir(parents=True, exist_ok=True)

arms = []
for ver in ("3.11", "3.12", "3.13"):
    for arm in ("A", "B"):
        path = BASE / f"arm{arm}-{ver}.log"
        if not path.exists():
            arms.append((ver, arm, None))
            continue
        text = path.read_text(errors="replace")
        summary = [
            ln for ln in text.splitlines() if re.match(r"^=+ \d+ (failed|passed)", ln)
        ]
        failed = [ln for ln in text.splitlines() if ln.startswith("FAILED")]
        arms.append(
            (
                ver,
                arm,
                {
                    "path": path,
                    "summary": summary[-1] if summary else "NO SUMMARY",
                    "failed": failed,
                    "bytes": len(text),
                },
            )
        )

lines = []
lines.append(
    'arm table — exact CI step command (pytest plugin/ tests/ -v --tb=short -m "not integration"),'
)
lines.append(
    "run from the git-archive tree of origin/main f00967d; only `unzip` visibility differs between arms."
)
lines.append("")
lines.append(f"{'ver':5s} {'arm':4s} {'unzip':6s} {'summary'}")
for ver, arm, info in arms:
    if info is None:
        lines.append(f"{ver:5s} {arm:4s} {'-':6s} MISSING LOG")
        continue
    lines.append(
        f"{ver:5s} {arm:4s} {'no' if arm == 'A' else 'yes':6s} {info['summary']}"
    )
lines.append("")
for ver, arm, info in arms:
    if info is None:
        continue
    lines.append(f"--- arm{arm} {ver} FAILED lines ({len(info['failed'])}) ---")
    for failed_line in info["failed"]:
        lines.append("  " + failed_line)
lines.append("")
sets = {}
for ver, arm, info in arms:
    if info:
        sets[(ver, arm)] = set(info["failed"])
for ver in ("3.11", "3.12", "3.13"):
    a_set, b_set = sets.get((ver, "A")), sets.get((ver, "B"))
    if a_set is None or b_set is None:
        continue
    lines.append(
        f"--- DELTA {ver}: A minus B = {sorted(a_set - b_set)} | B minus A = {sorted(b_set - a_set)}"
    )

cpath = BASE / "armC-clone-green.log"
if cpath.exists():
    ctext = cpath.read_text(errors="replace")
    csum = [
        ln for ln in ctext.splitlines() if re.match(r"^=* ?\d+ (failed|passed)", ln)
    ]
    cfailed = [ln for ln in ctext.splitlines() if ln.startswith("FAILED")]
    lines.append("")
    lines.append("--- armC (REAL git clone at f00967d, unzip present) ---")
    lines.append("summary: " + (csum[-1] if csum else "NO SUMMARY"))
    lines.append(f"failed lines: {len(cfailed)}")
    with gzip.open(DEST / "armC-clone-green.log.gz", "wb", compresslevel=9) as gz_out:
        gz_out.write(ctext.encode())
    print("wrote armC gz")

text = (BASE / "armA-3.11.log").read_text(errors="replace")
idx = text.find("test_release_wheel_install_without_unzip_uses_python_zipfile")
seg = text[idx : idx + 4000] if idx != -1 else ""
lines.append("")
lines.append("--- unzip-test traceback excerpt (armA-3.11) ---")
lines.append(seg)

out = "\n".join(lines) + "\n"
(DEST / "arm-summary.txt").write_text(out)
print("... summary bytes:", len(out))

for ver, arm, info in arms:
    if info is None:
        continue
    dst = DEST / f"arm{arm}-{ver}.log.gz"
    with (
        open(info["path"], "rb") as src_fh,
        gzip.open(dst, "wb", compresslevel=9) as dst_fh,
    ):
        shutil.copyfileobj(src_fh, dst_fh)
    print("wrote", dst, os.path.getsize(dst), "bytes  (from", info["bytes"], "bytes)")
