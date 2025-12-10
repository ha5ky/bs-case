import bpy
import sys
import argparse
import os
import math
from mathutils import Vector

def reset_scene():
    """清除场景中的所有对象，但保留 World 设置以防万一（虽然我们会覆盖）"""
    bpy.ops.wm.read_factory_settings(use_empty=True)

def setup_camera(scene, target_center, target_size):
    """设置摄像机，使其自动适配目标物体的大小和位置"""
    # 计算相机位置：在目标中心的前方 (平视)
    # 距离取决于物体大小
    cam_dist = target_size * 2.0
    
    # 平视视角：Z轴高度与目标中心一致
    # 之前是 target_size * 0.5 导致了俯视
    cam_pos = target_center + Vector((0, -cam_dist, 0))
    
    bpy.ops.object.camera_add(location=cam_pos)
    camera = bpy.context.object
    scene.camera = camera
    
    # 添加 Track To 约束，让相机始终看向物体中心
    bpy.ops.object.constraint_add(type='TRACK_TO')
    camera.constraints["Track To"].target = bpy.data.objects.get("CardParent")
    camera.constraints["Track To"].track_axis = 'TRACK_NEGATIVE_Z'
    camera.constraints["Track To"].up_axis = 'UP_Y'
    
    # 调整焦距 - 使用更长的焦距减少透视变形，看起来更像"平视"
    camera.data.lens = 85
    
    return camera

def setup_lighting(center, size):
    """设置类似 Viewport 的基础环境光和三点布光"""
    # 1. 设置世界环境光 (World Environment)
    world = bpy.context.scene.world
    if not world:
        world = bpy.data.worlds.new("World")
        bpy.context.scene.world = world
    
    world.use_nodes = True
    bg_node = world.node_tree.nodes.get('Background')
    if not bg_node:
        bg_node = world.node_tree.nodes.new('ShaderNodeBackground')
        
    # 设置为中性灰，模拟 Viewport
    bg_node.inputs[0].default_value = (0.4, 0.4, 0.4, 1) # Color
    bg_node.inputs[1].default_value = 1.0 # Strength
    
    # 2. 三点布光 (相对于物体中心)
    # 主光 (Key Light)
    key_pos = center + Vector((size, -size, size))
    bpy.ops.object.light_add(type='SUN', location=key_pos)
    key_light = bpy.context.object
    key_light.data.energy = 5.0 # Sun light intensity is different from Point
    key_light.rotation_euler = (math.radians(45), 0, math.radians(45))
    
    # 补光 (Fill Light) - 柔和一点
    fill_pos = center + Vector((-size, -size, size*0.5))
    bpy.ops.object.light_add(type='AREA', location=fill_pos)
    fill_light = bpy.context.object
    fill_light.data.energy = 300.0
    fill_light.data.size = size * 2
    # 让补光指向中心
    track = fill_light.constraints.new(type='TRACK_TO')
    track.target = bpy.data.objects.get("CardParent")
    track.track_axis = 'TRACK_NEGATIVE_Z'
    track.up_axis = 'UP_Y'

    # 轮廓光 (Back Light)
    back_pos = center + Vector((0, size, size))
    bpy.ops.object.light_add(type='AREA', location=back_pos)
    back_light = bpy.context.object
    back_light.data.energy = 500.0
    back_light.data.size = size
    track = back_light.constraints.new(type='TRACK_TO')
    track.target = bpy.data.objects.get("CardParent")
    track.track_axis = 'TRACK_NEGATIVE_Z'
    track.up_axis = 'UP_Y'

def import_model(file_path):
    """根据文件扩展名导入模型"""
    ext = os.path.splitext(file_path)[1].lower()
    
    if ext == '.obj':
        bpy.ops.import_scene.obj(filepath=file_path)
    elif ext == '.fbx':
        bpy.ops.import_scene.fbx(filepath=file_path)
    elif ext in ['.gltf', '.glb']:
        bpy.ops.import_scene.gltf(filepath=file_path)
    elif ext == '.blend':
        pass
    else:
        print(f"不支持的文件格式: {ext}")
        sys.exit(1)

def get_all_mesh_objects():
    """获取场景中所有的网格对象"""
    return [obj for obj in bpy.context.scene.objects if obj.type == 'MESH']

