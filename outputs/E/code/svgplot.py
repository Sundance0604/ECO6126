"""Minimal black-and-white SVG charting for the report.

All charts are monochrome (grey levels + line styles), no bold or italic
type, sized for journal-style reproduction.
"""
import math

PALETTE = [
    ("#000000", "", "o"),
    ("#3d3d3d", "7 3", "s"),
    ("#6e6e6e", "2 2", "^"),
    ("#939393", "9 2 2 2", "v"),
]


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def nice(lo, hi, n=5):
    if hi <= lo:
        hi = lo + 1.0
    raw = (hi - lo) / n
    mag = 10 ** math.floor(math.log10(raw))
    for step in (1, 2, 2.5, 5, 10):
        if raw / mag <= step:
            s = step * mag
            break
    else:
        s = 10 * mag
    a = math.floor(lo / s) * s
    b = math.ceil(hi / s) * s
    ticks = []
    x = a
    while x <= b + s * 0.5:
        ticks.append(round(x, 10))
        x += s
    return ticks


def fmt(v):
    if abs(v - round(v)) < 1e-9:
        return "%.0f" % v
    if abs(v) >= 1000:
        return "%.0f" % v
    if abs(v) >= 1:
        return "%.1f" % v
    return "%.2f" % v


def marker(m, x, y, color, size=3.0):
    if m == "none":
        return ""
    if m == "o":
        return '<circle cx="%.2f" cy="%.2f" r="%.2f" fill="%s"/>' % (x, y, size, color)
    if m == "s":
        return '<rect x="%.2f" y="%.2f" width="%.2f" height="%.2f" fill="%s"/>' % (
            x - size, y - size, 2 * size, 2 * size, color)
    if m == "^":
        return '<polygon points="%.2f,%.2f %.2f,%.2f %.2f,%.2f" fill="%s"/>' % (
            x, y - size, x - size, y + size, x + size, y + size, color)
    return '<polygon points="%.2f,%.2f %.2f,%.2f %.2f,%.2f" fill="%s"/>' % (
        x, y + size, x - size, y - size, x + size, y - size, color)


