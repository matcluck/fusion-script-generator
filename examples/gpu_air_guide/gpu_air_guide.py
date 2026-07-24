"""
Parametric full-face 120 mm front-fan GPU ram-air guide.

Builds a one-piece, support-free PETG duct for the middle front intake fan.
The duct collects nearly the full fan face, settles the flow in a short
plenum, then contracts smoothly toward the narrow space between two GPUs.
"""

import math
import traceback

import adsk.core
import adsk.fusion


BUILD_SPEC = {
    "schema_version": 1,
    "units": "cm",
    "coordinate_system": (
        "X spans the fan width, Y rises from the middle/lower fan seam, "
        "and +Z runs from the fan flange toward the GPUs"
    ),
    "generated_body_prefixes": ["GPU Air Guide"],
    "printable_body_names": ["GPU Air Guide"],
    "expected_printable_body_count": 1,
    "print_orientation": {
        "GPU Air Guide": "flat fan flange on the build plate; duct upward"
    },
}


# PARAMETERS (Fusion API units are centimetres)
FAN_SIZE = 12.00                       # 120.0 mm fan frame
FAN_HOLE_SPACING = 10.50               # 105.0 mm mounting-hole spacing
MOUNT_HOLE_DIAMETER = 0.45             # 4.5 mm through-holes

FLANGE_THICKNESS = 0.30                # 3.0 mm
DUCT_JOIN_OVERLAP = 0.02               # 0.2 mm overlap into flange
DUCT_LENGTH = 8.50                     # 85.0 mm beyond inside fan face
DUCT_WALL = 0.24                       # 2.4 mm PETG wall
STRAIGHT_PLENUM_LENGTH = 1.00          # 10.0 mm before contraction

INLET_WIDTH = 10.80                    # 108.0 mm outside width
INLET_HEIGHT = 10.80                   # 108.0 mm outside height
INLET_CENTRE_Y = 6.00                  # Middle of 120 mm fan
INLET_CORNER_RADIUS = 1.80             # 18.0 mm outside radius

OUTLET_WIDTH = 9.80                    # 98.0 mm outside width
OUTLET_HEIGHT = 7.00                   # 70.0 mm outside height
OUTLET_CENTRE_Y = 3.50                 # Outlet spans seam to +70 mm
OUTLET_CORNER_RADIUS = 0.65            # 6.5 mm outside radius
GPU_GAP_CENTRE_ABOVE_SEAM = 2.00       # Measured target: 20.0 mm

OUTLET_LIP_START = 0.45                # 4.5 mm before duct end
OUTLET_LIP_WIDTH = 10.15               # 101.5 mm maximum width
OUTLET_LIP_HEIGHT = 7.35                # 73.5 mm maximum height
OUTLET_LIP_CORNER_RADIUS = 0.82         # 8.2 mm outside radius

ZIP_SLOT_WIDTH = 0.35                  # 3.5 mm
ZIP_SLOT_HEIGHT = 1.00                 # 10.0 mm
ZIP_SLOT_X = 5.65                      # Outside the duct wall
ZIP_SLOT_Y_POSITIONS = (3.00, 9.00)    # 30.0 and 90.0 mm above seam

RIB_START_Z = 1.45                     # 14.5 mm from fan-side datum
RIB_END_Z = 7.65                       # 76.5 mm from fan-side datum
RIB_HEIGHT = 0.30                      # 3.0 mm tall in side view
RIB_PLANE_X = 5.05                     # Rib mid-plane from duct centre
RIB_TOTAL_DEPTH = 1.00                 # 10.0 mm symmetric extrusion
RIB_HEIGHT_FRACTIONS = (0.24, 0.50, 0.76)

PLAQUE_PLANE_X = 5.20                  # Mid-plane of side plaque
PLAQUE_OUTER_X = 5.56                  # Flat lettering face
PLAQUE_TOTAL_DEPTH = 0.72              # 7.2 mm symmetric extrusion
PLAQUE_Z_MIN = 1.55                    # 15.5 mm
PLAQUE_Z_MAX = 7.25                    # 72.5 mm
PLAQUE_Y_MIN = 2.00                    # 20.0 mm above seam
PLAQUE_Y_MAX = 5.25                    # 52.5 mm above seam
PLAQUE_CHAMFER = 0.35                  # 3.5 mm corner cuts
TEXT_RECESS_TOTAL_DEPTH = 0.18         # 1.8 mm symmetric cutter

