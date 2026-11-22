"""Render SVG figures to PNG, export the report to PDF, and make QA screenshots."""
import sys, os, re, glob, shutil, zipfile, tempfile, subprocess, pathlib
sys.stdout.reconfigure(encoding='utf-8')
import fitz

OUT = r"C:\Users\86187\WorkBuddy\2026-11-22-21-56-35\outputs"
FIG = os.path.join(OUT, "figures")
QA = os.path.join(OUT, "_qa")
os.makedirs(QA, exist_ok=True)
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
profile = tempfile.mkdtemp(prefix="edge_render_")


def uri(p):
    return pathlib.Path(p).as_uri()


def edge(args, timeout=240):
    cmd = [EDGE, "--headless=new", "--disable-gpu", "--no-first-run",
           "--no-default-browser-check", "--user-data-dir=" + profile] + args
    r = subprocess.run(cmd, capture_output=True, timeout=timeout)
    if r.returncode != 0:
        print("EDGE WARN", r.returncode, r.stderr.decode("utf-8", "ignore")[:400])
    return r


# ---- figures -> PNG ----
for svg_path in sorted(glob.glob(os.path.join(FIG, "*.svg"))):
    name = os.path.splitext(os.path.basename(svg_path))[0]
    content = open(svg_path, encoding="utf-8").read()
    m = re.search(r'viewBox="0 0 (\d+) (\d+)"', content)
    W, H = int(m.group(1)), int(m.group(2))
    wrap = ('<!DOCTYPE html><html><head><meta charset="utf-8">'
            '<style>html,body{margin:0;padding:0;background:#fff}svg{display:block}</style>'
            '</head><body>' + content + '</body></html>')
    wrap_path = os.path.join(QA, "_wrap_" + name + ".html")
    open(wrap_path, "w", encoding="utf-8").write(wrap)
    png = os.path.join(FIG, name + ".png")
    edge(["--hide-scrollbars", "--screenshot=" + png,
          "--window-size=%d,%d" % (W, H), "--force-device-scale-factor=2",
          uri(wrap_path)])
    ok = os.path.exists(png) and os.path.getsize(png) > 1000
    print(name, "->", os.path.getsize(png) if os.path.exists(png) else 0, "bytes", "OK" if ok else "FAIL")

# ---- report -> PDF ----
pdf = os.path.join(OUT, "report.pdf")
edge(["--no-pdf-header-footer", "--print-to-pdf=" + pdf,
      uri(os.path.join(OUT, "report.html"))], timeout=300)
print("report.pdf", os.path.getsize(pdf) if os.path.exists(pdf) else "MISSING")

# ---- QA screenshots from the PDF ----
if os.path.exists(pdf):
    doc = fitz.open(pdf)
    print("PDF pages:", doc.page_count)
    for i in range(doc.page_count):
        page = doc[i]
        pix = page.get_pixmap(matrix=fitz.Matrix(1.6, 1.6), alpha=False)
        p = os.path.join(QA, "page_%02d.png" % (i + 1))
        pix.save(p)
        print("  qa", p, pix.width, "x", pix.height)
    doc.close()

# ---- bundle ----
zpath = os.path.join(OUT, "Section7_Mechanism_Welfare.zip")
if os.path.exists(zpath):
    os.remove(zpath)
with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
    for root, dirs, files in os.walk(OUT):
        dirs[:] = [d for d in dirs if d not in ("_qa", "__pycache__")]
        for fn in files:
            if fn.endswith((".zip", ".pyc")) or fn.startswith("_"):
                continue
            full = os.path.join(root, fn)
            z.write(full, os.path.relpath(full, OUT))
print("zip", zpath, os.path.getsize(zpath), "bytes")
shutil.rmtree(profile, ignore_errors=True)
