"""Assemble the final film: per-scene image sequences -> scene clips (with optional frame-step interpolation) -> concat with crossfades
-> audio mix (stems + music) -> renders/JIJI_IN_MOTION_final.mp4. Uses FFmpeg only.
Usage: python3 edit_film.py [--step N] (N = frame step used when rendering; frames are interpolated back to 24 fps)
"""
import os, json, subprocess, sys, glob, shutil
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
cfg = json.load(open(os.path.join(ROOT, 'scripts', 'film_config.json'))); FPS = cfg['fps']; W, H = cfg['resolution']
step = int(sys.argv[sys.argv.index('--step') + 1]) if '--step' in sys.argv else 1
SUF = sys.argv[sys.argv.index('--suffix') + 1] if '--suffix' in sys.argv else ''
R = os.path.join(ROOT, 'renders'); TMP = os.path.join(R, '_edit' + SUF); os.makedirs(TMP, exist_ok=True)
XF = 0.5  # crossfade seconds between scenes

def run(cmd): print(' '.join(cmd) if isinstance(cmd, list) else cmd); subprocess.run(cmd, check=True)

clips = []
# title cards (pre-rendered at 24 fps by brand_cards.py) bracket the film
cards = [{'id': 'card_open', 'title': 'Opening card', 'frames': 72}] + cfg['scenes'] + [{'id': 'card_close', 'title': 'Closing card', 'frames': 120}]
for s in cards:
    base = s['id'] if s['id'].startswith('card') else s['id'] + SUF
    d = os.path.join(R, base)
    if glob.glob(os.path.join(R, base + '_ui', 'f_*.png')): d = os.path.join(R, base + '_ui')  # composited UI versions take precedence
    frames = sorted(glob.glob(os.path.join(d, 'f_*.png')))
    nums = [int(os.path.basename(p)[2:6]) for p in frames]
    gaps = [b - a for a, b in zip(nums, nums[1:])] + [max(1, s['frames'] - nums[-1] + 1)] if frames else []
    this_step = max(gaps) if gaps else 1
    if not frames: print('MISSING', s['id']); continue
    lst = os.path.join(TMP, f"{s['id']}.txt")
    with open(lst, 'w') as f:
        for p, gp in zip(frames, gaps): f.write(f"file '{p}'\nduration {gp / FPS}\n")
        f.write(f"file '{frames[-1]}'\n")
    out = os.path.join(TMP, f"{s['id']}.mp4")
    vf = f"scale={W}:{H}:flags=lanczos,format=yuv420p"
    if this_step > 1: vf = f"minterpolate=fps={FPS}:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1," + vf
    run(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', lst, '-vf', vf, '-r', str(FPS), '-c:v', 'libx264', '-preset', 'medium', '-crf', '17', out])
    clips.append((s, out))

# ---- concat with crossfades
dur = lambda p: float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', p]).decode().strip())
inputs = []; filt = []; prev = None; offset = 0.0; durs = []
for i, (s, p) in enumerate(clips):
    inputs += ['-i', p]; d = dur(p); durs.append(d)
for i in range(len(clips)):
    label = f'[{i}:v]'
    if i == 0: prev = label; offset = durs[0] - XF; continue
    outl = f'[v{i}]' if i < len(clips) - 1 else '[vout]'
    filt.append(f"{prev}{label}xfade=transition=fade:duration={XF}:offset={offset:.3f}{outl}")
    prev = outl; offset += durs[i] - XF
video = os.path.join(TMP, 'video.mp4')
run(['ffmpeg', '-y', '-loglevel', 'error', *inputs, '-filter_complex', ';'.join(filt), '-map', '[vout]', '-c:v', 'libx264', '-preset', 'medium', '-crf', '17', '-pix_fmt', 'yuv420p', video])
total = dur(video); print('video seconds', total)

# ---- audio mix: stems placed at scene start times, music under everything, brand sting at the end
starts = {}; t = 0.0
for (s, p), d in zip(clips, durs): starts[s['id']] = t; t += d - XF
A = os.path.join(ROOT, 'audio')
plan = [  # (stem, scene id, offset within scene, gain dB)
    ('stems/s01_construction_amb.wav', 's01', 0.0, -6), ('stems/s01_buildup.wav', 's01', 4.0, -8),
    ('stems/s02_digital_buildings.wav', 's02', 0.0, -8), ('stems/s03_digital_roads.wav', 's03', 0.0, -9),
    ('stems/s04_city_binary_amb.wav', 's04', 0.0, -8), ('stems/s05_human_transform.wav', 's05', 0.0, -10),
    ('stems/s06_city_real_amb.wav', 's06', 0.0, -8), ('stems/s07_helicopter.wav', 's07', 0.0, -9),
    ('stems/s08_camera_ui.wav', 's08', 1.0, -10), ('stems/s08_lens_dive.wav', 's08', 5.5, -6),
    ('stems/s10_fall_splash.wav', 's10', 0.0, -6), ('stems/s11_underwater.wav', 's11', 0.0, -7),
    ('stems/s12_diver.wav', 's12', 0.0, -7), ('stems/s13_ui_share.wav', 's13', 2.0, -10), ('stems/s14_brand_sting.wav', 's14', 0.0, -4),
    ('music/music_bed.wav', 'card_open', 0.0, -9),
]
ain = []; af = []; mixin = []
for i, (stem, sid, off, g) in enumerate(plan):
    if sid not in starts: continue
    ain += ['-i', os.path.join(A, stem)]; delay = int((starts[sid] + off) * 1000)
    af.append(f"[{i}:a]volume={g}dB,adelay={delay}|{delay}[a{i}]"); mixin.append(f'[a{i}]')
af.append(f"{''.join(mixin)}amix=inputs={len(mixin)}:duration=longest:normalize=0,alimiter=limit=0.95,atrim=0:{total:.3f}[aout]")
audio = os.path.join(TMP, 'audio.wav')
run(['ffmpeg', '-y', '-loglevel', 'error', *ain, '-filter_complex', ';'.join(af), '-map', '[aout]', '-ar', '48000', audio])
final = os.path.join(R, 'JIJI_IN_MOTION' + ('_preview' if SUF else '_final') + '.mp4')
run(['ffmpeg', '-y', '-loglevel', 'error', '-i', video, '-i', audio, '-c:v', 'libx264', '-preset', 'slow', '-crf', '20', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k', '-shortest', '-movflags', '+faststart', final])
print('FINAL', final, dur(final))