def analyze_and_setup_scene():
    """
    分析场景：
    1. 区分背景和卡片
    2. 计算卡片的几何中心
    3. 创建父级 Empty 用于旋转 (不移动原始物体)
    4. 返回场景的整体中心和大小，用于设置相机
    """
    objects = get_all_mesh_objects()
    if not objects:
        return Vector((0,0,0)), 1.0

    card_objects = []
    background_objects = []

    for obj in objects:
        is_bg = False
        # 检查材质名称
        if obj.data.materials:
            if any("背景" in m.name for m in obj.data.materials if m):
                is_bg = True
        
        # 检查物体名称
        if "VEN" in obj.name or "CARNAGE" in obj.name:
            is_bg = True
            
        if is_bg:
            background_objects.append(obj)
        else:
            card_objects.append(obj)

    if not card_objects:
        card_objects = objects

    # 清除卡片对象的现有动画，以避免与转盘动画冲突
    # (用户希望控制旋转速度，这意味着我们需要接管动画)
    for obj in card_objects:
        if obj.animation_data:
            obj.animation_data_clear()

    # 1. 计算卡片的边界框中心 (用于旋转轴心)
    min_co = Vector((float('inf'), float('inf'), float('inf')))
    max_co = Vector((float('-inf'), float('-inf'), float('-inf')))
    
    has_card_bounds = False
    for obj in card_objects:
        for corner in obj.bound_box:
            # 转换为世界坐标
            world_corner = obj.matrix_world @ Vector(corner)
            min_co = Vector((min(min_co.x, world_corner.x), min(min_co.y, world_corner.y), min(min_co.z, world_corner.z)))
            max_co = Vector((max(max_co.x, world_corner.x), max(max_co.y, world_corner.y), max(max_co.z, world_corner.z)))
            has_card_bounds = True
            
    if not has_card_bounds:
        card_center = Vector((0,0,0))
        card_size = 1.0
    else:
        card_center = (min_co + max_co) / 2
        card_size = max(max_co - min_co)

    # 2. 创建 CardParent (旋转轴心) 在卡片中心
    bpy.ops.object.empty_add(type='PLAIN_AXES', location=card_center)
    card_parent = bpy.context.object
    card_parent.name = "CardParent"
    
    # 将卡片物体设为子级 (保持变换 Keep Transform)
    for obj in card_objects:
        obj.parent = card_parent
        obj.matrix_parent_inverse = card_parent.matrix_world.inverted()

    # 3. 计算整个场景的边界 (包括背景)，用于相机定位
    scene_min = Vector((float('inf'), float('inf'), float('inf')))
    scene_max = Vector((float('-inf'), float('-inf'), float('-inf')))
    
    all_objects = card_objects + background_objects
    for obj in all_objects:
        for corner in obj.bound_box:
            world_corner = obj.matrix_world @ Vector(corner)
            scene_min = Vector((min(scene_min.x, world_corner.x), min(scene_min.y, world_corner.y), min(scene_min.z, world_corner.z)))
            scene_max = Vector((max(scene_max.x, world_corner.x), max(scene_max.y, world_corner.y), max(scene_max.z, world_corner.z)))
            
    scene_center = (scene_min + scene_max) / 2
    scene_size = max(scene_max - scene_min)
    
    return scene_center, scene_size

