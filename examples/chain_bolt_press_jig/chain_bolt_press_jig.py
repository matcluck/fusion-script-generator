"""
Bolt-tightened motorcycle chain master-link press jig.

Builds a two-piece jig for a 428 master link. Two M6 bolts slowly draw the
front and rear halves together while pressing the clip-side plate on evenly.
"""

import math
import traceback

import adsk.core
import adsk.fusion


BUILD_SPEC = {
    "schema_version": 1,
    "units": "cm",
    "coordinate_system": (
        "XY is each block's broad face; +Z rises through its thickness; "
        "the two printable halves are laid out side by side along X"
    ),
    "generated_body_prefixes": [
        "Bolt front pressing block",
        "Bolt rear support block",
    ],
    "printable_body_names": [
        "Bolt front pressing block",
        "Bolt rear support block",
    ],
    "expected_printable_body_count": 2,
    "print_orientation": {
        "Bolt front pressing block": "broad flat back face on the build plate",
        "Bolt rear support block": "broad flat back face on the build plate",
    },
}


# PARAMETERS (Fusion API units are centimetres)
PIN_DIAMETER = 0.45                    # 4.5 mm assumed 428 master-link pin
PIN_PITCH = 1.27                       # 12.7 mm 428 chain pitch
FRONT_PIN_CLEARANCE_DIAMETRAL = 0.12   # 1.2 mm diametral clearance

FRONT_LINK_LOBE_DIAMETER = 1.08        # 10.8 mm figure-8 locating lobe
FRONT_LINK_WAIST_WIDTH = 0.88          # 8.8 mm wider middle waist for easier link placement
FRONT_RELIEF_DEPTH = 0.12              # 1.2 mm
# Rear side is a flat support pad for the fixed-pin master-link plate.
# The grooved/free pin ends are on the front/clip side only.

BODY_LENGTH = 4.80                     # 48.0 mm
BODY_WIDTH = 6.00                      # 60.0 mm
FRONT_BASE_THICKNESS = 1.00            # 10.0 mm
REAR_BASE_THICKNESS = 1.30             # 13.0 mm
WORKING_PAD_HEIGHT = 0.18              # 1.8 mm raised chain-contact pad
WORKING_PAD_LENGTH = 3.20              # 32.0 mm
WORKING_PAD_WIDTH = 1.80               # 18.0 mm
WORKING_PAD_CORNER_RADIUS = 0.25       # 2.5 mm
MINIMUM_WALL = 0.50                    # 5.0 mm

CORNER_RADIUS = 0.40                   # 4.0 mm rounded body corners
EDGE_CHAMFER = 0.20                    # 2.0 mm top/bottom body chamfer
PART_GAP = 2.60                        # 26.0 mm print-layout gap between halves

# Hardware: two M6 bolts above and below the chain.
BOLT_DIAMETER = 0.60                   # 6.0 mm nominal M6 bolt
BOLT_CLEARANCE_DIAMETRAL = 0.14        # 1.4 mm diametral clearance, prints around 7.4 mm
BOLT_Y_SPACING = 3.60                  # 36.0 mm between bolt centres
BOLT_HEAD_RECESS_DIAMETER = 1.35       # 13.5 mm washer/head relief on front back face
BOLT_HEAD_RECESS_DEPTH = 0.35          # 3.5 mm
VISIBLE_BOLT_RECESS_DEPTH = 0.12       # 1.2 mm top-side visual washer relief
REAR_NUT_RECESS_DIAMETER = 1.35        # 13.5 mm circular rear nut/washer relief
REAR_NUT_RECESS_DEPTH = 0.45           # 4.5 mm


def value(real_cm):
    return adsk.core.ValueInput.createByReal(float(real_cm))


def point(x, y, z=0.0):
    return adsk.core.Point3D.create(float(x), float(y), float(z))


def mm(cm_value):
    return cm_value * 10.0


