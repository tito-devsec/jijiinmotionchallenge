# Asset and environment audit — JIJI IN MOTION (Posta 2040)

Date: 2026-11-09 · Environment: Linux cloud container, 4 CPU cores, 15 GB RAM, no GPU.

## Environment

| Item | Status |
|------|--------|
| Blender | Not pre-installed → **installed Blender 4.5.9 LTS** to `/opt/blender` |
| Render engines | Cycles CPU: OK (~11 s / simple 720p frame, 32 spp + denoise). EEVEE: OK via Mesa llvmpipe after installing `libegl1 libegl-mesa0` (18 s shader warm-up, then fast) |
| Python | 3.13 + numpy, Pillow, trimesh, pygltflib, shapely |
| FFmpeg | 6.1.1 (edit, encode, audio mix) |
| Node 22 / Playwright / Chromium | available for Three.js / p5.js supporting renders |
| Fonts | Inter, Inter Display, JetBrains Mono (OFL) — titles and binary glyphs |
| Network | blender.org, PyPI, Poly Haven API reachable; freesound.org blocked (403) |
| Filmcraft / Artcraft | not installed in this container; forks exist on the author's GitHub. Editing is done with FFmpeg here |

## Geographic source — verified

`gen-map_Export_-6.819_39.293_2200x1800.zip` → preserved untouched in `assets/city/original_map/` (SHA-256 in `CHECKSUMS.sha256`).

| Tile | Nodes | Triangles | Buildings | Roads | Bounds (m) |
|------|-------|-----------|-----------|-------|------------|
| X0_Y0 | 7,103 | 325,680 | 2,368 | 423 | x −1100…900, z −900…900 |
| X1_Y0 | 265 | 14,495 | 104 | 16 | x 900…1100 |

Materials carry semantic names (`OSM_Building_Wall`, `OSM_Road`, `OSM_Water`, `OSM_Terrain`…), so
every object class can be selected programmatically. GeoJSON carries OSM tags: 474 named features
including Ikulu (State House), National Museum of Tanzania, Karimjee Hall, High Court, Southern Sun,
Bandari Terminal, Fish Market. Building heights 0–112 m, 84 buildings ≥ 30 m.
Top-down check: `previews/00_original_map_topdown.png` — Kivukoni Front, ferry pier, Kigamboni and the
Azikiwe/Samora grid are all in place.

## Asset classification

A = already available · B = generated procedurally (code) · C = modelled directly in Blender · D = external download · E = user reference required

| Asset | Class | Notes |
|-------|-------|-------|
| Posta map (roads, buildings, water, terrain, trees) | **A** | ODbL, attribution included |
| Infinix HOT 70 | **C + E** | User supplied reference screenshots (front, rear, side, port, wireframe). Model built from scratch to match: vertical triple-lens pill camera housing, punch-hole display, flat frame, green textured back, Infinix wordmark. No third-party model file is used |
| Tesla Roadster | **C + E** | User supplied 6 reference views of a stylised roadster (white body, black glass canopy, 5-spoke wheels, red rear light bar, quad exhaust). Rebuilt procedurally |
| Helicopter | **C + E** | User supplied 6 views of a stylised helicopter with open passenger cabin. Rebuilt; nose-mounted guns in the reference are **omitted** (civilian passenger scene) |
| Rigged humans (hero + background) | **B + C + E** | User supplied a female athletic base-mesh reference and an armoured sci-fi suit reference. Humanoids are built procedurally with armatures; realism is limited by CPU/time, documented honestly |
| Construction workers, cranes, excavators | **B** | Procedural kits |
| Binary glyph system | **B** | Geometry Nodes + shaders |
| Buildings' futuristic materials | **B** | Procedural shaders, palette |
| Ocean surface / underwater volume | **B** | Shader + volumetrics |
| Coral, fish | **B + E** | User supplied reef photos for colour/composition; coral by procedural displacement, fish by instanced boids |
| Scuba diver | **C + E** | User supplied diver photo (mask, regulator, tank, fins) |
| Fonts | **A** | Inter / JetBrains Mono (OFL) |
| Music + SFX | **B** | Synthesised with NumPy (original, no licence risk). freesound.org is blocked and no paid library is used |
| HDRI sky | **D (optional)** | Poly Haven (CC0) reachable; procedural Nishita sky used by default |

Nothing was purchased, no subscriptions were started and no unlicensed commercial models are included.
