"""Procedural sound design and music for JIJI IN MOTION. Pure NumPy, original material, 48 kHz stereo WAV.
Produces per-scene stems in audio/stems and a music bed in audio/music; the edit script mixes them against the picture.
"""
import numpy as np, os, wave, struct, math
SR = 48000
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
OUT = os.path.join(ROOT, 'audio'); os.makedirs(os.path.join(OUT, 'stems'), exist_ok=True); os.makedirs(os.path.join(OUT, 'music'), exist_ok=True)
rng = np.random.default_rng(2040)

def t(dur): return np.arange(int(dur * SR)) / SR
def env(n, a=0.01, d=0.1, s=0.8, r=0.2):
    a, d, r = int(a * SR), int(d * SR), int(r * SR); e = np.ones(n) * s
    a = min(a, n); d = min(d, n - a); r = min(r, n)
    if a: e[:a] = np.linspace(0, 1, a)
    if d: e[a:a + d] = np.linspace(1, s, d)
    if r: e[-r:] *= np.linspace(1, 0, r)
    return e
def fade(x, fi=0.5, fo=0.5):
    n = len(x); a, b = int(fi * SR), int(fo * SR)
    sh = (lambda v: v[:, None]) if x.ndim == 2 else (lambda v: v)
    if a: x[:a] *= sh(np.linspace(0, 1, a))
    if b: x[-b:] *= sh(np.linspace(1, 0, b))
    return x
def lowpass(x, cutoff, order=2):
    # simple one-pole cascaded
    rc = 1 / (2 * np.pi * cutoff); dt = 1 / SR; a = dt / (rc + dt); y = x.copy()
    for _ in range(order):
        acc = 0.0; out = np.empty_like(y)
        for i in range(len(y)):
            acc += a * (y[i] - acc); out[i] = acc
        y = out
    return y
def lowpass_fast(x, cutoff):
    # FFT brickwall-ish with soft knee
    X = np.fft.rfft(x); f = np.fft.rfftfreq(len(x), 1 / SR)
    X *= 1 / (1 + (f / cutoff) ** 4); return np.fft.irfft(X, len(x))
def highpass_fast(x, cutoff):
    X = np.fft.rfft(x); f = np.fft.rfftfreq(len(x), 1 / SR)
    X *= 1 / (1 + (cutoff / np.maximum(f, 1e-3)) ** 4); return np.fft.irfft(X, len(x))
def bandpass(x, lo, hi): return highpass_fast(lowpass_fast(x, hi), lo)
def noise(n): return rng.standard_normal(n)
def norm(x, peak=0.9):
    m = np.max(np.abs(x)) + 1e-9; return x / m * peak
def stereo(l, r=None): return np.stack([l, r if r is not None else l], 1)
def write(name, data, sub='stems'):
    data = np.clip(data, -1, 1); p = os.path.join(OUT, sub, name + '.wav')
    with wave.open(p, 'w') as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((data * 32767).astype('<i2').tobytes())
    print('wrote', p, f'{len(data)/SR:.1f}s')
def pan(x, p):  # p -1..1
    return stereo(x * math.sqrt((1 - p) / 2), x * math.sqrt((1 + p) / 2))
def place(buf, x, at):
    i = int(at * SR); n = min(len(x), len(buf) - i)
    if n > 0: buf[i:i + n] += x[:n]

# ---------------------------------------------------------------- SFX primitives
def impact(f0=80, dur=0.6, tone=0.6):
    tt = t(dur); e = np.exp(-tt * 9)
    body = np.sin(2 * np.pi * (f0 * np.exp(-tt * 3) + f0 * 0.3) * tt) * e
    click = lowpass_fast(noise(len(tt)), 3000) * np.exp(-tt * 60)
    return body * tone + click * (1 - tone) * 0.8
def metal_clank(dur=0.9):
    tt = t(dur); out = np.zeros_like(tt)
    for f in (1240, 1810, 2630, 3470, 4120):
        out += np.sin(2 * np.pi * f * tt * (1 + rng.normal(0, 0.003))) * np.exp(-tt * (6 + f / 600))
    return out * 0.2 + lowpass_fast(noise(len(tt)), 6000) * np.exp(-tt * 40) * 0.6
def digital_tick(dur=0.05, f=2400):
    tt = t(dur); return np.sign(np.sin(2 * np.pi * f * tt)) * np.exp(-tt * 80) * 0.3
