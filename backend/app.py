#!/usr/bin/env python3
"""Read-only Migration Verification Dashboard. Run on destination with sudo."""
import grp, hashlib, json, os, pwd, socket, stat, subprocess, tarfile
from datetime import datetime
from pathlib import Path
from flask import Flask, jsonify, render_template

BASE = Path(__file__).resolve().parent.parent
CFG = {
    "data": "/srv/company", "backup": "/srv/backup",
    "log": "/var/log/company-backup/backup.log",
    "fstab": "/etc/fstab", "script": "/usr/local/sbin/company-backup.sh",
    "baseline": str(BASE / "baseline" / "source_baseline.json"),
    "report": str(BASE / "reports" / "migration_report.txt"),
    "disk": "/dev/sdb", "part": "/dev/sdb1", "vg": "vg_migration",
    "lv_size_gb": {"lv_data": 12.0, "lv_backup": 5.0},
}
app = Flask(__name__)

def run(cmd):
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
        return p.returncode, p.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return 127, ""

def chk(group, name, ok, detail):
    return {"group": group, "name": name, "ok": bool(ok), "detail": str(detail)}

def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()

def baseline():
    with open(CFG["baseline"]) as f:
        return json.load(f)

def human(n):
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if n < 1024 or unit == "TiB":
            return f"{n:.0f} {unit}" if unit in ("B", "KiB") else f"{n:.1f} {unit}"
        n /= 1024

def table(cmd):
    rc, out = run(cmd)
    if rc:
        return []
    return [[x.strip() for x in line.split("|")] for line in out.splitlines() if line.strip()]

def usage(mount):
    rc, out = run(["df", "-P", "-B1", mount])
    cols = out.splitlines()[-1].split() if rc == 0 and out else []
    if len(cols) < 6:
        return {"size": 0, "used": 0, "avail": 0, "pct": 0}
    size, used, avail = map(int, (cols[1], cols[2], cols[3]))
    return {"size": size, "used": used, "avail": avail,
            "pct": round(used * 100 / size, 1) if size else 0}

def storage():
    g, checks = "Storage", []
    _, diskout = run(["lsblk", "-dn", "-o", "SIZE,PTTYPE", CFG["disk"]])
    disk_size, pttype = (diskout.split() + ["?", "?"])[:2]
    _, partout = run(["lsblk", "-n", "-o", "SIZE,PARTTYPENAME", CFG["part"]])
    part_size, part_type = (partout.split(None, 1) + ["?", "?"])[:2]
    pvs = table(["pvs", "--noheadings", "--separator", "|", "--units", "g", "--nosuffix",
                 "-o", "pv_name,vg_name,pv_size,pv_free"])
    vgs = table(["vgs", "--noheadings", "--separator", "|", "--units", "g", "--nosuffix",
                 "-o", "vg_name,vg_size,vg_free,lv_count"])
    lvs = table(["lvs", "--noheadings", "--separator", "|", "--units", "g", "--nosuffix",
                 "-o", "lv_name,vg_name,lv_size,lv_attr"])
    num = lambda s: float(s.replace("<", "") or 0)
    pv = next((r for r in pvs if r[0] == CFG["part"]), None)
    vg = next((r for r in vgs if r[0] == CFG["vg"]), None)
    layers = [
        {"layer": "Disk", "name": CFG["disk"], "detail": f"{disk_size}, {pttype.upper()} partition table"},
        {"layer": "Partition", "name": CFG["part"], "detail": f"{part_size}, type {part_type}"},
        {"layer": "Physical volume", "name": CFG["part"],
         "detail": f"member of {pv[1]}" if pv else "not an LVM physical volume"},
    ]
    if vg:
        layers.append({"layer": "Volume group", "name": vg[0],
                       "detail": f"{num(vg[1]):.2f} GiB total, {num(vg[2]):.2f} GiB free"})
    mounts, lvchecks = {}, []
    for lv, mp in (("lv_data", CFG["data"]), ("lv_backup", CFG["backup"])):
        row = next((r for r in lvs if r[0] == lv and r[1] == CFG["vg"]), None)
        _, mountout = run(["findmnt", "-n", "-o", "SOURCE,FSTYPE", mp])
        src, fs = (mountout.split() + ["", ""])[:2]
        mounts[lv] = {"mount": mp, "source": src, "fstype": fs, **usage(mp)}
        layers.append({"layer": "Logical volume", "name": lv,
                       "detail": f"{num(row[2]):.2f} GiB; {src} mounted at {mp}" if row else "missing"})
        want = CFG["lv_size_gb"][lv]
        lvchecks.append(chk(g, f"{lv} has expected size ({want:g} GB)",
                            row is not None and abs(num(row[2])-want) < .1,
                            f"{num(row[2]):.2f} GiB" if row else "not found"))
        lvchecks.append(chk(g, f"{mp} is backed by {lv} and ext4",
                            bool(row and src.endswith(f"{CFG['vg']}-{lv}") and fs == "ext4"),
                            f"{src or 'not mounted'} ({fs or '-'})"))
    checks += [
        chk(g, "GPT partition table on data disk", pttype.lower() == "gpt", pttype),
        chk(g, "Partition type is Linux LVM", "lvm" in part_type.lower(), part_type),
        chk(g, "LVM physical volume and volume group exist", bool(pv and vg),
            f"{CFG['part']} -> {CFG['vg']}" if pv and vg else "missing"),
    ] + lvchecks
    try:
        fstab = Path(CFG["fstab"]).read_text().splitlines()
    except OSError:
        fstab = []
    persistent = all(any(line.startswith("UUID=") and len(line.split()) > 1 and line.split()[1] == mp
                         for line in fstab) for mp in (CFG["data"], CFG["backup"]))
    rc, _ = run(["findmnt", "--verify"])
    checks.append(chk(g, "UUID entries in /etc/fstab verify clean", persistent and rc == 0,
                      "UUID entries present" if persistent and rc == 0 else "fstab problem"))
    return {"layers": layers, "mounts": mounts, "checks": checks}

