# Fusion 360 Python API — Patterns & Pitfalls

This file is the cheat sheet for writing Fusion 360 scripts that actually run. The Fusion API has several non-obvious behaviours that will silently break naive code. Use these patterns instead of guessing.

## Contents

- [Setup and basic features](#verify-api-signatures-first): signatures, units, skeletons, extrusion, holes, and fillets.
- [Reliable modeling](#feature-and-body-assertions): assertions, reruns, construction planes, profiles, combines, and temporary BRep.
- [Text and interfaces](#sketch-text-and-curved-body-engraving): engraving, mating envelopes, reference geometry, datums, and bezels.
- [Print-fit workflow](#thread-reconstruction): threads, gauges, breakaway tabs, orientation, and printable-body accounting.
- [Troubleshooting](#common-pitfalls-quick-list): symptom-to-fix table and worked-example conventions.

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

## Temporary BRep bodies

Use `TemporaryBRepManager` for freeform solids, spheres, oval ribs, internal sealed pockets, and compound cutters. Temporary BRep booleans mutate the target body, so always check the return value before persisting the body.

```python
temp_mgr = adsk.fusion.TemporaryBRepManager.get()
target = temp_mgr.createSphere(adsk.core.Point3D.create(cx, cy, cz), radius)
tool = temp_mgr.createCylinderOrCone(p1, tool_radius, p2, tool_radius)

if not temp_mgr.booleanOperation(target, tool, adsk.fusion.BooleanTypes.DifferenceBooleanType):
    raise RuntimeError("Temporary BRep boolean failed: channel")

base = rootComp.features.baseFeatures.add()
if not base.startEdit():
    raise RuntimeError("Could not start BaseFeature edit")
try:
    source_body = rootComp.bRepBodies.add(target, base)
    if not source_body:
        raise RuntimeError("Could not persist temporary body")
finally:
    if not base.finishEdit():
        raise RuntimeError("Could not finish BaseFeature edit")

# source_body is edit-only and can become invalid after finishEdit(). Always
# reacquire the parametric result body before using it in combines or features.
if base.bodies.count == 0:
    raise RuntimeError("BaseFeature created no result body")
body = base.bodies.item(0)
if not body or not body.isValid:
    raise RuntimeError("BaseFeature result body is invalid")
body.name = "generated body"
```

In a parametric design, persist temporary bodies through a base feature using `startEdit()` / `finishEdit()`. Do not assume a normal cut extrude will find a target body when the cutter is on an offset plane or only partially intersects a curved body.

The body returned by `rootComp.bRepBodies.add(..., base)` is the source body visible only while the BaseFeature is being edited. Passing it to `CombineFeatures.createInput` after `finishEdit()` can raise `ALL_TOOL_BODY_REFERENCE_LOST`. Use `base.bodies.item(0)` instead.

## Sketch text and curved-body engraving

Text that looks valid in a sketch can still fail during a solid boolean. Treat text, profile references, and curved target bodies as three separate failure surfaces.

### Keep text-box points exactly on the sketch plane

`modelToSketchSpace` can leave a microscopic normal-coordinate residue on an offset plane. Sketch curves may accept it, but `SketchTextInput.setAsMultiLine` can raise `Invalid Point - position needs to be located on sketch plane`.

```python
def sketch_plane_point(sketch, world_point):
    local = sketch.modelToSketchSpace(world_point)
    return adsk.core.Point3D.create(local.x, local.y, 0.0)
```

Use this flattened point for APIs that explicitly require points on the sketch XY plane.

### Resolve profiles after all sketch mutations

Adding `SketchText` or more curves can rebuild `sketch.profiles` and invalidate previously captured `Profile` objects. Create every curve and text object first, then query profiles, select the intended profile, and check `profile.isValid` immediately before feature creation.

For an outlined frame, `profile.profileLoops.count == 2` is often a useful predicate. Prefer separate sketches when practical.

### Use boolean-friendly fonts and orientation

- Prefer simple static TrueType fonts such as Arial for geometry that will be extruded.
- Avoid variable fonts combined with forced bold, horizontal flip, and vertical flip. They can produce outlines that display correctly but fail with `ASM_INCONS_REL`.
- For path text that must read in the opposite direction, reverse the path endpoints instead of flipping the glyphs.
- Treat a path as the glyph baseline, not its visual centreline. `setAsFitOnPath(..., True)` does not inherently mean world `+Z`; its side depends on the path direction and sketch basis.
- Reversing a path also reverses which side Fusion considers "above." Recalculate the baseline offset. If glyphs rise toward world `+Z`, start a nominal height `h` at `centre_z - h / 2`; use `centre_z + h / 2` when they rise toward `-Z`.
- Font ascent, descent, and side bearings make nominal height and path width imperfect visual bounds. Expose small X/Z nudge parameters for framed monograms, inspect the generated result, and prefer custom sketch geometry when exact optical centring matters.
- Define visual gaps numerically. Do not rely only on nominal path endpoints; compute logo bounds, text bounds, and inter-item spacing.
- Decide the colour method before modeling. Debossed text is ideal for paint filling. Sideways lettering that spans many Z layers is expensive in an AMS; use separate shallow inlay bodies only when true multicolour output is worth the repeated swaps and purge.

### Split compound branding booleans

Do not send a mixed collection of an outlined logo profile and several `SketchText` objects into one curved-body cut. Fusion can fail the entire operation with `ASM_INCONS_REL`. Cut one profile or text object per feature and pass the latest result body into the next cut.

```python
def cut_branding_entity(root, target_body, plane, entity, depth, name):
    origin = plane.geometry.origin
    toward_body = adsk.core.Vector3D.create(-origin.x, -origin.y, 0.0)
    if not toward_body.normalize():
        raise RuntimeError("Could not determine branding direction")

    plane_normal = plane.geometry.normal
    direction = (
        adsk.fusion.ExtentDirections.PositiveExtentDirection
        if plane_normal.dotProduct(toward_body) >= 0.0
        else adsk.fusion.ExtentDirections.NegativeExtentDirection
    )

    extent = adsk.fusion.ToEntityExtentDefinition.create(
        target_body,
        False,
        adsk.core.ValueInput.createByReal(-depth),
    )
    extent.isMinimumSolution = True
    extent.directionHint = toward_body

    extrudes = root.features.extrudeFeatures
    inp = extrudes.createInput(
        entity,
        adsk.fusion.FeatureOperations.CutFeatureOperation,
    )
    inp.participantBodies = [target_body]
    if not inp.setOneSideExtent(extent, direction):
        raise RuntimeError("Could not define '{}' extent".format(name))

    volume_before = target_body.volume
    feature = extrudes.add(inp)
    if not feature or feature.bodies.count == 0:
        raise RuntimeError("'{}' created no result body".format(name))
    result_body = feature.bodies.item(0)
    if volume_before - result_body.volume <= 0.000001:
        raise RuntimeError("'{}' removed no material".format(name))
    feature.name = name
    return result_body
```

The negative `ToEntity` offset above is intended to continue from the near exterior face into the body. Derive direction from the actual plane geometry and verify material removal; do not trust an assumed construction-plane normal or offset sign.

## Mating-envelope audit

For connectors, threads, cartridges, and nested sleeves, draw a radial/axial cross-section before coding. Label every region as printed material, reused hardware, mating-part travel, wire clearance, or intentional void.

- Research official manufacturer drawings or STEP files for the complete mating envelope, latch travel, keyways, and insertion depth.
- Do not infer shell geometry from standardized pin spacing alone.
- Explicitly determine which connector member enters which bore. Male/female labels describe contacts and do not reliably describe the largest mating shell.
- Inspect both halves in their mated orientation. Preserve an annular void only when the other connector actually occupies it; otherwise the gap creates needless weakness and should remain solid.
- If strength is low around a required mating void, add material outward where the product envelope permits; do not fill the mating volume.
- Keep separate retention functions separate in the model. For an XLR microphone interface, the cable plug's spring latch normally needs a blind recess with solid backing; the reused chassis insert may independently need a measured keyway and radial retaining-screw access. Do not replace the latch recess with a fragile printed cantilever unless the real mechanism requires one.

## Reference geometry and dimension provenance

When an existing STL, STEP, drawing, or failed print defines a working interface, extract its dimensions before redesigning the surrounding structure.

- Record plate bounds, thickness, hole diameters, hole centres/pitch, keyed profile vertices, and coordinate orientation.
- Keep a dimension ledger that labels each value as user-measured, recovered from geometry, manufacturer-specified, inferred, or chosen clearance.
- Preserve interface dimensions unless the user explicitly changes them. A request to thicken walls does not silently authorize moving chassis holes.
- Treat numbered prose carefully. A value following `3.` may be measurement number three, not a 3 mm dimension; never reuse one measurement for another feature without evidence.
- Use photographs to confirm topology such as a straight bevel versus a radius, but not to assign an exact chamfer without scale. Measure it, obtain a drawing, choose a deliberately non-interfering profile, or generate a coupon.
- After regeneration, compare the exported mesh's bounding box and critical dimensions with the ledger. Existing STL/3MF exports are stale until explicitly regenerated.

Before approving the redesign, produce or internally evaluate a reconciliation table:

| Interface | Reference value | Script value | Difference | Status |
|---|---:|---:|---:|---|
| Mount-hole pitch | measured from mesh | parameter/derived | signed difference | match/change/block |
| Hole diameter | measured from mesh | parameter/derived | signed difference | match/change/block |
| Plate bounds/thickness | measured from mesh | parameter/derived | signed difference | intentional/unintentional |
| Keyed opening vertices | measured or specified | generated profile | per-axis difference | clear/interfering |

Do not stop at the mesh bounding box when the preserved interface contains holes or keyed profiles. If exact extraction is unavailable, state which interface remains unverified and do not claim print readiness.

For a binary STL, a lightweight read-only parser can recover exact mesh vertices, bounds, cylindrical-hole centres, and planar profile vertices without importing it into the Fusion script. Keep import/reconstruction out of the generated script unless the user explicitly requests it.

## Axial datum and stop audit

Draw an axial section and name every relevant plane before writing length formulas:

```text
outside face | front lip | rear panel face | seated part face ... body end | stop front | stop back
```

Derive positions from the part's actual seated face, not from an assumed origin or the model's overall end. Keep these quantities separate:

- front lip thickness or face setback;
- measured face-to-shoulder/body/strain-relief distances;
- desired axial play;
- stop front position;
- stop thickness;
- final rail or enclosure end.

For example:

```python
relief_start = seated_face_z + face_to_relief
stop_front = relief_start + axial_clearance
rail_end = stop_front + stop_thickness

if stop_front < relief_start:
    raise RuntimeError("Rear stop intersects the mating part")
```

Do not let a terminal stop's thickness consume the clearance it is meant to provide. Audit the complete installation motion too: the final position can be valid while the part still collides with the stop before it reaches that position.

Calculate and report the signed margin, not merely the two positions:

```python
rear_margin = stop_front - relief_start
if rear_margin < 0.0:
    raise RuntimeError("Rear stop collision: {:.2f} mm".format(-rear_margin * 10.0))
```

Use the same signed-margin pattern for retaining-lip overlap, material around screw pilots, cover play, and insertion clearances.

## Retaining bezels and external mating access

If a front opening is smaller than the retained connector face, that face cannot project through it. A full-thickness small opening therefore recesses the connector by the panel thickness and may prevent the external mate from reaching full engagement.

Use a stepped bezel when capture and mating access conflict:

1. Cut a rear pocket large enough for the retained face/body plus print clearance.
2. Leave only the structurally required front lip thickness.
3. Cut the smaller mating aperture through that lip.
4. Verify the external mate's insertion depth, shoulder envelope, keyed corners, and withdrawal path.
5. Assert positive overlap between the lip and retained shoulder on every relevant side.

Do not describe a face as projecting through an opening when the coded opening is smaller than that face. Keep comments, datums, and geometry consistent after revisions.

## Gravity, support datums, and accumulated play

For a part that rests on a printed floor, place the nominal part bottom on the support datum. Do not center it inside a symmetrically enlarged vertical cavity unless another feature actually holds it centered.

Symmetric vertical clearance can accumulate unexpectedly: a nominal `0.4 mm` allowance above and below becomes `0.8 mm` above once gravity consumes the lower gap, and any separate lid clearance adds again. This can also shift a tight mating aperture relative to the supported part.

Specify independently:

- lateral insertion clearance;
- support-surface datum;
- top/lid clearance;
- axial clearance at each stop.

Use pads or ribs when a moulded body's true seating surface is not its bounding-box minimum. Measure the offset between the support surface and the mating-feature centreline when tight alignment matters.

## Thread reconstruction

Treat crest count, pitch, turns, lead-in, and total engagement as separate measurements.

- If a measurement runs from the centre of the first crest to the centre of the Nth crest, it spans `N - 1` pitch intervals. Ask what the caliper endpoints touched instead of dividing blindly by the crest count.
- Compare the result with nearby standard pitches, but use full-length labeled coupons to resolve measurement and printer error.
- Keep the production coupon's engaged axial length and thread profile representative of the final part. A short token helix can fit while the full thread binds.
- Compute turns explicitly from the helix centreline height and pitch. If more complete loops must occupy the same axial height, pitch or path height must change coherently; do not stack a duplicate helix over the same path.
- Extend total ridge length by the profile's axial half-width at both ends when the sweep profile projects beyond the helix centreline.
- Model the assembled axial stop separately from thread pitch and diameter. A setback measured from the female part's lip is not automatically the correct male lead-in; copying it to both halves can double the clearance and leave a visible gap when fully tightened.
- When pitch and hand fit are already proven, correct axial seating with male lead-in, runout, or neck height before changing thread diameter or pitch.

For a printed male threaded collar, keep these dimensions independent and report them in the build contract:

- female lip-to-first-thread setback;
- male shoulder-to-first-thread lead-in;
- helix centreline path height;
- thread-profile axial half-width;
- total threaded neck height;
- pass-through bore diameter;
- minimum radial wall beneath the thread root.

For a swept thread profile, calculate the occupied axial ridge length rather than treating the path height as the full thread:

```python
ridge_axial_length = helix_path_height + 2.0 * profile_axial_half_width
threaded_neck_height = male_lead_in + ridge_axial_length
thread_turns = helix_path_height / pitch
root_wall = (thread_root_diameter - pass_through_bore) / 2.0
```

If the mating thread screws on comfortably but leaves a closed-up assembly gap, preserve the proven major diameter and pitch. Reduce duplicated male lead-in or excess neck/runout by the measured gap while retaining a little axial play. Recompute turns and root wall, then assert that the shoulder still seats and the thread remains printable.

Treat the central opening as a separate functional interface. Measure the cartridge or nested part's maximum diameter, the old nominal CAD bore, and the resulting printed bore in the same material and orientation. Estimate the revised nominal bore with:

```text
new_cad_bore = desired_printed_bore + (old_cad_bore - measured_printed_bore)
```

Add deliberate insertion clearance to `desired_printed_bore`; do not merely set it equal to the mating part. Verify that the larger bore still leaves adequate `root_wall`. When the collar is a separate printable body, reprint only that body after a collar-only change.

## Fit gauges and production mode

For uncertain printed fits, generate small gauges around the nominal dimension before the final part.

- Use at least three values spanning likely printer/material error.
- Add permanent physical identifiers such as one, two, and three holes. Body names alone are lost after slicing.
- Select the easiest repeatable hand fit that does not wobble or require force.
- Copy the selected value into the production parameter.
- Record nominal CAD size, measured printed size, material, orientation, and desired final size. For the same printer/material/orientation, use `new_cad = desired_printed + (old_cad - measured_printed)` as a first compensation estimate, then preserve a small functional clearance.
- Make calibration and final generation separate code paths. The final path must create only final printable solids; leave gauge helpers dormant or comment out their calls.

## Layer-zero topology and breakaway supports

Review the model in its intended print orientation, not only as a finished solid. A sleeve connected to the main body at its far end can still be an isolated tower for dozens of layers.

- If a small standalone gauge detaches, assume the equivalent isolated feature in the final body is also at risk.
- Add sacrificial tabs between isolated concentric walls when slicer-generated brims cannot reach the inner island.
- For a 0.4 mm nozzle and 0.2 mm layers, a useful starting point is 0.6-0.8 mm tab width and 0.4 mm height.
- Place tabs away from latch channels, keyways, sealing faces, and critical diameter checks.
- Mention tab removal in the final Fusion message and print instructions.

## Print orientation and tall-part adhesion

Choose orientation by tracing the model as a directed layer stack, not by selecting the widest end automatically.

- When an internal void radius increases as build height rises, material falls away and exposes a supported cavity floor. When the void radius abruptly decreases, new material must bridge inward over empty space and creates an annular ceiling.
- Prefer the orientation that minimizes abrupt bore contractions, inaccessible supports, and support contact in precision threads or connector bores. Use a brim to compensate for a smaller footprint.
- Inspect every axial step, blind latch pocket, radial screw hole, and thread lead-in in sliced preview before enabling supports. Avoid support inside a dimensional bore when a small bridge, chamfer, or orientation change can solve it.
- For a roughly 127 mm tall PLA part on a 27.5 mm footprint, a useful starting point is an outer-only 12-15 mm brim, 0-0.05 mm brim gap, two skirt loops one layer high, five walls, 35-40 mm/s outer walls, and 1500-2000 mm/s^2 outer-wall acceleration. Scale these values with height, footprint, material, and printer motion system.
- Keep inner brims out of calibrated connector bores. Clean the plate before relying on an outer brim, and place the seam away from visible branding or sealing surfaces.
- PLA is suitable for indoor prototypes and light use; PLA+ or PETG is preferable for impact-prone functional parts. Silk PLA benefits from slower outer walls and extra walls because appearance-oriented formulations can be more brittle.

### Terminal walls in axial prints

A rear wall or stop that begins after a long open cradle is a horizontal ceiling when the front face is on the bed. It may require a long bridge across the cavity even though the completed model looks like an ordinary box.

At every major build-height transition, compare the new cross-section with material directly below it. If a terminal wall adds unsupported material across a precision cavity, choose one of these deliberately:

- make a floor, rail, or flange face co-planar so the part can print on that surface;
- grow the wall with printable ramps/chamfers from supported material;
- move the stop into a separately printed cover or retainer;
- select another orientation and evaluate how it affects screw holes and mating apertures;
- allow a bridge only after checking its span and accepting the underside quality.

## Printable-body accounting and handoff

Fusion may retain a wire body for a persisted helix path alongside the actual solids. Do not describe every browser body as a print part.

- Classify final printable bodies as closed solids with positive volume. Treat zero-volume wire/surface bodies, sketches, planes, and persisted sweep paths as construction geometry.
- Give printable solids explicit names such as `Main Chassis` and `Threaded Collar`. Prefix construction bodies with `Construction -`, hide them, and delete them after feature creation only when Fusion's dependency graph permits it.
- State the exact printable count and names in the script's final `messageBox`. Separately state the number of hidden construction bodies when they remain.
- Export separate assembly solids independently so each can receive its own bed orientation. Provide orientation for every printed solid, not only the largest body.

## Common pitfalls (quick list)

| Symptom | Cause | Fix |
|---|---|---|
| Part is 10× too big | Treated cm as mm | Divide all lengths by 10 |
| Holes appear above the part, not in it | Cut extrude went the wrong direction | Use the current `setSymmetricExtent(...)` API |
| Hole is in the wrong location on a construction plane | Skipped the world→sketch transform | Use the `w2s` helper |
| `No target body found to cut or intersect` | Cut sketch plane does not intersect material at that feature location | Sketch from the target body's face/base plane, or use a symmetric cut through material |
| `Part Design documents can only contain one component` | Script called `root.occurrences.addNewComponent(...)` in a Part Design document | Build named bodies directly in `design.rootComponent` |
| `profiles.item(0)` cuts away the body instead of the hole | Picked the outer profile, not the circle | One sketch per feature, or pick by smallest area |
| `ALL_TOOL_BODY_REFERENCE_LOST` | Used the edit-only BaseFeature source body after `finishEdit()` | Reacquire `base.bodies.item(0)` and use the result body |
| `Invalid Point` from `setAsMultiLine` | World-to-sketch transform left normal-axis noise | Recreate the local point with an exact local Z of `0.0` |
| `invalid profile(s)` after adding text | Captured a Profile before the sketch rebuilt | Resolve and validate profiles after all sketch edits |
| `ASM_INCONS_REL` on engraved text | Compound curved-body boolean or problematic font outline | Use a simple static font and cut each text/profile entity separately |
| Reversed path text is laterally misaligned | Path reversal changed the "above" side | Reverse the baseline offset sign and verify the computed centerline |
| Monogram overlaps its frame | Treated the path baseline as the glyph centre | Offset the baseline by half the nominal height opposite the glyph-rise direction, then apply an optical nudge if needed |
| Connector model creates a fragile concentric sleeve | Mating envelope was inferred from gender or contact dimensions | Align both manufacturer STEP models and confirm which nose enters which bore before cutting any annular gap |
| Mounting holes move during a wall-thickness revision | Reference-interface dimensions were not recovered or tracked | Measure the original artifact, record hole pitch/diameter provenance, and preserve the interface independently of wall geometry |
| Rear stop blocks the part before assembly | Stop position was derived from the overall end or omitted its own thickness | Derive stop front from the seated part datum, then add clearance and stop thickness separately |
| External plug will not fully seat | A small retaining aperture was cut through the full panel thickness | Use a larger rear pocket and a thin stepped front bezel; verify mating insertion depth |
| Supported part rattles or sits below its aperture | Symmetric vertical clearance accumulated above a gravity-supported part | Datum the part on its support surface and specify top clearance separately |
| Rear wall prints as a rough bridge | Front-down orientation turns a terminal wall into a ceiling over the cavity | Trace cross-sections by layer; align a floor/rail face for bed contact or separate/support the stop |
| Exported STL still has old dimensions | Script changed but the mesh was not regenerated | Compare timestamp, bounding box, thickness, holes, and critical openings before slicing |
| Inner sleeve or tower detaches during printing | Feature is an isolated first-layer island | Add removable two-layer tabs away from mating features |
| Widest-end-down orientation creates an internal ceiling | Orientation was chosen from footprint alone | Trace bore-radius changes upward and orient to minimize abrupt contractions; stabilize with an outer brim |
| User sees three bodies but only two are printable | Persisted helix wire was counted as a part | Hide and prefix construction bodies, then report only closed positive-volume solids as printable |
| Script silently does nothing | Uncaught exception | Wrap in `try/except` with `messageBox(traceback.format_exc())` |
| `ValueInput.createByReal` errors | Passed an int where a float was expected | Always pass floats (`1.0` not `1`) |
| Created body but no confirmation | Forgot the final messageBox | Always end with a summary `messageBox` so the user knows it worked |

## Worked example

Keep reviewed, redistributable worked examples in the skill's repository-relative `examples/` directory. Refer to them with paths such as `examples/ptfe_bracket/ptfe_bracket.py`, never with an absolute local path. Before adding an example, remove personal paths, identifying details, proprietary geometry, and generated output files.
