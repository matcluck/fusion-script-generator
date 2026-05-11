---
name: fusion-script-generator
description: Interview the user about a part they want to 3D model, then generate a parametric Autodesk Fusion 360 Python script that builds it. Use this skill ANY time the user wants to design, model, prototype, or 3D-print a physical part — brackets, mounts, enclosures, jigs, fixtures, adapters, holders, clips, spacers, knobs, etc. — even if they don't explicitly say "Fusion" or "script". Also use it whenever the user asks for help with CAD, 3D modeling, parametric design, or generating Fusion 360 / Autodesk scripts. The user has a Fusion install configured to load scripts from a specific folder, so this skill writes ready-to-run .py files there.
---

# Fusion 360 Script Generator

Generates parametric Autodesk Fusion 360 Python scripts from a natural-language description of a part. The user pastes (or auto-loads) the resulting `.py` file into Fusion's script editor and runs it to materialise the design.

## Output location

**Always** write generated scripts as `<name>/<name>.py` inside:

```
~/FusionScripts/
```

If the directory doesn't exist, create it.

Fusion 360 requires each script to live in a folder of the **same name** as the .py file — e.g. `example_part/example_part.py`, not a loose `example_part.py`. A loose file in the scripts folder will silently fail to load. Use a descriptive snake_case name for both the folder and the file.

When generating a multi-script build (see "Splitting big designs" below), each script gets its own same-named folder: `complex_part_01_body/complex_part_01_body.py`, etc.

If a folder with that name already exists, ask the user whether to overwrite or pick a new name — don't silently clobber prior work.

## Workflow

### 1. Interview the user

Don't dive into code. First, build a mental model of the part. Ask the questions that actually matter for *this* part — not a rote checklist. Skip questions that are obvious from context, and group related ones so it doesn't feel like an interrogation.

Things worth understanding before writing code:

- **What is it for?** The use case often answers half the dimensional questions for free (e.g. "A simple bracket" tells you the hole size).
- **Overall shape and orientation.** A rough verbal description, or an ASCII sketch from the side / top. Ask the user to describe what it looks like from each relevant view if it's non-trivial.
- **Critical dimensions.** Lengths, thicknesses, diameters. Ask for the *constraints* (table is 18 mm thick) rather than the final numbers — you can derive the rest.
- **Mating parts.** Anything it has to fit, slide over, screw into, clip onto. Get the mating dimensions, plus a clearance preference if relevant.
- **Holes and features.** Count, diameter, position, what passes through them, whether they're through-holes or blind, whether they need countersinks.
- **Fixing method.** Screws? Glue? Press-fit? Magnets? This drives whether you need screw holes / pilot holes / pockets.
- **3D-printing considerations.** Wall thickness (default to ~3–5 mm for FDM structural parts), fillets on stress concentrators, orientation for printing if it affects the design.

If the user says something ambiguous, draw an ASCII diagram of your interpretation and ask them to confirm before you code. **Cheap to ask, expensive to redesign.**

### 2. Plan before writing

Once you have the picture, briefly summarise back the part to the user — dimensions, features, hole positions — and get a thumbs-up. Then mentally decompose the geometry into Fusion operations:

- What's the base profile? On which plane? Extruded along which axis?
- Are there secondary features (holes, slots, pockets) and which face/plane do they live on?
- What gets filleted/chamfered for strength or print quality?

### 3. Write the script

Use the patterns in `references/fusion_api_patterns.md` — there are several Fusion 360 API gotchas (sketch coordinate transforms, profile selection, hole direction, unit conventions) that will silently break a naive script. Read that file before writing code; don't try to remember the API from scratch.

Key conventions for every generated script:

- **Pull all dimensions into a `PARAMETERS` block at the top** with both the cm value and a `# NN mm` comment, so the user can tweak without hunting through the code.
- **Use cm everywhere** (Fusion's internal unit). Convert from mm in comments only.
- **Wrap everything in `def run(context):` with `try`/`except`** that surfaces errors via `ui.messageBox` — Fusion swallows raw Python tracebacks otherwise.
- **End with a confirmation `messageBox`** that summarises what was built (dimensions, hole counts) so the user gets immediate feedback that the script succeeded.
- **Add comments explaining the geometry**, especially an ASCII cross-section if the part has one. Future-you (or future-Claude) will need to understand the script without rerunning the interview.

### 4. Save and hand off

Tell the user:

1. The file path
2. How to run it: Fusion → **Utilities** → **Scripts and Add-Ins** (`Shift+S`) → find the script in "My Scripts" → **Run**. (Fusion picks up scripts from its configured scripts folder automatically; the user shouldn't have to add it manually.)
3. A one-line summary of what to expect when it runs
4. An offer to iterate — "let me know if anything needs adjusting and I'll regenerate"

### 5. Iterate gracefully

When the user comes back with tweaks ("the holes are 2 mm too close to the edge", "make the wall thicker"), prefer **editing the existing script** over rewriting from scratch. The parameter block at the top of the file makes most tweaks one-line changes. Only rewrite if the geometry itself is wrong.

## Splitting big designs across multiple scripts

If a part has several distinct features (e.g. body + slot + engraving), prefer **multiple short scripts the user runs in sequence** over one monolithic script. Each script modifies the active document — script 1 creates the body as `NewBodyFeatureOperation`, scripts 2+ find the existing body and apply `CutFeatureOperation` / `JoinFeatureOperation` features.

Why: a single very long script can trigger API 500 errors during generation (output too large), and it's also harder to iterate on — when the user wants to tweak just the engraving, they re-run script 3 instead of regenerating the whole part. Name files `<part>_01_body.py`, `<part>_02_<feature>.py`, etc., and have each script's final `messageBox` tell the user which script to run next.

This applies whenever the part has 3+ logically separable features. For simple single-feature parts, one script is fine.

## What this skill is NOT for

- **Live manipulation of an open Fusion document.** This skill produces standalone scripts the user runs manually. There's no MCP integration with Fusion.
- **Importing existing STEP/STL files.** Use Fusion's GUI for that.
- **Complex assemblies with joints/constraints.** Single-body parametric parts only. If the user wants a multi-component assembly, warn them and offer to script the individual parts.
- **Surface/sculpt modeling.** Solid modeling primitives only (sketch + extrude + boolean + fillet/chamfer).

## Reference

See `references/fusion_api_patterns.md` for:
- The minimal script skeleton
- Sketch / extrude / hole / fillet patterns
- The world-to-sketch coordinate transform helper (critical for placing features correctly on construction planes)
- Common API pitfalls and how to avoid them
