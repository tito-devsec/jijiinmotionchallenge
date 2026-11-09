"""Collage-style title cards in the JIJI IN MOTION campaign look (paint-stroke swooshes in cobalt, orange, yellow, teal;
bold condensed type with a green highlight block; Swahili + English). Generates animated PNG sequences:
  renders/card_open/f_####.png   (3.0 s)  — opening title
  renders/card_close/f_####.png  (5.0 s)  — closing pillars + credit
Pure Pillow, so it is cheap and crisp. Palette follows the HOT 70 colourways / production palette.
"""
import os, math, random, glob
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import numpy as np
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
W, H, FPS = 1280, 720, 24
PAPER = (243, 240, 232); INK = (12, 14, 18); COBALT = (7, 85, 201); ORANGE = (255, 101, 13); YELLOW = (246, 201, 40); TEAL = (0, 198, 168); GREEN = (178, 222, 60); SAGE = (196, 214, 170)
rng = random.Random(70)

def font(sz, bold=True):
    cands = glob.glob('/usr/share/fonts/**/InterDisplay-Black.otf', recursive=True) + glob.glob('/usr/share/fonts/**/InterDisplay-ExtraBold.otf', recursive=True) + glob.glob('/usr/share/fonts/**/Inter-Bold.otf', recursive=True) + glob.glob('/usr/share/fonts/**/DejaVuSans-Bold.ttf', recursive=True)
    return ImageFont.truetype(cands[0], sz)

def paper_texture():
    im = Image.new('RGB', (W, H), PAPER); a = np.array(im).astype(np.int16)
    g = np.random.default_rng(1).normal(0, 6, (H, W, 1)).astype(np.int16); a = np.clip(a + g, 0, 255).astype(np.uint8)
    return Image.fromarray(a)

