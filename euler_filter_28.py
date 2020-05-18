import bpy
from math import pi, radians, degerees
from mathutils import Euler
import itertools

bl_info = {
    "name": "Euler Filter",
    "author": "Manuel Odendahl, Artell",
    "version": (0, 2),
    "blender": (2, 80, 0),
    "location": "Search > Euler Filter",
    "description": "Euler Filter",
    "warning": "",
    "wiki_url": "http://",
    "tracker_url": "https://",
    "category": "Animation"
}

# not used?
def get_fcu_keyframe_numbers(fcu):
    return sorted([p.co[0] for p in fcu.keyframe_points])


def get_selected_fcu_keyframe_numbers(fcu):
    return sorted([p.co[0] for p in fcu.keyframe_points if p.select_control_point])


# not used?
def update_euler_keyframes(bone, keyframes):
    for kf in keyframes:
        bone.rotation_euler = kf["rotation_euler"]
        bone.keyframe_insert(data_path='rotation_euler', frame=kf["key"])


# actual euler filter
# not used ?
def euler_to_string(e):
    return "%.2f, %.2f, %.2f" % (radians(e[0]), radians(e[1]), radians(e[2]))


# not used?
def wrap_angle(a):
    return (a + pi) % (2 * pi) - pi


def euler_distance(e1, e2):
    return abs(e1[0] - e2[0]) + abs(e1[1] - e2[1]) + abs(e1[2] - e2[2])


def euler_axis_index(axis):
    if axis == 'X':
        return 0
    if axis == 'Y':
        return 1
    if axis == 'Z':
        return 2
    return None


def flip_euler(euler, rotation_mode):
    ret = euler.copy()
    inner_axis = rotation_mode[0]
    middle_axis = rotation_mode[1]
    outer_axis = rotation_mode[2]

    ret[euler_axis_index(inner_axis)] += pi
    ret[euler_axis_index(outer_axis)] += pi
    ret[euler_axis_index(middle_axis)] *= -1
    ret[euler_axis_index(middle_axis)] += pi
    return ret


def naive_flip_diff(a1, a2):
    while abs(a1 - a2) > pi:
        if a1 < a2:
            a2 -= 2 * pi
        else:
            a2 += 2 * pi

    return a2


def euler_filter(kfs, rotation_mode):
    if len(kfs) <= 1:
        return kfs
    prev = kfs[0]["rotation_euler"]
    ret = [{"key": kfs[0]["key"],
            "rotation_euler": prev.copy()}]
    for i in range(1, len(kfs)):
        e = kfs[i]["rotation_euler"].copy()
        e[0] = naive_flip_diff(prev[0], e[0])
        e[1] = naive_flip_diff(prev[1], e[1])
        e[2] = naive_flip_diff(prev[2], e[2])

        fe = flip_euler(e, rotation_mode)
        fe[0] = naive_flip_diff(prev[0], fe[0])
        fe[1] = naive_flip_diff(prev[1], fe[1])
        fe[2] = naive_flip_diff(prev[2], fe[2])

        de = euler_distance(prev, e)
        dfe = euler_distance(prev, fe)
        # print("distance: %s, flipped distance: %s" % (de, dfe))

        if dfe < de:
            e = fe
        prev = e
        ret += [{"key": kfs[i]["key"],
                 "rotation_euler": e}]
    return ret


#################################################
# keyframes / fcurves helpers

def split_data_path(data_path):
    """
    :param data_path: an FCurve data path
    :return: object path, property
    """
    return data_path.rsplit(".", 1)


# XXX when needed for rotation_mode
def get_bone_from_fcurve(obj, fcurve):
    """
    Resolve the path of a bone from the data_path of an fcurve
    :param obj: object the action belongs to (to resolve the fcurve data_path)
    :param fcurve: the fcurve
    :return: the resolved bone
    """
    if len(split_data_path(fcurve.data_path)) > 1:  # bone case
        bone, prop = split_data_path(fcurve.data_path)
    else:  # object case
        return obj
    return obj.path_resolve(bone)


def get_selected_rotation_fcurves(context):
    """
    Returns the selected rotation euler curves.
    This checks that 3 curves for the same bone with property "rotation_euler" are selected,
    and that their array_index cover 0, 1, 2.
    :param context:
    :return: fcurves, error_string
    """
    obj = context.active_object
    if not obj:
        return None, "No object selected"
    if not obj.animation_data:
        return None, "Object have no animation data"
    if not obj.animation_data.action:
        return None, "Object has no action"
    fcurves = obj.animation_data.action.fcurves

    selected_fcurves = []
    selected_bone = None

    for fc in fcurves:
        if not fc.select:
            continue

        if len(split_data_path(fc.data_path)) > 1:  # bones animation
            bone, prop = split_data_path(fc.data_path)

            if bone != 'pose.bones["' + bpy.context.active_pose_bone.name + '"]':
                continue

            if prop != "rotation_euler":
                continue

            if not selected_bone:
                selected_bone = bone
            print("selected bone", selected_bone)
            if bone != selected_bone:
                return None, "Only select the rotation of a single object"

        else:  # object animation
            prop = fc.data_path
            if prop != "rotation_euler":
                continue

        selected_fcurves.append(fc)

    if len(selected_fcurves) != 3:
        return None, "Select only XYZ rotation curves"

    selected_fcurves = sorted(selected_fcurves, key=lambda fcu: fcu.array_index)
    for i in range(3):
        if selected_fcurves[i].array_index != i:
            return None, "Wrong index for rotation curves, selected all 3 angles"

    return selected_fcurves, None


