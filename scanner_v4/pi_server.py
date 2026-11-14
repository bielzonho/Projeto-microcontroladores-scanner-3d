"""
pi_server.py - runs on the Raspberry Pi. The PC sends the order, the Pi scans.

    python3 pi_server.py                      (prints the token to use)
    python3 pi_server.py --token mysecret --port 8000

The PC side is pc_client.py. Only the Python standard library is used.

What the server answers (every request needs the token, in the header
"X-Token", or as ?token=... in the address):

    GET  /            the web page (start button, progress, 3D view); no token needed
    GET  /status     {"state": "idle|scanning|done|error|stopped", "done": 12,
                      "total": 60, "scan": "scan_20261109_141500", "message": ""}
    POST /start      body (JSON, all optional): {"photos": 60,
                      "platform": "uln2003" or "stepper", "reverse": false,
                      "format": "jpg", "steps_per_turn": 4096,
                      "mesh": false, "map": "camera_map.json"}
                     starts capture.py in a separate process; 409 if busy.
    POST /stop       stops the running scan (Ctrl+C for capture.py, so that
                     the laser is switched off)
    GET  /download   the photos of the last finished scan as a .zip
    GET  /model      the .obj the Pi made (only if /start had "mesh": true;
                     optional "map": "camera_map.json", a file in the Pi's folder)
    GET  /model.stl  the same model as .stl (for 3D printing)
      (/download, /model and /model.stl accept  ?scan=scan_20261110_215433  to
       fetch an OLD scan instead of the last one)
    GET  /scans      list of the scans kept on the Pi, and the free disk space
    POST /delete     {"scan": "scan_..."}  erases that scan from the Pi
    POST /test/laser blinks the laser 3 times (about 6 s)
    POST /test/photo takes one photo pair (laser on / off) and reports on it;
                     the photos: GET /test/photo/on.jpg and /off.jpg

"manual" is refused: nobody is at the Pi to press Enter.

SECURITY - read this: this server itself speaks plain http. On a trusted
network (your home, the lab's, a hotspot) that is acceptable. To put it on
the internet use a Cloudflare tunnel (guide, Part J-4): the PC then talks
https to Cloudflare. Start the server with  --host 127.0.0.1  in that case, so
that ONLY the tunnel can reach it. Anyone who has the token can switch the
laser on and turn the motor: it must be long (at least 10 characters; a
wrong token is answered after 1 s), and not shared.
"""

import argparse
import json
import os
import re
import secrets
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import zipfile
from export_stl import obj_to_stl
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

HERE = os.path.dirname(os.path.abspath(__file__))
ALLOWED_PLATFORMS = ("uln2003", "stepper")
MODEL_NAME = "model_pi.obj"
MIN_TOKEN = 10
PAGE_FILE = os.path.join(HERE, "scanner_page.html")
SCAN_NAME = re.compile(r"^scan_\d{8}_\d{6}(_\d+)?$")      # the only folder names we ever touch
BUSY = ("scanning", "meshing", "testing")


