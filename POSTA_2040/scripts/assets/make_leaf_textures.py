"""Generate procedural leaf-cluster alpha textures (512x512 RGBA) with Pillow.
Run with Blender's python: /opt/blender/4.5/python/bin/python3.11 make_leaf_textures.py
Outputs assets/textures/leaves_broad.png, leaves_mango.png, leaves_umbrella.png, needles_conifer.png, palm_frond.png, bark_*.png
"""
import os, math, random
from PIL import Image, ImageDraw, ImageFilter, ImageChops
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
OUT = os.path.join(ROOT, 'assets', 'textures'); os.makedirs(OUT, exist_ok=True)
S = 512

def lerp(a, b, t): return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))

def leaf_shape(w, h, kind='oval', pts=24):
    """Polygon of a leaf centred at origin pointing +y."""
    P = []
    for i in range(pts + 1):
        t = i / pts; y = -h / 2 + h * t
        if kind == 'oval': x = w / 2 * math.sin(math.pi * t) ** 0.8
        elif kind == 'lance': x = w / 2 * math.sin(math.pi * t ** 0.7) ** 1.3  # mango: long narrow pointed
        elif kind == 'round': x = w / 2 * math.sin(math.pi * t) ** 0.55
        P.append((x, y))
    right = P; left = [(-x, y) for x, y in reversed(P[1:-1])]
    return right + left

