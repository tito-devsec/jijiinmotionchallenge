"""Composite clean phone-camera / social UI frames over rendered sequences (PIL). Readable, restrained, no fake logos.
Usage: python3 overlay_ui.py camera <in_dir> <out_dir>   |   python3 overlay_ui.py social <in_dir> <out_dir>
"""
import sys, os, glob, math
from PIL import Image, ImageDraw, ImageFont, ImageFilter
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
mode, src, dst = sys.argv[1], sys.argv[2], sys.argv[3]; os.makedirs(dst, exist_ok=True)
def font(sz, bold=True):
    for p in ('/usr/share/fonts/opentype/inter/Inter-SemiBold.otf', '/usr/share/fonts/opentype/inter/InterDisplay-SemiBold.otf', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'):
        if os.path.exists(p): return ImageFont.truetype(p, sz)
    import glob as g
    c = g.glob('/usr/share/fonts/**/*Inter*', recursive=True) or g.glob('/usr/share/fonts/**/DejaVuSans-Bold.ttf', recursive=True)
    return ImageFont.truetype(c[0], sz)
def font_black(sz):
    for p in ('/usr/share/fonts/opentype/inter/InterDisplay-Black.otf', '/usr/share/fonts/opentype/inter/Inter-Black.otf'):
        if os.path.exists(p): return ImageFont.truetype(p, sz)
    return font(sz)
WHITE = (243, 240, 232); TURQ = (0, 198, 168); ORANGE = (255, 101, 13)
files = sorted(glob.glob(os.path.join(src, 'f_*.png')))
# fill frame-step gaps so the output is a contiguous 24 fps sequence (also usable as an image sequence on the phone screen)
nums = [int(os.path.basename(p)[2:6]) for p in files]
seq = []
for k, (n, p) in enumerate(zip(nums, files)):
    nxt = nums[k + 1] if k + 1 < len(nums) else n + (nums[1] - nums[0] if len(nums) > 1 else 1)
    for fno in range(n, nxt): seq.append((fno, p))
for fno, fp in seq:
    im = Image.open(fp).convert('RGBA'); W, H = im.size; d = ImageDraw.Draw(im, 'RGBA')
    t = (fno - 1) / 24.0
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
    elif mode == 'brand':
        # final title: JIJI IN MOTION (MOTION on the campaign green block) + tagline, left third, rising fade-in
        def ease(x): return 0.5 - 0.5 * math.cos(math.pi * max(0.0, min(1.0, x)))
        GREEN = (178, 222, 60); INK = (12, 14, 18)
        a1 = ease((t - 2.0) / 1.0); a2 = ease((t - 3.0) / 1.0)
        lay = Image.new('RGBA', (W, H), (0, 0, 0, 0)); dl = ImageDraw.Draw(lay)
        fbig = font_black(int(H * 0.11)); x0 = int(W * 0.07); y0 = int(H * 0.36) + int(24 * (1 - a1))
        w1 = dl.textlength('JIJI IN ', font=fbig); w2 = dl.textlength('MOTION', font=fbig)
        dl.text((x0, y0), 'JIJI IN ', font=fbig, fill=WHITE + (int(255 * a1),))
        dl.rectangle([x0 + w1 - 8, y0 + int(H * 0.012), x0 + w1 + w2 + 8, y0 + int(H * 0.118)], fill=GREEN + (int(255 * a1),))
        dl.text((x0 + w1, y0), 'MOTION', font=fbig, fill=INK + (int(255 * a1),))
        dl.text((x0 + 4, y0 + int(H * 0.15) + int(16 * (1 - a2))), 'THE FUTURE IS WORTH CAPTURING.', font=font(int(H * 0.04)), fill=WHITE + (int(255 * a2),))
        im.alpha_composite(lay)
    im.convert('RGB').save(os.path.join(dst, f'f_{fno:04d}.png'))
print('overlaid', len(seq), 'frames ->', dst)
