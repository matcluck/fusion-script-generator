"""Open-top cradle and retainer cover for a measured IEC C14 lead.

The front panel mounts to a chassis. The C14 male face projects
out through a standards-based keyed opening while the larger moulded shoulder
is captured by the panel.  The plug drops in from above, then the separate
cover is screwed to reinforced side rails.
"""
import adsk.core
import adsk.fusion
import traceback


BUILD_SPEC = {
    "schema_version": 1,
    "units": "cm",
    "coordinate_system": (
        "X is left/right across the IEC face; Y is bottom/top; "
        "Z runs from the outer mounting face into the chassis."
    ),
    "generated_body_prefixes": ["IEC C14 - "],
    "printable_body_names": ["IEC C14 - Cradle", "IEC C14 - Top Cover"],
    "expected_printable_body_count": 2,
    "print_orientation": {
        "IEC C14 - Cradle": "Front mounting face on the bed; use a 4 mm brim if adhesion needs help.",
        "IEC C14 - Top Cover": "Large inside face on the bed; no supports.",
    },
}


# ── PARAMETERS (cm; source measurements in comments are mm) ────────────────
# Reference lead moulded shoulder/body measurements.
C14_FACE_W = 2.873          # 28.73 mm measured front shoulder width
C14_FACE_H = 2.048          # 20.48 mm measured front shoulder height
C14_BODY_W = 2.873          # 28.73 mm measured largest plug body width
C14_BODY_H = 2.110          # 21.10 mm measured largest plug body height
C14_HEAD_LENGTH = 4.200     # 42.00 mm, face to start of strain relief

# Measured clear cavity inside the reference C14 nose. The front plate overlaps
# the moulded nose and exposes only this mating cavity, so the external C13
# plug can enter while the 28.73 x 20.48 mm C14 shoulder cannot pull through.
C14_INNER_W = 2.428         # 24.28 mm measured clear cavity width
C14_INNER_H = 1.624         # 16.24 mm measured clear cavity height
FRONT_CLEARANCE_X = 0.020   # 0.20 mm per side; finished opening 24.68 mm
FRONT_CLEARANCE_Y = 0.020   # 0.20 mm per side; finished opening 16.64 mm
LOWER_CORNER_CHAMFER = 0.270  # 2.70 mm straight 45-degree lower returns
BODY_CLEARANCE = 0.040      # 0.40 mm per side in the open cradle channel

# Cradle structure.
FRONT_THICK = 0.400         # 4.00 mm front retaining panel thickness
WALL = 1.000                # 10.00 mm side rails; 3.8 mm around 2.4 mm pilots
FLOOR_THICK = 0.400         # 4.00 mm support under the plug body
TOP_CLEARANCE = 0.100       # 1.00 mm above body before the fitted cover
REAR_ALLOWANCE = 0.300      # 3.00 mm beyond the strain-relief start
REAR_STOP_THICK = 0.400     # 4.00 mm rear bridge that stops inward movement
CABLE_CENTER_Y = 0.000      # cable leaves the plug on the centreline
CABLE_NOTCH_DIA = 1.500     # 15.00 mm clear opening for moulded strain relief

# Chassis-mounting flange. The holes are the intended 9- and 3-o'clock pair
# on the front face, retained as small 1 mm pilots from the original concept.
MOUNT_PLATE_W = 5.500       # 55.0 mm overall width; extra side material
MOUNT_PLATE_H = 3.600       # 36.0 mm overall height; extra top/bottom material
CHASSIS_HOLE_DIA = 0.100    # 1.0 mm legacy pilot; enlarge only for your screws
CHASSIS_HOLE_PITCH_X = 4.200  # 42.0 mm centre-to-centre, horizontal only