def identities():
    base, rows = baseline()["identities"], []
    for name, expected in base["users"].items():
        try:
            pw = pwd.getpwnam(name); got = {"uid": pw.pw_uid, "gid": pw.pw_gid}
        except KeyError:
            got = {"uid": None, "gid": None}
        rows.append({"kind":"user","name":name,"source":f"{expected['uid']}:{expected['gid']}",
                     "dest":f"{got['uid']}:{got['gid']}","ok":got == expected})
    for name, gid in base["groups"].items():
        try: actual = grp.getgrnam(name).gr_gid
        except KeyError: actual = None
        rows.append({"kind":"group","name":name,"source":str(gid),"dest":str(actual),"ok":actual == gid})
    return {"rows": rows, "checks":[chk("Identities","Source and destination UIDs/GIDs match",
            all(r["ok"] for r in rows), f"{sum(r['ok'] for r in rows)}/{len(rows)} identities identical")]}

def inventory(root):
    result = {".": root}
    for dp, dirs, files in os.walk(root):
        for name in dirs + files:
            full = os.path.join(dp, name)
            result[os.path.relpath(full, root)] = full
    return result

def owner(uid, gid):
    try: user = pwd.getpwuid(uid).pw_name
    except KeyError: user = str(uid)
    try: group = grp.getgrgid(gid).gr_name
    except KeyError: group = str(gid)
    return f"{user}:{group}"

