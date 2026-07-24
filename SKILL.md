---
name: autodesk-fusion-script-generator
description: Generate or refine parametric Autodesk Fusion 360 Python scripts for 3D-printable parts. Use when a user asks for a Fusion script, wants a physical part modelled in Fusion, or wants an existing Fusion Python script updated; do not use for general CAD advice or interactive Fusion work without a script deliverable.
---

# Autodesk Fusion AI Script Generator

Generate parametric Autodesk Fusion 360 Python scripts from a natural-language description of a part. Save or hand off the resulting files for the user to run manually in Fusion. This skill does not launch Fusion or execute scripts inside it.

## Output location

First, check the optional local preference file in the platform configuration directory: `%APPDATA%\autodesk-fusion-script-generator\config.json` on Windows, `~/Library/Application Support/autodesk-fusion-script-generator/config.json` on macOS, and `$XDG_CONFIG_HOME/autodesk-fusion-script-generator/config.json` (or `~/.config/...`) on Linux. When it contains a non-empty `scripts_root` string, use that directory unless the user gives a different destination. If the file is missing, invalid, or has no `scripts_root`, ask the user for their Fusion scripts directory. If they want code only, return the script and manifest without writing either file.

After a user explicitly approves saving their preference, create or update the local, untracked file:

```json
{
  "scripts_root": "<fusion-scripts-directory>"
}
```

Never create, overwrite, or change this preference file without that approval. Treat it as local configuration: do not add it to Git, quote its contents in public output, or assume its value applies to another machine.

Each script must live in its own subfolder, and the subfolder name, Python file name, and manifest file name must match:

```
<fusion-scripts-directory>/<script_name>/<script_name>.py
<fusion-scripts-directory>/<script_name>/<script_name>.manifest
```

Use a descriptive, short snake_case script name without a `.py` extension for the folder (e.g. `ptfe_bracket`, `pi_camera_mount`, `desk_cable_clip`). Keep names practical for Fusion's script loader; prefer about 30 characters or fewer when possible. Create a `.manifest` JSON file with the same base name:

```json
{
  "autodeskProduct": "Fusion360",
  "type": "script",
  "id": "<script_name>",
  "supportedOS": "windows|mac"
}
```

Set `id` to the script name. Include the four fields above; the bundled preflight validator requires them.

By default, keep the script folder clean: only `<script_name>.py` and `<script_name>.manifest`. Do not put README files, generated STLs, images, or helper files in the Fusion script folder unless the user explicitly needs them there or the script itself must generate them at runtime. Extra files can make Fusion's manual "Add" flow more confusing while debugging imports.

If a script folder or matching file already exists, ask the user whether to overwrite or pick a new name before changing it.

## Workflow

### 1. Interview the user

Don't dive into code. First, build a mental model of the part. Ask the questions that actually matter for *this* part - not a rote checklist. Skip questions that are obvious from context, and group related ones so it doesn't feel like an interrogation.

Things worth understanding before writing code:

- **What is it for?** The use case often answers half the dimensional questions for free (e.g. "PTFE tube guide" tells you the hole size).
- **Overall shape and orientation.** A rough verbal description, or an ASCII sketch from the side / top. Ask the user to describe what it looks like from each relevant view if it's non-trivial.
- **Critical dimensions.** Lengths, thicknesses, diameters. Ask for the *constraints* (table is 18 mm thick) rather than the final numbers - you can derive the rest.
- **Mating parts.** Anything it has to fit, slide over, screw into, clip onto. Get the mating dimensions, plus a clearance preference if relevant.
- **Mating envelopes.** For connectors and nested parts, identify which member enters which bore and which physical part occupies every radial and axial region. Do not infer plug/socket behavior from male/female labels. Verify a mated pair of official drawings or STEP models; standardized contacts do not guarantee interchangeable housing geometry.
- **Reference artifacts.** When an existing STL, STEP, sketch, or failed print defines an interface, inspect it read-only and record exact hole centres, diameters, plate bounds, thicknesses, and keyed profiles before redesigning. Keep a dimension ledger with the source of every value; do not repurpose a number from an unrelated measurement or numbered list item.
- **Seating datums and installation path.** Identify the actual surface that seats against the print, then measure every axial stop, shoulder, strain relief, latch, and cover from that datum. Describe how the real part enters, translates, rotates, and becomes captive; a valid final cavity can still be impossible to assemble.
- **Part size versus required clearance.** Clarify whether a stated diameter or width is the mating part's maximum size or the desired printed opening. Add printer/material clearance only after that distinction is explicit.
- **Holes and features.** Count, diameter, position, what passes through them, whether they're through-holes or blind, whether they need countersinks.
- **Fixing method.** Screws? Glue? Press-fit? Magnets? This drives whether you need screw holes / pilot holes / pockets.
- **3D-printing considerations.** Wall thickness (default to ~3-5 mm for FDM structural parts), fillets on stress concentrators, material, intended orientation, internal support access, adhesion, and whether branding will be paint-filled or printed as a separate multicolour body.