# Separate cover and its self-tapping fixings.
COVER_THICK = 0.400         # 4.00 mm
COVER_OVERHANG = 0.100      # 1.00 mm each side beyond the cradle walls
COVER_SCREW_CLEAR_DIA = 0.340  # 3.4 mm clearance for M3 self-tappers
COVER_PILOT_DIA = 0.240     # 2.4 mm pilot in printed side rails
COVER_SCREW_FRONT_OFFSET = 0.650  # 6.5 mm behind the panel
COVER_SCREW_REAR_OFFSET = 0.700   # 7.0 mm before the cable exit


def _delete_previous_generated_bodies(component):
    """Delete only bodies created by an earlier run of this script."""
    old_bodies = []
    for index in range(component.bRepBodies.count):
        body = component.bRepBodies.item(index)
        if body.name.startswith("IEC C14 - "):
            old_bodies.append(body)
    for body in old_bodies:
        body.deleteMe()


def _require_body(feature, label):
    if not feature:
        raise RuntimeError("{} returned no feature".format(label))
    if feature.healthState != adsk.fusion.FeatureHealthStates.HealthyFeatureHealthState:
        raise RuntimeError("{} is unhealthy: {}".format(label, feature.errorOrWarningMessage))
    if feature.bodies.count == 0:
        raise RuntimeError("{} produced no body".format(label))
    body = feature.bodies.item(0)
    if not body or not body.isValid or body.volume <= 0.000001:
        raise RuntimeError("{} did not produce a valid positive-volume body".format(label))
    return body


def _world_to_sketch(sketch, x, y, z):
    transform = sketch.transform.copy()
    transform.invert()
    point = adsk.core.Point3D.create(x, y, z)
    point.transformBy(transform)
    return point.x, point.y


def _add_closed_polygon(sketch, points):
    lines = sketch.sketchCurves.sketchLines
    local_points = [adsk.core.Point3D.create(x, y, 0) for x, y in points]
    for index in range(len(local_points)):
        lines.addByTwoPoints(local_points[index], local_points[(index + 1) % len(local_points)])


def _new_box(root, name, x_min, y_min, z_start, width, height, depth):
    """Create an axis-aligned solid box using the XY plane and a Z extrusion."""
    sketch = root.sketches.add(root.xYConstructionPlane)
    _add_closed_polygon(sketch, [
        (x_min, y_min),
        (x_min + width, y_min),
        (x_min + width, y_min + height),
        (x_min, y_min + height),
    ])
    extrudes = root.features.extrudeFeatures
    extrusion_input = extrudes.createInput(
        sketch.profiles.item(0), adsk.fusion.FeatureOperations.NewBodyFeatureOperation
    )
    extrusion_input.setOneSideExtent(
        adsk.fusion.DistanceExtentDefinition.create(adsk.core.ValueInput.createByReal(depth)),
        adsk.fusion.ExtentDirections.PositiveExtentDirection,
    )
    extrusion_input.startExtent = adsk.fusion.OffsetStartDefinition.create(
        adsk.core.ValueInput.createByReal(z_start)
    )
    feature = extrudes.add(extrusion_input)
    body = _require_body(feature, name)
    body.name = name
    return body


def _join(root, target, tool, label):
    target_name = target.name
    tools = adsk.core.ObjectCollection.create()
    tools.add(tool)
    combine_input = root.features.combineFeatures.createInput(target, tools)
    combine_input.operation = adsk.fusion.FeatureOperations.JoinFeatureOperation
    combine_input.isKeepToolBodies = False
    result = root.features.combineFeatures.add(combine_input)
    body = _require_body(result, label)
    body.name = target_name
    return body


def _cut_xy_polygon(root, target, world_points, z_plane, full_depth, label):
    """Cut a polygon through Z; used for the front C14 mating opening."""
    target_name = target.name
    plane_input = root.constructionPlanes.createInput()
    plane_input.setByOffset(root.xYConstructionPlane, adsk.core.ValueInput.createByReal(z_plane))
    plane = root.constructionPlanes.add(plane_input)
    sketch = root.sketches.add(plane)
    local_points = []
    for x, y in world_points:
        sx, sy = _world_to_sketch(sketch, x, y, z_plane)
        local_points.append((sx, sy))
    _add_closed_polygon(sketch, local_points)
    extrusion_input = root.features.extrudeFeatures.createInput(
        sketch.profiles.item(0), adsk.fusion.FeatureOperations.CutFeatureOperation
    )
    extrusion_input.participantBodies = [target]
    extrusion_input.setSymmetricExtent(adsk.core.ValueInput.createByReal(full_depth), True)
    feature = root.features.extrudeFeatures.add(extrusion_input)
    body = _require_body(feature, label)
    body.name = target_name
    return body


