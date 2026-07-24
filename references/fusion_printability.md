# Autodesk Fusion Printability and Handoff

Use this reference to audit how generated bodies print, how they should be counted and handed off, and which common failure modes to check.

## Contents

- [Layer-zero topology and breakaway supports](#layer-zero-topology-and-breakaway-supports)
- [Print orientation and tall-part adhesion](#print-orientation-and-tall-part-adhesion)
- [Printable-body accounting and handoff](#printable-body-accounting-and-handoff)
- [Common pitfalls](#common-pitfalls-quick-list)
- [Worked example](#worked-example)

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

Keep reviewed, redistributable worked examples in the skill's repository-relative `examples/` directory. Refer to them with paths such as `examples/speaker_stand_flange/speaker_stand_flange.py`, never with an absolute local path. Before adding an example, remove personal paths, identifying details, proprietary geometry, and generated output files.
