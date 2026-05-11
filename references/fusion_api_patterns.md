# Fusion 360 Python API — Patterns & Pitfalls

This file is the cheat sheet for writing Fusion 360 scripts that actually run. The Fusion API has several non-obvious behaviours that will silently break naive code. Use these patterns instead of guessing.

## Units

**Fusion's internal API unit is centimetres**, not millimetres. Every length you pass to `ValueInput.createByReal()` is in cm. Write parameters as cm and put the mm equivalent in a comment:

```python
WALL = 0.5      # 5 mm
HOLE = 0.42     # 4.2 mm
```

If you forget this, your part will be 10× too big and you'll waste time debugging.

## Minimal script skeleton

Every generated script should follow this shape:

```python
"""
<one-line title>
<2-3 line description of what the script builds>
"""
import adsk.core, adsk.fusion, traceback


def run(context):
    app = adsk.core.Application.get()
    ui = app.userInterface

    try:
        design = adsk.fusion.Design.cast(app.activeProduct)
        if not design:
            ui.messageBox('No active Fusion design. Create or open one first.')
            return

        rootComp = design.rootComponent
        sketches = rootComp.sketches
        extrudes = rootComp.features.extrudeFeatures

        # ── PARAMETERS (cm) ────────────────────────────────────────
        # ... pull every dimension into named constants here

        # ── GEOMETRY ──────────────────────────────────────────────
        # ... sketch + extrude + holes + fillets

        # ── DONE ──────────────────────────────────────────────────
        ui.messageBox('Created! <summary of dimensions>')

    except Exception:
        if ui:
            ui.messageBox('Script failed:\n{}'.format(traceback.format_exc()))
```

The `try/except` with `messageBox` is essential — Fusion swallows uncaught Python exceptions and you'll see nothing.

## Sketch + extrude (the basic block)

```python
sk = sketches.add(rootComp.xYConstructionPlane)
ln = sk.sketchCurves.sketchLines

# Build a closed polygon by sequential line segments
coords = [(0, 0), (5, 0), (5, 3), (0, 3)]
pts = [adsk.core.Point3D.create(x, y, 0) for x, y in coords]
for i in range(len(pts)):
    ln.addByTwoPoints(pts[i], pts[(i + 1) % len(pts)])

ext_in = extrudes.createInput(
    sk.profiles.item(0),
    adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
)
ext_in.setDistanceExtent(False, adsk.core.ValueInput.createByReal(2.0))
feat = extrudes.add(ext_in)
body = feat.bodies.item(0)
```

`profiles.item(0)` works when there's exactly one closed loop. For sketches with multiple profiles (e.g. a circle inside a rectangle), you have to pick the right one — see "Profile selection" below.

## Holes — the reliable pattern

The `HoleFeatures` API and direct `CutFeatureOperation` extrudes both have direction-and-face-selection footguns. The most reliable approach is **subtractive cylinder extrusion using a symmetric cut**:

```python
# Create a construction plane at the height where the hole starts
cpIn = rootComp.constructionPlanes.createInput()
cpIn.setByOffset(
    rootComp.xZConstructionPlane,
    adsk.core.ValueInput.createByReal(WALL),  # plane at y = WALL
)
top_plane = rootComp.constructionPlanes.add(cpIn)


def w2s(sketch_obj, wx, wy, wz):
    """Convert a world (x, y, z) point to this sketch's local 2D coords.
    Critical helper — without this, points placed on a construction plane
    will land in the wrong place because the sketch has its own basis."""
    t = sketch_obj.transform.copy()
    t.invert()
    p = adsk.core.Point3D.create(wx, wy, wz)
    p.transformBy(t)
    return p.x, p.y


def cut_hole(world_x, world_z, dia, plane_y):
    """Sketch a circle on top_plane at world (world_x, plane_y, world_z)
    and cut-extrude symmetrically through the body."""
    s = sketches.add(top_plane)
    sx, sy = w2s(s, world_x, plane_y, world_z)
    s.sketchCurves.sketchCircles.addByCenterRadius(
        adsk.core.Point3D.create(sx, sy, 0), dia / 2
    )
    ci = extrudes.createInput(
        s.profiles.item(0),
        adsk.fusion.FeatureOperations.CutFeatureOperation,
    )
    # Symmetric extent eliminates the "wrong direction" failure mode:
    # the cut extends both ways from the sketch plane, so it always
    # passes through the body regardless of which way "positive normal"
    # points on this construction plane.
    ci.setDistanceExtent(True, adsk.core.ValueInput.createByReal(1.0))
    extrudes.add(ci)
```