def offset_xy_plane(component, z_height):
    plane_input = component.constructionPlanes.createInput()
    plane_input.setByOffset(component.xYConstructionPlane, value(z_height))
    return component.constructionPlanes.add(plane_input)


def largest_profile(sketch):
    best = None
    best_area = -1.0
    for i in range(sketch.profiles.count):
        profile = sketch.profiles.item(i)
        area = profile.areaProperties().area
        if area > best_area:
            best_area = area
            best = profile
    if best is None:
        raise RuntimeError("No closed sketch profile was created.")
    return best


def draw_rounded_rectangle(sketch, cx, cy, length, width, radius):
    radius = min(radius, length / 2.0 - 0.001, width / 2.0 - 0.001)
    x0 = cx - length / 2.0
    x1 = cx + length / 2.0
    y0 = cy - width / 2.0
    y1 = cy + width / 2.0

    lines = sketch.sketchCurves.sketchLines
    arcs = sketch.sketchCurves.sketchArcs

    lines.addByTwoPoints(point(x0 + radius, y1), point(x1 - radius, y1))
    arcs.addByCenterStartSweep(
        point(x1 - radius, y1 - radius),
        point(x1 - radius, y1),
        -math.pi / 2.0,
    )
    lines.addByTwoPoints(point(x1, y1 - radius), point(x1, y0 + radius))
    arcs.addByCenterStartSweep(
        point(x1 - radius, y0 + radius),
        point(x1, y0 + radius),
        -math.pi / 2.0,
    )
    lines.addByTwoPoints(point(x1 - radius, y0), point(x0 + radius, y0))
    arcs.addByCenterStartSweep(
        point(x0 + radius, y0 + radius),
        point(x0 + radius, y0),
        -math.pi / 2.0,
    )
    lines.addByTwoPoints(point(x0, y0 + radius), point(x0, y1 - radius))
    arcs.addByCenterStartSweep(
        point(x0 + radius, y1 - radius),
        point(x0, y1 - radius),
        -math.pi / 2.0,
    )


def draw_figure8_link_pocket(sketch, cx, cy, centre_pitch, lobe_diameter, waist_width):
    radius = lobe_diameter / 2.0
    half_waist = min(waist_width / 2.0, radius * 0.85)
    dx = math.sqrt(max(radius * radius - half_waist * half_waist, 0.001))
    alpha = math.atan2(half_waist, dx)
    left_cx = cx - centre_pitch / 2.0
    right_cx = cx + centre_pitch / 2.0

    left_top = point(left_cx + dx, cy + half_waist)
    right_top = point(right_cx - dx, cy + half_waist)
    right_bottom = point(right_cx - dx, cy - half_waist)
    left_bottom = point(left_cx + dx, cy - half_waist)

    lines = sketch.sketchCurves.sketchLines
    arcs = sketch.sketchCurves.sketchArcs

    lines.addByTwoPoints(left_top, right_top)
    arcs.addByCenterStartSweep(
        point(right_cx, cy),
        right_top,
        -2.0 * math.pi + 2.0 * alpha,
    )
    lines.addByTwoPoints(right_bottom, left_bottom)
    arcs.addByCenterStartSweep(
        point(left_cx, cy),
        left_bottom,
        -2.0 * math.pi + 2.0 * alpha,
    )


def extrude_new_body(component, profile, distance, name):
    extrudes = component.features.extrudeFeatures
    extrude_input = extrudes.createInput(
        profile,
        adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
    )
    extent = adsk.fusion.DistanceExtentDefinition.create(value(distance))
    extrude_input.setOneSideExtent(
        extent,
        adsk.fusion.ExtentDirections.PositiveExtentDirection,
    )
    feature = extrudes.add(extrude_input)
    body = feature.bodies.item(0)
    body.name = name
    return body


