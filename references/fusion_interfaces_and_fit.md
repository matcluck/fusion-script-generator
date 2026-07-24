# Autodesk Fusion Interfaces and Fit

Use this reference when a generated part must preserve, retain, or mate with measured hardware or another printed part.

## Contents

- [Mating-envelope audit](#mating-envelope-audit)
- [Reference geometry and dimension provenance](#reference-geometry-and-dimension-provenance)
- [Axial datum and stop audit](#axial-datum-and-stop-audit)
- [Retaining bezels and external mating access](#retaining-bezels-and-external-mating-access)
- [Gravity, support datums, and accumulated play](#gravity-support-datums-and-accumulated-play)
- [Thread reconstruction](#thread-reconstruction)
- [Fit gauges and production mode](#fit-gauges-and-production-mode)

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