CUT_DEPTH = 0.60                       # 6.0 mm clears flange and overlap
CUT_OVERTRAVEL = 0.10                  # 1.0 mm beyond duct outlet

GENERATED_BODY_PREFIX = "GPU Air Guide"
FINAL_BODY_NAME = "GPU Air Guide"


def value(real_cm):
    return adsk.core.ValueInput.createByReal(float(real_cm))


def point(x, y, z=0.0):
    return adsk.core.Point3D.create(float(x), float(y), float(z))


def mm(cm_value):
    return cm_value * 10.0


def lerp(start, end, amount):
    return start + (end - start) * amount


def smoothstep(amount):
    amount = max(0.0, min(1.0, amount))
    return amount * amount * (3.0 - 2.0 * amount)


def world_to_sketch_point(sketch, world_x, world_y, world_z):
    """Convert world coordinates to the local coordinates of a sketch."""
    transform = sketch.transform.copy()
    transform.invert()
    result = point(world_x, world_y, world_z)
    result.transformBy(transform)
    return point(result.x, result.y)


def offset_xy_plane(component, z_height):
    if abs(z_height) < 1e-9:
        return component.xYConstructionPlane

    plane_input = component.constructionPlanes.createInput()
    plane_input.setByOffset(component.xYConstructionPlane, value(z_height))
    return component.constructionPlanes.add(plane_input)


def offset_yz_plane(component, x_offset):
    if abs(x_offset) < 1e-9:
        return component.yZConstructionPlane

    plane_input = component.constructionPlanes.createInput()
    plane_input.setByOffset(component.yZConstructionPlane, value(x_offset))
    return component.constructionPlanes.add(plane_input)


def largest_profile(sketch):
    best = None
    best_area = -1.0
    for index in range(sketch.profiles.count):
        profile = sketch.profiles.item(index)
        area = profile.areaProperties().area
        if area > best_area:
            best_area = area
            best = profile

    if best is None:
        raise RuntimeError("No closed sketch profile was created.")
    return best


def draw_closed_world_polygon(sketch, world_points):
    lines = sketch.sketchCurves.sketchLines
    local_points = [
        world_to_sketch_point(sketch, x, y, z)
        for x, y, z in world_points
    ]
    for index in range(len(local_points)):
        lines.addByTwoPoints(
            local_points[index],
            local_points[(index + 1) % len(local_points)],
        )


def draw_closed_polygon_xy(sketch, world_points, z_height):
    draw_closed_world_polygon(
        sketch,
        [(x, y, z_height) for x, y in world_points],
    )


def draw_rectangle(sketch, cx, cy, width, height, z_height):
    half_w = width / 2.0
    half_h = height / 2.0
    draw_closed_polygon_xy(
        sketch,
        (
            (cx - half_w, cy - half_h),
            (cx + half_w, cy - half_h),
            (cx + half_w, cy + half_h),
            (cx - half_w, cy + half_h),
        ),
        z_height,
    )


def draw_rounded_rectangle(sketch, cx, cy, width, height, radius, z_height):
    """Draw a closed rounded rectangle with four tangent quarter arcs."""
    radius = min(radius, width / 2.0 - 0.001, height / 2.0 - 0.001)
    if radius <= 0.0:
        raise ValueError("Rounded rectangle radius must be positive.")

    x0 = cx - width / 2.0
    x1 = cx + width / 2.0
    y0 = cy - height / 2.0
    y1 = cy + height / 2.0

    def local(world_x, world_y):
        return world_to_sketch_point(sketch, world_x, world_y, z_height)

    lines = sketch.sketchCurves.sketchLines
    arcs = sketch.sketchCurves.sketchArcs

    lines.addByTwoPoints(local(x0 + radius, y1), local(x1 - radius, y1))
    arcs.addByCenterStartSweep(
        local(x1 - radius, y1 - radius),
        local(x1 - radius, y1),
        -math.pi / 2.0,
    )
    lines.addByTwoPoints(local(x1, y1 - radius), local(x1, y0 + radius))
    arcs.addByCenterStartSweep(
        local(x1 - radius, y0 + radius),
        local(x1, y0 + radius),
        -math.pi / 2.0,
    )
    lines.addByTwoPoints(local(x1 - radius, y0), local(x0 + radius, y0))
    arcs.addByCenterStartSweep(
        local(x0 + radius, y0 + radius),
        local(x0 + radius, y0),
        -math.pi / 2.0,
    )
    lines.addByTwoPoints(local(x0, y0 + radius), local(x0, y1 - radius))
    arcs.addByCenterStartSweep(
        local(x0 + radius, y1 - radius),
        local(x0, y1 - radius),
        -math.pi / 2.0,
    )