def extrude_join(component, profile, distance):
    extrudes = component.features.extrudeFeatures
    extrude_input = extrudes.createInput(
        profile,
        adsk.fusion.FeatureOperations.JoinFeatureOperation,
    )
    extent = adsk.fusion.DistanceExtentDefinition.create(value(distance))
    extrude_input.setOneSideExtent(
        extent,
        adsk.fusion.ExtentDirections.PositiveExtentDirection,
    )
    extrudes.add(extrude_input)


def cut_profile(component, profile, distance, direction):
    extrudes = component.features.extrudeFeatures
    cut_input = extrudes.createInput(
        profile,
        adsk.fusion.FeatureOperations.CutFeatureOperation,
    )
    distance_extent = adsk.fusion.DistanceExtentDefinition.create(value(distance))
    cut_input.setOneSideExtent(distance_extent, direction)
    extrudes.add(cut_input)


def delete_previous_generated_bodies(component):
    bodies_to_delete = []
    for index in range(component.bRepBodies.count):
        body = component.bRepBodies.item(index)
        if any(
            body.name.startswith(prefix)
            for prefix in BUILD_SPEC["generated_body_prefixes"]
        ):
            bodies_to_delete.append(body)

    for body in bodies_to_delete:
        body.deleteMe()


def add_body_perimeter_chamfer(component, body, thickness, warnings):
    if EDGE_CHAMFER <= 0.0:
        return

    edges = adsk.core.ObjectCollection.create()
    tol = 0.002
    for i in range(body.edges.count):
        edge = body.edges.item(i)
        start = edge.startVertex.geometry
        end = edge.endVertex.geometry
        on_bottom = abs(start.z) < tol and abs(end.z) < tol
        on_top = abs(start.z - thickness) < tol and abs(end.z - thickness) < tol
        if on_bottom or on_top:
            edges.add(edge)

    if edges.count == 0:
        warnings.append("No perimeter edges found for body chamfer.")
        return

    try:
        chamfers = component.features.chamferFeatures
        chamfer_input = chamfers.createInput(edges, True)
        chamfer_input.setToEqualDistance(value(EDGE_CHAMFER))
        chamfers.add(chamfer_input)
    except Exception as exc:
        warnings.append("Body chamfer could not be applied: {}".format(exc))


def create_base_block(component, center_x, base_thickness, name, warnings):
    sketch = component.sketches.add(component.xYConstructionPlane)
    draw_rounded_rectangle(sketch, center_x, 0.0, BODY_LENGTH, BODY_WIDTH, CORNER_RADIUS)
    body = extrude_new_body(component, largest_profile(sketch), base_thickness, name)
    add_body_perimeter_chamfer(component, body, base_thickness, warnings)
    return body


def add_working_pad(component, center_x, base_thickness):
    plane = offset_xy_plane(component, base_thickness)
    sketch = component.sketches.add(plane)
    draw_rounded_rectangle(
        sketch,
        center_x,
        0.0,
        WORKING_PAD_LENGTH,
        WORKING_PAD_WIDTH,
        WORKING_PAD_CORNER_RADIUS,
    )
    extrude_join(component, largest_profile(sketch), WORKING_PAD_HEIGHT)


def cut_circle_from_plane(component, cx, cy, z_height, diameter, distance, direction):
    plane = offset_xy_plane(component, z_height)
    sketch = component.sketches.add(plane)
    sketch.sketchCurves.sketchCircles.addByCenterRadius(point(cx, cy), diameter / 2.0)
    cut_profile(component, largest_profile(sketch), distance, direction)


def cut_figure8_link_pocket_from_top(component, cx, cy, top_z, pitch, lobe_diameter, waist_width, depth):
    plane = offset_xy_plane(component, top_z)
    sketch = component.sketches.add(plane)
    draw_figure8_link_pocket(sketch, cx, cy, pitch, lobe_diameter, waist_width)
    cut_profile(
        component,
        largest_profile(sketch),
        depth,
        adsk.fusion.ExtentDirections.NegativeExtentDirection,
    )


def bolt_y_positions():
    return (-BOLT_Y_SPACING / 2.0, BOLT_Y_SPACING / 2.0)


