"""Run on a local machine with Blender installed. Example:
blender --background --python make_blend.py -- inspection
This script is optional; direct glTF import works without it.
"""
import bpy
import sys
from pathlib import Path
p=Path(__file__).resolve().parent
variant=sys.argv[sys.argv.index('--')+1] if '--' in sys.argv and len(sys.argv)>sys.argv.index('--')+1 else 'inspection'
if variant not in ('assembled','inspection','backplate','tray'):
    raise ValueError('Unknown variant')
source=p/f'AFP_FE_Node_Rev0_2_{variant}.glb'
# Factory reset removes default objects (run in a new/background instance).
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(source))
scene=bpy.context.scene
scene.unit_settings.system='METRIC'
scene.unit_settings.scale_length=1.0
scene.unit_settings.length_unit='MILLIMETERS'
for area in bpy.context.screen.areas if bpy.context.screen else []:
    if area.type=='VIEW_3D':
        area.spaces.active.shading.color_type='MATERIAL'
bpy.ops.wm.save_as_mainfile(filepath=str(source.with_suffix('.blend')))