def whoosh(dur=1.5, lo=200, hi=6000, direction=1):
    tt = t(dur); n = noise(len(tt))
    sweep = lo * (hi / lo) ** (tt / dur if direction > 0 else 1 - tt / dur)
    X = np.fft.rfft(n); f = np.fft.rfftfreq(len(n), 1 / SR)
    out = np.zeros_like(n); chunks = 24; L = len(n) // chunks
    for i in range(chunks):
        c = sweep[min(i * L, len(sweep) - 1)]; seg = n[i * L:(i + 1) * L]
        Y = np.fft.rfft(seg); ff = np.fft.rfftfreq(len(seg), 1 / SR)
        Y *= np.exp(-((np.log(np.maximum(ff, 1)) - np.log(c)) ** 2) / 0.6); out[i * L:(i + 1) * L] = np.fft.irfft(Y, len(seg))
    return norm(out) * np.sin(np.pi * tt / dur) ** 0.7

# ---------------------------------------------------------------- scene stems
def construction_ambience(dur):
    n = int(dur * SR); buf = np.zeros(n)
    # diesel engine idle: low pulse train
    tt = t(dur); eng = (np.sin(2 * np.pi * 28 * tt) + 0.5 * np.sin(2 * np.pi * 56 * tt + 0.3) + 0.25 * np.sin(2 * np.pi * 84 * tt)) * (0.7 + 0.3 * np.sin(2 * np.pi * 0.7 * tt))
    buf += lowpass_fast(eng, 300) * 0.25
    buf += lowpass_fast(noise(n), 900) * 0.07 * (0.8 + 0.2 * np.sin(2 * np.pi * 0.2 * tt))  # wind/dust
    for k in range(int(dur * 1.6)):
        at = rng.uniform(0, dur - 1); kind = rng.integers(0, 3)
        x = metal_clank() * 0.6 if kind == 0 else impact(60, 0.7, 0.8) * 0.7 if kind == 1 else highpass_fast(noise(int(0.25 * SR)), 2500) * np.exp(-t(0.25) * 14) * 0.35
        place(buf, x, at)
    # hydraulic whine sweeps
    for k in range(int(dur / 6)):
        at = rng.uniform(0, dur - 3); d = 2.5; tt2 = t(d); f = 600 + 300 * np.sin(np.pi * tt2 / d)
        place(buf, np.sin(2 * np.pi * np.cumsum(f) / SR) * np.sin(np.pi * tt2 / d) * 0.04, at)
    L = buf + highpass_fast(noise(n), 4000) * 0.01; R = buf + highpass_fast(noise(n), 4000) * 0.01
    return fade(stereo(norm(L, 0.7), norm(R, 0.7)), 1.0, 1.5)

def build_up_sequence(dur):
    """Mechanical assembly: rising clicks and rhythmic impacts accelerating."""
    n = int(dur * SR); buf = np.zeros(n); at = 0.3; gap = 0.6
    while at < dur - 0.5:
        place(buf, impact(90 + 40 * rng.random(), 0.4, 0.7) * 0.6, at); place(buf, metal_clank(0.5) * 0.3, at + 0.08)
        at += gap; gap = max(0.09, gap * 0.93)
    tt = t(dur); riser = whoosh(dur, 120, 5000) * 0.4
    return fade(stereo(norm(buf + riser, 0.8)), 0.2, 0.8)

def digital_transform(dur, intensity=1.0):
    """Binary conversion: granular ticks, data streams, shimmering harmonics."""
    n = int(dur * SR); buf = np.zeros(n); tt = t(dur)
    density = 12 + 60 * intensity
    for k in range(int(dur * density)):
        at = rng.uniform(0, dur - 0.1); place(buf, digital_tick(0.04, rng.choice([1800, 2400, 3200, 4800, 6400])) * (0.25 + 0.5 * rng.random()), at)
    # data stream: FM shimmer
    car = 440 * 2 ** (np.sin(2 * np.pi * 0.11 * tt) * 0.5)
    shim = np.sin(2 * np.pi * np.cumsum(car) / SR + 2.0 * np.sin(2 * np.pi * 220 * tt)) * 0.12
    shim += np.sin(2 * np.pi * np.cumsum(car * 1.5) / SR) * 0.06
    pad = sum(np.sin(2 * np.pi * f * tt + p) for f, p in ((110, 0), (165, 1), (220, 2), (330, 0.5))) * 0.05 * (0.5 + 0.5 * np.sin(2 * np.pi * 0.25 * tt))
    L = buf * 0.7 + shim + pad; R = np.roll(buf, int(0.012 * SR)) * 0.7 + shim * 0.9 + pad
    return fade(stereo(norm(L, 0.8), norm(R, 0.8)), 0.5, 1.0)