def migration():
    base, root = baseline(), CFG["data"]
    expected = {e["path"]: e for e in base["entries"]}
    actual = inventory(root)
    rows, ownbad, modebad, shabad = [], 0, 0, 0
    for path in sorted(set(expected) | set(actual)):
        e = expected.get(path)
        if path not in actual or e is None:
            rows.append({"path":path,"type":"-","owner":"-","mode":"-","sha":"-","ok":False,
                         "note":"missing on destination" if e else "not on source"})
            continue
        st = os.lstat(actual[path])
        isdir = stat.S_ISDIR(st.st_mode)
        mode = format(stat.S_IMODE(st.st_mode), "o")
        digest = "" if isdir else sha256(actual[path])
        ownerok = (st.st_uid, st.st_gid) == (e["uid"], e["gid"])
        modeok = mode == e["mode"]
        shaok = isdir or digest == e.get("sha256")
        ownbad += not ownerok; modebad += not modeok; shabad += not shaok
        rows.append({"path":path,"type":"dir" if isdir else "file","owner":owner(st.st_uid,st.st_gid),
                     "mode":mode,"sha":digest[:12] if digest else "-",
                     "ok":ownerok and modeok and shaok,"note":""})
    files = sum(1 for r in rows if r["type"] == "file")
    dirs = sum(1 for r in rows if r["type"] == "dir")
    basefiles = sum(1 for e in base["entries"] if e["type"] == "file")
    basedirs = sum(1 for e in base["entries"] if e["type"] == "dir")
    _, aclout = run(["getfacl","-R","-s","-p",root])
    _, xout = run(["getfattr","-R","-d","-m","-",root])
    aclcount = sum(1 for line in aclout.splitlines() if line and not line.startswith("#"))
    xcount = sum(1 for line in xout.splitlines() if line.startswith("# file"))
    invok = set(expected) == set(actual)
    checks = [
        chk("Migration","File/directory inventory matches",invok,f"{files} files, {dirs} directories"),
        chk("Migration","File and directory counts match",(files,dirs)==(basefiles,basedirs),
            f"source {basefiles}/{basedirs}, destination {files}/{dirs}"),
        chk("Migration","Numeric ownership matches",invok and ownbad==0,f"{ownbad} mismatches"),
        chk("Migration","Modes including setgid match",invok and modebad==0,f"{modebad} mismatches"),
        chk("Migration","SHA-256 checksums match",invok and shabad==0,f"{shabad} mismatches"),
        chk("Migration","ACL and xattr counts match",aclcount==base["acl_entries"] and xcount==base["xattr_entries"],
            f"ACL entries {aclcount}, xattr files {xcount}"),
    ]
    tests = []
    for user, flag, rel, expected_ok, label in [
        ("devuser","-r","development/config.txt",True,"devuser can read development file"),
        ("financeuser","-r","finance/records.txt",True,"financeuser can read finance file"),
        ("financeuser","-w","development",False,"financeuser cannot write development directory"),
        ("devuser","-r","finance/records.txt",False,"devuser cannot read finance file")]:
        rc, _ = run(["runuser","-u",user,"--","test",flag,os.path.join(root,rel)])
        passed = (rc == 0) == expected_ok
        tests.append({"test":label,"expected":"allowed" if expected_ok else "denied",
                      "actual":"allowed" if rc == 0 else "denied","ok":passed})
    checks.append(chk("Access","Access-control tests behave as intended",all(t["ok"] for t in tests),
                      f"{sum(t['ok'] for t in tests)}/{len(tests)} tests passed"))
    return {"rows":rows,"files":files,"dirs":dirs,"acl":aclcount,"xattr":xcount,"tests":tests,"checks":checks}

def backups():
    base, folder = baseline(), Path(CFG["backup"])
    expected = {"company"} | {"company/"+e["path"] for e in base["entries"] if e["path"] != "."}
    rows = []
    for tarpath in sorted(folder.glob("*.tar"),key=lambda p:p.stat().st_mtime,reverse=True):
        st, side = tarpath.stat(), tarpath.with_name(tarpath.name+".sha256")
        try:
            with tarfile.open(tarpath) as tf:
                content = {n.rstrip("/") for n in tf.getnames()} == expected
        except (tarfile.TarError,OSError):
            content = False
        if side.exists():
            try: checksum = "OK" if side.read_text().split()[0] == sha256(tarpath) else "FAILED"
            except (OSError,IndexError): checksum = "FAILED"
        else: checksum = "no .sha256 file"
        rows.append({"name":tarpath.name,"size":human(st.st_size),
                     "time":datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M"),
                     "mode":format(stat.S_IMODE(st.st_mode),"o"),"content":content,"checksum":checksum})
    pre = next((r for r in rows if "pre-migration" in r["name"]),None)
    scheduled = [r for r in rows if "pre-migration" not in r["name"]]
    _, cronout = run(["crontab","-l"])
    cronline = next((line for line in cronout.splitlines()
                     if CFG["script"] in line and not line.lstrip().startswith("#")), "")
    try: st = os.stat(CFG["script"])
    except OSError: st = None
    scriptok = bool(st and st.st_uid == 0 and st.st_gid == 0 and stat.S_IMODE(st.st_mode) == 0o750)
    private = bool(rows) and all((int(r["mode"],8) & 0o007) == 0 for r in rows)
    checks = [
        chk("Backup","Pre-migration archive tree matches source",bool(pre and pre["content"]),
            pre["name"] if pre else "archive not found"),
        chk("Backup","Latest scheduled archive checksum is OK",
            bool(scheduled and scheduled[0]["checksum"]=="OK"),
            f"{scheduled[0]['name']}: {scheduled[0]['checksum']}" if scheduled else "no scheduled archive yet"),
        chk("Backup","Archives are not world-readable",private,"no world permissions" if private else "missing/open archive"),
        chk("Backup","Backup script root-owned with mode 0750",scriptok,CFG["script"]),
        chk("Backup","Cron entry exists",bool(cronline),cronline or "not scheduled"),
    ]
    return {"rows":rows,"cron":cronline,"checks":checks}

