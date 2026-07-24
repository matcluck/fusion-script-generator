# Fusion API Research Workflow

Use this when a script needs an unfamiliar Fusion API call, uses temporary BRep geometry, or fails inside Fusion with a runtime API error.

## Contents

- [Local source of truth](#local-source-of-truth)
- [API currency rule](#api-currency-rule)
- [Official docs to cross-check](#official-docs-to-cross-check)
- [Distilled rules](#distilled-rules)
- [Temporary BRep pattern](#temporary-brep-pattern)

## Local source of truth

First inspect the installed Autodesk Python stubs. They match the Fusion build on this machine and include signatures plus docstrings.

```powershell
python "<skill-directory>/scripts/fusion_api_lookup.py" TemporaryBRepManager.createSphere
python "<skill-directory>/scripts/fusion_api_lookup.py" SketchFittedSplines.add
python "<skill-directory>/scripts/fusion_api_lookup.py" "No target body found"
```

Use `Class.method` for exact lookup. Use plain text for fuzzy lookup. Automatic discovery uses the Windows `LOCALAPPDATA` installation path; on another platform, pass the Fusion `adsk` package directory with `--adsk-package <path>`.

The lookup also supports properties:

```powershell
python "<skill-directory>/scripts/fusion_api_lookup.py" BaseFeature.bodies
python "<skill-directory>/scripts/fusion_api_lookup.py" BRepBody.volume
python "<skill-directory>/scripts/fusion_api_lookup.py" Feature.healthState
```

## API currency rule

Use three levels of evidence in this order:

1. Check the installed stubs to prove that the user's Fusion build exposes the symbol and to get the exact Python signature.
2. Check the official Autodesk reference page for retirement notices, replacement APIs, units, ownership, and version history.
3. Check Autodesk's official sample for the expected object lifecycle and feature-input sequence.

A symbol remaining in the local stubs does not mean Autodesk still supports it. Retired methods remain for backward compatibility. Prefer the current replacement for all new scripts.

| Retired compatibility API | Current API for new scripts | Official status |
|---|---|---|
| `SketchTexts.createInput2(text, height)` | `SketchTexts.createInput3(expression, ValueInput)` | Retired November 2025 |
| `ExtrudeFeatureInput.setDistanceExtent(...)` | `setOneSideExtent(...)` or `setSymmetricExtent(...)` | Retired September 2022 |
| `ThreadFeatures.createThreadInfo(...)` | `ThreadInfo.create(...)` | Retired September 2025 |

For literal text with `createInput3`, pass a Fusion expression and a length `ValueInput`, for example:

```python
text_input = sketch.sketchTexts.createInput3(
    "'GHIDRA'",
    adsk.core.ValueInput.createByReal(0.42),
)
```

## Official docs to cross-check

Use only Autodesk's official Fusion API pages for semantic claims. This map covers the APIs most often needed by generated printable-part scripts.

### Entry points and object context

- User manual index: `https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/UserManualIndex_UM.htm`
- Official API samples: `https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/SampleList.htm`
- Documents, products, components, occurrences, and proxies: `https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/ComponentsProxies_UM.htm`
- Units: `https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/Units_UM.htm`
- `ValueInput.createByReal`: `https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/ValueInput_createByReal.htm`

### Sketches, coordinates, profiles, and text

- `Sketch.modelToSketchSpace`: `https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/Sketch_modelToSketchSpace.htm`
- `Matrix3D.invert`: `https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/Matrix3D_invert.htm`
- `SketchFittedSplines.add`: `https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/SketchFittedSplines_add.htm`
- `Profile.areaProperties`: `https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/Profile_areaProperties.htm`
- `SketchTexts.createInput3`: `https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/SketchTexts_createInput3.htm`
- `SketchTextInput.setAsMultiLine`: `https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/SketchTextInput_setAsMultiLine.htm`
- `SketchTextInput.setAsFitOnPath`: `https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/SketchTextInput_setAsFitOnPath.htm`
- Sketch text sample: `https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/SketchTextSample_Sample.htm`

### Construction geometry and feature inputs

- `ConstructionPlaneInput`: `https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/ConstructionPlaneInput.htm`
- `ConstructionPlaneInput.setByDistanceOnPath`: `https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/ConstructionPlaneInput_setByDistanceOnPath.htm`
- `ExtrudeFeatures.createInput`: `https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/ExtrudeFeatures_createInput.htm`
- `ExtrudeFeatureInput.setOneSideExtent`: `https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/ExtrudeFeatureInput_setOneSideExtent.htm`
- `ExtrudeFeatureInput.setSymmetricExtent`: `https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/ExtrudeFeatureInput_setSymmetricExtent.htm`
- `DistanceExtentDefinition.create`: `https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/DistanceExtentDefinition_create.htm`
- `ToEntityExtentDefinition`: `https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/ToEntityExtentDefinition.htm`
- `RevolveFeatures.createInput`: `https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/RevolveFeatures_createInput.htm`
- `SweepFeatures.createInput`: `https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/SweepFeatures_createInput.htm`
- `SweepFeatureInput`: `https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/SweepFeatureInput.htm`
- `Path.create`: `https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/Path_create.htm`

### BRep, base features, and booleans

- `TemporaryBRepManager`: `https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/TemporaryBRepManager.htm`
- `TemporaryBRepManager.booleanOperation`: `https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/TemporaryBRepManager_booleanOperation.htm`
- `TemporaryBRepManager.createHelixWire`: `https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/TemporaryBRepManager_createHelixWire.htm`
- Temporary BRep sample: `https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/TemporaryBRepManager_Sample.htm`
- `BaseFeatures.add`: `https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/BaseFeatures_add.htm`
- `BRepBodies.add`: `https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/BRepBodies_add.htm`
- `BaseFeature.bodies`: `https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/BaseFeature_bodies.htm`
- `CombineFeatures.add`: `https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/CombineFeatures_add.htm`
- `BRepBody.volume`: `https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/BRepBody_volume.htm`

### Threads, export, and diagnostics

- `ThreadDataQuery`: `https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/ThreadDataQuery.htm`
- `ThreadDataQuery.recommendThreadData`: `https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/ThreadDataQuery_recommendThreadData.htm`
- `ThreadInfo.create`: `https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/ThreadInfo_create.htm`
- `ThreadFeatures.createInput`: `https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/ThreadFeatures_createInput.htm`
- `ExportManager`: `https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/ExportManager.htm`
- `Feature.healthState`: `https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/Feature_healthState.htm`
- `Feature.errorOrWarningMessage`: `https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/Feature_errorOrWarningMessage.htm`
- `TimelineObject.rollTo`: `https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/TimelineObject_rollTo.htm`

## Distilled rules

- Design API length values are centimeters; angles are radians. Convert user millimeters into cm in the parameter block.
- `ValueInput.createByReal(x)` uses Fusion internal database units for the parameter type.
- Sketches on construction planes have local coordinates. Convert world coordinates through `sketch.transform.copy().invert()` before placing points on offset planes.
- Prefer `Sketch.modelToSketchSpace` for point conversion when a `Sketch` object is available; flatten the returned sketch-space Z to exactly `0.0` for text-box APIs that reject microscopic plane-normal residue.
- Prefer one sketch per feature. If a sketch has multiple profiles, choose by area instead of assuming `profiles.item(0)`.
- Use `setOneSideExtent` with an explicit extent definition or `setSymmetricExtent` for new extrudes. Do not generate new code with retired `setDistanceExtent`.
- For organic visible outlines, use `SketchFittedSplines.add(ObjectCollection)` and set `spline.isClosed = True` for closed loops.
- Use `SketchTexts.createInput3` with a quoted text expression and length `ValueInput`; reserve retired `createInput2` only for maintaining old scripts.
- Query standard thread names and classes through `ThreadDataQuery`, then create current thread metadata with `ThreadInfo.create` rather than retired `ThreadFeatures.createThreadInfo`.
- Temporary BRep booleans mutate the target temporary body. The target must be temporary; the tool is not modified.
- Check the boolean return value. Raise an error with the operation name if it returns false.
- Persist temporary BRep bodies through a base feature in parametric designs: create base feature, `startEdit()`, `rootComp.bRepBodies.add(temp_body, base_feature)`, then `finishEdit()`.
- After `finishEdit()`, discard the source-body reference returned by `bRepBodies.add`. Reacquire `base_feature.bodies.item(0)` before a combine or later feature.
- Treat `ASM_INCONS_REL` as a geometry-kernel failure, not a Python/API-signature failure. Simplify the font or profile, split compound booleans into one entity per feature, and pass each feature's result body forward.
- If adding curves or text changes a sketch, reacquire `Sketch.profiles` afterward. Profile references can become invalid even when the visible sketch looks unchanged.
- If a cut fails with "No target body found", the sketch/profile likely does not intersect a persisted body in the cut direction. Use a symmetric extent, verify the sketch plane, or use TemporaryBRep booleans for complex freeform cavities.
- After adding a feature, inspect `feature.healthState` and include `feature.errorOrWarningMessage` in raised diagnostics when the state is warning or error.
- Use `body.volume > 0` to distinguish closed printable solids from zero-volume wire or surface construction bodies.

## Temporary BRep pattern

```python
temp_mgr = adsk.fusion.TemporaryBRepManager.get()
target = temp_mgr.createSphere(adsk.core.Point3D.create(cx, cy, cz), radius)
tool = temp_mgr.createCylinderOrCone(p1, tool_radius, p2, tool_radius)

if not temp_mgr.booleanOperation(target, tool, adsk.fusion.BooleanTypes.DifferenceBooleanType):
    raise RuntimeError("Temporary BRep boolean failed: string channel")

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

if base.bodies.count == 0:
    raise RuntimeError("BaseFeature created no result body")
body = base.bodies.item(0)
if not body or not body.isValid:
    raise RuntimeError("BaseFeature result body is invalid")
body.name = "generated body"
```

Use this pattern for spheres, rounded ribs, sealed internal pockets, compound cutters, and shapes where normal sketch extrudes would depend on fragile target-body selection.