def city_future_ambience(dur):
    n = int(dur * SR); tt = t(dur)
    hum = lowpass_fast(noise(n), 400) * 0.12 + np.sin(2 * np.pi * 55 * tt) * 0.05
    traffic = bandpass(noise(n), 300, 1500) * 0.05 * (0.7 + 0.3 * np.sin(2 * np.pi * 0.08 * tt))
    buf = hum + traffic
    for k in range(int(dur * 0.4)):  # distant vehicle passes (doppler-ish sweep)
        at = rng.uniform(0, dur - 3); d = 2.8; tt2 = t(d); f = 900 * (1.25 - 0.5 * tt2 / d)
        place(buf, bandpass(noise(len(tt2)), 500, 3000) * np.sin(np.pi * tt2 / d) ** 2 * 0.06 + np.sin(2 * np.pi * np.cumsum(f) / SR) * np.sin(np.pi * tt2 / d) ** 2 * 0.02, at)
    for k in range(int(dur * 0.8)):  # soft chimes of the digital infrastructure
        at = rng.uniform(0, dur - 1); f = rng.choice([880, 1108, 1318, 1760]); d = 0.8
        place(buf, np.sin(2 * np.pi * f * t(d)) * np.exp(-t(d) * 5) * 0.04, at)
    # waterfront: gentle waves
    waves = lowpass_fast(noise(n), 700) * (0.5 + 0.5 * np.sin(2 * np.pi * 0.12 * tt + 1)) ** 2 * 0.08
    return fade(stereo(norm(buf + waves, 0.6), norm(np.roll(buf, 900) + waves, 0.6)), 1.0, 1.5)

def helicopter(dur, approach=True):
    n = int(dur * SR); tt = t(dur)
    gain = np.clip(tt / (dur * 0.6), 0.15, 1.0) if approach else np.ones(n)
    bpf = 18.0  # blade pass frequency (Hz)
    rotor = np.zeros(n); ph = 2 * np.pi * bpf * tt
    for h in range(1, 12): rotor += np.sin(h * ph) / h ** 1.2
    rotor = np.tanh(rotor * 1.5) * 0.4
    chop = (0.5 + 0.5 * np.cos(ph)) ** 6
    turbine = bandpass(noise(n), 1500, 6000) * 0.08 * (0.6 + 0.4 * chop) + np.sin(2 * np.pi * 1850 * tt) * 0.01
    tail = np.sign(np.sin(2 * np.pi * 98 * tt)) * 0.03 * lowpass_fast(np.ones(n), 10)
    buf = (lowpass_fast(rotor, 900) + turbine + tail) * gain
    L = buf * (0.9 + 0.1 * np.sin(2 * np.pi * bpf * tt)); R = buf * (0.9 - 0.1 * np.sin(2 * np.pi * bpf * tt))
    return fade(stereo(norm(L, 0.85), norm(R, 0.85)), 0.3, 1.0)

def camera_ui(dur):
    n = int(dur * SR); buf = np.zeros(n)
    place(buf, digital_tick(0.06, 3000) * 0.8, 0.5)  # tap
    place(buf, digital_tick(0.08, 2000) * 0.9 + digital_tick(0.08, 2600) * 0.6, 1.1)  # record start beep
    return stereo(norm(buf, 0.6))

def lens_dive(dur):
    tt = t(dur); n = len(tt)
    w = whoosh(dur, 80, 9000, 1) * 0.6
    sub = np.sin(2 * np.pi * np.cumsum(40 + 30 * tt / dur) / SR) * np.exp(-((tt - dur * 0.75) ** 2) / 0.3) * 0.5
    glass = sum(np.sin(2 * np.pi * f * tt) * np.exp(-tt * 1.5) for f in (3200, 4100, 5700)) * 0.05
    return fade(stereo(norm(w + sub + glass, 0.9)), 0.1, 0.3)

