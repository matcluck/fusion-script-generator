"""
Speaker-stand flange for a 13-inch laptop platform.

Builds one reinforced printable body: a socket that slides over a nominal
35 mm metal speaker pole, joined to a timber flange with recessed screw holes.
"""

import adsk.core
import adsk.fusion
import math
import traceback


BUILD_SPEC = {
    "schema_version": 1,
    "units": "cm",
    "coordinate_system": (
        "XY is the plywood mounting face; +Y points toward the platform's "
        "retaining lip; the socket axis tilts 10 degrees toward +Y"
    ),
    "generated_body_prefixes": ["Generated "],
    "printable_body_names": ["Generated Laptop Stand Flange"],
    "expected_printable_body_count": 1,
    "print_orientation": {
        "Generated Laptop Stand Flange": (
            "flat timber-contact face on the build plate; socket upward"
        )
    },
}


# PARAMETERS (Fusion API internal units are centimetres)
POLE_DIAMETER = 3.50          # 35.0 mm nominal metal pole diameter
SOCKET_CLEARANCE = 0.08       # 0.8 mm diametral clearance; tune for the printer
SOCKET_DEPTH = 6.5            # 65 mm pole engagement beyond the flange
SOCKET_WALL = 0.5             # 5 mm radial wall
SOCKET_ROOF = 0.3             # 3 mm closed stop beneath the timber
TILT_ANGLE_DEGREES = 10.0     # Front retaining-lip edge sits lower in use
FLANGE_WIDTH = 10.0           # 100 mm
FLANGE_DEPTH = 10.0           # 100 mm
FLANGE_THICKNESS = 0.8        # 8 mm
CORNER_FILLET = 0.6           # 6 mm
RIB_HEIGHT = 3.0              # 30 mm above the flange
RIB_REACH = 2.2               # 22 mm outward from the socket
RIB_THICKNESS = 0.8           # 8 mm
RIB_OVERLAP = 0.2             # 2 mm overlap into adjoining solids
SCREW_HOLE_DIAMETER = 0.45    # 4.5 mm clearance for 4 mm wood screws
SCREW_HEAD_DIAMETER = 0.9     # 9 mm pan-head recess
SCREW_HEAD_DEPTH = 0.3        # 3 mm recess from the socket side
SCREW_CENTRE_OFFSET = 3.8     # 38 mm from the flange centre in X and Y
CLAMP_COLLAR_OFFSET = 4.2     # 42 mm from socket closed end to collar
CLAMP_COLLAR_LENGTH = 1.2     # 12 mm along the socket axis
CLAMP_COLLAR_RADIAL = 0.5     # 5 mm added around the socket wall
CLAMP_PILOT_DIAMETER = 0.5    # 5 mm pilot hole to tap M6

# Reference dimensions for the recommended timber platform.
BOARD_WIDTH = 35.0            # 350 mm
BOARD_DEPTH = 25.0            # 250 mm
BOARD_THICKNESS = 1.2         # 12 mm plywood


def _delete_previous_generated_bodies(component):
    old_bodies = []
    for index in range(component.bRepBodies.count):
        body = component.bRepBodies.item(index)
        if any(
            body.name.startswith(prefix)
            for prefix in BUILD_SPEC["generated_body_prefixes"]
        ):
            old_bodies.append(body)

    for body in old_bodies:
        if not body.deleteMe():
            raise RuntimeError("Could not remove previous generated body")


def _require_result_body(feature, feature_name):
    if not feature:
        raise RuntimeError("{} returned no feature".format(feature_name))
    if (
        feature.healthState
        != adsk.fusion.FeatureHealthStates.HealthyFeatureHealthState
    ):
        raise RuntimeError(
            "{} is unhealthy: {}".format(
                feature_name, feature.errorOrWarningMessage
            )
        )
    if feature.bodies.count == 0:
        raise RuntimeError("{} created no result body".format(feature_name))
    body = feature.bodies.item(0)
    if not body or not body.isValid or body.volume <= 0.000001:
        raise RuntimeError(
            "{} did not create a valid solid".format(feature_name)
        )
    return body


def _world_to_sketch(sketch, x, y, z):
    transform = sketch.transform.copy()
    transform.invert()
    point = adsk.core.Point3D.create(x, y, z)
    point.transformBy(transform)
    return adsk.core.Point3D.create(point.x, point.y, 0.0)