def security():
    services = []
    # Ubuntu uses "cron"; Arch/EndeavourOS uses "cronie".
    for service in ("sshd", "cron" if Path("/etc/os-release").exists() and
                    "ubuntu" in Path("/etc/os-release").read_text().lower() else "cronie",
                    "firewalld"):
        _, state = run(["systemctl","is-active",service])
        services.append({"service":service,"state":state or "unknown","ok":state=="active"})
    _, fw = run(["firewall-cmd","--list-services"])
    checks = [
        chk("Security","SSH, cron scheduler and firewalld are active",all(s["ok"] for s in services),
            ", ".join(f"{s['service']}={s['state']}" for s in services)),
        chk("Security","Firewall allows SSH","ssh" in fw.split(),f"services: {fw or 'none'}"),
    ]
    return {"services":services,"firewall":fw,"checks":checks}

def logs(n=12):
    try: return Path(CFG["log"]).read_text().splitlines()[-n:]
    except OSError: return []

def summary():
    s, i, m, b, sec = storage(), identities(), migration(), backups(), security()
    checks = s["checks"] + i["checks"] + m["checks"] + b["checks"] + sec["checks"]
    passed = sum(c["ok"] for c in checks)
    return {"generated":datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "host":socket.gethostname(),"passed":passed,"total":len(checks),
            "status":"VERIFIED" if passed==len(checks) else "ATTENTION",
            "storage":s,"identities":i,"migration":m,"backup":b,"security":sec,"checks":checks}

def report_text():
    d = summary()
    lines = ["LINUX SERVER MIGRATION - VERIFICATION REPORT","="*44,
             f"Generated : {d['generated']}",f"Host      : {d['host']}",
             f"Data path : {CFG['data']}",f"Baseline  : {CFG['baseline']}"]
    group = None
    for c in d["checks"]:
        if c["group"] != group:
            group = c["group"]; lines += ["",group.upper()]
        lines.append(f" [{'PASS' if c['ok'] else 'FAIL'}] {c['name']} - {c['detail']}")
    lines += ["",f"RESULT: {d['passed']}/{d['total']} checks passed - "+
              ("MIGRATION VERIFIED" if d["status"]=="VERIFIED" else "ATTENTION REQUIRED")]
    output = "\n".join(lines)+"\n"
    Path(CFG["report"]).parent.mkdir(parents=True,exist_ok=True)
    Path(CFG["report"]).write_text(output)
    return output

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/summary")
def api_summary(): return jsonify(summary())

@app.route("/api/storage")
def api_storage(): return jsonify(storage())

@app.route("/api/identities")
def api_identities(): return jsonify(identities())

@app.route("/api/migration")
def api_migration(): return jsonify(migration())

@app.route("/api/backup")
def api_backup(): return jsonify(backups())

@app.route("/api/security")
def api_security(): return jsonify(security())

@app.route("/api/logs")
def api_logs(): return jsonify({"logs":logs()})

@app.route("/api/report")
def api_report(): return jsonify({"report":report_text(),"saved_to":CFG["report"]})

if __name__ == "__main__":
    if os.geteuid() != 0:
        raise SystemExit("Run with sudo: dashboard needs read access to system metadata and backups.")
    app.run(host="127.0.0.1", port=5000, debug=False)