**Why symmetric extent?** When you offset a construction plane and put a sketch on it, Fusion's "default extrusion direction" (positive normal) is unpredictable — it depends on which way the offset went. A symmetric cut sidesteps this entirely by cutting in both directions. Choose the symmetric distance large enough to clear the body in both directions (1 cm each side is usually plenty).

**Why the `w2s` helper?** Sketches on construction planes have their own 2D basis. A point you intended to place at world `(1.0, 0.5, 2.0)` will land somewhere else if you just pass `Point3D.create(1.0, 2.0, 0)` directly. Always transform world coords through `sketch.transform.copy().invert()` first.

## Profile selection

When a sketch contains multiple closed loops, `sk.profiles` gives you all of them and you have to pick the right one. Two reliable strategies:

1. **One sketch per feature.** Don't pile multiple unrelated shapes into the same sketch. Then `profiles.item(0)` is always the right one. The minor cost (a busier feature tree) is worth the reliability.
2. **Pick by area.** If you must share a sketch, iterate `sk.profiles` and pick by `pr.areaProperties().area`. Smallest area = the inside of a hole circle; largest = the outer boundary.

## Fillets

```python
fillet_edges = adsk.core.ObjectCollection.create()
for ei in range(body.edges.count):
    e = body.edges.item(ei)
    sv = e.startVertex.geometry
    ev = e.endVertex.geometry
    # Predicate: identify the edge by its endpoint coordinates
    if abs(sv.y) < 0.01 and abs(ev.y) < 0.01:
        fillet_edges.add(e)

if fillet_edges.count > 0:
    fi = rootComp.features.filletFeatures.createInput()
    fi.addConstantRadiusEdgeSet(
        fillet_edges,
        adsk.core.ValueInput.createByReal(0.2),  # 2 mm
        True,
    )
    rootComp.features.filletFeatures.add(fi)
```

Edge identification by coordinate predicate is the most reliable way to pick edges programmatically. Wrap the whole fillet block in `try/except` and `pass` on failure — fillets are cosmetic, so a failed fillet shouldn't kill the whole script.

## Construction planes

```python
# Offset from a base plane along its normal
cpIn = rootComp.constructionPlanes.createInput()
cpIn.setByOffset(
    rootComp.xZConstructionPlane,                       # base plane
    adsk.core.ValueInput.createByReal(WALL),            # offset distance
)
plane = rootComp.constructionPlanes.add(cpIn)
```

The three default planes are `xYConstructionPlane`, `xZConstructionPlane`, `yZConstructionPlane` on `rootComp`.

## Combining bodies

If you build features as separate `NewBodyFeatureOperation` bodies and want to merge or subtract them:

```python
combines = rootComp.features.combineFeatures
tool_bodies = adsk.core.ObjectCollection.create()
tool_bodies.add(other_body)

ci = combines.createInput(target_body, tool_bodies)
ci.operation = adsk.fusion.FeatureOperations.CutFeatureOperation  # or JoinFeatureOperation
combines.add(ci)
```

This is an alternative to direct cut-extrude when geometry is complex enough that you'd rather build the cutter as its own body first.

## Sweep cut along a 3D path — use "build then combine"

Direct `sweepFeatures.createInput(profile, path, CutFeatureOperation)` along a 3D fitted spline frequently fails with:

```
RuntimeError: 3 : NO_TARGET_SWEEP_BODY - No intersecting target body was found.
```

Fusion's auto target-body detection on 3D paths is unreliable even when the swept tube clearly intersects an existing body. The robust pattern is to build the swept tube as its own body first, then subtract it via a Combine feature:

```python
# 1. Sweep as a NEW BODY (not a cut)
si = sweeps.createInput(profile, path, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
sweep_feat = sweeps.add(si)
cutter = sweep_feat.bodies.item(0)

# 2. Combine-subtract from the target
tools = adsk.core.ObjectCollection.create()
tools.add(cutter)
ci = rootComp.features.combineFeatures.createInput(target_body, tools)
ci.operation = adsk.fusion.FeatureOperations.CutFeatureOperation
ci.isKeepToolBodies = False  # discard the cutter after subtraction
rootComp.features.combineFeatures.add(ci)
```