def draw_leaf(img, cx, cy, w, h, ang, col, kind, vein=True):
    lay = Image.new('RGBA', (S, S), (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
    poly = leaf_shape(w, h, kind)
    ca, sa = math.cos(ang), math.sin(ang)
    pts = [(cx + x * ca - y * sa, cy + x * sa + y * ca) for x, y in poly]
    d.polygon(pts, fill=col + (255,))
    if vein:
        vc = lerp(col, (255, 255, 230), 0.35)
        x0, y0 = -0, -h / 2 * 0.9; x1, y1 = 0, h / 2 * 0.9
        d.line([(cx + x0 * ca - y0 * sa, cy + x0 * sa + y0 * ca), (cx + x1 * ca - y1 * sa, cy + x1 * sa + y1 * ca)], fill=vc + (255,), width=max(1, int(w * 0.07)))
    # simple shading: darker on one side
    shade = Image.new('RGBA', (S, S), (0, 0, 0, 0)); sd = ImageDraw.Draw(shade)
    half = [(cx + x * ca - y * sa, cy + x * sa + y * ca) for x, y in poly if x <= 0.001]
    if len(half) > 2: sd.polygon(half, fill=(0, 0, 0, 55))
    lay = Image.alpha_composite(lay, ImageChops.multiply(shade, lay) if False else Image.composite(Image.new('RGBA', (S, S), (0, 0, 0, 60)), Image.new('RGBA', (S, S), (0, 0, 0, 0)), shade.split()[3]))
    img.alpha_composite(lay)

def cluster(name, n, wmin, wmax, aspect, base_cols, kind, seed, spread=0.42, stem=True):
    random.seed(seed)
    img = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    cx0, cy0 = S / 2, S / 2
    if stem:  # twigs radiating from centre
        d = ImageDraw.Draw(img)
        for k in range(7):
            a = random.uniform(0, 2 * math.pi); L = random.uniform(0.25, 0.45) * S
            d.line([(cx0, cy0), (cx0 + math.cos(a) * L, cy0 + math.sin(a) * L)], fill=(70, 52, 35, 255), width=3)
    leaves = []
    for i in range(n):
        r = random.random() ** 0.6 * spread * S; a = random.uniform(0, 2 * math.pi)
        cx = cx0 + math.cos(a) * r; cy = cy0 + math.sin(a) * r
        w = random.uniform(wmin, wmax) * S; h = w * aspect * random.uniform(0.85, 1.15)
        ang = a + math.pi / 2 + random.uniform(-0.6, 0.6)  # leaf points outward
        # colour variation: lighter near the outside (sun), darker centre
        t = random.random(); c = lerp(base_cols[0], base_cols[1], t)
        c = lerp(c, base_cols[2], (r / (spread * S)) * random.uniform(0.2, 0.7))
        leaves.append((r, cx, cy, w, h, ang, c))
    leaves.sort(key=lambda L: -L[0] if False else L[0])  # inner first, outer leaves on top
    for r, cx, cy, w, h, ang, c in leaves:
        draw_leaf(img, cx, cy, w, h, ang, c, kind)
    # feather alpha edge slightly
    a = img.split()[3].filter(ImageFilter.GaussianBlur(0.6))
    img.putalpha(a)
    img.save(os.path.join(OUT, name)); print('wrote', name)

def needles(name, seed):
    random.seed(seed)
    img = Image.new('RGBA', (S, S), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
    cols = [(38, 66, 44), (58, 92, 60), (86, 120, 84), (110, 142, 108)]
    cx0, cy0 = S / 2, S * 0.08
    # main twig downwards from top centre, with side twigs covered in needles (spruce spray)
    def spray(x0, y0, ang, L, width, depth):
        x1 = x0 + math.cos(ang) * L; y1 = y0 + math.sin(ang) * L
        d.line([(x0, y0), (x1, y1)], fill=(95, 70, 48, 255), width=width)
        n = int(L / 3.2)
        for i in range(n):
            t = i / max(1, n - 1); px = x0 + (x1 - x0) * t; py = y0 + (y1 - y0) * t
            for side in (-1, 1):
                na = ang + side * random.uniform(0.9, 1.5); nl = random.uniform(11, 20) * (1.0 - 0.3 * t)
                c = random.choice(cols); c = lerp(c, (160, 180, 150), random.random() * 0.15)
                d.line([(px, py), (px + math.cos(na) * nl, py + math.sin(na) * nl)], fill=c + (255,), width=2)
        if depth > 0:
            k = int(L / 20)
            for i in range(1, k):
                t = i / k; px = x0 + (x1 - x0) * t; py = y0 + (y1 - y0) * t
                for side in (-1, 1):
                    spray(px, py, ang + side * random.uniform(0.75, 1.15), L * random.uniform(0.3, 0.5) * (1 - 0.45 * t), max(1, width - 1), depth - 1)
    spray(cx0, cy0, math.pi / 2, S * 0.82, 4, 2)
    img.save(os.path.join(OUT, name)); print('wrote', name)

def palm_leaflet(name, seed):
    """Single tapered palm leaflet blade along +x (base at left), alpha edges, dark midrib."""
    random.seed(seed)
    img = Image.new('RGBA', (S, S), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
    pts_top, pts_bot = [], []
    for i in range(41):
        t = i / 40; x = 4 + t * (S - 8)
        hw = S * 0.47 * min(1.0, 0.55 + t * 3) * (1 - t ** 2.2) ** 0.5 * (1 - 0.1 * t)
        hw = max(2, hw)
        pts_top.append((x, S / 2 - hw)); pts_bot.append((x, S / 2 + hw))
    d.polygon(pts_top + pts_bot[::-1], fill=(70, 124, 52, 255))
    # subtle lengthwise streaks and midrib
    for k in range(60):
        y = random.uniform(S * 0.08, S * 0.92); c = random.choice([(58, 108, 44), (84, 140, 60), (96, 150, 70)])
        d.line([(0, y), (S, y)], fill=c + (255,), width=random.randint(2, 5))
    d.line([(0, S / 2), (S, S / 2)], fill=(120, 130, 70, 255), width=5)
    a_img = img.split()[3]
    # re-cut the shape so streaks stay inside the blade
    mask = Image.new('L', (S, S), 0); ImageDraw.Draw(mask).polygon(pts_top + pts_bot[::-1], fill=255)
    img.putalpha(mask.filter(ImageFilter.GaussianBlur(0.7)))
    img.save(os.path.join(OUT, name)); print('wrote', name)

def bark(name, seed, base, dark, light, rings=False):
    """Tileable-ish bark colour texture (no alpha)."""
    import numpy as np
    rng = np.random.default_rng(seed)
    y, x = np.mgrid[0:S, 0:S] / S
    def fbm(fx, fy, oct=5):
        v = np.zeros((S, S)); amp = 1; tot = 0
        for o in range(oct):
            g = rng.random((int(fy) + 1, int(fx) + 1))
            # bilinear upsample via PIL
            im = Image.fromarray((g * 255).astype('uint8')).resize((S, S), Image.BICUBIC)
            v += amp * (np.asarray(im) / 255.0); tot += amp; amp *= 0.5; fx *= 2; fy *= 2
        return v / tot
    if rings:
        v = 0.5 + 0.5 * np.sin(y * 2 * math.pi * 28 + fbm(2, 2) * 1.5)
        v = v ** 3 * 0.8 + fbm(6, 40) * 0.5
    else:
        v = fbm(5, 24) * 0.7 + fbm(40, 3) * 0.3  # vertical furrows
    v = (v - v.min()) / (v.max() - v.min() + 1e-6)
    col = np.zeros((S, S, 3))
    for i in range(3):
        col[..., i] = np.where(v < 0.5, dark[i] + (base[i] - dark[i]) * v * 2, base[i] + (light[i] - base[i]) * (v - 0.5) * 2)
    Image.fromarray(col.clip(0, 255).astype('uint8')).save(os.path.join(OUT, name)); print('wrote', name)

if __name__ == '__main__':
    # broadleaf: mid greens, oval leaves
    cluster('leaves_broad.png', 110, 0.055, 0.095, 1.7, [(40, 82, 30), (74, 126, 44), (130, 170, 70)], 'oval', 1)
    cluster('leaves_broad2.png', 95, 0.06, 0.10, 1.9, [(36, 74, 28), (66, 118, 40), (120, 160, 66)], 'oval', 7)
    # mango: long lanceolate dark glossy leaves
    cluster('leaves_mango.png', 120, 0.035, 0.06, 3.6, [(26, 62, 24), (46, 98, 36), (92, 140, 52)], 'lance', 3)
    # umbrella / acacia: tiny fine leaflets dense cluster
    cluster('leaves_umbrella.png', 260, 0.025, 0.045, 2.6, [(34, 70, 30), (64, 112, 46), (112, 150, 70)], 'lance', 5, spread=0.46)
    needles('needles_conifer.png', 11)
    palm_leaflet('palm_leaflet.png', 13)
    bark('bark_broad.png', 21, (92, 76, 60), (48, 38, 28), (150, 135, 112))
    bark('bark_mango.png', 22, (70, 58, 50), (30, 26, 24), (120, 108, 96))
    bark('bark_palm.png', 23, (150, 135, 105), (85, 72, 52), (200, 190, 160), rings=True)
    bark('bark_conifer.png', 24, (96, 70, 52), (48, 34, 24), (150, 120, 95))