def swoosh(draw_layer, p0, p1, p2, width, color, progress=1.0, taper=True, speckle=True):
    """Quadratic bezier brush stroke, drawn with overlapping circles; progress 0..1 reveals the stroke."""
    n = 260; pts = []
    for i in range(int(n * progress)):
        t = i / (n - 1); x = (1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t ** 2 * p2[0]; y = (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t ** 2 * p2[1]
        w = width * (0.35 + 0.65 * math.sin(math.pi * min(1, t * 1.15))) if taper else width
        pts.append((x, y, w))
    for x, y, w in pts:
        draw_layer.ellipse([x - w / 2, y - w / 2, x + w / 2, y + w / 2], fill=color)
    if speckle and pts:
        for x, y, w in pts[::9]:
            for k in range(3):
                dx, dy = rng.uniform(-w, w), rng.uniform(-w, w); r = rng.uniform(1, 4)
                draw_layer.ellipse([x + dx - r, y + dy - r, x + dx + r, y + dy + r], fill=color)

def halftone_band(im, y0, y1, color, spacing=9):
    d = ImageDraw.Draw(im)
    for y in range(y0, y1, spacing):
        t = (y - y0) / max(1, y1 - y0); r = 1.2 + 3.2 * (1 - t)
        for x in range(0, W, spacing): d.ellipse([x - r, y - r, x + r, y + r], fill=color)

def skyline_silhouette(im, base_y, color, alpha=255, progress=1.0):
    """Posta 2040 skyline silhouette from the futurised building heights (sampled along x)."""
    import json
    prof = os.path.join(ROOT, 'assets', 'textures', 'skyline_profile.json')
    if os.path.exists(prof): heights = json.load(open(prof))
    else:
        rr = random.Random(3); heights = [rr.choice([40, 60, 90, 130, 170, 220, 90, 60, 50]) * rr.uniform(0.7, 1.2) for _ in range(64)]
    layer = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(layer)
    n = len(heights); bw = W / n
    for i, h in enumerate(heights):
        hh = h * 0.9 * progress; x0 = i * bw
        d.rectangle([x0 + 1, base_y - hh, x0 + bw - 2, base_y], fill=color + (alpha,))
        if h > 150: d.polygon([(x0 + bw / 2, base_y - hh - 28 * progress), (x0 + 2, base_y - hh), (x0 + bw - 2, base_y - hh)], fill=color + (alpha,))
    im.alpha_composite(layer)

def title_block(im, text, xy, size, fill=INK, highlight=None, hl_word=None):
    d = ImageDraw.Draw(im); f = font(size)
    if highlight and hl_word and hl_word in text:
        pre = text[:text.index(hl_word)]; wpre = d.textlength(pre, font=f); whl = d.textlength(hl_word, font=f)
        d.rectangle([xy[0] + wpre - 6, xy[1] + size * 0.08, xy[0] + wpre + whl + 6, xy[1] + size * 1.0], fill=highlight)
    d.text(xy, text, font=f, fill=fill)

def ease(t): return 0.5 - 0.5 * math.cos(math.pi * max(0, min(1, t)))

def render_open(out):
    os.makedirs(out, exist_ok=True); N = int(3.0 * FPS); base = paper_texture().convert('RGBA')
    for i in range(N):
        t = i / FPS; im = base.copy(); layer = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(layer)
        swoosh(d, (-100, 520), (500, 80), (1380, 420), 150, COBALT + (255,), ease(t / 0.9))
        swoosh(d, (-60, 650), (640, 330), (1340, 600), 70, ORANGE + (255,), ease((t - 0.25) / 0.9))
        swoosh(d, (200, 760), (700, 560), (1300, 700), 46, YELLOW + (255,), ease((t - 0.45) / 0.8))
        swoosh(d, (-40, 300), (400, 200), (900, 60), 26, TEAL + (255,), ease((t - 0.6) / 0.7))
        im.alpha_composite(layer)
        skyline_silhouette(im, 600, INK, 255, ease((t - 0.8) / 1.0))
        a = ease((t - 1.3) / 0.7)
        if a > 0:
            txt = Image.new('RGBA', (W, H), (0, 0, 0, 0)); title_block(txt, 'JIJI IN MOTION', (70, 70 + int(40 * (1 - a))), 104, INK, GREEN, 'MOTION')
            ImageDraw.Draw(txt).text((74, 190 + int(40 * (1 - a))), 'THE FUTURE IS BUILT IN CODE', font=font(30), fill=COBALT)
            ImageDraw.Draw(txt).text((74, 232 + int(40 * (1 - a))), 'Posta · Dar es Salaam · 2040', font=font(22), fill=INK)
            txt.putalpha(txt.getchannel('A').point(lambda v: int(v * a))); im.alpha_composite(txt)
        # fade out last 0.4 s to black (next shot opens at ground level)
        fo = max(0.0, (t - 2.6) / 0.4)
        if fo: im = Image.blend(im, Image.new('RGBA', (W, H), (0, 0, 0, 255)), fo)
        im.convert('RGB').save(os.path.join(out, f'f_{i+1:04d}.png'))
    print('open card', N, 'frames')

def render_close(out):
    os.makedirs(out, exist_ok=True); N = int(5.0 * FPS); base = paper_texture().convert('RGBA')
    pillars = [('01', 'MAISHA YA MIJI YA TZ', 'Tanzanian city elements — the real Posta map, Kivukoni, the harbour'),
               ('02', 'RANGI ZA HOT 70', 'Colour drawn from the Infinix HOT 70 colourways'),
               ('03', 'MTAZAMO NA UBUNIFU WAKO', 'Personal signature — code, procedural art, Dar es Salaam')]
    for i in range(N):
        t = i / FPS; im = base.copy(); layer = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(layer)
        swoosh(d, (1400, 120), (800, 380), (-100, 240), 120, COBALT + (255,), ease(t / 0.8))
        swoosh(d, (1340, 700), (700, 500), (-60, 680), 60, ORANGE + (255,), ease((t - 0.2) / 0.8))
        swoosh(d, (1300, 40), (900, 160), (300, -40), 30, YELLOW + (255,), ease((t - 0.4) / 0.7))
        im.alpha_composite(layer)
        halftone_band(im, 560, 720, SAGE)
        txt = Image.new('RGBA', (W, H), (0, 0, 0, 0)); dd = ImageDraw.Draw(txt)
        for k, (num, sw, en) in enumerate(pillars):
            a = ease((t - 0.6 - k * 0.45) / 0.6)
            if a <= 0: continue
            y = 90 + k * 140; x = 90 + int(30 * (1 - a))
            dd.text((x, y), num, font=font(54), fill=[COBALT, ORANGE, TEAL][k]); dd.text((x + 90, y + 4), sw, font=font(40), fill=INK)
            dd.text((x + 92, y + 58), en, font=font(22), fill=(60, 64, 72))
            dd.line([(x, y + 110), (x + 900, y + 110)], fill=INK, width=2)
        a = ease((t - 2.4) / 0.6)
        if a > 0:
            title_block(txt, 'JIJI IN MOTION', (90, 540), 64, INK, GREEN, 'MOTION'); dd.text((94, 620), 'A film built in code by tito-devsec  ·  Map data © OpenStreetMap contributors', font=font(20), fill=INK)
        txt.putalpha(txt.getchannel('A').point(lambda v: int(v * min(1, ease(t / 0.6))))); im.alpha_composite(txt)
        fi = min(1.0, t / 0.5); im = Image.blend(Image.new('RGBA', (W, H), (0, 0, 0, 255)), im, fi)
        im.convert('RGB').save(os.path.join(out, f'f_{i+1:04d}.png'))
    print('close card', N, 'frames')

if __name__ == '__main__':
    render_open(os.path.join(ROOT, 'renders', 'card_open')); render_close(os.path.join(ROOT, 'renders', 'card_close'))