def replace_texture(image_path):
    """
    将指定图片应用到模型材质的 Base Color 上。
    只针对卡片的特定材质（'正面', '反面' 等），避免覆盖背景。
    """
    if not image_path or not os.path.exists(image_path):
        print(f"Texture image not found: {image_path}")
        return

    print(f"Replacing texture with: {image_path}")

    # 1. 加载新图片
    try:
        new_image = bpy.data.images.load(image_path)
    except Exception as e:
        print(f"Failed to load image {image_path}: {e}")
        return

    # 2. 遍历场景中的网格物体
    objects_to_process = get_all_mesh_objects()

    # 需要替换纹理的目标材质名称关键词
    # 用户要求：原本的素材都要保留，只替换"背景"、"正面"、"背面"
    # 我们这里主要关注卡片的正面和反面。如果用户确实想换背景图，也可以包含 '背景'
    # 但为了防止意外修改环境背景，我们暂时只锁定 '正面', '反面', '背面'
    target_materials = ['正面', '反面', '背面']

    # 3. 遍历物体和材质
    for obj in objects_to_process:
        if not obj.data.materials:
            continue
        
        # 跳过背景对象 (VEN - CARNAGE)
        # 除非我们确定要替换背景
        if "VEN" in obj.name or "CARNAGE" in obj.name:
            continue

        for mat in obj.data.materials:
            if not mat or not mat.use_nodes:
                continue
            
            # 严格匹配：只有当材质名称包含目标关键词时才进行替换
            # 这能确保"磨砂"、"亚克力"、"白色材质"等其他素材不被修改
            is_target = any(tm in mat.name for tm in target_materials)
            
            if not is_target:
                continue

            print(f"Found target material: {mat.name} on {obj.name}")
            
            nodes = mat.node_tree.nodes
            links = mat.node_tree.links
            
            # 寻找 Principled BSDF 节点
            bsdf = next((n for n in nodes if n.type == 'BSDF_PRINCIPLED'), None)
            
            if not bsdf:
                continue
            
            # 寻找或创建 Image Texture 节点
            tex_node = None
            
            # 检查 Base Color 输入是否有连接
            base_color_socket = bsdf.inputs.get('Base Color')
            if not base_color_socket:
                base_color_socket = bsdf.inputs.get('BaseColor')
                
            if base_color_socket and base_color_socket.is_linked:
                link = base_color_socket.links[0]
                if link.from_node.type == 'TEX_IMAGE':
                    tex_node = link.from_node
            
            # 如果没有找到纹理节点，但这是目标材质，我们创建一个
            if not tex_node:
                print(f"Creating new texture node for {mat.name}")
                tex_node = nodes.new(type='ShaderNodeTexImage')
                if base_color_socket:
                    links.new(tex_node.outputs['Color'], base_color_socket)
            
            if tex_node:
                # 设置图片
                tex_node.image = new_image
                print(f"Applied texture to material: {mat.name} on object {obj.name}")

def setup_turntable_animation(frames=120, rotations=1):
    """设置转盘动画"""
    # 之前是 "ModelParent"，现在改为 "CardParent"
    parent_empty = bpy.data.objects.get("CardParent")
    if not parent_empty:
        # 如果找不到 CardParent，尝试找 ModelParent (兼容旧逻辑)
        parent_empty = bpy.data.objects.get("ModelParent")
    
    if not parent_empty:
        return

    parent_empty.rotation_mode = 'XYZ'
    
    # 0帧
    parent_empty.rotation_euler.z = 0
    parent_empty.keyframe_insert(data_path="rotation_euler", frame=1, index=2)
    
    # 最后一帧
    parent_empty.rotation_euler.z = 2 * math.pi * rotations
    parent_empty.keyframe_insert(data_path="rotation_euler", frame=frames + 1, index=2)

    # 设置线性插值
    for fcurve in parent_empty.animation_data.action.fcurves:
        for keyframe in fcurve.keyframe_points:
            keyframe.interpolation = 'LINEAR'

