# JIJI IN MOTION — The Future Is Built in Code

**A cinematic creative-coding film set in Posta / Kivukoni, Dar es Salaam, Tanzania — 2040.**

Posta begins as an ordinary construction site, becomes a city of binary digits, grows into a living
digital civilisation and finally resolves into a realistic futuristic Tanzanian city, captured through
the lens of an Infinix HOT 70 and discovered on the floor of the Indian Ocean.

Everything in this repository is built in code: the city is generated from real OpenStreetMap geometry
of Posta, the binary transformations are Blender Geometry Nodes and shader systems driven by Python,
every 3D asset is modelled procedurally from reference, the sound design is synthesised with NumPy and
the edit is assembled with FFmpeg.

## Repository description (for the GitHub "About" field)

> Cinematic creative-coding film: real Posta/Kivukoni (Dar es Salaam) map → construction → binary city →
> digital civilisation → realistic 2040 Tanzania, captured on an Infinix HOT 70. Blender Geometry Nodes,
> Python, GLSL, procedural audio, FFmpeg. © tito-devsec. Code GPL-3.0, film and assets All Rights Reserved.

## Watch the film

- **Final film:** `POSTA_2040/renders/JIJI_IN_MOTION_final.mp4` — 2 min 02 s, 1280×720, 24 fps, H.264 + AAC stereo.
- Per-scene clips: `POSTA_2040/renders/clips/` · frame contact sheet: `POSTA_2040/previews/final_contact_sheet.png`.

## Story (14 scenes)

| # | Scene | Core technique |
|---|-------|----------------|
| 01 | The city begins with construction | Procedural build-up animation of real OSM footprints |
| 02 | Real buildings transform into binary | Geometry Nodes surface→glyph instancing, progress-driven |
| 03 | Roads become digital | Same system on OSM road meshes, flowing data pulses |
| 04 | Posta as a binary civilisation | Aerial reveal, volumetrics, emission palette |
| 05 | Humans transform from binary into real people | Rigged characters, point-cloud→skin shader transition |
| 06 | Realistic futuristic civilisation | Same geography, realistic materials |
| 07 | Ascent and the helicopter | Procedural helicopter, animated rotor |
| 08 | The Infinix HOT 70 moment | Phone modelled to reference, macro lens dive |
| 09 | Through the camera, the city is real | Camera-UI framed realistic Posta |
| 10 | The phone falls into the ocean | Rigid-body gravity, motion blur, tracking camera |
| 11 | Underwater world | Volumetric water, caustics, coral, fish boids |
| 12 | The diver discovers the phone | Procedural diver, bubbles |
| 13 | "I FOUND SOMETHING FROM TOMORROW." | Clean screen UI |
| 14 | Brand reveal — JIJI IN MOTION | Product shot, Posta skyline |

## Project structure

```
POSTA_2040/
  assets/        original map (untouched), references, generated assets, audio
  blender/       original_map.blend, posta_2040.blend, characters.blend, vehicles.blend
  scripts/       city_generation / binary_transformation / human_transformation / camera / rendering
  shaders/       GLSL and OSL sources
  previews/      per-scene test frames
  renders/       final frames and the edited film
  audio/         synthesised sound design and music
  documentation/ asset audit, pipeline, map comparison, process notes
  tools/         inspection and validation utilities
```

## Geographic source

`POSTA_2040/assets/city/original_map/` is the authoritative, unmodified gen-map export of
Posta/Kivukoni (2200 × 1800 m, origin −6.81926, 39.29268): 2,472 buildings, 439 roads, waterfront,
terrain, trees. It is © OpenStreetMap contributors (ODbL) and is never edited; all transformations
are applied to copies. See `THIRD_PARTY_NOTICES.md`.

## Pipeline

Blender 4.5 LTS (headless, Cycles CPU) · Python 3 / bpy · Geometry Nodes · GLSL/OSL · NumPy audio
synthesis · FFmpeg. Related forks maintained by the author for this pipeline:
[blender](https://github.com/tito-devsec/blender), [filmcraft](https://github.com/tito-devsec/filmcraft),
[artcraft](https://github.com/tito-devsec/artcraft), [effectcraft](https://github.com/tito-devsec/effectcraft),
[photocraft](https://github.com/tito-devsec/photocraft).

## Reproduce the film

Requirements: Blender 4.5 LTS (headless is fine), Python 3 with NumPy and Pillow, FFmpeg.

```bash
# 1. city from the OSM export (original preserved untouched), DEM fixes, 2040 towers, trees
blender -b --python POSTA_2040/scripts/city_generation/build_city_base.py
blender -b --python POSTA_2040/scripts/city_generation/fix_water_level.py
blender -b --python POSTA_2040/scripts/city_generation/flatten_terrain.py
blender -b --python POSTA_2040/scripts/city_generation/build_future_city.py
blender -b --python POSTA_2040/scripts/city_generation/lift_roads.py
# 2. assets
for a in phone roadster helicopter characters construction underwater trees; do blender -b --python POSTA_2040/scripts/assets/build_$a.py; done
blender -b --python POSTA_2040/scripts/city_generation/place_trees.py
# 3. sound design and music
python3 POSTA_2040/scripts/audio/synth_sound_design.py
# 4. render + edit (preview pass, then final)
POSTA_2040/scripts/rendering/render_film.sh preview
POSTA_2040/scripts/rendering/render_film.sh final
```

Outputs: `POSTA_2040/renders/JIJI_IN_MOTION_final.mp4`, per-scene review clips in `POSTA_2040/renders/clips/`.
Documentation: `POSTA_2040/documentation/` (asset audit, pipeline, map comparison, scene guide).

## Campaign pillars

- **01 Maisha ya miji ya TZ** — the real Posta map, Kivukoni Front, the harbour and its ferry, palms and mango trees.
- **02 Rangi za HOT 70** — the palette and grade follow the HOT 70 colourways.
- **03 Mtazamo na ubunifu wako** — a streetwear hero styled after the campaign poster, collage title cards and the author's credit.

## Licence

- **Source code** (`scripts/`, `shaders/`, `tools/`): GNU GPL v3.0 or later — see `LICENSE`.
- **Film, renders, audio, 3D models, storyboard, documentation and all creative content**:
  © 2026 tito-devsec. **All Rights Reserved** — see `LICENSE-CREATIVE.md`.
- Third-party data and tools: see `THIRD_PARTY_NOTICES.md`.

Infinix and HOT 70 are trademarks of their owner; they are depicted as story objects and this
project is not affiliated with or endorsed by Infinix.