Track the target body explicitly when you create it (`target_body = rev_feat.bodies.item(0)`) so you can pass it directly to Combine — don't rely on `bRepBodies.item(0)` after multiple operations have run.

The same logic applies for sweep-join along a 3D path. Build first, then combine.

## `setByDistanceOnPath` — never pass exactly 0.0

`ConstructionPlaneInput.setByDistanceOnPath(curve, ValueInput.createByReal(0.0))` can produce a plane with an undefined tangent at the curve's start, which downstream operations then reject. Use a tiny offset like `0.001` (well within fitted-spline tolerance) instead of `0.0`.

## 3D paths — DON'T trust fitted splines, USE sketch line polylines

`SketchFittedSplines.add(point_collection)` is documented as auto-promoting to a 3D spline when fit points are non-coplanar. **In practice this is unreliable in current Fusion builds** — the points get silently projected onto the sketch plane, collapsing your helix to a flat ring at the plane's z. The sweep then succeeds (no error) but the resulting tube is in the wrong place, so the downstream cut/combine removes nothing visible.

Use `SketchLines.addByTwoPoints(p1, p2)` with `Point3D` arguments instead. 3D coordinates are reliably preserved on sketch lines, and `features.createPath(first_line)` auto-chains the connected segments into a usable Path:

```python
sk_path = sketches.add(rootComp.xYConstructionPlane)
sl = sk_path.sketchCurves.sketchLines

prev = adsk.core.Point3D.create(x0, y0, z0)
first_line = None
for i in range(1, N + 1):
    curr = adsk.core.Point3D.create(xi, yi, zi)  # any non-coplanar 3D point is fine
    line = sl.addByTwoPoints(prev, curr)
    if first_line is None:
        first_line = line
    prev = curr

path = rootComp.features.createPath(first_line)
```

The polyline isn't C¹-smooth, but with 60–100 segments per helix turn the kinks are well below sweep's tolerance.

## Verify cuts actually applied — `body.volume`

When sweep+combine cut along a 3D path silently produces no change, the script reports success and the user opens a "incomplete geometry" file. Always capture `body.volume` before and after a cut/combine step and surface the delta in the final `messageBox`:

```python
vol_before = main_body.volume
# ... combine cut ...
vol_after = main_body.volume
removed = vol_before - vol_after
ui.messageBox('Slot removed: {:.2f} cm³ {}'.format(
    removed, '✓' if removed > 0.5 else '⚠ no cut!'))
```

This makes silent geometric failures obvious to the user without needing them to hunt through the timeline.

## Sketch text — extrude the SketchText, not its profiles

`sk.profiles` does NOT contain entries for sketch text. Iterating it returns 0 profiles, so passing the resulting empty ObjectCollection to `extrudes.createInput()` raises `invalid profile(s) for Extrude Feature`.

`extrudeFeatures.createInput()` accepts a `SketchText` object directly. Capture the return value of `sketchTexts.add()` and pass it in:

```python
ti = sk.sketchTexts.createInput2('Example User', 1.6)
ti.setAsMultiLine(corner1, corner2, h_align, v_align, 0.0)
ti.fontName = 'Calibri'
text_obj = sk.sketchTexts.add(ti)        # capture this!

ei = extrudes.createInput(
    text_obj,                            # SketchText, not profiles
    adsk.fusion.FeatureOperations.CutFeatureOperation,
)
ei.setDistanceExtent(False, adsk.core.ValueInput.createByReal(-DEPTH))
extrudes.add(ei)
```

The same applies to JoinFeatureOperation if you're embossing text raised from a surface.

## Common pitfalls (quick list)

| Symptom | Cause | Fix |
|---|---|---|
| Part is 10× too big | Treated cm as mm | Divide all lengths by 10 |
| Holes appear above the part, not in it | Cut extrude went the wrong direction | Use `setDistanceExtent(True, …)` (symmetric) |
| Hole is in the wrong location on a construction plane | Skipped the world→sketch transform | Use the `w2s` helper |
| `profiles.item(0)` cuts away the body instead of the hole | Picked the outer profile, not the circle | One sketch per feature, or pick by smallest area |
| Script silently does nothing | Uncaught exception | Wrap in `try/except` with `messageBox(traceback.format_exc())` |
| `ValueInput.createByReal` errors | Passed an int where a float was expected | Always pass floats (`1.0` not `1`) |
| Created body but no confirmation | Forgot the final messageBox | Always end with a summary `messageBox` so the user knows it worked |
