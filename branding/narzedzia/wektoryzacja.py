"""Odtworzenie SVG z PNG (potrace, biblioteka potracer): osobny obrys dla każdego koloru znaku.

    python branding/narzedzia/wektoryzacja.py branding/logotyp-aedane.png branding/logotyp-aedane.svg '#00965E' '#1B266B'
    python branding/narzedzia/wektoryzacja.py branding/ikona-aedane-1024.png branding/ikona-aedane.svg '#00965E'

Zgodność z PNG sprawdzona po wyrenderowaniu SVG (rsvg-convert): ok. 98% pikseli znaku (IoU),
różnice to wygładzone krawędzie. Plik wyeksportowany z programu graficznego ma pierwszeństwo.
"""
import sys, numpy as np, potrace
from PIL import Image

def trace_color(arr, rgb, thr=0.5):
    # udział koloru w pikselu względem białego tła (antyaliasing) → maska
    a = arr[..., :3].astype(float)
    w = np.array([255, 255, 255], float); c = np.array(rgb, float)
    # rzut na odcinek biały→kolor
    t = ((a - w) @ (c - w)) / ((c - w) @ (c - w))
    # tylko piksele bliskie odcinkowi (nie innego koloru)
    proj = w + np.clip(t, 0, 1)[..., None] * (c - w)
    near = np.linalg.norm(a - proj, axis=-1) < 40
    if arr.shape[-1] == 4:
        t = np.where(arr[..., 3] < 128, 0, t)
    mask = (t > thr) & near
    bm = potrace.Bitmap(~mask)  # potracer: True = tło
    plist = bm.trace(turdsize=4, turnpolicy=potrace.POTRACE_TURNPOLICY_MINORITY, alphamax=1.0, opticurve=True, opttolerance=0.2)
    parts = []
    for curve in plist:
        s = curve.start_point
        d = [f"M{s.x:.2f},{s.y:.2f}"]
        for seg in curve.segments:
            if seg.is_corner:
                d.append(f"L{seg.c.x:.2f},{seg.c.y:.2f}L{seg.end_point.x:.2f},{seg.end_point.y:.2f}")
            else:
                d.append(f"C{seg.c1.x:.2f},{seg.c1.y:.2f} {seg.c2.x:.2f},{seg.c2.y:.2f} {seg.end_point.x:.2f},{seg.end_point.y:.2f}")
        d.append("Z")
        parts.append("".join(d))
    return " ".join(parts)

src, out = sys.argv[1], sys.argv[2]
colors = [tuple(int(h[i:i+2], 16) for i in (1, 3, 5)) for h in sys.argv[3:]]
im = Image.open(src).convert("RGBA"); arr = np.array(im)
W, H = im.size
paths = []
for rgb in colors:
    d = trace_color(arr, rgb)
    paths.append(f'<path fill="#{rgb[0]:02X}{rgb[1]:02X}{rgb[2]:02X}" fill-rule="evenodd" d="{d}"/>')
svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">'
       f'<title>AEDane</title>' + "".join(paths) + '</svg>\n')
open(out, "w").write(svg)
print(out, len(svg))
