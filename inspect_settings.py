import bpy
import sys

def inspect_render_settings(file_path):
    bpy.ops.wm.open_mainfile(filepath=file_path)
    scene = bpy.context.scene
    
    print(f"\n--- Render Settings in {file_path} ---")
    print(f"Engine: {scene.render.engine}")
    print(f"Resolution: {scene.render.resolution_x} x {scene.render.resolution_y} ({scene.render.resolution_percentage}%)")
    print(f"Frame Range: {scene.frame_start} - {scene.frame_end}")
    print(f"FPS: {scene.render.fps}")
    
    # Color Management
    if hasattr(scene.view_settings, 'view_transform'):
        print(f"View Transform: {scene.view_settings.view_transform}")
    if hasattr(scene.view_settings, 'look'):
        print(f"Look: {scene.view_settings.look}")
    if hasattr(scene.view_settings, 'exposure'):
        print(f"Exposure: {scene.view_settings.exposure}")
        
    # Output
    print(f"File Format: {scene.render.image_settings.file_format}")
    if hasattr(scene.render, 'ffmpeg'):
        print(f"FFmpeg Format: {scene.render.ffmpeg.format}")
        print(f"FFmpeg Codec: {scene.render.ffmpeg.codec}")

if __name__ == "__main__":
    args = sys.argv
    if "--" in args:
        file_path = args[args.index("--") + 1]
        inspect_render_settings(file_path)