def rounded_profile_at(component, z_height, cx, cy, width, height, radius):
    plane = offset_xy_plane(component, z_height)
    sketch = component.sketches.add(plane)
    draw_rounded_rectangle(sketch, cx, cy, width, height, radius, z_height)
    return largest_profile(sketch)


def rectangle_profile_at(component, z_height, cx, cy, width, height):
    plane = offset_xy_plane(component, z_height)
    sketch = component.sketches.add(plane)
    draw_rectangle(sketch, cx, cy, width, height, z_height)
    return largest_profile(sketch)


def world_polygon_profile(component, plane, world_points):
    sketch = component.sketches.add(plane)
    draw_closed_world_polygon(sketch, world_points)
    return largest_profile(sketch)


def circle_profile_at(component, z_height, cx, cy, diameter):
    plane = offset_xy_plane(component, z_height)
    sketch = component.sketches.add(plane)
    centre = world_to_sketch_point(sketch, cx, cy, z_height)
    sketch.sketchCurves.sketchCircles.addByCenterRadius(
        centre,
        diameter / 2.0,
    )
    return largest_profile(sketch)


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
    if feature.bodies.count < 1:
        raise RuntimeError("Extrusion did not create a body: {}".format(name))
    body = feature.bodies.item(0)
    body.name = name
    return body


def extrude_symmetric_new_body(component, profile, full_distance, name):
    extrudes = component.features.extrudeFeatures
    extrude_input = extrudes.createInput(
        profile,
        adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
    )
    if not extrude_input.setSymmetricExtent(value(full_distance), True):
        raise RuntimeError("Could not set symmetric extrusion: {}".format(name))
    feature = extrudes.add(extrude_input)
    if feature.bodies.count < 1:
        raise RuntimeError("Extrusion did not create a body: {}".format(name))
    body = feature.bodies.item(0)
    body.name = name
    return body


def extrude_text_cutters(component, sketch_text, full_distance, name):
    extrudes = component.features.extrudeFeatures
    extrude_input = extrudes.createInput(
        sketch_text,
        adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
    )
    if not extrude_input.setSymmetricExtent(value(full_distance), True):
        raise RuntimeError("Could not set text-cutter extrusion.")
    feature = extrudes.add(extrude_input)
    bodies = [feature.bodies.item(index) for index in range(feature.bodies.count)]
    if not bodies:
        raise RuntimeError("Text extrusion did not create cutter bodies.")
    for body in bodies:
        body.name = name
    return bodies


def loft_new_body(component, profiles, name):
    lofts = component.features.loftFeatures
    loft_input = lofts.createInput(
        adsk.fusion.FeatureOperations.NewBodyFeatureOperation
    )
    loft_input.isSolid = True
    for profile in profiles:
        loft_input.loftSections.add(profile)

    feature = lofts.add(loft_input)
    if feature.bodies.count < 1:
        raise RuntimeError("Loft did not create a body: {}".format(name))
    body = feature.bodies.item(0)
    body.name = name
    return body


def combine_body(component, target, tool, operation):
    tools = adsk.core.ObjectCollection.create()
    tools.add(tool)
    combine_input = component.features.combineFeatures.createInput(target, tools)
    combine_input.operation = operation
    combine_input.isKeepToolBodies = False
    component.features.combineFeatures.add(combine_input)
    return target


