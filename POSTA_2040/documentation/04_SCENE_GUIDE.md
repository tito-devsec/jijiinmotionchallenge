# Scene guide

| # | Frames | What happens | Key systems |
|---|--------|--------------|-------------|
| Card | 72 | Collage opening title | `brand_cards.py` |
| 01 | 264 | Ground-level construction site in Posta, worker signals, the block assembles floor by floor | `GN_BuildUp`, construction kit, WORKER rig |
| 02 | 240 | Street-level: a real building's walls break into flowing 0/1 glyphs | `GN_BinaryTransform` progress 0→1 |
| 03 | 168 | Roads along the original geometry become data networks | same system on `CITY_ROAD` and paving |
| 04 | 216 | Aerial rise: all of Posta as a binary civilisation | binary on every class, mist |
| 05 | 264 | A binary hero walks and resolves into a real person, head first | binary system on a rigged character |
| 06 | 192 | The binary city resolves into realistic 2040 towers; cars, ferry | progress 1→0, `city_future.blend` |
| 07 | 192 | Camera rises over Kivukoni; the helicopter approaches | helicopter rotor animation |
| 08 | 216 | Passenger films on the HOT 70; camera dives into the main lens | phone asset, `PHONE_LENS_MAIN` |
| 09 | 168 | The real futuristic city inside a camera interface | `overlay_ui.py camera` |
| 10 | 168 | The phone slips, tumbles and splashes into the harbour | analytic fall, motion blur, splash |
| 11 | 192 | Underwater: sinks past fish to the reef sand | reef kit, caustics, fish schools |
| 12 | 216 | A diver finds the phone; the footage lights up | DIVER rig, swim cycle, Child Of pick-up |
| 13 | 168 | On deck, reviewing and sharing: "I FOUND SOMETHING FROM TOMORROW." | `overlay_ui.py social` |
| 14 | 168 | Product hero shot; JIJI IN MOTION / THE FUTURE IS WORTH CAPTURING. | studio lights over the harbour |
| Card | 120 | Pillars 01–03 and credit | `brand_cards.py` |

Product-accuracy rules respected: no waterproof claim or rating is shown, the underwater footage is presented as a fictional
cinematic device, the camera UI shows no invented specifications, and the share UI uses no third-party logos.
