
bl_info = {
    "name": "Import Valve VMF",
    "description": "Imports Valve Map Format files into Blender.",
    "author": "Jon Ross",
    "version": (0, 1, 0),
    "blender": (2, 80, 0),
    "location": "File > Import > Valve VMF (.vmf)",
    "warning": "Alpha version. Ping ZLSA#3222 on Discord.",
    "support": "COMMUNITY",
    "category": "Import/Export"
}

from bpy_extras.io_utils import ImportHelper 
from bpy.props import StringProperty, EnumProperty, FloatProperty
from bpy.types import Operator
import bpy

class ImportVMF(Operator, ImportHelper):
    """Import VMF"""
    bl_idname = "io.import_vmf"
    bl_label = "Import VMF"

    filename_ext: ".vmf"
    
    filter_glob: StringProperty(
            default="*.vmf",
    )

    scale_enum: EnumProperty(
        name="Scale",
        items=(
            ("1", "Default (1:1)", "One hammer unit is one meter."),
            ("12", "CS:GO (12:1)", "Twelve hammer units to one meter. (Used by Counter-Strike: Global Offensive)"),
            ("14", "TF2 (145:1)", "Fourteen hammer units to one meter. (Used by Team Fortress 2)"),
            ("0", "Other", "Set a custom scale"),
        ),
        description="Import scale",
    )

    scale_value: FloatProperty(
        name="Scale",
        min=0, max=1000,
        default=1.0
    )
    
    def draw(self, context):
        layout = self.layout

        layout.prop(self, "scale_enum")

        if self.scale_enum == "0":
            layout.prop(self, "scale_value")
    
    def execute(self, context):
        keywords = self.as_keywords(ignore=("filter_glob", "directory"))

        # Above, the key is defined as a string containing an int value.
        scale = int(self.scale_enum)

        # If we're using 'Other', actually use the 'other' value.
        if scale == 0:
            scale = self.scale_value

        from . import import_vmf

        # Force update
        import importlib
        importlib.reload(import_vmf)
        
        return import_vmf.load(self, context, filename=self.filepath, options={
            "scale": scale
        })
    
def menu_func(self, context): 
    self.layout.operator(ImportVMF.bl_idname, text="Valve VMF (.vmf)") 
    
def register():
    bpy.utils.register_class(ImportVMF)
    bpy.types.TOPBAR_MT_file_import.append(menu_func)

def unregister():
    bpy.utils.unregister_class(ImportVMF)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func)