class ScanJob:
    """The one scan that can run at a time, and the state of the last one.

    States: idle, scanning (capture.py running), meshing (scan_folder.py
    running on the Pi, only if the PC asked for it), testing (laser or photo
    test), done, error, stopped.
    """

    def __init__(self, scans_dir, allow_dry_run=False, capture_script=None,
                 mesh_script=None):
        self.scans_dir = scans_dir
        self.allow_dry_run = allow_dry_run
        self.capture_script = capture_script or os.path.join(HERE, "capture.py")
        self.mesh_script = mesh_script or os.path.join(HERE, "scan_folder.py")
        self.lock = threading.Lock()
        self.proc = None
        self.state = "idle"
        self.scan = ""
        self.total = 0
        self.message = ""
        self.mesh_wanted = False
        self.mesh_seconds = None
        self.stop_asked = False
        os.makedirs(scans_dir, exist_ok=True)

    # ---- helpers --------------------------------------------------------
    def folder(self):
        return os.path.join(self.scans_dir, self.scan)

    def done_count(self):
        if not self.scan or not os.path.isdir(self.folder()):
            return 0
        names = os.listdir(self.folder())
        offs = {n.split(".")[0][4:] for n in names if n.startswith("off_")}
        ons = {n.split(".")[0][3:] for n in names if n.startswith("on_")}
        return len(offs & ons)          # a position counts when both photos exist

    def status(self):
        with self.lock:
            return {"state": self.state, "done": self.done_count(),
                    "total": self.total, "scan": self.scan,
                    "mesh_wanted": self.mesh_wanted,
                    "mesh_seconds": self.mesh_seconds,
                    "allow_dry_run": self.allow_dry_run,
                    "message": self.message}

    def _tail(self, logname):
        try:
            with open(os.path.join(self.folder(), logname), errors="replace") as f:
                lines = [x.strip() for x in f.read().replace("\r", "\n").split("\n") if x.strip()]
            return " | ".join(lines[-4:])
        except OSError:
            return ""

    def _pipeline(self, proc, mesh_cmd, name):
        """Own thread: wait for capture.py, then (if asked) run scan_folder.py."""
        code = proc.wait()
        with self.lock:
            if self.scan != name:
                return
            if self.stop_asked:
                self.state, self.message = "stopped", "stopped on request"
                return
            if code != 0:
                self.state = "error"
                self.message = f"capture.py ended with code {code}. {self._tail('capture.log')}"
                return
            if mesh_cmd is None:
                self.state, self.message = "done", ""
                return
            self.state = "meshing"
            log = open(os.path.join(self.folder(), "mesh.log"), "w")
            try:
                mp = subprocess.Popen(mesh_cmd, stdout=log, stderr=subprocess.STDOUT, cwd=HERE)
            except OSError as e:
                self.state, self.message = "error", f"could not start scan_folder.py: {e}"
                return
            finally:
                log.close()
            self.proc = mp
        t0 = time.time()
        code = mp.wait()
        took = time.time() - t0
        with self.lock:
            if self.scan != name:
                return
            self.mesh_seconds = round(took, 1)
            obj = os.path.join(self.folder(), MODEL_NAME)
            if self.stop_asked:
                self.state, self.message = "stopped", "stopped on request"
            elif not os.path.exists(obj):
                self.state = "error"
                self.message = (f"photos taken, but scan_folder.py made no model "
                                f"(code {code}). {self._tail('mesh.log')}")
            else:
                self.state = "done"
                self.message = "" if code == 0 else (
                    "model made, but scan_folder.py ended with an error after it "
                    "(probably the preview picture): " + self._tail("mesh.log"))

    # ---- commands -------------------------------------------------------
    def start(self, opts):
        """Returns (http_status, answer dict)."""
        try:
            photos = int(opts.get("photos", 60))
            platform = str(opts.get("platform", "uln2003"))
            reverse = bool(opts.get("reverse", False))
            fmt = str(opts.get("format", "jpg"))
            spt = opts.get("steps_per_turn")
            spt = None if spt is None else int(spt)
            dry = bool(opts.get("dry_run", False))
            mesh = bool(opts.get("mesh", False))
            map_file = opts.get("map")
            map_file = None if map_file in (None, "") else str(map_file)
        except (TypeError, ValueError):
            return 400, {"error": "bad option value"}
        if not 3 <= photos <= 360:
            return 400, {"error": "photos must be from 3 to 360"}
        if fmt not in ("jpg", "png"):
            return 400, {"error": "format must be jpg or png"}
        if dry and not self.allow_dry_run:
            return 400, {"error": "dry_run is not allowed (start the server with --allow-dry-run)"}
        if not dry and platform not in ALLOWED_PLATFORMS:
            return 400, {"error": "platform must be one of " + ", ".join(ALLOWED_PLATFORMS)
                         + " (manual needs a person at the Pi)"}
        if spt is not None and not 100 <= spt <= 100000:
            return 400, {"error": "steps_per_turn out of range"}
        if platform == "stepper" and spt is None and not dry:
            return 400, {"error": "platform stepper needs steps_per_turn"}
        if map_file is not None:
            if not mesh:
                return 400, {"error": "map only makes sense together with mesh"}
            if os.path.basename(map_file) != map_file or not map_file.endswith(".json"):
                return 400, {"error": "map must be the NAME of a .json file in the scanner folder of the Pi"}
            if not os.path.exists(os.path.join(HERE, map_file)):
                return 400, {"error": f"the Pi has no file '{map_file}' in its scanner folder"}

        with self.lock:
            if self.state in BUSY:
                return 409, {"error": "the Pi is busy (scan or test running)", "scan": self.scan}
            base = "scan_" + time.strftime("%Y%m%d_%H%M%S")
            name, i = base, 1
            while os.path.exists(os.path.join(self.scans_dir, name)):   # same second
                i += 1
                name = f"{base}_{i}"
            folder = os.path.join(self.scans_dir, name)
            os.makedirs(folder)
            cmd = [sys.executable, self.capture_script, "--out", folder,
                   "--photos", str(photos), "--format", fmt]
            if dry:
                cmd.append("--dry-run")
            else:
                cmd += ["--platform", platform]
                if spt is not None:
                    cmd += ["--steps-per-turn", str(spt)]
                if reverse:
                    cmd.append("--reverse")
            mesh_cmd = None
            if mesh:
                mesh_cmd = [sys.executable, self.mesh_script, folder, "--out",
                            os.path.join(folder, MODEL_NAME), "--preview",
                            os.path.join(folder, "model_preview.png")]
                if map_file:
                    mesh_cmd += ["--map", os.path.join(HERE, map_file)]
                if reverse:
                    mesh_cmd.append("--mirror")   # a reversed turn gives a mirrored scan
            log = open(os.path.join(folder, "capture.log"), "w")
            try:
                proc = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, cwd=HERE)
            except OSError as e:
                return 500, {"error": f"could not start capture.py: {e}"}
            finally:
                log.close()
            with open(os.path.join(folder, "scan_info.json"), "w") as f:
                json.dump({"photos": photos, "platform": "dry-run" if dry else platform,
                           "reverse": reverse, "format": fmt, "steps_per_turn": spt,
                           "mesh_on_pi": mesh, "map": map_file,
                           "started": time.strftime("%Y-%m-%d %H:%M:%S")}, f, indent=1)
            self.proc = proc
            self.scan, self.total, self.message = name, photos, ""
            self.mesh_wanted, self.mesh_seconds = mesh, None
            self.state, self.stop_asked = "scanning", False
            threading.Thread(target=self._pipeline, args=(proc, mesh_cmd, name),
                             daemon=True).start()
            return 202, {"started": name, "photos": photos, "mesh": mesh}

    def stop(self):
        with self.lock:
            if self.state not in ("scanning", "meshing") or self.proc is None:
                return 409, {"error": "no scan is running"}
            self.stop_asked = True
            self.proc.send_signal(signal.SIGINT)   # capture.py switches the laser off
            return 200, {"stopping": self.scan}

    def _folder_of(self, name):
        """(folder, None) of a finished or old scan by name, or (None, (code, reason))."""
        if not SCAN_NAME.match(name or ""):
            return None, (400, "bad scan name")
        folder = os.path.join(self.scans_dir, name)
        if not os.path.isdir(folder):
            return None, (404, "no such scan")
        if name == self.scan and self.state in BUSY:
            return None, (409, "that scan is still running")
        return folder, None

    def make_zip(self, name=None):
        """Zip of the photos of a scan (default: the last finished one) in a temp file.
        Returns (file, name) or (None, (code, reason))."""
        with self.lock:
            if name is None:
                if self.state != "done":
                    return None, (409, f"no finished scan to download (state: {self.state})")
                folder, name = self.folder(), self.scan
            else:
                folder, err = self._folder_of(name)
                if folder is None:
                    return None, err
        tmp = tempfile.TemporaryFile()
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_STORED) as z:   # jpg/png don't shrink
            for fn in sorted(os.listdir(folder)):
                if fn.startswith(("on_", "off_")) or fn == "scan_info.json":
                    z.write(os.path.join(folder, fn), fn)
        tmp.seek(0)
        return tmp, name

    def model_path(self, name=None):
        """(path, name) of the .obj made on the Pi, or (None, (code, reason))."""
        with self.lock:
            if name is None:
                if self.state != "done":
                    return None, (409, f"no finished scan (state: {self.state})")
                if not self.mesh_wanted:
                    return None, (409, "this scan was started without mesh (the Pi made no model)")
                return os.path.join(self.folder(), MODEL_NAME), self.scan
            folder, err = self._folder_of(name)
            if folder is None:
                return None, err
            path = os.path.join(folder, MODEL_NAME)
            if not os.path.exists(path):
                return None, (409, "that scan has no model")
            return path, name

    def stl_bytes(self, name=None):
        """(bytes, name) of the model as .stl, or (None, (code, reason))."""
        path, info = self.model_path(name)
        if path is None:
            return None, info
        try:
            with open(path, "rb") as f:
                return obj_to_stl(f.read()), info
        except (OSError, ValueError) as e:
            return None, (500, f"could not make the .stl: {e}")

    def list_scans(self):
        """Every scan folder on the Pi (newest first), and the free disk space."""
        with self.lock:
            running = self.scan if self.state in BUSY else None
            current = self.scan
        rows = []
        for name in sorted(os.listdir(self.scans_dir), reverse=True):
            folder = os.path.join(self.scans_dir, name)
            if not SCAN_NAME.match(name) or not os.path.isdir(folder):
                continue
            info = {}
            try:
                with open(os.path.join(folder, "scan_info.json")) as f:
                    info = json.load(f)
            except (OSError, ValueError):
                pass
            names = os.listdir(folder)
            offs = {n.split(".")[0][4:] for n in names if n.startswith("off_")}
            ons = {n.split(".")[0][3:] for n in names if n.startswith("on_")}
            size = sum(os.path.getsize(os.path.join(folder, n)) for n in names
                       if os.path.isfile(os.path.join(folder, n)))
            model = os.path.join(folder, MODEL_NAME)
            rows.append({"scan": name, "photos_planned": info.get("photos"),
                         "photos_done": len(offs & ons), "size_mb": round(size / 1e6, 1),
                         "has_model": os.path.exists(model),
                         "model_kb": round(os.path.getsize(model) / 1024) if os.path.exists(model) else 0,
                         "running": name == running, "current": name == current,
                         "started": info.get("started")})
        usage = shutil.disk_usage(self.scans_dir)
        return {"scans": rows, "disk_free_mb": round(usage.free / 1e6),
                "disk_total_mb": round(usage.total / 1e6)}

    def delete_scan(self, name):
        with self.lock:
            folder, err = self._folder_of(name)
            if folder is None:
                return err[0], {"error": err[1]}
            shutil.rmtree(folder)
            if name == self.scan:                    # the "last scan" no longer exists
                self.scan, self.total, self.message = "", 0, ""
                self.mesh_wanted, self.mesh_seconds = False, None
                if self.state not in BUSY:
                    self.state = "idle"
            return 200, {"deleted": name}

    # ---- tests of the hardware (laser blink, one photo pair) ------------
    def check_dir(self):
        return os.path.join(self.scans_dir, "_check")     # not a scan name: never listed

    def run_test(self, kind, dry=False):
        """kind 'laser' or 'photo'. Runs capture.py and waits (a few seconds).
        Returns (http_status, answer)."""
        if dry and not self.allow_dry_run:
            return 400, {"error": "dry_run is not allowed (start the server with --allow-dry-run)"}
        with self.lock:
            if self.state in BUSY:
                return 409, {"error": "the Pi is busy (scan or test running)"}
            before = self.state
            self.state = "testing"
        try:
            cmd = [sys.executable, self.capture_script]
            if kind == "laser":
                cmd += ["--laser-test"]
                limit = 30
            else:
                shutil.rmtree(self.check_dir(), ignore_errors=True)
                cmd += ["--check", "--out", self.check_dir()]
                limit = 60
            if dry:
                cmd.append("--dry-run")
            try:
                r = subprocess.run(cmd, capture_output=True, text=True, cwd=HERE, timeout=limit)
                text = (r.stdout + r.stderr).replace("\r", "\n")
                ok = r.returncode == 0
            except subprocess.TimeoutExpired:
                text, ok = f"the test did not finish in {limit} s", False
            except OSError as e:
                text, ok = f"could not start capture.py: {e}", False
            lines = [x.rstrip() for x in text.split("\n") if x.strip()]
            has_photos = all(os.path.exists(os.path.join(self.check_dir(), f"{w}_00.jpg"))
                             for w in ("on", "off"))
            return 200, {"ok": ok, "report": "\n".join(lines[-25:]),
                         "has_photos": kind == "photo" and has_photos}
        finally:
            with self.lock:
                self.state = before

    def check_photo(self, which):
        path = os.path.join(self.check_dir(), f"{which}_00.jpg")
        return path if which in ("on", "off") and os.path.exists(path) else None

    def shutdown(self):
        with self.lock:
            self.stop_asked = True
            proc = self.proc
        if proc is not None and proc.poll() is None:
            proc.send_signal(signal.SIGINT)
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()


