"""
pc_client.py - runs on the PC. Sends the order to the Pi, waits, downloads the model.

    python pc_client.py --host 192.168.0.50 --token SECRET run        (same wifi)
    python pc_client.py --url https://NAME.trycloudflare.com --token SECRET run
                                                   (over the internet, Part J-4)
    python pc_client.py ... start --photos 60      only start (the Pi also makes the model)
    python pc_client.py ... status                 where is it?
    python pc_client.py ... wait                   wait until it ends
    python pc_client.py ... download               get the model of the last scan
    python pc_client.py ... stop                   stop the scan

The 3D model is made ONLY on the Pi (scan_folder.py runs there after the last
photo). "run" = start + wait (shows progress) + download  model.obj  into
the folder --out. The PC does no processing. The photos stay on the Pi, in
scans/scan_DATE_TIME/; --photos-zip also downloads them (tens of MB) and
--stl also gets model.stl (3D printing).
--map camera_map.json: a file that must exist in the scanner folder of the Pi.

Only the Python standard library is used.
"""

import argparse
import io
import json
import os
import sys
import time
import urllib.error
import urllib.request
import zipfile


class ScannerError(Exception):
    pass


class Client:
    def __init__(self, host, port, token, timeout=15, url=None):
        # url = full address (for example the https one of a Cloudflare tunnel)
        self.base = url.rstrip("/") if url else f"http://{host}:{port}"
        self.token = token
        self.timeout = timeout

    def _call(self, method, path, body=None, raw=False):
        data = None if body is None else json.dumps(body).encode()
        req = urllib.request.Request(self.base + path, data=data, method=method,
                                     headers={"X-Token": self.token,
                                              "Content-Type": "application/json",
                                              # the default "Python-urllib" name is
                                              # blocked by some web proxies
                                              "User-Agent": "scanner-client/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                content = r.read()
                return content if raw else json.loads(content)
        except urllib.error.HTTPError as e:
            try:
                msg = json.loads(e.read()).get("error", "")
            except ValueError:
                msg = ""
            raise ScannerError(f"the Pi answered {e.code}: {msg}") from None
        except (urllib.error.URLError, OSError) as e:
            raise ScannerError(f"cannot reach the Pi at {self.base}: "
                               f"{getattr(e, 'reason', e)}") from None

    def start(self, **opts):
        return self._call("POST", "/start", opts)

    def status(self):
        return self._call("GET", "/status")

    def stop(self):
        return self._call("POST", "/stop", {})

    def download_zip(self):
        return self._call("GET", "/download", raw=True)

    def download_model(self):
        return self._call("GET", "/model", raw=True)

    def download_stl(self):
        return self._call("GET", "/model.stl", raw=True)

    def wait(self, poll=1.0, show=True, give_up_after=1800):
        """Wait until the scan is no longer scanning or meshing. Returns the last status."""
        t0 = time.time()
        while True:
            st = self.status()
            if show:
                what = ("the Pi is making the model" if st["state"] == "meshing"
                        else f"{st['state']}: {st['done']} of {st['total']} positions")
                print(f"\r  {what}   ", end="", flush=True)
            if st["state"] not in ("scanning", "meshing"):
                if show:
                    print()
                return st
            if time.time() - t0 > give_up_after:
                raise ScannerError("gave up waiting (30 min); the scan may still be running")
            time.sleep(poll)


def unzip_to(data, folder):
    os.makedirs(folder, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        for name in z.namelist():
            if os.path.basename(name) != name:      # only flat names are expected
                raise ScannerError(f"unexpected path in the zip: {name}")
        z.extractall(folder)
        return len(z.namelist())


def save_model(client, folder):
    """Downloads the model of the last scan into folder/model.obj. Returns (path, KB, seconds)."""
    os.makedirs(folder, exist_ok=True)
    t0 = time.time()
    data = client.download_model()
    path = os.path.join(folder, "model.obj")
    with open(path, "wb") as f:
        f.write(data)
    return path, len(data) / 1024, time.time() - t0


def main(argv=None):
    p = argparse.ArgumentParser(description="Remote control of the scanner Pi.")
    p.add_argument("--host", default=None, help="IP or name of the Pi (same network)")
    p.add_argument("--url", default=None,
                   help="full address instead of --host/--port, for example "
                        "https://NAME.trycloudflare.com (over the internet)")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--token", default=os.environ.get("SCANNER_TOKEN"), required=False)
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("start", "run"):
        s = sub.add_parser(name)
        s.add_argument("--photos", type=int, default=60)
        s.add_argument("--platform", default="uln2003", choices=["uln2003", "stepper"])
        s.add_argument("--steps-per-turn", type=int, default=None)
        s.add_argument("--reverse", action="store_true")
        s.add_argument("--format", default="jpg", choices=["jpg", "png"])
        s.add_argument("--map", default=None,
                       help="perspective map file name on the Pi, e.g. camera_map.json")
        s.add_argument("--dry-run", action="store_true",
                       help="fake scan on the Pi (only if the server allows it)")
        if name == "run":
            s.add_argument("--out", default="scan_from_pi",
                           help="folder on the PC for model.obj (default scan_from_pi)")
            s.add_argument("--photos-zip", action="store_true",
                           help="also download the photos (into OUT/photos)")
            s.add_argument("--stl", action="store_true",
                           help="also download model.stl (for 3D printing)")
    sub.add_parser("status")
    sub.add_parser("wait")
    sub.add_parser("stop")
    d = sub.add_parser("download")
    d.add_argument("--out", default="scan_from_pi")
    d.add_argument("--photos-zip", action="store_true")
    d.add_argument("--stl", action="store_true")
    a = p.parse_args(argv)
    if not a.token:
        p.error("the token is needed (--token, or the environment variable SCANNER_TOKEN)")

    if not a.host and not a.url:
        p.error("give --host (same network) or --url (over the internet)")
    c = Client(a.host, a.port, a.token, url=a.url)

    def fetch(out, photos_zip, stl=False):
        path, kb, secs = save_model(c, out)
        print(f"{path}: {kb:.0f} KB (downloaded in {secs:.1f} s)")
        if stl:
            data = c.download_stl()
            with open(os.path.join(out, "model.stl"), "wb") as f:
                f.write(data)
            print(f"{os.path.join(out, 'model.stl')}: {len(data) / 1024:.0f} KB (units: mm)")
        if photos_zip:
            t0 = time.time()
            n = unzip_to(c.download_zip(), os.path.join(out, "photos"))
            print(f"{n} photo files in '{os.path.join(out, 'photos')}' "
                  f"(downloaded in {time.time() - t0:.1f} s)")

    try:
        if a.cmd in ("start", "run"):
            opts = dict(photos=a.photos, platform=a.platform, reverse=a.reverse,
                        format=a.format, dry_run=a.dry_run, mesh=True)
            if a.map:
                opts["map"] = os.path.basename(a.map)
            if a.steps_per_turn:
                opts["steps_per_turn"] = a.steps_per_turn
            ans = c.start(**opts)
            print(f"started: {ans['started']} ({ans['photos']} positions; the Pi makes the model)")
            if a.cmd == "start":
                return 0
            st = c.wait()
            if st["state"] != "done":
                print(f"The scan did not finish: {st['state']}. {st['message']}")
                return 1
            if st["message"]:
                print("Note from the Pi:", st["message"])
            if st.get("mesh_seconds") is not None:
                print(f"the Pi made the model in {st['mesh_seconds']} s")
            fetch(a.out, a.photos_zip, a.stl)
        elif a.cmd == "status":
            print(json.dumps(c.status(), indent=1))
        elif a.cmd == "wait":
            st = c.wait()
            print(json.dumps(st, indent=1))
            return 0 if st["state"] == "done" else 1
        elif a.cmd == "stop":
            print(c.stop())
        elif a.cmd == "download":
            fetch(a.out, a.photos_zip, a.stl)
    except ScannerError as e:
        print("Error:", e)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