If the user says something ambiguous, draw an ASCII diagram of your interpretation and ask them to confirm before you code. **Cheap to ask, expensive to redesign.**

### 2. Plan before writing

Once you have the picture, briefly summarise back the part to the user - dimensions, features, hole positions - and get a thumbs-up. Then mentally decompose the geometry into Fusion operations:

- What's the base profile? On which plane? Extruded along which axis?
- Are there secondary features (holes, slots, pockets) and which face/plane do they live on?
- What gets filleted/chamfered for strength or print quality?
- Can each feature keep one obvious job? Prefer a few readable ribs, collars, or bosses over merging adjustment hardware into a more elaborate load-bearing form without a clear need.
- Which dimensions are measured, recovered from reference geometry, standards-based, inferred from imagery, or deliberately chosen as print clearance? Do not treat an unscaled photograph as a dimensional drawing.
- What is the complete assembly sequence, and does every intermediate position clear fixed stops, lips, and cable strain reliefs?
- Which bodies or sleeves begin as isolated first-layer islands in the intended print orientation, and do they need a brim or removable breakaway tabs?
- In each candidate orientation, where does an internal bore abruptly contract as layers rise? Those contractions create annular ceilings; prefer an orientation that leaves precision cavities open and support-free even when its footprint is smaller.
- Which uncertain fits should be calibrated with small, physically labeled gauges before generating the final build?
- Which generated entities are final printable solids, separate assembly parts, or hidden construction bodies? Decide the exact printable-part count before coding the final message.

### 3. Write the script

Use the patterns in `references/fusion_api_patterns.md` - there are several Fusion 360 API gotchas (sketch coordinate transforms, profile selection, hole direction, unit conventions) that will silently break a naive script. Read that file before writing code; don't try to remember the API from scratch.

For any unfamiliar Fusion API class or method, verify the signature against the installed Autodesk stubs before writing code:

```
python "<skill-directory>/scripts/fusion_api_lookup.py" ClassName.methodName
```

Read `references/fusion_api_research.md` when using temporary BRep geometry, fitted splines, base features, non-trivial booleans, threads, sketch text, or when a Fusion runtime error needs diagnosis. Cross-check official Autodesk documentation for semantics and retirement notices, while using the local installed stubs for the exact Python signature. A method remaining in the stubs can be backward-compatible but retired; use Autodesk's current replacement in new scripts.

After generating or materially editing a script, run the bundled static preflight:

```text
python "<skill-directory>/scripts/preflight_fusion_script.py" "<fusion-script-or-folder>"
```

Preflight checks Python syntax, the manifest, inspectable Autodesk API symbols, retired calls, and the literal `BUILD_SPEC`. It does not execute Fusion or validate the resulting geometry. Report that runtime validation remains pending until the user runs the script in Fusion.

Key conventions for every generated script:

- **Build in `design.rootComponent` by default.** Do not call `root.occurrences.addNewComponent(...)` unless the user explicitly needs a real multi-component assembly; Fusion Part Design documents can reject new components with "Part Design documents can only contain one component." For two-piece printable tools, create multiple named bodies in the root component instead.
- **Make cut planes intersect the body being cut.** A cut sketch on the top of a raised pad will fail with "No target body found" if the hole is outside that pad. For through-holes in the base plate, sketch on the base top face/plane or use a symmetric cut from a plane that passes through the target material.
- **Clear the complete surface envelope for radial holes.** On tapered, curved, or tilted bodies, size the cut from the maximum exterior envelope across the whole aperture, then extend it deliberately beyond the exterior and into the bore. A cut based only on the surface radius at the hole centre can leave part of the mouth covered. Keep clamp collars or bosses distinct from structural ribs when that improves access and makes the load path easier to audit. See `references/fusion_api_patterns.md`.
- **Preserve measured interfaces from reference geometry.** Recover hole pitch, diameter, flange bounds, thickness, and keyed profiles from the supplied artifact before changing surrounding structure. Compare the script's derived values with that ledger and assert critical distances. See `references/fusion_api_patterns.md`.
- **Reconcile reference interfaces explicitly.** Before approving a redesign, map every preserved interface value as `reference artifact -> script parameter/derived value -> difference`. Overall bounding boxes are not a substitute for hole centres, diameters, keyed vertices, or seating planes. If an interface cannot be extracted, mark it unverified and block print approval rather than saying only to check it later.
- **Derive stops from seated datums, not overall extents.** Name the outer face, inner panel face, seating plane, body end, relief start, and both faces of every stop. Calculate each position independently and assert non-intersection plus intended play; include the stop's own thickness when deriving the overall body length.
- **Audit threaded collars as both an axial and radial stack.** Keep the female lip-to-thread setback, male lead-in, helix path height, swept-profile overhang, shoulder position, pass-through bore, and thread-root wall as independent parameters. Once a labeled coupon proves diameter and pitch, preserve them; fix a closed-up assembly gap with lead-in, runout, or neck height, and size the bore from measured printed error plus functional clearance. See `references/fusion_api_patterns.md`.
- **Report numeric margins.** Evaluate stop clearance, retaining overlap, wall around pilots, cover play, and insertion clearance as signed distances. A negative margin is a collision; do not hide it inside a generic verification checklist.
- **Use stepped retaining bezels when mating access and capture conflict.** If an opening must be smaller than the retained shoulder but an external mate must still reach the connector, cut a larger pocket from behind and leave only the required thin front lip. Verify insertion depth as well as width and height.
- **Datum gravity-supported parts from their support surface.** Do not distribute clearance symmetrically around a part that will rest on a floor: unused bottom clearance becomes top play and shifts the mating feature. Specify lateral, top, and axial clearances separately.
- **For rerunnable scripts, name generated bodies clearly** and delete only previous bodies with those exact names/prefixes before rebuilding. Never delete unnamed or user-created bodies.
- **Pull all dimensions into a `PARAMETERS` block at the top** with both the cm value and a `# NN mm` comment, so the user can tweak without hunting through the code.
- **Add a literal `BUILD_SPEC` contract near the top.** Include units, coordinate direction, generated-body prefixes, exact printable body names/count, and per-body print orientation. Keep coordinate and body ownership decisions explicit enough that another model can audit the geometry without reconstructing the interview.
- **Use cm everywhere** (Fusion's internal unit). Convert from mm in comments only.
- **Wrap everything in `def run(context):` with `try`/`except`** that surfaces errors via `ui.messageBox` - Fusion swallows raw Python tracebacks otherwise.
- **End with a confirmation `messageBox`** that summarises what was built (dimensions, hole counts) so the user gets immediate feedback that the script succeeded.
- **Use fitted splines or arcs for organic/OEM outlines** such as automotive clips, molded plastic hooks, handles, rounded covers, and ergonomic shapes. Do not approximate these visible outlines with chunky polygon point loops unless the part is intentionally faceted. In Fusion Python, use `sketch.sketchCurves.sketchFittedSplines.add(fit_points)` and set `spline.isClosed = True` for closed smooth profiles.
- **Use TemporaryBRepManager for freeform solids** such as spheres, rounded ribs, sealed internal pockets, compound cutters, and geometry where ordinary cut extrudes are likely to miss the target body. Check boolean return values and persist temporary bodies through a base feature.
- **Do not reuse the edit-only body returned while a BaseFeature is active.** After `finishEdit()`, retrieve `base_feature.bodies.item(0)` and use that result body for combines. See `references/fusion_api_patterns.md` for the safe persistence helper.
- **Treat sketch text and curved-body engraving as fragile geometry.** Use simple static fonts, finish all sketch edits before resolving profiles, split mixed text/profile booleans into independent features, and carry forward each feature's result body. Read the branding section in `references/fusion_api_patterns.md` before scripting text on a curved part.
- **Make calibration and production explicit modes.** Mark near-identical gauges physically, record the selected fit in the production parameter, and ensure the final run path creates only final printable solids.
- **Review the layer-zero topology.** If a thin internal sleeve or tower is disconnected from the surrounding body for many layers, add two-layer breakaway tabs that avoid latch slots, keyways, and other mating features.
- **Audit the directed layer stack before recommending orientation.** Do not automatically put the widest end on the bed. Trace the exterior and every internal radius from layer zero upward, then use a brim to stabilize the orientation with the cleanest unsupported geometry.
- **Treat terminal walls and stops as possible bridges.** In an axial print, a rear wall that suddenly closes an open cradle is a ceiling even when the final solid looks ordinary. Prefer co-planar floor/flange bed surfaces, gradual supported growth, a separate retainer, or another orientation that does not sacrifice critical holes.
- **Account for output bodies explicitly.** Give every final solid a printable name, prefix and hide persisted sweep paths or wire bodies as construction geometry, and report the exact number and names of printable solids in the completion dialog.
- **Assert computable geometry.** After fragile features, check the returned feature, `healthState`, `errorOrWarningMessage`, result body validity, positive volume, and expected body count/name. Add bounding-box or critical-distance assertions when they can be evaluated without brittle topology indexing.
- **Add comments explaining the geometry**, especially an ASCII cross-section if the part has one. Future-you (or future-Claude) will need to understand the script without rerunning the interview.

### 4. Save and hand off

When a destination directory has been confirmed, write the files to:

```
<fusion-scripts-directory>/<name>/<name>.py
<fusion-scripts-directory>/<name>/<name>.manifest
```

Then tell the user:

1. The script folder path and Python file path
2. How to run it: Fusion → **Utilities** → **Scripts and Add-Ins** (`Shift+S`) → find the script in "My Scripts" → **Run**. (Fusion picks up scripts from its configured scripts folder automatically; the user should not have to add it manually.)
3. A one-line summary of what to expect when it runs
4. The exact printable-solid count, which visible or hidden bodies are construction only, and whether each solid should be exported separately
5. A per-part print orientation based on internal geometry, plus any essential support, brim, material, seam, or paint-fill guidance
6. An offer to iterate - "let me know if anything needs adjusting and I'll regenerate"

### 5. Iterate gracefully

When the user comes back with tweaks ("the holes are 2 mm too close to the edge", "make the wall thicker"), prefer **editing the existing script** over rewriting from scratch. The parameter block at the top of the file makes most tweaks one-line changes. Only rewrite if the geometry itself is wrong.

After each material edit, run `scripts/preflight_fusion_script.py` and fix its errors. Ask the user to run the script manually in Fusion and return any traceback or unexpected result for the next iteration. Clearly distinguish static preflight success from runtime geometry validation.

Before approving another full print, compare any existing exported STL/3MF against the current parameter ledger: bounding box, plate thickness, hole pitch, critical openings, body count, and modification time. Script edits do not update old exports. For uncertain mating apertures or inferred chamfers, generate a small labeled coupon before the production body.

## What this skill is NOT for

- **Launching Fusion, executing scripts automatically, or directly manipulating an open document.** This skill produces standalone scripts for the user to run manually.
- **Importing existing STEP/STL files.** Use Fusion's GUI for that.
- **Complex assemblies with joints/constraints.** This skill is for single-component parametric models or simple multi-body printable parts. If the user wants a true multi-component assembly, warn them and offer to script the individual printable bodies unless they explicitly need assembly components.
- **Direct surface/sculpt modeling.** The skill targets parametric solid modeling, including temporary BRep solids when appropriate, not interactive T-Spline or sculpt workflows.

## Reference

See `references/fusion_api_patterns.md` for:
- The minimal script skeleton
- Sketch / extrude / hole / fillet patterns
- Radial set-screw holes, clamp collars, and full surface-envelope clearance
- The world-to-sketch coordinate transform helper (critical for placing features correctly on construction planes)
- Common API pitfalls and how to avoid them
- BaseFeature result-body lifetime, sketch-text engraving, ASM boolean failures, threaded-collar fit, fit gauges, and breakaway print supports

See `references/fusion_api_research.md` for:
- How to inspect the installed Autodesk Python stubs
- Official Autodesk documentation entry points
- Temporary BRep and boolean-operation rules

## Examples

Read only the example closest to the requested geometry:

- [`examples/speaker_stand_flange/speaker_stand_flange.py`](examples/speaker_stand_flange/speaker_stand_flange.py) for a tilted revolved socket, structural ribs, radial clamp hole, recessed mounting holes, and final bounding-box assertions.
- [`examples/iec_c14_cradle/iec_c14_cradle.py`](examples/iec_c14_cradle/iec_c14_cradle.py) for a measured mating interface, stepped retention, an open installation path, separate cover, and explicit printable-body accounting.
- [`examples/gpu_air_guide/gpu_air_guide.py`](examples/gpu_air_guide/gpu_air_guide.py) for multi-station lofts, hollow ducts, body combines, ribs, mounting features, and fitted-path text.
- [`examples/chain_bolt_press_jig/chain_bolt_press_jig.py`](examples/chain_bolt_press_jig/chain_bolt_press_jig.py) for a two-part jig, rounded profiles, pockets from opposing faces, hardware clearances, and parameter-margin checks.

Treat example dimensions as illustrative. Re-interview the user, derive the new part's interfaces, and copy only relevant patterns. Each example has a matching manifest in the same folder.