def make_handler(job, token):
    class Handler(BaseHTTPRequestHandler):
        server_version = "scanner-pi"

        def log_message(self, fmt, *args):
            sys.stderr.write("[%s] %s\n" % (time.strftime("%H:%M:%S"), fmt % args))

        def _send(self, code, obj):
            body = json.dumps(obj).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_bytes(self, code, body, ctype, filename=None, cache=True):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            if filename:
                self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
            if not cache:
                self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _read_json(self):
            """The JSON object of the request body, or None after answering an error."""
            n = int(self.headers.get("Content-Length") or 0)
            if n > 10000:
                self._send(413, {"error": "body too large"})
                return None
            try:
                opts = json.loads(self.rfile.read(n) or b"{}")
                if not isinstance(opts, dict):
                    raise ValueError
            except ValueError:
                self._send(400, {"error": "body must be a JSON object"})
                return None
            return opts

        def _authorised(self, query):
            given = self.headers.get("X-Token") or (query.get("token") or [""])[0]
            return secrets.compare_digest(given.encode(), token.encode())

        def _route(self, method):
            url = urlparse(self.path)
            query = parse_qs(url.query)
            page = url.path.rstrip("/")
            if method == "GET" and page in ("", "/index.html"):
                # the web page itself needs no token: the token is typed into it
                try:
                    with open(PAGE_FILE, "rb") as f:
                        body = f.read()
                except OSError:
                    return self._send(500, {"error": "scanner_page.html is missing next to pi_server.py"})
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)
                return None
            if not self._authorised(query):
                time.sleep(1.0)            # makes guessing the token slow
                return self._send(401, {"error": "wrong or missing token"})
            path = url.path.rstrip("/")
            if method == "GET" and path == "/status":
                return self._send(200, job.status())
            if method == "POST" and path == "/start":
                opts = self._read_json()
                if opts is None:
                    return None
                code, ans = job.start(opts)
                return self._send(code, ans)
            if method == "POST" and path == "/stop":
                code, ans = job.stop()
                return self._send(code, ans)
            scan = (query.get("scan") or [None])[0]
            if method == "GET" and path == "/scans":
                return self._send(200, job.list_scans())
            if method == "POST" and path == "/delete":
                opts = self._read_json()
                if opts is None:
                    return None
                code, ans = job.delete_scan(str(opts.get("scan", "")))
                return self._send(code, ans)
            if method == "POST" and path in ("/test/laser", "/test/photo"):
                opts = self._read_json()
                if opts is None:
                    return None
                code, ans = job.run_test("laser" if path.endswith("laser") else "photo",
                                         bool(opts.get("dry_run", False)))
                return self._send(code, ans)
            if method == "GET" and path in ("/test/photo/on.jpg", "/test/photo/off.jpg"):
                p = job.check_photo(path.split("/")[-1][:-4])
                if p is None:
                    return self._send(404, {"error": "no test photo yet"})
                with open(p, "rb") as f:
                    return self._send_bytes(200, f.read(), "image/jpeg", cache=False)
            if method == "GET" and path == "/download":
                tmp, info = job.make_zip(scan)
                if tmp is None:
                    return self._send(info[0], {"error": info[1]})
                size = tmp.seek(0, 2)
                tmp.seek(0)
                self.send_response(200)
                self.send_header("Content-Type", "application/zip")
                self.send_header("Content-Length", str(size))
                self.send_header("Content-Disposition", f'attachment; filename="{info}.zip"')
                self.end_headers()
                while True:
                    chunk = tmp.read(1 << 16)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                tmp.close()
                return None
            if method == "GET" and path == "/model":
                obj, info = job.model_path(scan)
                if obj is None:
                    return self._send(info[0], {"error": info[1]})
                with open(obj, "rb") as f:
                    return self._send_bytes(200, f.read(), "text/plain")
            if method == "GET" and path == "/model.stl":
                data, info = job.stl_bytes(scan)
                if data is None:
                    return self._send(info[0], {"error": info[1]})
                return self._send_bytes(200, data, "model/stl", filename=f"{info}.stl")
            return self._send(404, {"error": "unknown address"})

        def do_GET(self):
            self._route("GET")

        def do_POST(self):
            self._route("POST")

    return Handler