def _extrude_profile(extrudes, profile, operation, distance, name):
    extrude_input = extrudes.createInput(profile, operation)
    extent = adsk.fusion.DistanceExtentDefinition.create(
        adsk.core.ValueInput.createByReal(float(distance))
    )
    extrude_input.setOneSideExtent(
        extent, adsk.fusion.ExtentDirections.PositiveExtentDirection
    )
    feature = extrudes.add(extrude_input)
    feature.name = name
    return _require_result_body(feature, name)


def _revolve_tilted_solid(
    root,
    axis_start_distance,
    axis_end_distance,
    start_radius,
    end_radius,
    angle_radians,
    operation,
    name,
):
    """Revolve a cylinder or conical frustum around the tilted pole axis."""
    sin_angle = math.sin(angle_radians)
    cos_angle = math.cos(angle_radians)

    def section_point(axis_distance, radial_distance):
        # Axis unit vector: (0, sin(a), cos(a)). The radial vector below is
        # perpendicular to it in the YZ sketch plane: (0, cos(a), -sin(a)).
        return (
            0.0,
            axis_distance * sin_angle + radial_distance * cos_angle,
            axis_distance * cos_angle - radial_distance * sin_angle,
        )

    sketch = root.sketches.add(root.yZConstructionPlane)
    sketch.name = "{} Sketch".format(name)
    world_points = (
        section_point(axis_start_distance, 0.0),
        section_point(axis_start_distance, start_radius),
        section_point(axis_end_distance, end_radius),
        section_point(axis_end_distance, 0.0),
    )
    points = [
        _world_to_sketch(sketch, point[0], point[1], point[2])
        for point in world_points
    ]
    lines = sketch.sketchCurves.sketchLines
    lines.addByTwoPoints(points[0], points[1])
    lines.addByTwoPoints(points[1], points[2])
    lines.addByTwoPoints(points[2], points[3])
    axis_line = lines.addByTwoPoints(points[3], points[0])

    if sketch.profiles.count != 1:
        raise RuntimeError("{} sketch did not create one profile".format(name))

    revolve_input = root.features.revolveFeatures.createInput(
        sketch.profiles.item(0), axis_line, operation
    )
    if not revolve_input.setAngleExtent(
        False, adsk.core.ValueInput.createByReal(2.0 * math.pi)
    ):
        raise RuntimeError("Could not set full revolution for {}".format(name))
    feature = root.features.revolveFeatures.add(revolve_input)
    feature.name = name
    return _require_result_body(feature, name)


def _add_rib(root, plane, world_points, thickness, name):
    sketch = root.sketches.add(plane)
    sketch.name = "{} Sketch".format(name)
    points = [
        _world_to_sketch(sketch, point[0], point[1], point[2])
        for point in world_points
    ]
    lines = sketch.sketchCurves.sketchLines
    for index in range(len(points)):
        lines.addByTwoPoints(points[index], points[(index + 1) % len(points)])

    if sketch.profiles.count != 1:
        raise RuntimeError("{} sketch did not create one profile".format(name))

    extrude_input = root.features.extrudeFeatures.createInput(
        sketch.profiles.item(0),
        adsk.fusion.FeatureOperations.JoinFeatureOperation,
    )
    extrude_input.setSymmetricExtent(
        adsk.core.ValueInput.createByReal(float(thickness)), True
    )
    feature = root.features.extrudeFeatures.add(extrude_input)
    feature.name = name
    return _require_result_body(feature, name)


def _cut_round_pocket(
    root, plane, world_x, world_y, world_z, diameter, cut_length, name
):
    sketch = root.sketches.add(plane)
    sketch.name = "{} Sketch".format(name)
    centre = _world_to_sketch(sketch, world_x, world_y, world_z)
    sketch.sketchCurves.sketchCircles.addByCenterRadius(
        centre, float(diameter) / 2.0
    )
    if sketch.profiles.count != 1:
        raise RuntimeError("{} sketch did not create one profile".format(name))

    extrude_input = root.features.extrudeFeatures.createInput(
        sketch.profiles.item(0),
        adsk.fusion.FeatureOperations.CutFeatureOperation,
    )
    extrude_input.setSymmetricExtent(
        adsk.core.ValueInput.createByReal(float(cut_length)), True
    )
    feature = root.features.extrudeFeatures.add(extrude_input)
    feature.name = name
    return _require_result_body(feature, name)


