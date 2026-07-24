# Autodesk Fusion Advanced Geometry

Use these patterns for temporary BRep geometry, BaseFeature persistence, sketch text, and curved-body engraving.

## Contents

- [Temporary BRep bodies](#temporary-brep-bodies)
- [Sketch text and curved-body engraving](#sketch-text-and-curved-body-engraving)

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