def make_server(host, port, token, scans_dir, allow_dry_run=False, capture_script=None,
                mesh_script=None):
    job = ScanJob(scans_dir, allow_dry_run, capture_script, mesh_script)
    server = ThreadingHTTPServer((host, port), make_handler(job, token))
    return server, job


def main(argv=None):
    p = argparse.ArgumentParser(description="Scanner server for the Raspberry Pi.")
    p.add_argument("--host", default="0.0.0.0", help="0.0.0.0 = reachable from the network")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--token", default=os.environ.get("SCANNER_TOKEN"),
                   help="password the PC must send (default: a random one is made and printed)")
    p.add_argument("--scans-dir", default=os.path.join(HERE, "scans"))
    p.add_argument("--allow-dry-run", action="store_true",
                   help="let the PC ask for a fake scan (to test without hardware)")
    a = p.parse_args(argv)
    token = a.token or secrets.token_urlsafe(9)
    if len(token) < MIN_TOKEN:
        sys.exit(f"The token must have at least {MIN_TOKEN} characters (it protects the "
                 "laser and the motor, and with a tunnel anybody on the internet can try it).")
    server, job = make_server(a.host, a.port, token, a.scans_dir, a.allow_dry_run)
    print(f"Scanner server on port {a.port}.  Token: {token}")
    print(f"In a browser:  http://<IP of the Pi>:{a.port}/   (or the https address of the tunnel)")
    print("On the PC:  python pc_client.py --host <IP of the Pi> --port "
          f"{a.port} --token {token} run")
    print("(The IP of the Pi: type  hostname -I  on the Pi.)  Ctrl+C stops the server.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopping ...")
    finally:
        job.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