def panel_svg(p, W, H):
    """p: dict with title, xlabel, ylabel, series, type, xlim, ylim, xticks, yticks, legend"""
    L, R, T, B = 66, 16, 46, 46
    pw, ph = W - L - R, H - T - B
    s = p.get("series", [])
    ptype = p.get("type", "line")

    allx, ally = [], []
    for ser in s:
        allx += list(ser.get("x", []))
        ally += list(ser.get("y", []))
        if "ci" in ser:
            for v in ser["ci"]:
                ally.append(v)
    if not allx:
        allx = [0]
    if not ally:
        ally = [0]
    xmin, xmax = p.get("xlim", (min(allx), max(allx)))
    ymin, ymax = p.get("ylim", (min(ally), max(ally)))
    if ymin == ymax:
        ymax = ymin + 1
    pad = (ymax - ymin) * 0.08
    ymin_plot, ymax_plot = ymin - pad, ymax + pad
    if p.get("zero_base") and ymin > 0:
        ymin_plot = 0.0
    xt = p.get("xticks", nice(xmin, xmax))
    yt = p.get("yticks", nice(ymin_plot, ymax_plot))

    def X(v):
        return L + (v - xmin) / (xmax - xmin) * pw

    def Y(v):
        return T + ph - (v - ymin_plot) / (ymax_plot - ymin_plot) * ph

    o = []
    o.append('<rect x="%d" y="%d" width="%d" height="%d" fill="#ffffff"/>' % (0, 0, W, H))
    o.append('<text x="%.1f" y="16" font-size="12" fill="#111">%s</text>' % (L, esc(p.get("title", ""))))
    # grid
    for v in yt:
        if v < ymin_plot or v > ymax_plot:
            continue
        o.append('<line x1="%.2f" y1="%.2f" x2="%.2f" y2="%.2f" stroke="#dcdcdc" stroke-width="0.7" stroke-dasharray="3 3"/>' % (L, Y(v), L + pw, Y(v)))
        ylab = p.get("yticklabels", {}).get(v, fmt(v))
        o.append('<text x="%.2f" y="%.2f" font-size="9.5" fill="#333" text-anchor="end">%s</text>' % (L - 7, Y(v) + 3.2, esc(ylab)))
    for v in xt:
        if v < xmin or v > xmax:
            continue
        o.append('<line x1="%.2f" y1="%.2f" x2="%.2f" y2="%.2f" stroke="#e6e6e6" stroke-width="0.6"/>' % (X(v), T + ph, X(v), T + ph + 4))
        xlab = p.get("xticklabels", {}).get(v, fmt(v))
        o.append('<text x="%.2f" y="%.2f" font-size="9.5" fill="#333" text-anchor="middle">%s</text>' % (X(v), T + ph + 16, esc(xlab)))
    # axes
    o.append('<line x1="%.2f" y1="%.2f" x2="%.2f" y2="%.2f" stroke="#111" stroke-width="0.9"/>' % (L, T, L, T + ph))
    o.append('<line x1="%.2f" y1="%.2f" x2="%.2f" y2="%.2f" stroke="#111" stroke-width="0.9"/>' % (L, T + ph, L + pw, T + ph))
    if ymin_plot < 0 < ymax_plot:
        o.append('<line x1="%.2f" y1="%.2f" x2="%.2f" y2="%.2f" stroke="#888" stroke-width="0.8"/>' % (L, Y(0), L + pw, Y(0)))
    # axis labels
    o.append('<text x="%.2f" y="%.2f" font-size="10.5" fill="#111" text-anchor="middle">%s</text>' % (L + pw / 2, H - 6, esc(p.get("xlabel", ""))))
    o.append('<text x="14" y="%.2f" font-size="10.5" fill="#111" text-anchor="middle" transform="rotate(-90 14 %.2f)">%s</text>' % (T + ph / 2, T + ph / 2, esc(p.get("ylabel", ""))))

    # body
    if ptype == "line":
        for k, ser in enumerate(s):
            color, dash, mk = PALETTE[k % len(PALETTE)]
            if ser.get("color"):
                color = ser["color"]
            if "dash" in ser:
                dash = ser["dash"]
            if ser.get("marker"):
                mk = ser["marker"]
            xs, ys = ser["x"], ser["y"]
            pts = " ".join("%.2f,%.2f" % (X(a), Y(b)) for a, b in zip(xs, ys))
            da = ' stroke-dasharray="%s"' % dash if dash else ""
            o.append('<polyline points="%s" fill="none" stroke="%s" stroke-width="1.7"%s/>' % (pts, color, da))
            if ser.get("band"):
                lo, hi = ser["band"]
                poly = " ".join("%.2f,%.2f" % (X(a), Y(b)) for a, b in zip(xs, hi))
                poly += " " + " ".join("%.2f,%.2f" % (X(a), Y(b)) for a, b in zip(reversed(xs), reversed(lo)))
                o.append('<polygon points="%s" fill="%s" fill-opacity="0.10" stroke="none"/>' % (poly, color))
            step = max(1, int(len(xs) / 22))
            for a, b in list(zip(xs, ys))[::step]:
                o.append(marker(mk, X(a), Y(b), color, 2.6))
    elif ptype == "stacked":
        # series are cumulative shares, draw filled bands bottom-up
        prev = [0.0] * len(s[0]["x"])
        fills = ["#ffffff", "#c9c9c9", "#8a8a8a", "#4a4a4a"]
        for k, ser in enumerate(s):
            xs, ys = ser["x"], ser["y"]
            upper = [(a + b) for a, b in zip(prev, ys)]
            poly = " ".join("%.2f,%.2f" % (X(a), Y(b)) for a, b in zip(xs, upper))
            poly += " " + " ".join("%.2f,%.2f" % (X(a), Y(b)) for a, b in zip(reversed(xs), reversed(prev)))
            o.append('<polygon points="%s" fill="%s" stroke="#111" stroke-width="0.6"/>' % (poly, fills[k % len(fills)]))
            prev = upper
    elif ptype == "bar":
        groups = p.get("groups", [])
        gw = pw / max(len(groups), 1)
        bw = gw / (len(s) + 1.2)
        # s[k]["y"] length = number of groups; groups labelled by xticks
        for k, ser in enumerate(s):
            color, dash, mk = PALETTE[k % len(PALETTE)]
            for gi, val in enumerate(ser["y"]):
                cx = L + (gi + 0.5) * gw
                bx = cx - (len(s) * bw) / 2 + k * bw
                y0, y1 = Y(0), Y(val)
                top = min(y0, y1)
                h = abs(y1 - y0)
                fill = color if k == 0 else ("#c0c0c0" if k == 1 else "#808080")
                o.append('<rect x="%.2f" y="%.2f" width="%.2f" height="%.2f" fill="%s" stroke="#111" stroke-width="0.6"/>' % (bx, top, bw * 0.88, h, fill))
    elif ptype == "scatter":
        for k, ser in enumerate(s):
            color, dash, mk = PALETTE[k % len(PALETTE)]
            for a, b in zip(ser["x"], ser["y"]):
                o.append(marker("o", X(a), Y(b), color, 1.7))
            if ser.get("fit"):
                (x0, y0), (x1, y1) = ser["fit"]
                o.append('<line x1="%.2f" y1="%.2f" x2="%.2f" y2="%.2f" stroke="%s" stroke-width="1.6"%s/>' % (
                    X(x0), Y(y0), X(x1), Y(y1), color,
                    ' stroke-dasharray="%s"' % dash if dash else ""))
    elif ptype == "coef":
        for k, ser in enumerate(s):
            color, dash, mk = PALETTE[k % len(PALETTE)]
            for a, b, lo, hi in zip(ser["x"], ser["y"], ser["lo"], ser["hi"]):
                o.append('<line x1="%.2f" y1="%.2f" x2="%.2f" y2="%.2f" stroke="%s" stroke-width="1.1"/>' % (X(lo), Y(b), X(hi), Y(b), color))
                o.append('<line x1="%.2f" y1="%.2f" x2="%.2f" y2="%.2f" stroke="%s" stroke-width="1.1"/>' % (X(lo), Y(b) - 4, X(lo), Y(b) + 4, color))
                o.append('<line x1="%.2f" y1="%.2f" x2="%.2f" y2="%.2f" stroke="%s" stroke-width="1.1"/>' % (X(hi), Y(b) - 4, X(hi), Y(b) + 4, color))
                o.append(marker(mk, X(a), Y(b), color, 3.4))
        if 0 >= xmin and 0 <= xmax:
            o.append('<line x1="%.2f" y1="%.2f" x2="%.2f" y2="%.2f" stroke="#888" stroke-width="0.8" stroke-dasharray="4 3"/>' % (X(0), T, X(0), T + ph))

    # legend (two rows when there are four or more series)
    if p.get("legend", True) and s:
        two_rows = len(s) >= 4
        per = 2 if two_rows else len(s)
        for k, ser in enumerate(s):
            color, dash, mk = PALETTE[k % len(PALETTE)]
            col, rowi = k % per, k // per
            xx = L + 4 + col * (pw / per)
            yy = (T - 20 + rowi * 11) if two_rows else (T - 8)
            da = ' stroke-dasharray="%s"' % dash if dash else ""
            o.append('<line x1="%.2f" y1="%.2f" x2="%.2f" y2="%.2f" stroke="%s" stroke-width="1.7"%s/>' % (xx, yy - 3, xx + 16, yy - 3, color, da))
            o.append(marker(ser.get("marker", mk), xx + 8, yy - 3, color, 2.4))
            o.append('<text x="%.2f" y="%.2f" font-size="9.0" fill="#222">%s</text>' % (xx + 20, yy, esc(ser.get("label", ""))))
    return "\n".join(o)


def compose(panels, cols=2, pw=360, ph=270, title=None):
    rows = math.ceil(len(panels) / cols)
    W, H = cols * pw, rows * ph
    o = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" width="%d" height="%d" font-family="Helvetica, Arial, sans-serif">' % (W, H, W, H)]
    o.append('<rect width="100%" height="100%" fill="#ffffff"/>')
    for k, p in enumerate(panels):
        x = (k % cols) * pw
        y = (k // cols) * ph
        o.append('<g transform="translate(%d,%d)">' % (x, y))
        o.append(panel_svg(p, pw, ph))
        o.append('</g>')
    o.append('</svg>')
    return "\n".join(o)
