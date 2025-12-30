bl_info = {
    "name": "Auto-Hide Backfaces",
    "author": "LunaMoca",
    "version": (0, 5, 0),
    "blender": (5, 0, 0),
    "location": "View3D > Tool",
    "description": "Continuously hide backfaces in Edit Mode relative to view direction, intended only for interiors using flipped normals",
    "category": "3D View",
}

import bpy
import bmesh
from mathutils import Vector

# -----------------------------
# Globals
# -----------------------------
_hidden_faces_cache = {}
_timer_interval = 0.05  # ~20 Hz update

# -----------------------------
# Utilities
# -----------------------------
def get_view_direction(context):
    """Return view direction in world space for active 3D view."""
    for area in context.screen.areas:
        if area.type == 'VIEW_3D':
            for region in area.regions:
                if region.type == 'WINDOW':
                    rv3d = region.data if hasattr(region, "data") else area.spaces.active.region_3d
                    if rv3d:
                        return rv3d.view_rotation @ Vector((0, 0, -1)), rv3d
    return None, None

def update_backfaces(obj, context, debug=False):
    """Hide/show faces depending on view direction."""
    if context.mode != 'EDIT_MESH' or obj is None:
        return

    mesh = obj.data
    bm = bmesh.from_edit_mesh(mesh)

    view_dir, rv3d = get_view_direction(context)
    if view_dir is None:
        return

    normal_matrix = obj.matrix_world.to_3x3()
    hidden_faces = _hidden_faces_cache.get(obj.name, set())
    new_hidden = set()

    changed = False

    for face in bm.faces:
        face_world_normal = normal_matrix @ face.normal
        is_backface = face_world_normal.dot(view_dir) > 0
        if is_backface and not face.hide:
            face.hide = True
            new_hidden.add(face.index)
            changed = True
        elif not is_backface and face.hide:
            face.hide = False
            changed = True
        elif is_backface:
            new_hidden.add(face.index)

    if changed:
        bmesh.update_edit_mesh(mesh, loop_triangles=False, destructive=False)
        _hidden_faces_cache[obj.name] = new_hidden
        if debug:
            print(f"[DEBUG] Updated backfaces for {obj.name}: hidden {len(new_hidden)} faces")

# -----------------------------
# Modal Operator
# -----------------------------
class VIEW3D_OT_auto_hide_backface_modal(bpy.types.Operator):
    bl_idname = "view3d.auto_hide_backface_modal"
    bl_label = "Auto Hide Backface Modal"

    _timer = None

    def modal(self, context, event):
        if not context.scene.auto_hide_backfaces_enabled:
            self.cancel(context)
            return {'CANCELLED'}

        if event.type == 'TIMER':
            for obj in context.editable_objects:
                if obj.type == 'MESH':
                    update_backfaces(obj, context, context.scene.auto_hide_backfaces_debug)

        return {'PASS_THROUGH'}

    def execute(self, context):
        wm = context.window_manager
        self._timer = wm.event_timer_add(_timer_interval, window=context.window)
        wm.modal_handler_add(self)
        if context.scene.auto_hide_backfaces_debug:
            print("[DEBUG] Auto-Hide Backface Modal started")
        return {'RUNNING_MODAL'}

    def cancel(self, context):
        wm = context.window_manager
        if self._timer:
            wm.event_timer_remove(self._timer)
        # Restore all hidden faces
        for obj_name, indices in _hidden_faces_cache.items():
            obj = context.scene.objects.get(obj_name)
            if obj and obj.type == 'MESH':
                bm = bmesh.from_edit_mesh(obj.data)
                for idx in indices:
                    if idx < len(bm.faces):
                        bm.faces[idx].hide = False
                bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)
        _hidden_faces_cache.clear()
        if context.scene.auto_hide_backfaces_debug:
            print("[DEBUG] Auto-Hide Backface Modal stopped")

# -----------------------------
# UI Panel
# -----------------------------
class VIEW3D_PT_auto_hide_backface_panel(bpy.types.Panel):
    bl_label = "Continuous Backface Hide"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Tool'

    def draw(self, context):
        layout = self.layout
        layout.prop(context.scene, "auto_hide_backfaces_enabled")
        layout.prop(context.scene, "auto_hide_backfaces_debug")

def toggle_modal(self, context):
    if context.scene.auto_hide_backfaces_enabled:
        bpy.ops.view3d.auto_hide_backface_modal('INVOKE_DEFAULT')

# -----------------------------
# Registration
# -----------------------------
def register():
    bpy.types.Scene.auto_hide_backfaces_enabled = bpy.props.BoolProperty(
        name="Enable Auto-Hide Backfaces",
        default=False,
        update=toggle_modal
    )
    bpy.types.Scene.auto_hide_backfaces_debug = bpy.props.BoolProperty(
        name="Enable Debug Printing",
        default=False
    )

    bpy.utils.register_class(VIEW3D_OT_auto_hide_backface_modal)
    bpy.utils.register_class(VIEW3D_PT_auto_hide_backface_panel)

def unregister():
    bpy.utils.unregister_class(VIEW3D_PT_auto_hide_backface_panel)
    bpy.utils.unregister_class(VIEW3D_OT_auto_hide_backface_modal)

    del bpy.types.Scene.auto_hide_backfaces_enabled
    del bpy.types.Scene.auto_hide_backfaces_debug

if __name__ == "__main__":
    register()
