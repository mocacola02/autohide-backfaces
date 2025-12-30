'''
Auto-Hide Backfaces - Automatic backface hider for Blender 5
Copyright (C) 2025 LunaMoca

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
'''

import bpy
import bmesh
from mathutils import Vector

# -----------------------------
# Globals
# -----------------------------
# Cache to track hidden faces per object to avoid redundant updates
_hidden_faces_cache = {}
# Timer interval in seconds for modal operator updates
_timer_interval = 0.05

# -----------------------------
# Utilities
# -----------------------------
def get_view_direction(context):
    """Return view direction in world space for active 3D view."""
    # Iterate over areas in the current screen
    for area in context.screen.areas:
        # Only consider 3D View areas
        if area.type == 'VIEW_3D':
            # Iterate regions to find window region
            for region in area.regions:
                if region.type == 'WINDOW':
                    # Get the region 3D data (view rotation)
                    rv3d = region.data if hasattr(region, "data") else area.spaces.active.region_3d
                    if rv3d:
                        # Return view direction as a vector and the region data
                        return rv3d.view_rotation @ Vector((0, 0, -1)), rv3d
    # Return None if no view direction could be determined
    return None, None

def update_backfaces(obj, context, debug=False):
    """Hide/show faces depending on view direction."""
    # Only operate in edit mode on mesh objects
    if context.mode != 'EDIT_MESH' or obj is None:
        return

    mesh = obj.data
    bm = bmesh.from_edit_mesh(mesh)

    # Get current view direction
    view_dir, rv3d = get_view_direction(context)
    if view_dir is None:
        return

    # Compute normal transformation to world space
    normal_matrix = obj.matrix_world.to_3x3()
    # Retrieve previously hidden faces from cache
    hidden_faces = _hidden_faces_cache.get(obj.name, set())
    new_hidden = set()

    changed = False

    # Iterate over all faces
    for face in bm.faces:
        # Transform face normal to world space
        face_world_normal = normal_matrix @ face.normal
        # Determine if face is backfacing relative to view
        is_backface = face_world_normal.dot(view_dir) > 0
        # Hide or unhide faces based on backface status
        if is_backface and not face.hide:
            face.hide = True
            new_hidden.add(face.index)
            changed = True
        elif not is_backface and face.hide:
            face.hide = False
            changed = True
        elif is_backface:
            new_hidden.add(face.index)

    # Update mesh if any changes occurred
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

    # -----------------------------
    # Modal event loop
    # -----------------------------
    def modal(self, context, event):
        # Stop modal if feature is disabled
        if not context.scene.auto_hide_backfaces_enabled:
            self.cancel(context)
            return {'CANCELLED'}

        # Update hidden faces on timer events
        if event.type == 'TIMER':
            for obj in context.editable_objects:
                if obj.type == 'MESH':
                    update_backfaces(obj, context, context.scene.auto_hide_backfaces_debug)

        return {'PASS_THROUGH'}

    # -----------------------------
    # Start the modal operator
    # -----------------------------
    def execute(self, context):
        wm = context.window_manager
        # Add a repeating timer
        # I'm not really a big fan of this timer setup, I need to learn more about Blender to implement a more optimized approach
        self._timer = wm.event_timer_add(_timer_interval, window=context.window)
        wm.modal_handler_add(self)
        if context.scene.auto_hide_backfaces_debug:
            print("[DEBUG] Auto-Hide Backface Modal started")
        return {'RUNNING_MODAL'}

    # -----------------------------
    # Cancel and cleanup
    # -----------------------------
    def cancel(self, context):
        wm = context.window_manager
        # Remove the timer
        if self._timer:
            wm.event_timer_remove(self._timer)
        # Unhide all previously hidden faces
        for obj_name, indices in _hidden_faces_cache.items():
            obj = context.scene.objects.get(obj_name)
            if obj and obj.type == 'MESH':
                bm = bmesh.from_edit_mesh(obj.data)
                for idx in indices:
                    if idx < len(bm.faces):
                        bm.faces[idx].hide = False
                bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)
        # Clear cache
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
        # Checkbox to enable/disable auto hide
        layout.prop(context.scene, "auto_hide_backfaces_enabled")
        # Checkbox to enable debug print statements
        layout.prop(context.scene, "auto_hide_backfaces_debug")

# Callback to start modal when enabling feature
def toggle_modal(self, context):
    if context.scene.auto_hide_backfaces_enabled:
        bpy.ops.view3d.auto_hide_backface_modal('INVOKE_DEFAULT')

# -----------------------------
# Registration
# -----------------------------
def register():
    # Scene property to enable/disable auto hide
    bpy.types.Scene.auto_hide_backfaces_enabled = bpy.props.BoolProperty(
        name="Enable Auto-Hide Backfaces",
        default=False,
        update=toggle_modal
    )
    # Scene property to enable debug printing
    bpy.types.Scene.auto_hide_backfaces_debug = bpy.props.BoolProperty(
        name="Enable Debug Printing",
        default=False
    )

    # Register operator and panel
    bpy.utils.register_class(VIEW3D_OT_auto_hide_backface_modal)
    bpy.utils.register_class(VIEW3D_PT_auto_hide_backface_panel)

def unregister():
    # Unregister panel and operator
    bpy.utils.unregister_class(VIEW3D_PT_auto_hide_backface_panel)
    bpy.utils.unregister_class(VIEW3D_OT_auto_hide_backface_modal)

    # Remove scene properties
    del bpy.types.Scene.auto_hide_backfaces_enabled
    del bpy.types.Scene.auto_hide_backfaces_debug

# Run script
if __name__ == "__main__":
    register()