def add_front_hardware_features(component, center_x, base_top_z):
    bolt_clearance = BOLT_DIAMETER + BOLT_CLEARANCE_DIAMETRAL
    for y in bolt_y_positions():
        cut_circle_from_plane(
            component,
            center_x,
            y,
            base_top_z,
            bolt_clearance,
            base_top_z + 0.20,
            adsk.fusion.ExtentDirections.NegativeExtentDirection,
        )
        cut_circle_from_plane(
            component,
            center_x,
            y,
            base_top_z,
            BOLT_HEAD_RECESS_DIAMETER,
            VISIBLE_BOLT_RECESS_DEPTH,
            adsk.fusion.ExtentDirections.NegativeExtentDirection,
        )
        cut_circle_from_plane(
            component,
            center_x,
            y,
            0.0,
            BOLT_HEAD_RECESS_DIAMETER,
            BOLT_HEAD_RECESS_DEPTH,
            adsk.fusion.ExtentDirections.PositiveExtentDirection,
        )


def add_rear_hardware_features(component, center_x, base_top_z):
    bolt_clearance = BOLT_DIAMETER + BOLT_CLEARANCE_DIAMETRAL
    for y in bolt_y_positions():
        cut_circle_from_plane(
            component,
            center_x,
            y,
            base_top_z,
            bolt_clearance,
            base_top_z + 0.20,
            adsk.fusion.ExtentDirections.NegativeExtentDirection,
        )
        cut_circle_from_plane(
            component,
            center_x,
            y,
            base_top_z,
            BOLT_HEAD_RECESS_DIAMETER,
            VISIBLE_BOLT_RECESS_DEPTH,
            adsk.fusion.ExtentDirections.NegativeExtentDirection,
        )
        cut_circle_from_plane(
            component,
            center_x,
            y,
            0.0,
            REAR_NUT_RECESS_DIAMETER,
            REAR_NUT_RECESS_DEPTH,
            adsk.fusion.ExtentDirections.PositiveExtentDirection,
        )


def build_front_piece(component, center_x, warnings):
    body = create_base_block(component, center_x, FRONT_BASE_THICKNESS, "Bolt front pressing block", warnings)
    add_working_pad(component, center_x, FRONT_BASE_THICKNESS)

    top_z = FRONT_BASE_THICKNESS + WORKING_PAD_HEIGHT
    front_pin_hole = PIN_DIAMETER + FRONT_PIN_CLEARANCE_DIAMETRAL
    for pin_offset in (-PIN_PITCH / 2.0, PIN_PITCH / 2.0):
        cut_circle_from_plane(
            component,
            center_x + pin_offset,
            0.0,
            top_z,
            front_pin_hole,
            top_z + 0.20,
            adsk.fusion.ExtentDirections.NegativeExtentDirection,
        )

    cut_figure8_link_pocket_from_top(
        component,
        center_x,
        0.0,
        top_z,
        PIN_PITCH,
        FRONT_LINK_LOBE_DIAMETER,
        FRONT_LINK_WAIST_WIDTH,
        FRONT_RELIEF_DEPTH,
    )
    add_front_hardware_features(component, center_x, FRONT_BASE_THICKNESS)
    body.name = "Bolt front pressing block"
    return body


def build_rear_piece(component, center_x, warnings):
    body = create_base_block(component, center_x, REAR_BASE_THICKNESS, "Bolt rear support block", warnings)
    add_working_pad(component, center_x, REAR_BASE_THICKNESS)

    add_rear_hardware_features(component, center_x, REAR_BASE_THICKNESS)
    body.name = "Bolt rear support block"
    return body


