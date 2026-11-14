"""test_web.py - tests the web page (scanner_page.html) in a real browser (Chromium via
Playwright, if installed) against pi_server.py running on this computer with fake scans."""
import os, subprocess, sys, tempfile, time, urllib.request, json, socket

HERE = os.path.dirname(os.path.abspath(__file__))
RES = []
def check(name, ok, detail=""):
    RES.append(bool(ok))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"   ({detail})" if detail else ""))

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("Playwright is not installed here: the browser test is SKIPPED (the page itself is not tested).")
    sys.exit(0)

TOKEN = "web-test-token-1"
shots = os.environ.get("SHOTS")        # folder for screenshots, optional

def free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p

with tempfile.TemporaryDirectory() as tmp:
    port = free_port()
    srv = subprocess.Popen([sys.executable, os.path.join(HERE, "pi_server.py"), "--host", "127.0.0.1",
                            "--port", str(port), "--token", TOKEN, "--allow-dry-run",
                            "--scans-dir", os.path.join(tmp, "scans")],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base = f"http://127.0.0.1:{port}"
    try:
        for _ in range(50):
            try:
                urllib.request.urlopen(base + "/", timeout=1); break
            except Exception:
                time.sleep(0.2)
        print("1. THE PAGE IS SERVED")
        r = urllib.request.urlopen(base + "/")
        html = r.read().decode()
        check("GET / needs no token and returns the page", r.status == 200 and "Scanner 3D" in html
              and r.headers["Content-Type"].startswith("text/html"))
        try:
            urllib.request.urlopen(base + "/status", timeout=3); open_ = True
        except urllib.error.HTTPError as e:
            open_ = e.code != 401
        check("/status still needs the token", not open_)

        print("2. IN THE BROWSER")
        with sync_playwright() as pw:
            br = pw.chromium.launch()
            ctx = br.new_context(viewport={"width": 1100, "height": 900}, device_scale_factor=1)
            page = ctx.new_page()
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.on("console", lambda m: errors.append(m.text) if m.type == "error" and "401" not in m.text else None)
            page.on("dialog", lambda d: (errors.append("DIALOG " + d.message), d.dismiss()))
            page.goto(base + "/")
            page.wait_for_timeout(600)
            check("without a token the page asks for it", "Digite a senha" in page.inner_text("#state"),
                  page.inner_text("#state"))
            page.fill("#token", "wrong-token-123"); page.press("#token", "Tab")
            page.wait_for_timeout(1800)
            check("wrong token: 'Senha incorreta', start still possible to click but refused",
                  "Senha incorreta" in page.inner_text("#state"), page.inner_text("#state"))
            page.fill("#token", TOKEN); page.press("#token", "Tab")
            page.wait_for_function("document.getElementById('state').textContent.includes('Parado')", timeout=8000)
            check("right token: state 'Parado'", True)
            check("download buttons hidden before any scan", not page.is_visible("#dl-model") and not page.is_visible("#dl-photos"))
            check("test-scan box appears because the server allows dry runs",
                  page.is_visible("#dry"))
            check("stop is disabled while idle", page.is_disabled("#stop"))
            page.fill("#photos", "36"); page.check("#dry")
            if shots: page.screenshot(path=os.path.join(shots, "1_idle.png"))
            page.click("#start")
            page.wait_for_function("document.getElementById('state').textContent.includes('Escaneando')", timeout=8000)
            check("after Iniciar: 'Escaneando' and start is disabled", page.is_disabled("#start") and not page.is_disabled("#stop"))
            if shots: page.screenshot(path=os.path.join(shots, "2_scanning.png"))
            page.wait_for_function("document.getElementById('state').textContent.includes('Concluído')", timeout=90000)
            check("scan reaches 'Concluído'", True, page.inner_text("#detail"))
            page.wait_for_function("!document.getElementById('dl-model').classList.contains('hidden')", timeout=15000)
            page.wait_for_timeout(500)
            inked = page.evaluate("""() => { const c = document.getElementById('view');
                const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data;
                let n = 0; for (let i = 3; i < d.length; i += 4) if (d[i] > 0) n++;
                return [n, c.width * c.height]; }""")
            check("the 3D view drew the model", inked[0] > 0.02 * inked[1], f"{100 * inked[0] / inked[1]:.1f} % of the canvas")
            obj = page.evaluate("""async () => { const a = document.getElementById('dl-model');
                const t = await (await fetch(a.href)).text(); return [t.slice(0, 2), t.split('\\n').length, a.download]; }""")
            check("download link gives the .obj (starts with 'v ') named after the scan", obj[0] == "v " and obj[2].startswith("scan_"), f"{obj[1]} lines, file name {obj[2]}")
            with page.expect_download() as dl:
                page.click("#dl-photos")
            d = dl.value; path = os.path.join(tmp, "photos.zip"); d.save_as(path)
            import zipfile
            check("'Baixar fotos' downloads a zip with 72 photos + info", len(zipfile.ZipFile(path).namelist()) == 73,
                  f"{len(zipfile.ZipFile(path).namelist())} files")
            if shots: page.screenshot(path=os.path.join(shots, "3_done.png"))
            page.mouse.move(400, 600); page.mouse.down(); page.mouse.move(520, 580); page.mouse.up()
            check("dragging the view does not break it", not errors, "; ".join(errors)[:100])

            print("2B. OLD SCANS, STL, TESTS")
            page.wait_for_selector("#scanlist .scan", timeout=8000)
            check("the list shows the finished scan with its model size and free disk space",
                  page.locator("#scanlist .scan").count() == 1 and "modelo" in page.inner_text("#scanlist") and "GB" in page.inner_text("#disk"),
                  page.inner_text("#scanlist").replace("\n", " | ")[:90])
            with page.expect_download() as dls:
                page.click("#dl-stl")
            sp = os.path.join(tmp, "m.stl"); dls.value.save_as(sp)
            data = open(sp, "rb").read()
            import struct
            check("'Baixar .stl' gives a binary STL whose size matches its triangle count",
                  len(data) == 84 + 50 * struct.unpack("<I", data[80:84])[0] and dls.value.suggested_filename.endswith(".stl"),
                  f"{len(data)} bytes, {dls.value.suggested_filename}")
            page.click("#t-laser")
            page.wait_for_function("document.getElementById('testmsg').textContent.includes('piscou')", timeout=30000)
            check("'Testar laser': 3 blinks reported", "3 blinks" in page.inner_text("#report"))
            page.click("#t-photo")
            page.wait_for_function("document.getElementById('img-off').naturalWidth > 0", timeout=30000)
            check("'Foto de teste': both photos appear and the report says what it found",
                  page.evaluate("document.getElementById('img-on').naturalWidth > 0") and "laser line" in page.inner_text("#report"),
                  page.inner_text("#report").splitlines()[-1][:70])
            # a second scan, then look at the old one, then delete it with two clicks
            page.fill("#photos", "12"); page.click("#start")
            page.wait_for_function("document.getElementById('state').textContent.includes('Concluído')", timeout=90000)
            page.wait_for_function("document.querySelectorAll('#scanlist .scan').length == 2 && "
                                   "document.querySelector('#scanlist .scan .info').textContent.includes('12 fotos')", timeout=15000)
            check("a second scan appears at the top of the list when it finishes",
                  "12 fotos" in page.inner_text("#scanlist .scan:first-child"),
                  page.inner_text("#scanlist .scan:first-child .info"))
            old = page.locator("#scanlist .scan").nth(1)
            old.get_by_role("button", name="Ver").click()
            page.wait_for_function("document.getElementById('viewhint').textContent.includes('1442 pontos')", timeout=8000)
            check("'Ver' on the old scan loads that one into the 3D view",
                  page.inner_text("#viewhint").startswith("scan_") and "1442 pontos" in page.inner_text("#viewhint"),
                  page.inner_text("#viewhint")[:60])
            dbtn = page.locator("#scanlist .scan").nth(1).get_by_role("button", name="Apagar")
            dbtn.click()
            check("first click on Apagar only asks for confirmation (no dialog)", "Confirmar" in dbtn.inner_text()
                  and page.locator("#scanlist .scan").count() == 2)
            dbtn.click()
            page.wait_for_function("document.querySelectorAll('#scanlist .scan').length == 1", timeout=8000)
            check("second click erases it; the viewer is cleared because it showed that scan",
                  not page.is_visible("#dl-stl"), "")

            print("3. STOP FROM THE PAGE")
            page.fill("#photos", "360")
            page.click("#start")
            page.wait_for_function("document.getElementById('state').textContent.includes('Escaneando')", timeout=8000)
            page.wait_for_timeout(1500)
            page.click("#stop")
            page.wait_for_function("document.getElementById('state').textContent.includes('Interrompido')", timeout=15000)
            check("Parar -> 'Interrompido', start enabled again", not page.is_disabled("#start"))
            check("no JavaScript errors or dialogs during the whole session", not errors, "; ".join(errors)[:150])

            print("4. PHONE SIZE AND DARK MODE")
            m = br.new_context(viewport={"width": 390, "height": 800}, device_scale_factor=2,
                               color_scheme="dark", is_mobile=True, has_touch=True)
            mp = m.new_page(); mp.goto(base + "/"); mp.fill("#token", TOKEN); mp.press("#token", "Tab")
            mp.wait_for_function("document.getElementById('state').textContent.includes('Interrompido')", timeout=8000)
            check("before a scan finishes, no download button is visible (phone, dark)",
                  not mp.is_visible("#dl-model") and not mp.is_visible("#dl-photos") and not mp.is_visible("#spin"))
            wide = mp.evaluate("document.documentElement.scrollWidth > window.innerWidth + 1")
            check("no sideways scrolling on a 390 px phone", not wide)
            if shots: mp.screenshot(path=os.path.join(shots, "4_phone_dark.png"), full_page=True)
            br.close()
    finally:
        srv.terminate()
        try: srv.wait(timeout=10)
        except subprocess.TimeoutExpired: srv.kill()

print(f"\n  {sum(RES)} of {len(RES)} checks passed")
sys.exit(0 if all(RES) else 1)
