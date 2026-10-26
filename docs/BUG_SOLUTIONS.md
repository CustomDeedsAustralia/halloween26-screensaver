# Bug Solutions

Check this file before fixing a bug in the Halloween 2026 screensaver.

## Wayland-scaled display shows a borderless window

**Symptom:** After running `wlr-randr --output DSI-1 --scale 0.75`, the
1480×320 borderless window no longer fills the Waveshare panel.

**Cause:** Wayland compositor scaling changes the logical desktop dimensions,
while a non-fullscreen pygame window still requests exactly 1480×320 logical
pixels.

**Solution:** Run the screensaver with `--fullscreen`:

```bash
python3 halloween26_screensaver.py --fullscreen
```

Do not use `--render-scale` to fix window sizing. That option changes the
internal rendering resolution for performance, not the output window size.

## Raspberry Pi performance

Start with the following profile and raise quality after confirming stable
performance:

```bash
python3 halloween26_screensaver.py --fullscreen --fps 30 --detail low --render-scale 0.5
```

The fog banks are the only full-width alpha blits in the frame; `--no-fog`
removes them entirely if frames still drop. Use `--frames 300` to print an
average FPS for a given set of options.

## Slow startup

**Symptom:** A pause of a second or two before the first frame.

**Cause:** All per-pixel shading (moon, tombstone), sprite generation and the
24 tombstone shimmer frames are built once at startup so the per-frame cost
stays low. `pygame.font.SysFont` also enumerates system fonts on first use.

**Solution:** Expected. To shorten it, drop an `assets/tombstone.ttf` file
beside the script (skips the system font scan) or lower `--render-scale`.

## Tombstone text wrong font / falls back to a plain font

**Cause:** `pygame.font.SysFont` is asked for `chiller, oldenglishtextmt,
blackadderitc, dejavuserif, liberationserif, serif` and silently uses the
pygame default font when none exist.

**Solution:** Install a serif font (`sudo apt install fonts-dejavu` on
Raspberry Pi OS) or place any TrueType file at `assets/tombstone.ttf`.

## Cloud has a hard vertical edge when it crosses the moon

**Cause:** Cloud blobs were drawn right up to the sprite boundary and got
clipped flat.

**Solution:** `build_cloud` pads the sprite by the largest blob radius so no
blob touches the edge. Keep the padding if you change blob sizes.

## Translucent detail punches holes in a sprite

**Symptom:** Moss, dust or shading drawn with an alpha colour leaves
see-through areas in the pumpkin, rack or tombstone.

**Cause:** `pygame.draw.*` and `Surface.fill` write raw RGBA on SRCALPHA
surfaces, replacing the pixel alpha instead of blending.

**Solution:** Draw translucent detail on a separate overlay surface and
`blit` it onto the opaque sprite (blitting alpha-blends). This pattern is
used in `build_rack`, `build_tombstone` and `build_pumpkin`; the only place
raw alpha replacement is intended is the deliberate "chip" erased from the
tombstone edge.

## Fog seam scrolls across the screen

**Cause:** A fog blob cut at the sprite's edge produces a visible join when
the layer wraps.

**Solution:** `build_fog_layer` draws every blob three times at `x - w`, `x`
and `x + w`, and the layer is blitted twice per frame at `x - w` and `x`.
Keep both halves of that scheme if you change the fog.

## Optional artwork is ignored

**Cause:** Override files must sit in `assets/` beside
`halloween26_screensaver.py` (paths are resolved from `__file__`, not the
working directory) and be named exactly `moon.png`, `tombstone.png` or
`tombstone.ttf`. An unreadable file prints a warning on stderr and the
procedural version is used.
