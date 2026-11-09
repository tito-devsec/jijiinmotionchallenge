# Infinix HOT 70 — product facts used in the film

Source: official specification sheet supplied by the author (model X6895B). Only facts from this sheet appear on screen.

| Used for | Fact |
|----------|------|
| 3D model size | 167.92 × 79.12 × 7.49 mm |
| Colour palette of the whole film | Night Pulse `#1A1A1D`, Dive Blue `#1E3A8A`, Silver Dancer `#D1D5DB`, Green Texture `#4F7F67`, Quiet Violet `#9B86BD`, Thermo Orange `#FF8C33` → `#E65100` |
| Hero phone colourway | Green Texture |
| Rear camera island / flash | rear dual flash modelled; front dual flash modelled |
| Camera interface | "2K · 30" (rear video 2K 30 fps), modes Super Night / Video / Portrait |
| Side button | side fingerprint (orange accent power key) |

## What the film deliberately does not claim

- **Water**: the sheet lists IP65 (splash, water jets and dust) and states that submersion damage is not covered by the
  warranty. The underwater sequence is a fictional cinematic device; no water-resistance rating or underwater
  capability is shown or implied.
- No battery, charging, chipset, memory or display numbers are shown in the film.
- No third-party or social-network logos are used.

## Palette enforcement

`posta_lib.enforce_palette()` runs on every scene before rendering. It snaps every material, light, sky and haze colour to
the nearest HOT 70 colourway (keeping brightness). Neutral colours map between Night Pulse and Silver Dancer. Human skin,
eyes and hair and the photographic leaf textures of trees are left natural. 2D layers (camera UI, share UI, titles,
collage cards) are drawn with the six hex values directly.