def _round_flange_corners(root, body):
    edge_set = adsk.core.ObjectCollection.create()
    half_width = FLANGE_WIDTH / 2.0
    half_depth = FLANGE_DEPTH / 2.0

    for index in range(body.edges.count):
        edge = body.edges.item(index)
        if not edge.startVertex or not edge.endVertex:
            continue
        start = edge.startVertex.geometry
        end = edge.endVertex.geometry
        is_vertical = abs(start.z - end.z) > FLANGE_THICKNESS * 0.9
        is_outer_corner = (
            abs(abs(start.x) - half_width) < 0.001
            and abs(abs(start.y) - half_depth) < 0.001
            and abs(abs(end.x) - half_width) < 0.001
            and abs(abs(end.y) - half_depth) < 0.001
        )
        if is_vertical and is_outer_corner:
            edge_set.add(edge)

    if edge_set.count != 4:
        return body

    try:
        fillet_input = root.features.filletFeatures.createInput()
        fillet_input.addConstantRadiusEdgeSet(
            edge_set,
            adsk.core.ValueInput.createByReal(float(CORNER_FILLET)),
            True,
        )
        feature = root.features.filletFeatures.add(fillet_input)
        feature.name = "Flange Corner Fillets"
        return _require_result_body(feature, feature.name)
    except Exception:
        # Rounded corners are cosmetic; retain a structurally valid square plate.
        return body


def _assert_final_geometry(body):
    bounds = body.boundingBox
    width = bounds.maxPoint.x - bounds.minPoint.x
    depth = bounds.maxPoint.y - bounds.minPoint.y
    height = bounds.maxPoint.z - bounds.minPoint.z
    angle_radians = math.radians(TILT_ANGLE_DEGREES)
    socket_inner_diameter = POLE_DIAMETER + SOCKET_CLEARANCE
    socket_outer_radius = (
        socket_inner_diameter + 2.0 * SOCKET_WALL
    ) / 2.0
    outer_start_distance = socket_outer_radius * math.tan(angle_radians)
    outer_end_distance = outer_start_distance + SOCKET_ROOF + SOCKET_DEPTH
    expected_height = (
        outer_end_distance * math.cos(angle_radians)
        + socket_outer_radius * math.sin(angle_radians)
    )

    checks = (
        (abs(width - FLANGE_WIDTH) <= 0.02, "flange width"),
        (abs(depth - FLANGE_DEPTH) <= 0.02, "flange depth"),
        (abs(height - expected_height) <= 0.02, "overall height"),
        (body.volume > 1.0, "positive solid volume"),
    )
    for passed, description in checks:
        if not passed:
            raise RuntimeError("Final geometry assertion failed: {}".format(description))