def setup_render_settings(scene, output_path, frames=120, is_blend_file=False):
    """配置渲染设置"""
    
    # 无论是否是 blend 文件，我们都需要设置输出路径和帧数
    scene.render.filepath = output_path
    scene.frame_start = 1
    scene.frame_end = frames

    # 如果是 blend 文件，我们信任文件中的渲染设置（引擎、分辨率、色彩空间等）
    # 只确保输出格式是我们想要的视频格式 (为了兼容性，我们还是强制输出为视频)
    if is_blend_file:
        print("Using render settings from project file (Resolution, Engine, Color Management).")
        # 确保输出是视频而不是图片序列
        scene.render.image_settings.file_format = 'FFMPEG'
        
        # 用户明确要求导出 MP4
        # 强制设置容器格式为 MPEG-4 (即使原文件是 MKV)
        scene.render.ffmpeg.format = 'MPEG4'
        scene.render.ffmpeg.codec = 'H264'
        
        # 确保高质量输出
        scene.render.ffmpeg.constant_rate_factor = 'HIGH'
        scene.render.ffmpeg.ffmpeg_preset = 'GOOD'
        return

    # 下面是针对非 blend 文件 (glb/obj导入) 的默认设置
    # Blender 4.2+ 推荐使用 BLENDER_EEVEE_NEXT，但也可能只有 BLENDER_EEVEE
    # 我们使用 try-except 来安全地设置引擎
    try:
        scene.render.engine = 'BLENDER_EEVEE_NEXT'
    except:
        try:
            scene.render.engine = 'BLENDER_EEVEE'
        except:
            print("Warning: EEVEE engine not found, falling back to CYCLES")
            scene.render.engine = 'CYCLES'
            scene.cycles.device = 'CPU'
            scene.cycles.samples = 32

    # 增加曝光度，防止太暗
    scene.view_settings.exposure = 1.0 
    # Blender 4.0+ 使用 AgX，旧版 Look 名称可能不同
    # 我们尝试设置，如果失败则使用默认或兼容值
    try:
        scene.view_settings.look = 'AgX - High Contrast'
    except TypeError:
        try:
            scene.view_settings.look = 'High Contrast'
        except:
            pass # 保持默认

    # 分辨率
    scene.render.resolution_x = 1080
    scene.render.resolution_y = 1080
    scene.render.resolution_percentage = 100

    # 输出格式
    scene.render.image_settings.file_format = 'FFMPEG'
    scene.render.ffmpeg.format = 'MPEG4'
    scene.render.ffmpeg.codec = 'H264'
    scene.render.ffmpeg.constant_rate_factor = 'HIGH'
    scene.render.ffmpeg.ffmpeg_preset = 'GOOD'


def main():
    # 获取传递给脚本的参数
    # Blender 命令行参数在 '--' 之后
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1:]
    else:
        argv = []

    parser = argparse.ArgumentParser(description="Blender Auto Render Script")
    parser.add_argument("--input", required=True, help="Input model file path")
    parser.add_argument("--output", required=True, help="Output video file path")
    parser.add_argument("--texture", help="Path to texture image to replace")
    parser.add_argument("--frames", type=int, default=120, help="Number of frames to render")
    parser.add_argument("--rotations", type=float, default=1.0, help="Number of full rotations")
    parser.add_argument("--test", action='store_true', help="Test run (render 1 frame)")
    
    try:
        args = parser.parse_args(argv)
    except SystemExit:
        # argparse 会在 help 时尝试退出，在 Blender 中这可能导致整个 Blender 关闭
        # 如果是命令行调用没问题，但这里为了安全起见
        return

    print(f"Blender Version: {bpy.app.version_string}")

    ext = os.path.splitext(args.input)[1].lower()
    is_blend_file = (ext == '.blend')

    if is_blend_file:
        print(f"Opening project file: {args.input}")
        bpy.ops.wm.open_mainfile(filepath=args.input)
        scene = bpy.context.scene
    else:
        # 1. 重置场景
        reset_scene()
        scene = bpy.context.scene

        # 2. 导入模型
        print(f"Importing {args.input}...")
        import_model(args.input)

    # 3. 替换纹理 (如果提供)
    if args.texture:
        replace_texture(args.texture)

    # 4. 分析场景并设置 Pivot
    scene_center, scene_size = analyze_and_setup_scene()

    if not is_blend_file:
        # 5. 设置灯光
        setup_lighting(scene_center, scene_size)

        # 6. 设置相机
        setup_camera(scene, scene_center, scene_size)
    else:
        print("Using existing camera and lighting from project file.")
        if not scene.camera:
             print("Warning: No camera found in project file. Setting up default camera.")
             setup_camera(scene, scene_center, scene_size)

    # 确定帧数
    frames = 1 if args.test else args.frames
    if args.test:
        print("Running in TEST mode: rendering only 1 frame.")

    # 7. 设置动画
    setup_turntable_animation(frames=frames, rotations=args.rotations)

    # 7. 渲染设置
    setup_render_settings(scene, args.output, frames=frames, is_blend_file=is_blend_file)

    # 8. 开始渲染
    print(f"Rendering to {args.output}...")
    bpy.ops.render.render(animation=True)
    print("Render finished.")

if __name__ == "__main__":
    main()
