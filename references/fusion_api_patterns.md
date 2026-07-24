# Autodesk Fusion Python API Patterns

This is the cheat sheet for writing Fusion scripts that actually run. It covers the standard API patterns and non-obvious behaviours that commonly break naive code.

## Contents

- [Setup](#verify-api-signatures-first): signatures, units, and the minimal script skeleton.
- [Standard features](#sketch--extrude-the-basic-block): extrusions, assertions, holes, radial cuts, reruns, profiles, fillets, and construction planes.
- [Body operations](#combining-bodies): combines and body ownership.

## Verify API signatures first

Before using an unfamiliar class or method, inspect the local Autodesk Python stubs. They match the installed Fusion build:

```powershell
python "<skill-directory>/scripts/fusion_api_lookup.py" TemporaryBRepManager.createSphere
python "<skill-directory>/scripts/fusion_api_lookup.py" SketchFittedSplines.add
```

For temporary BRep geometry, fitted splines, base features, or runtime API errors, also read `fusion_api_research.md`.

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


BUILD_SPEC = {
    "schema_version": 1,
    "units": "cm",
    "coordinate_system": "Z runs from the mounting face toward the free end",
    "generated_body_prefixes": ["Generated "],
    "printable_body_names": ["Generated Main Body"],
    "expected_printable_body_count": 1,
    "print_orientation": {"Generated Main Body": "mounting face on bed"},
}


def run(context):
    app = adsk.core.Application.get()
    ui = app.userInterface

    try:
        design = adsk.fusion.Design.cast(app.activeProduct)
        if not design:
            raise RuntimeError('No active Fusion design. Create or open one first.')

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

The script reports completion or a full traceback inside Fusion so the user can relay the result when iterating.

Use `design.rootComponent` as the default modeling target. Do not create a new component with `root.occurrences.addNewComponent(...)` unless the script truly needs an assembly component: Fusion Part Design documents can reject that call with "Part Design documents can only contain one component." For multi-piece printable tools, create multiple named `NewBodyFeatureOperation` bodies in the root component.

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
distance = adsk.fusion.DistanceExtentDefinition.create(
    adsk.core.ValueInput.createByReal(2.0)
)
ext_in.setOneSideExtent(
    distance,
    adsk.fusion.ExtentDirections.PositiveExtentDirection,
)
feat = extrudes.add(ext_in)
body = feat.bodies.item(0)
```

`profiles.item(0)` works when there's exactly one closed loop. For sketches with multiple profiles (e.g. a circle inside a rectangle), you have to pick the right one — see "Profile selection" below.

## Feature and body assertions

Fail close to the feature that broke instead of allowing a missing or unhealthy result body to cause a misleading error many operations later:

```python
def require_result_body(feature, name):
    if not feature:
        raise RuntimeError("{} returned no feature".format(name))
    if feature.healthState != adsk.fusion.FeatureHealthStates.HealthyFeatureHealthState:
        raise RuntimeError(
            "{} is unhealthy: {}".format(name, feature.errorOrWarningMessage)
        )
    if feature.bodies.count == 0:
        raise RuntimeError("{} created no result body".format(name))
    body = feature.bodies.item(0)
    if not body or not body.isValid or body.volume <= 0.000001:
        raise RuntimeError("{} did not create a valid solid".format(name))
    return body
```

Use this after fragile extrudes, revolves, sweeps, combines, and branding cuts. For an intentionally zero-volume wire or surface body, validate the expected edge/face topology instead of volume.

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
    # Current replacement for the retired setDistanceExtent helper. Here the
    # supplied 2.0 cm value is the full symmetric length: 1.0 cm each way.
    ci.setSymmetricExtent(adsk.core.ValueInput.createByReal(2.0), True)
    extrudes.add(ci)
```

**Why symmetric extent?** When you offset a construction plane and put a sketch on it, Fusion's "default extrusion direction" (positive normal) is unpredictable — it depends on which way the offset went. A symmetric cut sidesteps this entirely by cutting in both directions. Choose the symmetric distance large enough to clear the body in both directions (1 cm each side is usually plenty).

**Why the `w2s` helper?** Sketches on construction planes have their own 2D basis. A point you intended to place at world `(1.0, 0.5, 2.0)` will land somewhere else if you just pass `Point3D.create(1.0, 2.0, 0)` directly. Always transform world coords through `sketch.transform.copy().invert()` first.

**Why cut planes must intersect target material:** Fusion can raise `RuntimeError: No target body found to cut or intersect` when the cut sketch starts from a plane that does not pass through material at that X/Y location. This often happens on parts with raised pads: a bolt hole outside the pad cannot be cut from the pad's top plane. Sketch through-holes on the base top face/plane, or use a symmetric cut from a plane that actually intersects the body at the hole location.

## Radial set-screw holes and clamp features

Keep the structural load path and the adjustment hardware easy to identify. For a pole socket, four ordinary ribs at the flange plus a short round clamp collar above them is often clearer and easier to print than merging the screw boss into a rib or replacing the ribs with a large sculpted transition. Use a separate boss only when a full collar is impractical.

Place the hole where a drill, tap, and hand knob have unobstructed access. For an M6 x 1 printed pilot, start near 5.0 mm, drill it to size after printing, and provide enough radial material for useful thread engagement without expecting the screw to carry the main structural load.

For a radial cut through a curved, tilted, or tapered exterior, do not stop the cut at the outer radius evaluated at the hole centre. The exterior envelope changes across the hole diameter and can leave a crescent covering part of the opening. Compute or conservatively bound the largest exterior position across the entire aperture, then add explicit overtravel on both sides:

```python
# Axis coordinates for a radial hole through a clamp collar.
inner_cut = bore_radius - 0.15       # 1.5 mm into the bore
outer_cut = max_outer_envelope + 0.30  # 3 mm beyond the exterior
cut_length = outer_cut - inner_cut
cut_midpoint = (inner_cut + outer_cut) / 2.0
```

Also keep the hole centre at least `hole_radius + margin` from each end of a short collar. Assert those distances when they are computable. After runtime generation, visually inspect both the exterior mouth and the bore-side mouth; syntax, feature health, body count, and positive volume can all pass while a hole is still partially occluded or visually awkward.

## Rerunnable scripts

When the user is iterating, scripts are often run multiple times in the same document. Name generated bodies clearly and delete only those bodies before rebuilding:

```python
GENERATED_BODY_PREFIXES = (
    "Front block",
    "Rear block",
)


def delete_previous_generated_bodies(component):
    bodies_to_delete = []
    for index in range(component.bRepBodies.count):
        body = component.bRepBodies.item(index)
        if any(body.name.startswith(prefix) for prefix in GENERATED_BODY_PREFIXES):
            bodies_to_delete.append(body)

    for body in bodies_to_delete:
        body.deleteMe()
```

Never delete all bodies in the root component; the document may contain user geometry.

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
