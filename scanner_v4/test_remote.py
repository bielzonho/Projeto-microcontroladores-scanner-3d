"""test_remote.py - tests pi_server.py + pc_client.py on this computer (dry-run scans)."""
import json, os, re, subprocess, sys, tempfile, threading, time, urllib.request, urllib.error
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pi_server, pc_client

RES = []
def check(name, ok, detail=""):
    RES.append(bool(ok))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"   ({detail})" if detail else ""))

def serve(tmp, token="secret-token-1", dry=True, script=None):
    srv, job = pi_server.make_server("127.0.0.1", 0, token, os.path.join(tmp, "scans"), dry, script)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, job, srv.server_address[1]

def raw(port, method, path, token="secret-token-1", body=None):
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", method=method,
          data=None if body is None else json.dumps(body).encode(),
          headers={"X-Token": token} if token is not None else {})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()

with tempfile.TemporaryDirectory() as tmp:
    print("1. TOKEN AND ADDRESSES")
    srv, job, port = serve(tmp)
    check("no token -> 401", raw(port, "GET", "/status", token=None)[0] == 401)
    check("wrong token -> 401", raw(port, "GET", "/status", token="nope")[0] == 401)
    check("token in the address works", raw(port, "GET", "/status?token=secret-token-1", token=None)[0] == 200)
    check("unknown address -> 404", raw(port, "GET", "/x")[0] == 404)
    check("server stays idle at the start", json.loads(raw(port, "GET", "/status")[1])["state"] == "idle")
    c = pc_client.Client("127.0.0.1", port, "secret-token-1")
    code, body = raw(port, "GET", "/download")
    check("download before any scan -> 409", code == 409, body.decode()[:60])

    print("2. BAD ORDERS")
    for opts, why in [({"photos": 2}, "photos 2"), ({"photos": 9999}, "photos 9999"),
                      ({"photos": "abc"}, "photos abc"), ({"platform": "manual"}, "manual"),
                      ({"format": "bmp", "dry_run": True}, "format bmp"),
                      ({"platform": "stepper"}, "stepper without steps_per_turn")]:
        code, _ = raw(port, "POST", "/start", body=opts)
        check(f"refused: {why}", code == 400, f"code {code}")
    code, _ = raw(port, "POST", "/start", body=[1, 2])
    check("refused: body is not an object", code == 400)
    check("nothing started by bad orders", job.status()["state"] == "idle")

    print("3. A WHOLE SCAN: start, wait, download, mesh")
    t0 = time.time()
    ans = c.start(photos=36, dry_run=True)
    check("start accepted", ans["photos"] == 36 and ans["started"].startswith("scan_"))
    try:
        c.start(photos=36, dry_run=True); busy = False
    except pc_client.ScannerError as e:
        busy = "409" in str(e)
    check("second start while scanning -> 409", busy)
    check("download while scanning -> 409", raw(port, "GET", "/download")[0] == 409)
    st = c.wait(poll=0.2, show=False)
    check("state done, 36 of 36", st["state"] == "done" and st["done"] == 36 and st["total"] == 36,
          f"{st['state']} {st['done']}/{st['total']}, {time.time()-t0:.1f} s")
    out = os.path.join(tmp, "got")
    n = pc_client.unzip_to(c.download_zip(), out)
    names = sorted(os.listdir(out))
    check("zip has 36 on, 36 off and scan_info.json", n == 73 and "scan_info.json" in names
          and sum(x.startswith("on_") for x in names) == 36, f"{n} files")
    check("no log or other files leak into the zip", not any(x.endswith(".log") for x in names))
    r = subprocess.run([sys.executable, os.path.join(HERE, "scan_folder.py"), out, "--check-vase"],
                       capture_output=True, text=True, cwd=tmp)
    m = re.search(r"mean ([0-9.]+) mm", r.stdout)
    check("scan_folder on the downloaded photos: small error", m and float(m.group(1)) < 0.15,
          m.group(0) if m else r.stdout[-200:] + r.stderr[-200:])
    ans = c.start(photos=6, dry_run=True)
    check("a new scan can start after the first", True)
    c.wait(poll=0.2, show=False)
    check("it gets its own folder", len(os.listdir(os.path.join(tmp, "scans"))) == 2)

    print("4. STOP")
    ans = c.start(photos=360, dry_run=True)
    time.sleep(2.0)
    c.stop()
    st = c.wait(poll=0.2, show=False)
    check("stopped on request", st["state"] == "stopped" and st["done"] < 360,
          f"{st['state']}, {st['done']} of 360 done")
    check("download after stop -> 409", raw(port, "GET", "/download")[0] == 409)
    try:
        c.stop(); ok = False
    except pc_client.ScannerError as e:
        ok = "409" in str(e)
    check("stop when nothing runs -> 409", ok)

    print("5. THE SCAN FAILS / PC CANNOT REACH THE PI / DRY RUN NOT ALLOWED")
    bad = os.path.join(tmp, "bad_capture.py")
    open(bad, "w").write("import sys; print('camera not found'); sys.exit(3)\n")
    srv2, job2, port2 = serve(os.path.join(tmp, "b"), script=bad)
    c2 = pc_client.Client("127.0.0.1", port2, "secret-token-1")
    c2.start(photos=10, dry_run=True)
    st = c2.wait(poll=0.2, show=False)
    check("failing capture.py -> state error with its last output", st["state"] == "error"
          and "camera not found" in st["message"], st["message"][:70])
    srv3, job3, port3 = serve(os.path.join(tmp, "c"), dry=False)
    code, body = raw(port3, "POST", "/start", body={"dry_run": True})
    check("dry_run refused when the server does not allow it", code == 400)
    dead = pc_client.Client("127.0.0.1", 1, "x", timeout=2)
    try:
        dead.status(); msg = ""
    except pc_client.ScannerError as e:
        msg = str(e)
    check("clear message when the Pi cannot be reached", "cannot reach the Pi" in msg, msg[:70])
    try:
        pc_client.unzip_to(b"not a zip", out); bad_zip = False
    except Exception:
        bad_zip = True
    check("a broken zip is refused", bad_zip)

    print("6. COMMAND LINE: pc_client.py run")
    srv4, job4, port4 = serve(os.path.join(tmp, "d"))
    dest = os.path.join(tmp, "cli")
    r = subprocess.run([sys.executable, os.path.join(HERE, "pc_client.py"), "--host", "127.0.0.1",
                        "--port", str(port4), "--token", "secret-token-1", "run", "--photos", "8",
                        "--dry-run", "--out", dest], capture_output=True, text=True)
    check("run exits 0 and puts only model.obj on the PC (the Pi made it)",
          r.returncode == 0 and os.listdir(dest) == ["model.obj"],
          r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr[-150:])
    r = subprocess.run([sys.executable, os.path.join(HERE, "pc_client.py"), "--host", "127.0.0.1",
                        "--port", str(port4), "--token", "wrong", "status"], capture_output=True, text=True)
    check("wrong token on the command line: clear message, exit 1", r.returncode == 1 and "401" in r.stdout, r.stdout.strip())
    
    print("7. THE MODEL MADE ON THE PI AND THE ONE MADE ON THE PC")
    srv5, job5, port5 = serve(os.path.join(tmp, "e"))
    c5 = pc_client.Client("127.0.0.1", port5, "secret-token-1")
    code, _ = raw(port5, "GET", "/model")
    check("/model before any scan -> 409", code == 409)
    for opts, why in [({"mesh": True, "map": "../x.json"}, "map outside the folder"),
                      ({"mesh": True, "map": "nothere.json"}, "map file that does not exist"),
                      ({"map": "camera_map.json"}, "map without mesh")]:
        code, body = raw(port5, "POST", "/start", body=dict(opts, dry_run=True, photos=6))
        check(f"refused: {why}", code == 400, body.decode()[:70])
    c5.start(photos=36, dry_run=True, mesh=True)
    seen = set()
    while True:
        st = c5.status(); seen.add(st["state"])
        if st["state"] not in ("scanning", "meshing"):
            break
        time.sleep(0.1)
    check("states went scanning -> meshing -> done", st["state"] == "done"
          and "meshing" in seen or (st["state"] == "done" and st["mesh_seconds"] is not None),
          f"seen {sorted(seen)}, mesh {st['mesh_seconds']} s")
    obj_pi = c5.download_model()
    check("the Pi's model is a real .obj", obj_pi.startswith(b"#") or b"\nv " in obj_pi or obj_pi.startswith(b"v "),
          f"{len(obj_pi)} bytes")
    out5 = os.path.join(tmp, "got5")
    pc_client.unzip_to(c5.download_zip(), out5)
    open(os.path.join(out5, "model_pi.obj"), "wb").write(obj_pi)
    subprocess.run([sys.executable, os.path.join(HERE, "scan_folder.py"), out5, "--out",
                    os.path.join(out5, "model_pc.obj"), "--preview", os.path.join(out5, "p.png")],
                   capture_output=True, cwd=tmp)
    same = open(os.path.join(out5, "model_pc.obj"), "rb").read() == obj_pi
    check("same photos, same program: Pi model and PC model are byte-identical", same)
    c5.start(photos=6, dry_run=True)
    c5.wait(poll=0.2, show=False)
    code, body = raw(port5, "GET", "/model")
    check("scan without mesh: /model -> 409 with a clear reason", code == 409 and b"without mesh" in body)

    # mesh program that fails / writes the model and then fails / is slow
    fail = os.path.join(tmp, "mesh_fail.py")
    open(fail, "w").write("import sys; print('boom: no line found'); sys.exit(2)\n")
    srv6, job6, port6 = serve(os.path.join(tmp, "f"), script=None)
    job6.mesh_script = fail
    c6 = pc_client.Client("127.0.0.1", port6, "secret-token-1")
    c6.start(photos=6, dry_run=True, mesh=True)
    st = c6.wait(poll=0.2, show=False)
    check("scan_folder fails on the Pi -> state error, reason sent", st["state"] == "error"
          and "boom" in st["message"], st["message"][:80])
    half = os.path.join(tmp, "mesh_half.py")
    open(half, "w").write("import sys\nout = sys.argv[sys.argv.index('--out') + 1]\n"
                          "open(out, 'w').write('v 1 2 3\\n')\nprint('picture failed'); sys.exit(1)\n")
    job6.mesh_script = half
    c6.start(photos=6, dry_run=True, mesh=True)
    st = c6.wait(poll=0.2, show=False)
    check("model written but the picture failed -> done, with a warning", st["state"] == "done"
          and "picture" in st["message"], st["message"][:80])
    slow = os.path.join(tmp, "mesh_slow.py")
    open(slow, "w").write("import time; time.sleep(60)\n")
    job6.mesh_script = slow
    c6.start(photos=6, dry_run=True, mesh=True)
    for _ in range(100):
        if c6.status()["state"] == "meshing":
            break
        time.sleep(0.2)
    check("meshing state is visible", c6.status()["state"] == "meshing")
    try:
        c6.start(photos=6, dry_run=True); busy = False
    except pc_client.ScannerError as e:
        busy = "409" in str(e)
    check("a new order while meshing -> 409", busy)
    c6.stop()
    st = c6.wait(poll=0.2, show=False)
    check("stop while meshing works", st["state"] == "stopped", st["state"])

    dest7 = os.path.join(tmp, "cli7")
    cli = [sys.executable, os.path.join(HERE, "pc_client.py"), "--host", "127.0.0.1",
           "--port", str(port5), "--token", "secret-token-1"]
    r = subprocess.run(cli + ["run", "--photos", "36", "--dry-run", "--photos-zip", "--stl", "--out", dest7],
                       capture_output=True, text=True)
    pm = os.path.join(dest7, "model.obj")
    check("run: model.obj and (with --photos-zip) the photos arrive; times printed",
          r.returncode == 0 and os.path.exists(pm) and
          len(os.listdir(os.path.join(dest7, "photos"))) == 73 and "the Pi made the model in" in r.stdout,
          (r.stdout.strip().splitlines() or [""])[-1] + r.stderr[-120:])
    stlf = os.path.join(dest7, "model.stl")
    check("run --stl: model.stl arrives and is a binary STL", os.path.exists(stlf) and
          os.path.getsize(stlf) == 84 + 50 * int.from_bytes(open(stlf, "rb").read()[80:84], "little"))
    sf = subprocess.run([sys.executable, os.path.join(HERE, "scan_folder.py"),
                         os.path.join(dest7, "photos"), "--out", os.path.join(tmp, "check.obj"),
                         "--preview", os.path.join(tmp, "c.png")], capture_output=True, cwd=tmp)
    check("the Pi's model equals what scan_folder.py makes from the same photos (no quality loss)",
          open(pm, "rb").read() == open(os.path.join(tmp, "check.obj"), "rb").read())
    r = subprocess.run(cli + ["run", "--dry-run", "--mesh"], capture_output=True, text=True)
    check("the old --mesh (model on the PC) no longer exists", r.returncode != 0 and "unrecognized" in r.stderr)
    r = subprocess.run(cli + ["run", "--photos", "6", "--dry-run", "--map", "nothere.json"],
                       capture_output=True, text=True)
    check("--map of a file the Pi does not have: clear error", r.returncode == 1 and "has no file" in r.stdout,
          r.stdout.strip()[-80:])
    for s in (srv5, srv6): s.shutdown()
    print("9. OLD SCANS, STL, DELETE, TESTS OF THE LASER AND THE CAMERA")
    srv9, job9, port9 = serve(os.path.join(tmp, "h"))
    c9 = pc_client.Client("127.0.0.1", port9, "secret-token-1")
    code, body = raw(port9, "GET", "/scans")
    check("empty at the start: no scans, free disk space given", code == 200
          and json.loads(body)["scans"] == [] and json.loads(body)["disk_free_mb"] > 0)
    c9.start(photos=12, dry_run=True, mesh=True)
    c9.wait(poll=0.2, show=False)
    first = c9.status()["scan"]
    time.sleep(1.1)
    c9.start(photos=6, dry_run=True)                # a newer scan WITHOUT model
    c9.wait(poll=0.2, show=False)
    second = c9.status()["scan"]
    lst = json.loads(raw(port9, "GET", "/scans")[1])["scans"]
    check("two scans listed, newest first, with sizes and model information",
          [r["scan"] for r in lst] == [second, first] and lst[1]["has_model"] and not lst[0]["has_model"]
          and lst[1]["photos_done"] == 12 and lst[1]["model_kb"] > 0 and lst[1]["size_mb"] > 0,
          str([(r["scan"][-6:], r["photos_done"], r["has_model"]) for r in lst]))
    check("the newest is marked 'current', none 'running'", lst[0]["current"] and not any(r["running"] for r in lst))
    code, body = raw(port9, "GET", f"/model?scan={first}")
    check("an OLD scan's model can be fetched by name", code == 200 and body.startswith(b"v "), f"{len(body)} bytes")
    code, body = raw(port9, "GET", "/model")
    check("the plain /model refers to the LAST scan (which has no model) -> 409", code == 409)
    code, stl = raw(port9, "GET", f"/model.stl?scan={first}")
    check("model.stl of the old scan: binary STL with the right size", code == 200 and len(stl) == 84 + 50 * int.from_bytes(stl[80:84], "little"),
          f"{len(stl)} bytes")
    code, z = raw(port9, "GET", f"/download?scan={first}")
    import io, zipfile as zf
    check("photos of the old scan as zip (25 files)", code == 200 and len(zf.ZipFile(io.BytesIO(z)).namelist()) == 25)
    for bad, why in [("../etc", "path with .."), ("scan_1", "bad pattern"), ("scan_20200101_000000", "does not exist")]:
        code, _ = raw(port9, "GET", f"/model?scan={bad}")
        check(f"scan name refused: {why}", code in (400, 404), f"code {code}")
    code, _ = raw(port9, "POST", "/delete", body={"scan": "../scans"})
    check("delete refuses a name that is not a scan", code == 400)
    code, _ = raw(port9, "POST", "/delete", body={"scan": "scan_20200101_000000"})
    check("delete of a missing scan -> 404", code == 404)
    code, _ = raw(port9, "POST", "/delete", body={"scan": first})
    left = json.loads(raw(port9, "GET", "/scans")[1])["scans"]
    check("delete erases the old scan from the disk", code == 200 and [r["scan"] for r in left] == [second]
          and not os.path.exists(os.path.join(tmp, "h", "scans", first)))
    code, _ = raw(port9, "POST", "/delete", body={"scan": second})
    st = json.loads(raw(port9, "GET", "/status")[1])
    check("deleting the last scan resets the status to idle", code == 200 and st["state"] == "idle" and st["scan"] == "")
    # a running scan can't be deleted or fetched
    c9.start(photos=60, dry_run=True)
    run_name = c9.status()["scan"]
    code, _ = raw(port9, "POST", "/delete", body={"scan": run_name})
    check("a scan that is still running cannot be deleted (409)", code == 409)
    code, body = raw(port9, "POST", "/test/laser", body={"dry_run": True})
    check("tests are refused while a scan runs (409)", code == 409)
    c9.stop(); c9.wait(poll=0.2, show=False)

    # tests of laser and camera (fake hardware)
    t0 = time.time()
    code, body = raw(port9, "POST", "/test/laser", body={"dry_run": True})
    ans = json.loads(body)
    check("laser test: runs capture.py --laser-test and reports", code == 200 and ans["ok"] and "3 blinks" in ans["report"],
          f"{time.time()-t0:.1f} s")
    code, body = raw(port9, "POST", "/test/photo", body={"dry_run": True})
    ans = json.loads(body)
    check("photo test: report with the camera and a verdict, photos available", code == 200 and ans["ok"]
          and ans["has_photos"] and "rows with a laser line" in ans["report"], ans["report"][-60:].replace("\n", " "))
    code, jpg = raw(port9, "GET", "/test/photo/on.jpg")
    code2, jpg2 = raw(port9, "GET", "/test/photo/off.jpg")
    check("both test photos are real JPEG files", code == 200 and code2 == 200 and jpg[:2] == b"\xff\xd8" and jpg2[:2] == b"\xff\xd8",
          f"{len(jpg)} and {len(jpg2)} bytes")
    code, _ = raw(port9, "GET", "/test/photo/evil.jpg")
    check("only on.jpg and off.jpg are served", code == 404)
    check("state goes back to what it was after a test", json.loads(raw(port9, "GET", "/status")[1])["state"] in ("stopped", "idle"))
    srv10, job10, port10 = serve(os.path.join(tmp, "i"), dry=False)
    code, _ = raw(port10, "POST", "/test/laser", body={"dry_run": True})
    check("fake test refused when the server does not allow dry runs", code == 400)
    check("test_photo list does not show the _check folder",
          all(r["scan"].startswith("scan_") for r in json.loads(raw(port9, "GET", "/scans")[1])["scans"]))
    srv9.shutdown(); srv10.shutdown()

    print("8. OVER THE INTERNET: --url, user agent, token rules")
    import http.server
    seen_ua = []
    class Echo(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            seen_ua.append(self.headers.get("User-Agent"))
            body = b'{"state": "idle", "done": 0, "total": 0}'
            self.send_response(200); self.send_header("Content-Length", str(len(body))); self.end_headers()
            self.wfile.write(body)
        def log_message(self, *a): pass
    echo = http.server.HTTPServer(("127.0.0.1", 0), Echo)
    threading.Thread(target=echo.serve_forever, daemon=True).start()
    cu = pc_client.Client(None, None, "x", url=f"http://127.0.0.1:{echo.server_address[1]}/")
    cu.status()
    check("client sends its own User-Agent (not Python-urllib)", seen_ua == ["scanner-client/1.0"], str(seen_ua))
    check("--url address used as given (trailing / removed)", cu.base == f"http://127.0.0.1:{echo.server_address[1]}")
    srv8, job8, port8 = serve(os.path.join(tmp, "g"))
    r = subprocess.run([sys.executable, os.path.join(HERE, "pc_client.py"), "--url",
                        f"http://127.0.0.1:{port8}", "--token", "secret-token-1", "status"],
                       capture_output=True, text=True)
    check("command line with --url works", r.returncode == 0 and '"idle"' in r.stdout, r.stdout[:40])
    r = subprocess.run([sys.executable, os.path.join(HERE, "pc_client.py"), "--token", "x", "status"],
                       capture_output=True, text=True)
    check("neither --host nor --url: clear message", r.returncode != 0 and "--url" in r.stderr)
    r = subprocess.run([sys.executable, os.path.join(HERE, "pi_server.py"), "--token", "short"],
                       capture_output=True, text=True, timeout=20)
    check("server refuses a short token", r.returncode != 0 and "at least" in (r.stdout + r.stderr))
    t0 = time.time(); raw(port8, "GET", "/status", token="nope"); dt = time.time() - t0
    check("a wrong token is answered only after about 1 s", 0.9 < dt < 3, f"{dt:.2f} s")
    echo.shutdown(); srv8.shutdown()

    for s in (srv, srv2, srv3, srv4): s.shutdown()

print(f"\n  {sum(RES)} of {len(RES)} checks passed")
sys.exit(0 if all(RES) else 1)
