#!/usr/bin/env python3
"""Create the source-side baseline for the Linux Server Migration dashboard."""
import grp, hashlib, json, os, pwd, socket, stat, subprocess
from datetime import datetime

ROOT = "/srv/company"
USERS = ["devuser", "financeuser"]
GROUPS = ["developers", "finance"]

def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()

def count(cmd, marker=None):
    p = subprocess.run(cmd, capture_output=True, text=True)
    lines = p.stdout.splitlines()
    if marker:
        return sum(1 for line in lines if line.startswith(marker))
    return sum(1 for line in lines if line and not line.startswith("#"))

entries = []
paths = ["."]
for dp, dirs, files in os.walk(ROOT):
    paths.extend(os.path.relpath(os.path.join(dp, n), ROOT) for n in dirs + files)
for rel in sorted(set(paths)):
    full = os.path.join(ROOT, rel)
    st = os.lstat(full)
    item = {"path": rel, "type": "dir" if stat.S_ISDIR(st.st_mode) else "file",
            "uid": st.st_uid, "gid": st.st_gid,
            "mode": format(stat.S_IMODE(st.st_mode), "o")}
    if item["type"] == "file":
        item["size"] = st.st_size
        item["sha256"] = sha256(full)
    entries.append(item)

baseline = {
    "generated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "host": socket.gethostname(),
    "data_root": ROOT,
    "identities": {
        "users": {u: {"uid": pwd.getpwnam(u).pw_uid, "gid": pwd.getpwnam(u).pw_gid} for u in USERS},
        "groups": {g: grp.getgrnam(g).gr_gid for g in GROUPS},
    },
    "entries": entries,
    "acl_entries": count(["getfacl", "-R", "-s", "-p", ROOT]),
    "xattr_entries": count(["getfattr", "-R", "-d", "-m", "-", ROOT], "# file"),
}
print(json.dumps(baseline, indent=2))