def join_body(component, target, tool):
    return combine_body(
        component,
        target,
        tool,
        adsk.fusion.FeatureOperations.JoinFeatureOperation,
    )


def cut_body(component, target, tool):
    return combine_body(
        component,
        target,
        tool,
        adsk.fusion.FeatureOperations.CutFeatureOperation,
    )


def delete_previous_generated_bodies(component):
    bodies_to_delete = []
    for index in range(component.bRepBodies.count):
        body = component.bRepBodies.item(index)
        if body.name.startswith(GENERATED_BODY_PREFIX):
            bodies_to_delete.append(body)

    for body in bodies_to_delete:
        body.deleteMe()


def delete_auxiliary_generated_bodies(component):
    bodies_to_delete = []
    for index in range(component.bRepBodies.count):
        body = component.bRepBodies.item(index)
        if (
            body.name.startswith(GENERATED_BODY_PREFIX)
            and body.name != FINAL_BODY_NAME
        ):
            bodies_to_delete.append(body)

    for body in bodies_to_delete:
        body.deleteMe()


def duct_end_z():
    return FLANGE_THICKNESS + DUCT_LENGTH


def duct_start_z():
    return FLANGE_THICKNESS - DUCT_JOIN_OVERLAP


def plenum_end_z():
    return FLANGE_THICKNESS + STRAIGHT_PLENUM_LENGTH


def outer_state_at_z(z_height):
    """Return centre Y, width, height, and radius at a duct station."""
    if z_height <= plenum_end_z():
        amount = 0.0
    else:
        transition = duct_end_z() - plenum_end_z()
        amount = smoothstep((z_height - plenum_end_z()) / transition)

    return (
        lerp(INLET_CENTRE_Y, OUTLET_CENTRE_Y, amount),
        lerp(INLET_WIDTH, OUTLET_WIDTH, amount),
        lerp(INLET_HEIGHT, OUTLET_HEIGHT, amount),
        lerp(INLET_CORNER_RADIUS, OUTLET_CORNER_RADIUS, amount),
    )


def duct_station_z_values(extra_at_end=0.0):
    transition = duct_end_z() - plenum_end_z()
    return (
        duct_start_z(),
        plenum_end_z(),
        plenum_end_z() + transition * 0.25,
        plenum_end_z() + transition * 0.75,
        duct_end_z() + extra_at_end,
    )


def duct_profiles(component, inner=False, extra_at_end=0.0):
    profiles = []
    for z_height in duct_station_z_values(extra_at_end):
        state_z = min(z_height, duct_end_z())
        centre_y, width, height, radius = outer_state_at_z(state_z)
        if inner:
            width -= 2.0 * DUCT_WALL
            height -= 2.0 * DUCT_WALL
            radius -= DUCT_WALL
        profiles.append(
            rounded_profile_at(
                component,
                z_height,
                0.0,
                centre_y,
                width,
                height,
                radius,
            )
        )
    return profiles


def add_speed_ribs(component, guide):
    start_centre, _, start_height, _ = outer_state_at_z(RIB_START_Z)
    end_centre, _, end_height, _ = outer_state_at_z(RIB_END_Z)
    start_bottom = start_centre - start_height / 2.0
    end_bottom = end_centre - end_height / 2.0

    for side in (-1.0, 1.0):
        plane_x = side * RIB_PLANE_X
        plane = offset_yz_plane(component, plane_x)
        for fraction in RIB_HEIGHT_FRACTIONS:
            start_y = start_bottom + fraction * start_height
            end_y = end_bottom + fraction * end_height
            profile = world_polygon_profile(
                component,
                plane,
                (
                    (plane_x, start_y - RIB_HEIGHT / 2.0, RIB_START_Z),
                    (plane_x, start_y + RIB_HEIGHT / 2.0, RIB_START_Z),
                    (plane_x, end_y + RIB_HEIGHT / 2.0, RIB_END_Z),
                    (plane_x, end_y - RIB_HEIGHT / 2.0, RIB_END_Z),
                ),
            )
            rib = extrude_symmetric_new_body(
                component,
                profile,
                RIB_TOTAL_DEPTH,
                "GPU Air Guide speed rib",
            )
            guide = join_body(component, guide, rib)
    return guide