def fall_and_splash(dur, splash_at):
    n = int(dur * SR); tt = t(dur); buf = np.zeros(n)
    # wind rushing, rising pitch until splash
    d = splash_at; k = int(d * SR)
    wind = bandpass(noise(k), 200, 2500) * (np.linspace(0.2, 1.0, k) ** 2) * 0.5
    buf[:k] += wind
    # tumbling phone: whistling flutter
    tt1 = t(d); flutter = np.sin(2 * np.pi * np.cumsum(1200 + 400 * np.sin(2 * np.pi * 4.5 * tt1)) / SR) * (0.5 + 0.5 * np.sin(2 * np.pi * 9 * tt1)) * 0.04 * np.linspace(0.3, 1, k)
    buf[:k] += flutter
    # splash
    sp = t(2.5); splash = lowpass_fast(noise(len(sp)), 1200) * np.exp(-sp * 2.5) * 0.9; place(splash, impact(70, 0.8, 0.9) * 0.9, 0.0)
    place(buf, splash, splash_at)
    # bubbles after
    for i in range(40):
        at = splash_at + 0.2 + rng.uniform(0, 1.8); f = rng.uniform(600, 2400); dd = 0.08
        place(buf, np.sin(2 * np.pi * np.cumsum(f * (1 + 2.5 * t(dd))) / SR) * np.exp(-t(dd) * 40) * 0.15, at)
    return stereo(norm(buf, 0.9))

def underwater(dur, bubbles=True, diver=False):
    n = int(dur * SR); tt = t(dur)
    buf = lowpass_fast(noise(n), 350) * 0.2 * (0.8 + 0.2 * np.sin(2 * np.pi * 0.07 * tt))
    buf += np.sin(2 * np.pi * 48 * tt) * 0.03 * (0.5 + 0.5 * np.sin(2 * np.pi * 0.05 * tt))
    # muffled surface wash
    buf += lowpass_fast(noise(n), 900) * (0.5 + 0.5 * np.sin(2 * np.pi * 0.1 * tt + 2)) ** 3 * 0.1
    if bubbles:
        for i in range(int(dur * 2.5)):
            at = rng.uniform(0, dur - 0.5); f = rng.uniform(500, 2000); dd = rng.uniform(0.05, 0.12)
            place(buf, np.sin(2 * np.pi * np.cumsum(f * (1 + 2.0 * t(dd))) / SR) * np.exp(-t(dd) * 30) * 0.08, at)
    if diver:
        # regulator breathing: inhale hiss (4 s cycle), exhale bubble bursts
        at = 0.5
        while at < dur - 4:
            inh = bandpass(noise(int(1.6 * SR)), 800, 4000) * np.sin(np.pi * t(1.6) / 1.6) * 0.12; place(buf, inh, at)
            for j in range(18):
                f = rng.uniform(300, 1500); dd = 0.1
                place(buf, np.sin(2 * np.pi * np.cumsum(f * (1 + 2.5 * t(dd))) / SR) * np.exp(-t(dd) * 25) * 0.12, at + 2.0 + rng.uniform(0, 1.6))
            at += 4.2
    return fade(stereo(norm(buf, 0.7), norm(np.roll(buf, 1500), 0.7)), 1.0, 1.5)

def ui_share(dur):
    n = int(dur * SR); buf = np.zeros(n)
    place(buf, digital_tick(0.05, 2600) * 0.7, 0.8); place(buf, digital_tick(0.05, 3100) * 0.7, 1.3)
    tt = t(0.5); place(buf, (np.sin(2 * np.pi * 1318 * tt) + np.sin(2 * np.pi * 1760 * tt)) * np.exp(-tt * 6) * 0.3, 2.2)
    return stereo(norm(buf, 0.6))

def brand_sting(dur):
    tt = t(dur); n = len(tt)
    boom = impact(45, 2.5, 0.95) * 1.0
    pad = np.zeros(n)
    for f, p in ((55, 0), (110, 0.3), (164.8, 0.7), (220, 1.1), (329.6, 0.2), (440, 0.9)):
        pad += np.sin(2 * np.pi * f * tt + p) * np.exp(-tt * 0.35) / (1 + f / 110)
    pad = lowpass_fast(pad, 2500) * 0.35
    shimmer = whoosh(2.0, 300, 8000, -1) * 0.3
    buf = pad; place(buf, boom, 0.0); place(buf, shimmer, 0.0)
    return fade(stereo(norm(buf, 0.9)), 0.0, 2.0)