def _cut_circle_xz(root, target, x, z, diameter, y_plane, full_depth, label):
    """Cut a vertical-Y-axis hole from an XZ sketch, restricted to target."""
    target_name = target.name
    plane_input = root.constructionPlanes.createInput()
    plane_input.setByOffset(root.xZConstructionPlane, adsk.core.ValueInput.createByReal(y_plane))
    plane = root.constructionPlanes.add(plane_input)
    sketch = root.sketches.add(plane)
    sx, sy = _world_to_sketch(sketch, x, y_plane, z)
    sketch.sketchCurves.sketchCircles.addByCenterRadius(
        adsk.core.Point3D.create(sx, sy, 0), diameter / 2.0
    )
    extrusion_input = root.features.extrudeFeatures.createInput(
        sketch.profiles.item(0), adsk.fusion.FeatureOperations.CutFeatureOperation
    )
    extrusion_input.participantBodies = [target]
    extrusion_input.setSymmetricExtent(adsk.core.ValueInput.createByReal(full_depth), True)
    feature = root.features.extrudeFeatures.add(extrusion_input)
    body = _require_body(feature, label)
    body.name = target_name
    return body


def _cut_circle_xy(root, target, x, y, diameter, z_plane, full_depth, label):
    """Cut a Z-axis chassis mounting hole from an XY sketch."""
    target_name = target.name
    plane_input = root.constructionPlanes.createInput()
    plane_input.setByOffset(root.xYConstructionPlane, adsk.core.ValueInput.createByReal(z_plane))
    plane = root.constructionPlanes.add(plane_input)
    sketch = root.sketches.add(plane)
    sx, sy = _world_to_sketch(sketch, x, y, z_plane)
    sketch.sketchCurves.sketchCircles.addByCenterRadius(
        adsk.core.Point3D.create(sx, sy, 0), diameter / 2.0
    )
    extrusion_input = root.features.extrudeFeatures.createInput(
        sketch.profiles.item(0), adsk.fusion.FeatureOperations.CutFeatureOperation
    )
    extrusion_input.participantBodies = [target]
    extrusion_input.setSymmetricExtent(adsk.core.ValueInput.createByReal(full_depth), True)
    feature = root.features.extrudeFeatures.add(extrusion_input)
    body = _require_body(feature, label)
    body.name = target_name
    return body


def _assert_bounds(body, minimum_size, label):
    box = body.boundingBox
    size = (
        box.maxPoint.x - box.minPoint.x,
        box.maxPoint.y - box.minPoint.y,
        box.maxPoint.z - box.minPoint.z,
    )
    if any(actual < expected for actual, expected in zip(size, minimum_size)):
        raise RuntimeError("{} has unexpectedly small bounding box {}".format(label, size))


