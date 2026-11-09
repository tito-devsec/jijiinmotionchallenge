"""Composite clean phone-camera / social UI frames over rendered sequences (PIL). Readable, restrained, no fake logos.
Usage: python3 overlay_ui.py camera <in_dir> <out_dir>   |   python3 overlay_ui.py social <in_dir> <out_dir>
"""
import sys, os, glob, math
from PIL import Image, ImageDraw, ImageFont, ImageFilter
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
mode, src, dst = sys.argv[1], sys.argv[2], sys.argv[3]; os.makedirs(dst, exist_ok=True)
def font(sz, bold=True):
    for p in ('/usr/share/fonts/truetype/inter/Inter-SemiBold.ttf', '/usr/share/fonts/truetype/inter/InterDisplay-SemiBold.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'):
        if os.path.exists(p): return ImageFont.truetype(p, sz)
    import glob as g
    c = g.glob('/usr/share/fonts/**/*Inter*', recursive=True) or g.glob('/usr/share/fonts/**/DejaVuSans-Bold.ttf', recursive=True)
    return ImageFont.truetype(c[0], sz)
WHITE = (243, 240, 232); TURQ = (0, 198, 168); ORANGE = (255, 101, 13)
files = sorted(glob.glob(os.path.join(src, 'f_*.png')))
for i, fp in enumerate(files):
    im = Image.open(fp).convert('RGBA'); W, H = im.size; d = ImageDraw.Draw(im, 'RGBA')
    t = i / 24.0
    if mode == 'camera':
        # viewfinder: 16:9 safe frame corners, REC indicator with timer, focus reticle, exposure scale, mode strip
        m = int(W * 0.035); L = int(W * 0.05)
        for (x, y, sx, sy) in ((m, m, 1, 1), (W - m, m, -1, 1), (m, H - m, 1, -1), (W - m, H - m, -1, -1)):
            d.line([(x, y), (x + sx * L, y)], fill=WHITE, width=3); d.line([(x, y), (x, y + sy * L)], fill=WHITE, width=3)
        blink = (int(t * 2) % 2 == 0)
        if blink: d.ellipse([m + 10, m + 26, m + 30, m + 46], fill=(230, 50, 40))
        mm, ss = divmod(int(t), 60); ff = int((t - int(t)) * 24)
        d.text((m + 42, m + 22), f"REC  {mm:02d}:{ss:02d}:{ff:02d}", font=font(26), fill=WHITE)
        d.text((W - m - 170, m + 22), "4K  24", font=font(24), fill=WHITE)
        cx, cy = W // 2, H // 2; r = 46
        d.rectangle([cx - r, cy - r, cx + r, cy + r], outline=TURQ, width=2)
        d.text((cx + r + 10, cy - 14), "AF", font=font(20), fill=TURQ)
        # bottom mode strip
        modes = ["PHOTO", "VIDEO", "PORTRAIT"]; x = W // 2 - 150
        for k, name in enumerate(modes):
            col = ORANGE if name == 'VIDEO' else (200, 200, 200)
            d.text((x + k * 150, H - m - 34), name, font=font(22), fill=col)
        # zoom pill
        d.rounded_rectangle([W // 2 - 60, H - m - 90, W // 2 + 60, H - m - 50], radius=20, fill=(0, 0, 0, 120), outline=(255, 255, 255, 90))
        d.text((W // 2 - 20, H - m - 83), "1x", font=font(22), fill=WHITE)
    elif mode == 'social':
        # clean share card: dark panel bottom third, caption, posting progress
        panel = Image.new('RGBA', (W, int(H * 0.30)), (9, 13, 22, 215)); im.alpha_composite(panel, (0, H - panel.height))
        d = ImageDraw.Draw(im, 'RGBA')
        reveal = min(1.0, max(0.0, (t - 0.8) / 1.6)); cap = "I FOUND SOMETHING FROM TOMORROW."
        shown = cap[:int(len(cap) * reveal)]
        d.text((int(W * 0.06), H - panel.height + 36), shown, font=font(44), fill=WHITE)
        d.text((int(W * 0.06), H - panel.height + 104), "Dar es Salaam · Kivukoni", font=font(24), fill=(170, 175, 185))
        prog = min(1.0, max(0.0, (t - 3.0) / 2.0))
        bx0, bx1, by = int(W * 0.06), int(W * 0.94), H - 44
        d.rounded_rectangle([bx0, by, bx1, by + 8], radius=4, fill=(60, 66, 80))
        if prog > 0: d.rounded_rectangle([bx0, by, bx0 + int((bx1 - bx0) * prog), by + 8], radius=4, fill=TURQ)
        d.text((bx1 - 120, by - 34), "Shared" if prog >= 1 else "Sharing…", font=font(22), fill=TURQ if prog >= 1 else (200, 200, 200))
    im.convert('RGB').save(os.path.join(dst, os.path.basename(fp)))
print('overlaid', len(files), 'frames ->', dst)