# ---------------------------------------------------------------- music bed
def music_bed(dur, bpm=92):
    """Cinematic build: pulsing sub + arpeggio in D minor pentatonic + evolving pads, East-African inspired 6/8 marimba feel in the middle, swells toward the end."""
    n = int(dur * SR); tt = t(dur); out = np.zeros(n)
    beat = 60 / bpm
    def tone(f, d, shape='sine', a=0.005, r=0.3, vol=0.2):
        tt2 = t(d)
        if shape == 'sine': x = np.sin(2 * np.pi * f * tt2) + 0.3 * np.sin(2 * np.pi * 2 * f * tt2)
        elif shape == 'marimba': x = np.sin(2 * np.pi * f * tt2) * np.exp(-tt2 * 7) + 0.5 * np.sin(2 * np.pi * f * 4 * tt2) * np.exp(-tt2 * 20) + 0.2 * np.sin(2 * np.pi * f * 10.1 * tt2) * np.exp(-tt2 * 40)
        elif shape == 'saw': x = lowpass_fast(sum(np.sin(2 * np.pi * f * k * tt2) / k for k in range(1, 12)), 1800)
        e = env(len(tt2), a, 0.05, 0.7, r); return x * e * vol
    D = 73.42; scale = [D, D * 2 ** (3 / 12), D * 2 ** (5 / 12), D * 2 ** (7 / 12), D * 2 ** (10 / 12)]  # D minor pentatonic
    # sub pulse every beat (enters at 8%)
    b = 0.0
    while b < dur:
        if b > dur * 0.08: place(out, tone(D, beat * 0.9, 'sine', vol=0.25 * min(1, (b - dur * 0.08) / (dur * 0.2))), b)
        b += beat
    # arpeggio 16ths from 20%
    i = 0; b = dur * 0.2
    pattern = [0, 2, 4, 2, 1, 3, 4, 3]
    while b < dur * 0.92:
        f = scale[pattern[i % 8]] * (4 if (i // 8) % 2 == 0 else 8); amt = min(1, (b - dur * 0.2) / (dur * 0.15))
        place(out, tone(f, beat / 2 * 0.8, 'marimba', vol=0.14 * amt), b)
        b += beat / 2; i += 1
    # pads: chord changes every 4 bars (Dm - Bb - F - C)
    chords = [[0, 3, 7], [-4, 0, 5], [-7, -3, 0], [-2, 2, 7]]
    b = 0; ci = 0
    while b < dur:
        d = beat * 16
        for semi in chords[ci % 4]:
            f = D * 2 * 2 ** (semi / 12); x = tone(f, d, 'saw', a=1.5, r=1.5, vol=0.05 * min(1, 0.3 + b / dur))
            place(out, x, b)
        b += d; ci += 1
    # swell toward the brand reveal (last 10%)
    sw = np.clip((tt - dur * 0.86) / (dur * 0.08), 0, 1) ** 2
    out += lowpass_fast(noise(n), 1500) * sw * 0.15
    out *= 1 - 0.5 * np.clip((tt - dur * 0.95) / (dur * 0.05), 0, 1)  # dip into sting
    L = out + np.roll(out, int(0.011 * SR)) * 0.3; R = out + np.roll(out, int(0.017 * SR)) * 0.3
    return fade(stereo(norm(L, 0.8), norm(R, 0.8)), 2.0, 3.0)

if __name__ == '__main__':
    import json
    cfg = json.load(open(os.path.join(ROOT, 'scripts', 'film_config.json')))
    scenes = cfg['scenes']; fps = cfg['fps']
    dur = {s['id']: s['frames'] / fps for s in scenes}
    total = sum(dur.values())
    print('total film seconds', total)
    write('s01_construction_amb', construction_ambience(dur['s01'] + 2))
    write('s01_buildup', build_up_sequence(dur['s01'] * 0.6))
    write('s02_digital_buildings', digital_transform(dur['s02'] + 2, 1.0))
    write('s03_digital_roads', digital_transform(dur['s03'] + 2, 0.7))
    write('s04_city_binary_amb', city_future_ambience(dur['s04'] + 2))
    write('s05_human_transform', digital_transform(dur['s05'] + 2, 0.5))
    write('s06_city_real_amb', city_future_ambience(dur['s06'] + dur['s07'] + 2))
    write('s07_helicopter', helicopter(dur['s07'] + dur['s08'] + dur['s09'] + dur.get('s09b', 0) + dur['s10'] * 0.5 + 2, True))
    write('s08_camera_ui', camera_ui(4))
    write('s08_lens_dive', lens_dive(3.5))
    write('s10_fall_splash', fall_and_splash(dur['s10'] + 3, dur['s10'] * 0.72))
    write('s11_underwater', underwater(dur['s11'] + 2, True, False))
    write('s12_diver', underwater(dur['s12'] + dur['s13'] * 0.3 + 2, True, True))
    write('s13_ui_share', ui_share(5))
    write('s14_brand_sting', brand_sting(dur['s14'] + 1))
    write('music_bed', music_bed(total), 'music')