def add_side_plaque(component, guide):
    x = PLAQUE_PLANE_X
    y0 = PLAQUE_Y_MIN
    y1 = PLAQUE_Y_MAX
    z0 = PLAQUE_Z_MIN
    z1 = PLAQUE_Z_MAX
    corner = PLAQUE_CHAMFER
    plane = offset_yz_plane(component, x)
    profile = world_polygon_profile(
        component,
        plane,
        (
            (x, y0, z0 + corner),
            (x, y0, z1 - corner),
            (x, y0 + corner, z1),
            (x, y1 - corner, z1),
            (x, y1, z1 - corner),
            (x, y1, z0 + corner),
            (x, y1 - corner, z0),
            (x, y0 + corner, z0),
        ),
    )
    plaque = extrude_symmetric_new_body(
        component,
        profile,
        PLAQUE_TOTAL_DEPTH,
        "GPU Air Guide equipment plaque",
    )
    return join_body(component, guide, plaque)


def add_recessed_plaque_text(component, guide):
    plane = offset_yz_plane(component, PLAQUE_OUTER_X)
    sketch = component.sketches.add(plane)
    text_specs = (
        ("DUAL GPU RAM-AIR", 4.42, 0.30, 2.05, 6.75),
        ("A1225M12S / 4.56 W", 3.52, 0.24, 2.20, 6.62),
        ("THERMAL MANAGEMENT UNIT", 2.68, 0.19, 2.30, 6.52),
    )

    sketch_texts = []
    for label, y_height, text_height, z0, z1 in text_specs:
        path = sketch.sketchCurves.sketchLines.addByTwoPoints(
            world_to_sketch_point(sketch, PLAQUE_OUTER_X, y_height, z0),
            world_to_sketch_point(sketch, PLAQUE_OUTER_X, y_height, z1),
        )
        path.isConstruction = True
        text_input = sketch.sketchTexts.createInput3(
            "'{}'".format(label),
            value(text_height),
        )
        text_input.fontName = "Arial"
        text_input.textStyle = adsk.fusion.TextStyles.TextStyleBold
        if not text_input.setAsFitOnPath(path, True):
            raise RuntimeError("Could not fit plaque text to its guide path.")
        sketch_text = sketch.sketchTexts.add(text_input)
        if not sketch_text:
            raise RuntimeError("Could not create plaque text.")
        sketch_texts.append(sketch_text)

    for sketch_text in sketch_texts:
        cutters = extrude_text_cutters(
            component,
            sketch_text,
            TEXT_RECESS_TOTAL_DEPTH,
            "GPU Air Guide text cutter",
        )
        for cutter in cutters:
            guide = cut_body(component, guide, cutter)
    return guide