def run(context):
    app = adsk.core.Application.get()
    ui = app.userInterface
    try:
        design = adsk.fusion.Design.cast(app.activeProduct)
        if not design:
            raise RuntimeError("No active Fusion design. Create or open one first.")
        root = design.rootComponent
        _delete_previous_generated_bodies(root)

        # Derived mating envelope. The opening follows the measured clear
        # cavity plus a small FDM allowance. The larger moulded C14 shoulder
        # remains positively trapped behind the front panel.
        face_w = C14_INNER_W + 2.0 * FRONT_CLEARANCE_X
        face_h = C14_INNER_H + 2.0 * FRONT_CLEARANCE_Y
        capture_x = (C14_FACE_W - face_w) / 2.0
        capture_y = (C14_FACE_H - face_h) / 2.0
        if capture_x < 0.050 or capture_y < 0.020:
            raise RuntimeError(
                "Front retaining shoulder is too small: {:.2f} x {:.2f} mm per side".format(
                    capture_x * 10.0, capture_y * 10.0
                )
            )
        cavity_w = C14_BODY_W + 2.0 * BODY_CLEARANCE
        cavity_h = C14_BODY_H + 2.0 * BODY_CLEARANCE
        cavity_bottom = -cavity_h / 2.0
        cavity_top = cavity_h / 2.0
        outer_w = cavity_w + 2.0 * WALL
        rail_end = FRONT_THICK + C14_HEAD_LENGTH + REAR_ALLOWANCE
        rail_height = cavity_h + FLOOR_THICK + TOP_CLEARANCE
        rail_bottom = cavity_bottom - FLOOR_THICK
        cover_y = cavity_top + TOP_CLEARANCE
        screw_x = cavity_w / 2.0 + WALL / 2.0
        screw_zs = (FRONT_THICK + COVER_SCREW_FRONT_OFFSET, rail_end - COVER_SCREW_REAR_OFFSET)

        # Main cradle: a front capture bezel, continuous floor, side rails,
        # and rear bridge. The rear bridge is the positive inward/backward
        # stop: its cable U-channel is far smaller than the C14 plug body.
        # It is open at the top only while loading; the cover closes it.
        cradle = _new_box(
            root, "IEC C14 - Cradle",
            -MOUNT_PLATE_W / 2.0, -MOUNT_PLATE_H / 2.0, 0.0,
            MOUNT_PLATE_W, MOUNT_PLATE_H, FRONT_THICK,
        )
        floor = _new_box(
            root, "IEC C14 - Floor tool",
            -outer_w / 2.0, rail_bottom, FRONT_THICK,
            outer_w, FLOOR_THICK, rail_end - FRONT_THICK,
        )
        cradle = _join(root, cradle, floor, "Join cradle floor")
        left_rail = _new_box(
            root, "IEC C14 - Left rail tool",
            -outer_w / 2.0, rail_bottom, FRONT_THICK,
            WALL, rail_height, rail_end - FRONT_THICK,
        )
        cradle = _join(root, cradle, left_rail, "Join left rail")
        right_rail = _new_box(
            root, "IEC C14 - Right rail tool",
            outer_w / 2.0 - WALL, rail_bottom, FRONT_THICK,
            WALL, rail_height, rail_end - FRONT_THICK,
        )
        cradle = _join(root, cradle, right_rail, "Join right rail")
        rear_stop = _new_box(
            root, "IEC C14 - Rear stop tool",
            -outer_w / 2.0, rail_bottom, rail_end - REAR_STOP_THICK,
            outer_w, rail_height, REAR_STOP_THICK,
        )
        cradle = _join(root, cradle, rear_stop, "Join rear stop")

        half_face_w = face_w / 2.0
        half_face_h = face_h / 2.0
        chamfer = LOWER_CORNER_CHAMFER
        if chamfer <= 0.0 or chamfer >= min(face_w, face_h) / 2.0:
            raise RuntimeError("Invalid C14 lower corner chamfer")
        cradle = _cut_xy_polygon(
            root, cradle,
            [
                (-half_face_w, half_face_h),
                ( half_face_w, half_face_h),
                ( half_face_w, -half_face_h + chamfer),
                ( half_face_w - chamfer, -half_face_h),
                (-half_face_w + chamfer, -half_face_h),
                (-half_face_w, -half_face_h + chamfer),
            ],
            FRONT_THICK / 2.0, FRONT_THICK + 0.20,
            "Cut measured C14 mating opening with straight lower returns",
        )
        for hx in (-CHASSIS_HOLE_PITCH_X / 2.0, CHASSIS_HOLE_PITCH_X / 2.0):
            cradle = _cut_circle_xy(
                root, cradle, hx, 0.0, CHASSIS_HOLE_DIA, FRONT_THICK / 2.0,
                FRONT_THICK + 0.20, "Cut 3-and-9-o'clock chassis hole",
            )

        # The rear U-channel accepts the cable while loading from above. Its
        # round lower end supports the lead without pinching it; the installed
        # cover closes the open top and makes this rear stop captive.
        cable_notch_dia = CABLE_NOTCH_DIA
        cradle = _cut_circle_xy(
            root, cradle, 0.0, CABLE_CENTER_Y, cable_notch_dia,
            rail_end - REAR_STOP_THICK / 2.0, REAR_STOP_THICK + 0.20,
            "Cut rear cable radius",
        )
        cable_radius = cable_notch_dia / 2.0
        cradle = _cut_xy_polygon(
            root, cradle,
            [
                (-cable_radius, CABLE_CENTER_Y),
                ( cable_radius, CABLE_CENTER_Y),
                ( cable_radius, cover_y + 0.10),
                (-cable_radius, cover_y + 0.10),
            ],
            rail_end - REAR_STOP_THICK / 2.0, REAR_STOP_THICK + 0.20,
            "Open rear cable U-channel",
        )

        # Four vertical pilot holes lie in the solid side rails.  They receive
        # M3 self-tappers from the cover; screws should be 10-12 mm long so they
        # cannot reach into the C14 cavity.
        for hx in (-screw_x, screw_x):
            for hz in screw_zs:
                cradle = _cut_circle_xz(
                    root, cradle, hx, hz, COVER_PILOT_DIA, cover_y - 0.10,
                    rail_height + COVER_THICK + 0.50, "Cut cover pilot",
                )
        cradle.name = "IEC C14 - Cradle"

        # Separate top cover, modeled at its assembled position. It closes the
        # rear bridge's U-channel, so the cable and C14 head cannot lift out.
        cover = _new_box(
            root, "IEC C14 - Top Cover",
            -outer_w / 2.0 - COVER_OVERHANG, cover_y, FRONT_THICK,
            outer_w + 2.0 * COVER_OVERHANG, COVER_THICK, rail_end - FRONT_THICK,
        )
        for hx in (-screw_x, screw_x):
            for hz in screw_zs:
                cover = _cut_circle_xz(
                    root, cover, hx, hz, COVER_SCREW_CLEAR_DIA, cover_y + COVER_THICK / 2.0,
                    COVER_THICK + 0.20, "Cut cover clearance hole",
                )
        cover.name = "IEC C14 - Top Cover"

        _assert_bounds(cradle, (MOUNT_PLATE_W, MOUNT_PLATE_H, rail_end), "Cradle")
        _assert_bounds(
            cover,
            (outer_w + 2.0 * COVER_OVERHANG, COVER_THICK, rail_end - FRONT_THICK - 0.01),
            "Top cover",
        )
        expected = set(BUILD_SPEC["printable_body_names"])
        actual = {
            root.bRepBodies.item(index).name
            for index in range(root.bRepBodies.count)
            if root.bRepBodies.item(index).name.startswith("IEC C14 - ")
            and root.bRepBodies.item(index).volume > 0.000001
        }
        if actual != expected:
            raise RuntimeError("Expected printable bodies {}, found {}".format(expected, actual))

        ui.messageBox(
            "Created two printable bodies:\n"
            "• IEC C14 - Cradle\n"
            "• IEC C14 - Top Cover\n\n"
            "C14 face opening: {:.2f} x {:.2f} mm\n"
            "Retaining shoulder: {:.2f} x {:.2f} mm per side\n"
            "Rear U-channel: {:.1f} mm; closed by the fitted cover.\n"
            "Use four M3 self-tappers, 10-12 mm long, for the top cover.".format(
                face_w * 10.0,
                face_h * 10.0,
                capture_x * 10.0,
                capture_y * 10.0,
                cable_notch_dia * 10.0,
            )
        )
    except Exception:
        if ui:
            ui.messageBox("Script failed:\n{}".format(traceback.format_exc()))