def get_euler_fcurves(obj, *args):
    """
    Returns the rotation euler curves from an object, if x,y,z euler curves found
    *args expects pose bone
    """
    obj = bpy.context.object

    if not obj.animation_data:
        return None, "Object has no animation data"
    if not obj.animation_data.action:
        return None, "Object has no action"

    obj_fcurves = obj.animation_data.action.fcurves
    fcurves = []

    if args and obj.type == 'ARMATURE' and bpy.context.mode == 'POSE':
        pbone = arg[0]
        path = pbone.path_from_id()
        x_fcurve = obj_fcurves.find(f"{path}.rotation_euler", index=0)
        y_fcurve = obj_fcurves.find(f"{path}.rotation_euler", index=1)
        z_fcurve = obj_fcurves.find(f"{path}.rotation_euler", index=2)

    else:
        x_fcurve = obj_fcurves.find('rotation_euler', index=0)
        y_fcurve = obj_fcurves.find('rotation_euler', index=1)
        z_fcurve = obj_fcurves.find('rotation_euler', index=2)

    if not x_fcurve or not y_fcurve or not z_fcurve:
        self.report({'INFO'}, "XYZ Euler data not found")

    else:
        fcurves = [x_fcurve, y_fcurve, z_fcurve]

    return selected_fcurves, None


def get_selected_rotation_keyframes(context):
    """
    Returns the selected rotation keyframes.
    The keyframes are in the format {"key": frame, "rotation_euler": Euler}.
    If there is an error, keyframes, fcurves will be None, and error_string will be set to a descriptive string.
    :param context:
    :return: keyframes, fcurves, error_string
    """
    fcurves, error = get_selected_rotation_fcurves(context)
    if not fcurves or len(fcurves) != 3:
        return None, None, error

    fcu_keyframes = [get_selected_fcu_keyframe_numbers(fcu) for fcu in fcurves]
    if fcu_keyframes[0] != fcu_keyframes[1] or fcu_keyframes[1] != fcu_keyframes[2]:
        # XXX warn
        print("All 3 rotation angles need to be keyframed together")
        return None, None, "All 3 rotation angles need to be keyframed together on every keyframe"

    keyframes = sorted(set(itertools.chain.from_iterable([get_selected_fcu_keyframe_numbers(fcu) for fcu in fcurves])))

    res = []
    for keyframe in keyframes:
        euler = Euler([fcurve.evaluate(keyframe) for fcurve in fcurves], 'XYZ')
        res += [{
            "key": keyframe,
            "rotation_euler": euler,
        }]

    return res, fcurves, None


def run_filter(obj):
    kfs, fcus, error = get_selected_rotation_keyframes(context)
    if not kfs:
        self.report({'ERROR'}, error)
        return {'CANCELLED'}

    bone = get_bone_from_fcurve(context.active_object, fcus[0])

    efs = euler_filter(kfs, bone.rotation_mode)

    for i in range(len(efs)):
        e = efs[i]["rotation_euler"]
        frame = efs[i]["key"]
        # p = kfs[i]["rotation_euler"]
        # print("%s -> %s" % (euler_to_string(p), euler_to_string(e)))
        for i in range(3):
            fcus[i].keyframe_points.insert(frame=frame, value=e[i])

        fcu[i].update()

    return {'FINISHED'}


class GRAPH_OT_EulerFilter(bpy.types.Operator):
    bl_idname = "graph.euler_filter"
    bl_label = "Euler Filter"
    bl_description = "Filter euler rotations to remove danger of gimbal lock"
    bl_options = {'REGISTER', 'UNDO'}
    bl_space_type = 'GRAPH_EDITOR'
    bl_region_type = 'UI'

    @classmethod
    def poll(cls, context):
        fcus = get_euler_fcurves(obj, bone)
        return fcus

    def execute(self, context):
        kfs, fcus, error = get_selected_rotation_keyframes(context)
        if not kfs:
            self.report({'ERROR'}, error)
            return {'CANCELLED'}

        bone = get_bone_from_fcurve(context.active_object, fcus[0])

        efs = euler_filter(kfs, bone.rotation_mode)

        for i in range(len(efs)):
            e = efs[i]["rotation_euler"]
            frame = efs[i]["key"]
            # p = kfs[i]["rotation_euler"]
            # print("%s -> %s" % (euler_to_string(p), euler_to_string(e)))
            for i in range(3):
                fcus[i].keyframe_points.insert(frame=frame, value=e[i])

            fcu[i].update()

        return {'FINISHED'}


def register():
    from bpy.utils import register_class

    register_class(GRAPH_OT_EulerFilter)


def unregister():
    from bpy.utils import unregister_class

    unregister_class(GRAPH_OT_EulerFilter)


if __name__ == "__main__":
    register()