def validate_parameters():
    front_pin_hole = PIN_DIAMETER + FRONT_PIN_CLEARANCE_DIAMETRAL
    bolt_clearance = BOLT_DIAMETER + BOLT_CLEARANCE_DIAMETRAL
    largest_pin_cut = max(FRONT_LINK_LOBE_DIAMETER, front_pin_hole)
    largest_bolt_cut = max(bolt_clearance, BOLT_HEAD_RECESS_DIAMETER, REAR_NUT_RECESS_DIAMETER)

    end_wall = (BODY_LENGTH - PIN_PITCH - largest_pin_cut) / 2.0
    side_wall_at_chain = (WORKING_PAD_WIDTH - largest_pin_cut) / 2.0
    bolt_edge_wall = (BODY_WIDTH - BOLT_Y_SPACING - largest_bolt_cut) / 2.0

    if end_wall < MINIMUM_WALL:
        raise ValueError("End wall around chain features is only {:.1f} mm.".format(mm(end_wall)))
    if side_wall_at_chain < 0.30:
        raise ValueError("Working pad lands are only {:.1f} mm beside the pin relief.".format(mm(side_wall_at_chain)))
    if bolt_edge_wall < MINIMUM_WALL:
        raise ValueError("Bolt edge wall is only {:.1f} mm. Increase BODY_WIDTH or reduce BOLT_Y_SPACING.".format(mm(bolt_edge_wall)))
    if BOLT_HEAD_RECESS_DEPTH >= FRONT_BASE_THICKNESS - MINIMUM_WALL:
        raise ValueError("Front bolt-head relief is too deep for the front block.")
    if REAR_NUT_RECESS_DEPTH >= REAR_BASE_THICKNESS - MINIMUM_WALL:
        raise ValueError("Rear nut/washer relief is too deep for the rear block.")


def run(context):
    app = adsk.core.Application.get()
    ui = app.userInterface

    try:
        design = adsk.fusion.Design.cast(app.activeProduct)
        if not design:
            ui.messageBox("No active Fusion design. Create or open a design first.")
            return

        validate_parameters()

        # Build directly in the root component so the script works in Fusion
        # Part Design documents as well as normal assembly-capable designs.
        component = design.rootComponent
        delete_previous_generated_bodies(component)

        warnings = []
        part_center_offset = (BODY_LENGTH + PART_GAP) / 2.0
        build_front_piece(component, -part_center_offset, warnings)
        build_rear_piece(component, part_center_offset, warnings)

        app.activeViewport.fit()

        message = (
            "Created bolt-tightened 428 chain master-link press jig.\n\n"
            "Hardware: 2x M6 bolts with washers/nuts\n"
            "Bolt clearance holes: {:.1f} mm\n"
            "Bolt centre spacing: {:.1f} mm\n"
            "Pin diameter: {:.1f} mm\n"
            "Pin pitch: {:.1f} mm\n"
            "Front link pocket: {:.1f} mm lobes, {:.1f} mm waist\n"
            "Front block: {:.1f} x {:.1f} x {:.1f} mm plus {:.1f} mm pad\n"
            "Rear block: {:.1f} x {:.1f} x {:.1f} mm plus {:.1f} mm pad\n"
            "Rear support pad: flat, no pin pockets"
        ).format(
            mm(BOLT_DIAMETER + BOLT_CLEARANCE_DIAMETRAL),
            mm(BOLT_Y_SPACING),
            mm(PIN_DIAMETER),
            mm(PIN_PITCH),
            mm(FRONT_LINK_LOBE_DIAMETER),
            mm(FRONT_LINK_WAIST_WIDTH),
            mm(BODY_LENGTH),
            mm(BODY_WIDTH),
            mm(FRONT_BASE_THICKNESS),
            mm(WORKING_PAD_HEIGHT),
            mm(BODY_LENGTH),
            mm(BODY_WIDTH),
            mm(REAR_BASE_THICKNESS),
            mm(WORKING_PAD_HEIGHT),
        )

        if warnings:
            message += "\n\nWarnings:\n- " + "\n- ".join(warnings)

        ui.messageBox(message)

    except Exception:
        if ui:
            ui.messageBox("Script failed:\n{}".format(traceback.format_exc()))