def run(context):
    app = adsk.core.Application.get()
    ui = app.userInterface

    try:
        design = adsk.fusion.Design.cast(app.activeProduct)
        if not design:
            raise RuntimeError("No active Fusion design. Create or open one first.")

        root = design.rootComponent
        _delete_previous_generated_bodies(root)
        sketches = root.sketches
        extrudes = root.features.extrudeFeatures

        # 1. Flat flange, with the timber-contact face at Z = 0.
        flange_sketch = sketches.add(root.xYConstructionPlane)
        flange_sketch.name = "Flange Outline"
        flange_sketch.sketchCurves.sketchLines.addTwoPointRectangle(
            adsk.core.Point3D.create(
                -FLANGE_WIDTH / 2.0, -FLANGE_DEPTH / 2.0, 0.0
            ),
            adsk.core.Point3D.create(
                FLANGE_WIDTH / 2.0, FLANGE_DEPTH / 2.0, 0.0
            ),
        )
        body = _extrude_profile(
            extrudes,
            flange_sketch.profiles.item(0),
            adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
            FLANGE_THICKNESS,
            "Flange Plate",
        )
        body = _round_flange_corners(root, body)

        # 2. Build the socket around an axis tilted toward +Y. In use, attach
        # +Y toward the platform's retaining lip so that edge sits lower.
        socket_inner_diameter = POLE_DIAMETER + SOCKET_CLEARANCE
        socket_outer_diameter = socket_inner_diameter + 2.0 * SOCKET_WALL
        socket_outer_radius = socket_outer_diameter / 2.0
        tilt_angle = math.radians(TILT_ANGLE_DEGREES)
        outer_start_distance = socket_outer_radius * math.tan(tilt_angle)
        outer_end_distance = (
            outer_start_distance + SOCKET_ROOF + SOCKET_DEPTH
        )
        body = _revolve_tilted_solid(
            root,
            outer_start_distance,
            outer_end_distance,
            socket_outer_radius,
            socket_outer_radius,
            tilt_angle,
            adsk.fusion.FeatureOperations.JoinFeatureOperation,
            "Pole Socket Outer Join",
        )

        # 3. Four simple ribs transfer bending into the flange. The +/-Y roots
        # track the tilted socket centreline; the +/-X roots overlap it deeply
        # enough to remain robust at the top of each rib.
        rib_root_radius = socket_outer_radius - RIB_OVERLAP
        rib_base_z = FLANGE_THICKNESS - RIB_OVERLAP
        rib_top_z = FLANGE_THICKNESS + RIB_HEIGHT
        rib_base_axis_y = rib_base_z * math.tan(tilt_angle)
        rib_top_axis_y = rib_top_z * math.tan(tilt_angle)

        body = _add_rib(
            root,
            root.xZConstructionPlane,
            [
                (rib_root_radius, 0.0, rib_base_z),
                (socket_outer_radius + RIB_REACH, 0.0, rib_base_z),
                (rib_root_radius, 0.0, rib_top_z),
            ],
            RIB_THICKNESS,
            "Positive X Rib",
        )
        body = _add_rib(
            root,
            root.xZConstructionPlane,
            [
                (-rib_root_radius, 0.0, rib_base_z),
                (-rib_root_radius, 0.0, rib_top_z),
                (-socket_outer_radius - RIB_REACH, 0.0, rib_base_z),
            ],
            RIB_THICKNESS,
            "Negative X Rib",
        )
        body = _add_rib(
            root,
            root.yZConstructionPlane,
            [
                (0.0, rib_base_axis_y + rib_root_radius, rib_base_z),
                (0.0, rib_top_axis_y + rib_root_radius, rib_top_z),
                (
                    0.0,
                    rib_base_axis_y + socket_outer_radius + RIB_REACH,
                    rib_base_z,
                ),
            ],
            RIB_THICKNESS,
            "Positive Y Rib",
        )
        body = _add_rib(
            root,
            root.yZConstructionPlane,
            [
                (0.0, rib_base_axis_y - rib_root_radius, rib_base_z),
                (
                    0.0,
                    rib_base_axis_y - socket_outer_radius - RIB_REACH,
                    rib_base_z,
                ),
                (0.0, rib_top_axis_y - rib_root_radius, rib_top_z),
            ],
            RIB_THICKNESS,
            "Negative Y Rib",
        )

        # 4. A short round band provides a clean, symmetric M6 tapping area.
        # It sits above the rib tops and adds 5 mm of radial thread depth.
        clamp_collar_start = outer_start_distance + CLAMP_COLLAR_OFFSET
        clamp_collar_end = clamp_collar_start + CLAMP_COLLAR_LENGTH
        clamp_collar_radius = socket_outer_radius + CLAMP_COLLAR_RADIAL
        body = _revolve_tilted_solid(
            root,
            clamp_collar_start,
            clamp_collar_end,
            clamp_collar_radius,
            clamp_collar_radius,
            tilt_angle,
            adsk.fusion.FeatureOperations.JoinFeatureOperation,
            "Round M6 Clamp Collar",
        )

        # 5. Revolve the concentric pole bore on the same tilted axis. It starts
        # 3 mm along the axis from the closed end and opens past the free end.
        bore_start_distance = outer_start_distance + SOCKET_ROOF
        body = _revolve_tilted_solid(
            root,
            bore_start_distance,
            outer_end_distance + 0.02,
            socket_inner_diameter / 2.0,
            socket_inner_diameter / 2.0,
            tilt_angle,
            adsk.fusion.FeatureOperations.CutFeatureOperation,
            "Pole Socket Bore",
        )

        # 6. Cut through the middle of the straight clamp collar. The radial
        # cut deliberately extends 3 mm beyond the outside surface so the
        # opening cannot be left partially covered by model tolerances.
        socket_inner_radius = socket_inner_diameter / 2.0
        clamp_axis_distance = (
            clamp_collar_start + clamp_collar_end
        ) / 2.0
        clamp_hole_y = clamp_axis_distance * math.sin(tilt_angle)
        clamp_hole_z = clamp_axis_distance * math.cos(tilt_angle)
        clamp_hole_start_x = socket_inner_radius - 0.15
        clamp_hole_end_x = clamp_collar_radius + 0.30
        clamp_hole_mid_x = (clamp_hole_start_x + clamp_hole_end_x) / 2.0
        clamp_plane_input = root.constructionPlanes.createInput()
        clamp_plane_input.setByOffset(
            root.yZConstructionPlane,
            adsk.core.ValueInput.createByReal(float(clamp_hole_mid_x)),
        )
        clamp_plane = root.constructionPlanes.add(clamp_plane_input)
        clamp_plane.name = "M6 Clamp Pilot Midplane"
        body = _cut_round_pocket(
            root,
            clamp_plane,
            clamp_hole_mid_x,
            clamp_hole_y,
            clamp_hole_z,
            CLAMP_PILOT_DIAMETER,
            clamp_hole_end_x - clamp_hole_start_x,
            "M6 Clamp Pilot Hole",
        )

        # 7. Through-holes and pan-head recesses. Heads are accessible from the
        # socket side; screws point through Z = 0 into the timber platform.
        hole_locations = (
            (-SCREW_CENTRE_OFFSET, -SCREW_CENTRE_OFFSET),
            (-SCREW_CENTRE_OFFSET, SCREW_CENTRE_OFFSET),
            (SCREW_CENTRE_OFFSET, -SCREW_CENTRE_OFFSET),
            (SCREW_CENTRE_OFFSET, SCREW_CENTRE_OFFSET),
        )
        for index, (x_value, y_value) in enumerate(hole_locations, start=1):
            body = _cut_round_pocket(
                root,
                root.xYConstructionPlane,
                x_value,
                y_value,
                0.0,
                SCREW_HOLE_DIAMETER,
                FLANGE_THICKNESS * 2.5,
                "Screw {} Through Hole".format(index),
            )

        counterbore_plane_z = FLANGE_THICKNESS - SCREW_HEAD_DEPTH / 2.0
        plane_input = root.constructionPlanes.createInput()
        plane_input.setByOffset(
            root.xYConstructionPlane,
            adsk.core.ValueInput.createByReal(float(counterbore_plane_z)),
        )
        counterbore_plane = root.constructionPlanes.add(plane_input)
        counterbore_plane.name = "Screw Head Recess Plane"

        for index, (x_value, y_value) in enumerate(hole_locations, start=1):
            body = _cut_round_pocket(
                root,
                counterbore_plane,
                x_value,
                y_value,
                counterbore_plane_z,
                SCREW_HEAD_DIAMETER,
                SCREW_HEAD_DEPTH + 0.02,
                "Screw {} Head Recess".format(index),
            )

        body.name = BUILD_SPEC["printable_body_names"][0]
        _assert_final_geometry(body)

        ui.messageBox(
            "Created 1 printable solid: {}\n\n"
            "Socket: {:.1f} mm ID x {:.0f} mm engagement, {:.0f} mm wall\n"
            "Platform tilt: {:.1f} degrees toward the retaining lip\n"
            "Reinforcement: four {:.0f} mm ribs; {:.1f} mm OD clamp collar\n"
            "Flange: {:.0f} x {:.0f} x {:.0f} mm\n"
            "Mounting: 4 recessed holes for 4 mm pan-head wood screws; "
            "size screw length to the measured plywood thickness\n"
            "Locking: tap the 5.0 mm side pilot M6 and fit a hand knob\n"
            "Recommended board: {:.0f} x {:.0f} x {:.0f} mm plywood\n\n"
            "Print with the flat timber-contact face on the bed and the "
            "socket upward. No construction bodies remain."
            .format(
                body.name,
                socket_inner_diameter * 10.0,
                SOCKET_DEPTH * 10.0,
                SOCKET_WALL * 10.0,
                TILT_ANGLE_DEGREES,
                RIB_THICKNESS * 10.0,
                clamp_collar_radius * 20.0,
                FLANGE_WIDTH * 10.0,
                FLANGE_DEPTH * 10.0,
                FLANGE_THICKNESS * 10.0,
                BOARD_WIDTH * 10.0,
                BOARD_DEPTH * 10.0,
                BOARD_THICKNESS * 10.0,
            )
        )

    except Exception:
        if ui:
            ui.messageBox("Script failed:\n{}".format(traceback.format_exc()))