def validate_parameters():
    hole_offset = FAN_HOLE_SPACING / 2.0
    hole_radius = MOUNT_HOLE_DIAMETER / 2.0
    outlet_bottom = OUTLET_CENTRE_Y - OUTLET_HEIGHT / 2.0
    inlet_inner_width = INLET_WIDTH - 2.0 * DUCT_WALL
    inlet_inner_height = INLET_HEIGHT - 2.0 * DUCT_WALL
    outlet_inner_width = OUTLET_WIDTH - 2.0 * DUCT_WALL
    outlet_inner_height = OUTLET_HEIGHT - 2.0 * DUCT_WALL

    if FAN_SIZE <= 0.0 or DUCT_LENGTH <= 0.0:
        raise ValueError("Fan size and duct length must be positive.")
    if FLANGE_THICKNESS < 0.20:
        raise ValueError("Flange should be at least 2 mm thick for PETG.")
    if DUCT_WALL < 0.16:
        raise ValueError("Duct wall should be at least 1.6 mm for a 0.4 mm nozzle.")
    if STRAIGHT_PLENUM_LENGTH <= 0.0 or STRAIGHT_PLENUM_LENGTH >= DUCT_LENGTH:
        raise ValueError("Straight plenum length must be inside the duct length.")
    if min(inlet_inner_width, inlet_inner_height) <= 0.0:
        raise ValueError("Inlet is too small for the selected wall thickness.")
    if min(outlet_inner_width, outlet_inner_height) <= 0.0:
        raise ValueError("Outlet is too small for the selected wall thickness.")
    if outlet_bottom < -0.001:
        raise ValueError("Main outlet extends below the middle/lower fan seam.")
    if GPU_GAP_CENTRE_ABOVE_SEAM < outlet_bottom:
        raise ValueError("Measured GPU gap falls below the outlet.")
    if GPU_GAP_CENTRE_ABOVE_SEAM > OUTLET_CENTRE_Y + OUTLET_HEIGHT / 2.0:
        raise ValueError("Measured GPU gap falls above the outlet.")
    if INLET_WIDTH > FAN_SIZE or INLET_HEIGHT > FAN_SIZE:
        raise ValueError("Inlet must fit inside the 120 mm fan flange.")
    if hole_offset + hole_radius > FAN_SIZE / 2.0:
        raise ValueError("Fan mounting holes fall outside the flange.")
    if min(INLET_CORNER_RADIUS, OUTLET_CORNER_RADIUS) <= DUCT_WALL:
        raise ValueError("Outside corner radii must exceed duct wall thickness.")
    if OUTLET_LIP_WIDTH > FAN_SIZE:
        raise ValueError("Outlet lip is wider than the fan flange.")
    if PLAQUE_OUTER_X > FAN_SIZE / 2.0:
        raise ValueError("Equipment plaque extends beyond the fan flange width.")
    if RIB_PLANE_X + RIB_TOTAL_DEPTH / 2.0 > FAN_SIZE / 2.0:
        raise ValueError("Speed ribs extend beyond the fan flange width.")


def build_air_guide(component):
    """
    Coordinate system with the flange flat on the print bed:

      X across the fan, Y upward from the middle/lower fan seam,
      and Z from the front fan toward the GPUs.
    """
    warnings = []

    flange_profile = rectangle_profile_at(
        component,
        0.0,
        0.0,
        FAN_SIZE / 2.0,
        FAN_SIZE,
        FAN_SIZE,
    )
    guide = extrude_new_body(
        component,
        flange_profile,
        FLANGE_THICKNESS,
        "GPU Air Guide flange",
    )

    outer_duct = loft_new_body(
        component,
        duct_profiles(component),
        "GPU Air Guide outer duct",
    )
    guide = join_body(component, guide, outer_duct)

    lip_profiles = (
        rounded_profile_at(
            component,
            duct_end_z() - OUTLET_LIP_START,
            0.0,
            OUTLET_CENTRE_Y,
            OUTLET_WIDTH,
            OUTLET_HEIGHT,
            OUTLET_CORNER_RADIUS,
        ),
        rounded_profile_at(
            component,
            duct_end_z() - OUTLET_LIP_START / 2.0,
            0.0,
            OUTLET_CENTRE_Y,
            OUTLET_LIP_WIDTH,
            OUTLET_LIP_HEIGHT,
            OUTLET_LIP_CORNER_RADIUS,
        ),
        rounded_profile_at(
            component,
            duct_end_z(),
            0.0,
            OUTLET_CENTRE_Y,
            OUTLET_LIP_WIDTH,
            OUTLET_LIP_HEIGHT,
            OUTLET_LIP_CORNER_RADIUS,
        ),
    )
    outlet_lip = loft_new_body(
        component,
        lip_profiles,
        "GPU Air Guide outlet lip",
    )
    guide = join_body(component, guide, outlet_lip)

    try:
        guide = add_speed_ribs(component, guide)
    except Exception as error:
        warnings.append("Speed ribs skipped: {}".format(error))

    plaque_added = False
    try:
        guide = add_side_plaque(component, guide)
        plaque_added = True
    except Exception as error:
        warnings.append("Equipment plaque skipped: {}".format(error))

    inner_duct = loft_new_body(
        component,
        duct_profiles(component, inner=True, extra_at_end=CUT_OVERTRAVEL),
        "GPU Air Guide inner duct cutter",
    )
    guide = cut_body(component, guide, inner_duct)

    inner_inlet_width = INLET_WIDTH - 2.0 * DUCT_WALL
    inner_inlet_height = INLET_HEIGHT - 2.0 * DUCT_WALL
    inlet_opening_profile = rounded_profile_at(
        component,
        0.0,
        0.0,
        INLET_CENTRE_Y,
        inner_inlet_width,
        inner_inlet_height,
        INLET_CORNER_RADIUS - DUCT_WALL,
    )
    inlet_opening = extrude_new_body(
        component,
        inlet_opening_profile,
        CUT_DEPTH,
        "GPU Air Guide inlet cutter",
    )
    guide = cut_body(component, guide, inlet_opening)

    fan_centre_y = FAN_SIZE / 2.0
    hole_offset = FAN_HOLE_SPACING / 2.0
    for hole_x in (-hole_offset, hole_offset):
        for hole_y in (fan_centre_y - hole_offset, fan_centre_y + hole_offset):
            hole_profile = circle_profile_at(
                component,
                0.0,
                hole_x,
                hole_y,
                MOUNT_HOLE_DIAMETER,
            )
            hole_cutter = extrude_new_body(
                component,
                hole_profile,
                CUT_DEPTH,
                "GPU Air Guide mounting-hole cutter",
            )
            guide = cut_body(component, guide, hole_cutter)

    for slot_x in (-ZIP_SLOT_X, ZIP_SLOT_X):
        for slot_y in ZIP_SLOT_Y_POSITIONS:
            slot_profile = rectangle_profile_at(
                component,
                0.0,
                slot_x,
                slot_y,
                ZIP_SLOT_WIDTH,
                ZIP_SLOT_HEIGHT,
            )
            slot_cutter = extrude_new_body(
                component,
                slot_profile,
                CUT_DEPTH,
                "GPU Air Guide zip-slot cutter",
            )
            guide = cut_body(component, guide, slot_cutter)

    if plaque_added:
        try:
            guide = add_recessed_plaque_text(component, guide)
        except Exception as error:
            warnings.append("Recessed plaque lettering skipped: {}".format(error))

    guide.name = FINAL_BODY_NAME
    delete_auxiliary_generated_bodies(component)
    return guide, warnings


