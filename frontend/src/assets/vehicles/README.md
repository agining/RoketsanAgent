# Vehicle map sprites

200 transparent 128 × 128 WebP renders. Indices 0–7 mean N, NE, E, SE,
S, SW, W, NW relative to the screen. OperationsMap subtracts map bearing
from track heading before selecting a frame. Pitch does not change the
pre-rendered camera angle. Missing heading defaults to north.

## Sources and licenses

- car: Kenney Car Kit 3.1, sedan.glb
- van: Kenney Car Kit 3.1, van.glb
- truck: Kenney Car Kit 3.1, delivery.glb (box truck)
- bus: Quaternius Public Transport Pack, Bus.fbx; risk-colored body with blue windows

Both packs are CC0: https://creativecommons.org/publicdomain/zero/1.0/
Kenney: https://kenney.nl/assets/car-kit
Quaternius: https://quaternius.com/packs/publictransport.html
Bus downloaded from the author's alternate distribution:
https://opengameart.org/content/lowpoly-public-transport

Original selected models and Kenney texture/license are in sources/.
These files are build inputs only; the application imports just the WebP sprites.
Body colors and surrounding rings indicate risk: LOW green, MEDIUM amber, HIGH orange,
CRITICAL red, UNKNOWN gray. Only body atlas cells are recolored; lights, glass and tires
keep their original colors. Truck cab remains white; its cargo body carries risk color.
Unknown classes use a neutral procedural model with an upright question-mark badge.
Untracked detections use a fixed illustrative angle (not an inferred heading), a dashed risk ring,
and lower opacity when filtered. Unknown geometry is defined in the generator.

## Regenerate

From the repository root, with frontend development dependencies installed:

```sh
npm install --prefix /tmp/vehicle-render-tools three@0.180.0 --no-audit --no-fund
node scripts/render-vehicle-sprites.cjs /tmp/vehicle-render-tools
```

Requires Google Chrome at /usr/bin/google-chrome, or set CHROME_PATH.
Three.js is used only by this offline generator, not by the application.