def run(context):
    app = adsk.core.Application.get()
    ui = app.userInterface

    try:
        design = adsk.fusion.Design.cast(app.activeProduct)
        if not design:
            ui.messageBox("No active Fusion design. Create or open a design first.")
            return

        validate_parameters()
        component = design.rootComponent
        delete_previous_generated_bodies(component)
        _, warnings = build_air_guide(component)
        app.activeViewport.fit()

        warning_text = ""
        if warnings:
            warning_text = "\n\nStyling notes:\n- " + "\n- ".join(warnings)

        ui.messageBox(
            "Created full-face dual-GPU ram-air guide.\n\n"
            "Fan frame: {:.0f} mm\n"
            "Mounting holes: 4 x {:.1f} mm on {:.0f} mm centres\n"
            "Duct extension: {:.0f} mm\n"
            "Outside inlet: {:.0f} x {:.0f} mm\n"
            "Outside outlet: {:.0f} x {:.0f} mm\n"
            "Outlet span: seam to +{:.0f} mm\n"
            "Measured GPU gap centre: +{:.0f} mm\n"
            "Wall / flange: {:.1f} / {:.1f} mm\n"
            "Fallback zip-tie slots: 4\n\n"
            "Print with the flat fan flange on the build plate. "
            "PETG and no supports are intended.{}"
            .format(
                mm(FAN_SIZE),
                mm(MOUNT_HOLE_DIAMETER),
                mm(FAN_HOLE_SPACING),
                mm(DUCT_LENGTH),
                mm(INLET_WIDTH),
                mm(INLET_HEIGHT),
                mm(OUTLET_WIDTH),
                mm(OUTLET_HEIGHT),
                mm(OUTLET_HEIGHT),
                mm(GPU_GAP_CENTRE_ABOVE_SEAM),
                mm(DUCT_WALL),
                mm(FLANGE_THICKNESS),
                warning_text,
            )
        )

    except Exception:
        if ui:
            ui.messageBox("Script failed:\n{}".format(traceback.format_exc()))
