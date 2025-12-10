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
    # 之前是看 "CardParent"，现在改为看 "FocusPoint" (场景中心，含背景)
    bpy.ops.object.constraint_add(type='TRACK_TO')
    
    # 在某些 Blender 版本或语言环境下，约束名称可能不同 (例如中文环境 "Track To" 可能是 "标准跟踪")
    # 我们直接获取最后一个添加的约束，而不是通过名称索引
    track_constraint = camera.constraints[-1]
    track_constraint.target = bpy.data.objects.get("FocusPoint")
    track_constraint.track_axis = 'TRACK_NEGATIVE_Z'
    track_constraint.up_axis = 'UP_Y'
    
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

def check_if_animation_exists():
    """检查场景中的卡片对象是否有动画"""
    objects = get_all_mesh_objects()
    for obj in objects:
        if "VEN" in obj.name or "CARNAGE" in obj.name:
            continue
        if obj.animation_data and obj.animation_data.action:
            print(f"Found existing animation on {obj.name}: {obj.animation_data.action.name}")
            return True
    return False

def get_animation_length():
    """获取动画长度（结束帧）"""
    # 优先使用 Scene 的结束帧，因为通常动画长度和场景设置一致
    scene_end = bpy.context.scene.frame_end
    
    # 也可以检查 Action 的范围
    max_frame = scene_end
    objects = get_all_mesh_objects()
    for obj in objects:
        if obj.animation_data and obj.animation_data.action:
             max_frame = max(max_frame, obj.animation_data.action.frame_range[1])
             
    # 如果 Action 比 Scene 长很多，可能取 Scene 更合适？
    # 或者取两者最大值？为了安全起见，我们信任 Scene 的设置，
    # 除非 Scene 很短而 Action 很长
    if max_frame > scene_end and scene_end < 2: # 如果 Scene 似乎未设置
         return int(max_frame)
         
    return scene_end

def analyze_and_setup_scene(keep_animation=False):
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
    # 仅当 keep_animation 为 False 时执行
    if not keep_animation:
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

    # -------------------------------------------------------------------------
    # 3. 处理背景：不放大，保持原样
    # -------------------------------------------------------------------------
    # 用户要求：背景图要全显示，不要放大，保持模型文件中的设置
    # 所以我们移除之前的缩放代码
    
    # -------------------------------------------------------------------------
    # 4. 计算整个场景的边界 (包括背景)，用于相机定位
    # -------------------------------------------------------------------------
    # 为了确保背景全显示，我们需要让相机看到所有物体（包括背景）
    # 并且将相机对焦在整个场景的中心，而不是只对焦卡片
    
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

    # 创建一个对焦点 (FocusPoint) 在场景中心
    # 如果已经存在则获取
    focus_point = bpy.data.objects.get("FocusPoint")
    if not focus_point:
        bpy.ops.object.empty_add(type='PLAIN_AXES', location=scene_center)
        focus_point = bpy.context.object
        focus_point.name = "FocusPoint"
    else:
        focus_point.location = scene_center
    
    return scene_center, scene_size

def replace_texture(image_path, target_part="front"):
    """
    将指定图片应用到模型材质的 Base Color 上。
    target_part: "front" (正面), "back" (背面), "background" (背景)
    """
    if not image_path or not os.path.exists(image_path):
        print(f"Texture image not found: {image_path}")
        return

    print(f"Replacing texture with: {image_path}, Target: {target_part}")

    # 1. 加载新图片
    try:
        new_image = bpy.data.images.load(image_path)
    except Exception as e:
        print(f"Failed to load image {image_path}: {e}")
        return

    # 2. 遍历场景中的网格物体
    objects_to_process = get_all_mesh_objects()

    # 根据 target_part 确定目标材质关键词
    target_materials = []
    allow_background_objects = False

    if target_part == "front":
        target_materials = ['正面']
    elif target_part == "back":
        target_materials = ['背面', '反面']
    elif target_part == "background":
        target_materials = ['背景']
        allow_background_objects = True
    else:
        # 默认回退到原来的逻辑 (只换正反面)
        print(f"Unknown target part '{target_part}', defaulting to front/back")
        target_materials = ['正面', '反面', '背面']

    # 3. 遍历物体和材质
    for obj in objects_to_process:
        if not obj.data.materials:
            continue
        
        # 检查是否是背景对象 (VEN - CARNAGE)
        is_bg_obj = "VEN" in obj.name or "CARNAGE" in obj.name
        
        # 如果当前不是要替换背景，且遇到了背景对象，则跳过
        if is_bg_obj and not allow_background_objects:
            continue
            
        # 如果当前是要替换背景，但对象看起来不像背景（虽然逻辑上只要材质匹配就行，
        # 但为了效率和安全，我们可以反向过滤？或者干脆不通过对象名过滤，只信材质名）
        # 这里我们选择：如果允许背景对象，就放行所有对象去检查材质
        
        for mat in obj.data.materials:
            if not mat or not mat.use_nodes:
                continue
            
            # 严格匹配：只有当材质名称包含目标关键词时才进行替换
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

    # -------------------------------------------------------------------------
    # 针对非 blend 文件 (glb/obj导入)，我们模拟 1.blend 的配置
    # -------------------------------------------------------------------------
    print("Applying standard project configuration (from 1.blend)...")

    # 1. 渲染引擎: CYCLES
    scene.render.engine = 'CYCLES'
    
    # 尝试启用 GPU
    try:
        scene.cycles.device = 'GPU'
        # 必须设置偏好设置中的设备才能生效
        prefs = bpy.context.preferences
        cprefs = prefs.addons['cycles'].preferences
        
        # 尝试自动检测 CUDA, METAL, OPTIX
        for compute_device_type in ('METAL', 'OPTIX', 'CUDA'):
            try:
                cprefs.compute_device_type = compute_device_type
                # 获取可用设备
                devices = cprefs.get_devices_for_type(compute_device_type)
                if devices:
                    print(f"Using Cycles Device: {compute_device_type}")
                    for device in devices:
                        device.use = True
                    break
            except:
                continue
    except Exception as e:
        print(f"Failed to set GPU: {e}, falling back to CPU")
        scene.cycles.device = 'CPU'

    # 采样数 (原工程是 500，为了速度我们设为 128，或者保持 500 如果用户机器强)
    # 考虑到自动化脚本可能在服务器跑，给个适中的值
    scene.cycles.samples = 128 
    # 开启降噪
    scene.cycles.use_denoising = True

    # 2. 分辨率: 900x1200
    scene.render.resolution_x = 900
    scene.render.resolution_y = 1200
    scene.render.resolution_percentage = 100

    # 3. 帧率: 24 fps
    scene.render.fps = 24

    # 4. 色彩管理: Khronos PBR Neutral / None
    try:
        scene.view_settings.view_transform = 'Khronos PBR Neutral'
    except:
        # 如果版本不支持，回退到 Standard 或 Filmic
        scene.view_settings.view_transform = 'Standard'
        
    try:
        scene.view_settings.look = 'None'
    except:
        pass

    # 增加一点曝光度以匹配效果 (可选)
    # scene.view_settings.exposure = 0.0 # 保持默认

    # 5. 输出格式
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
    parser.add_argument("--texture_target", default="front", help="Target part to replace texture: front, back, background")
    parser.add_argument("--texture_front", help="Texture image path for front (optional)")
    parser.add_argument("--texture_back", help="Texture image path for back (optional)")
    parser.add_argument("--texture_background", help="Texture image path for background (optional)")
    parser.add_argument("--frames", type=int, default=0, help="Number of frames to render (0 = auto)")
    parser.add_argument("--rotations", type=float, default=-1.0, help="Number of full rotations (-1 = auto)")
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
        replace_texture(args.texture, args.texture_target)

    if args.texture_front:
        replace_texture(args.texture_front, "front")
    if args.texture_back:
        replace_texture(args.texture_back, "back")
    if args.texture_background:
        replace_texture(args.texture_background, "background")
        
    # --- 决定是否保留原有动画 ---
    # 如果用户没有指定 rotations (即 -1.0) 且场景中有动画，则保留
    should_keep_anim = (args.rotations < 0)
    has_existing_anim = check_if_animation_exists()
    
    # 默认值
    default_frames = 120
    default_rotations = 1.0
    
    keep_animation = False
    final_frames = default_frames
    final_rotations = default_rotations

    if should_keep_anim and has_existing_anim:
        print("Using existing animation from file.")
        keep_animation = True
        # 如果保留动画，我们需要知道动画多长
        anim_len = get_animation_length()
        # 如果 args.frames 未指定 (0)，则使用动画长度
        final_frames = args.frames if args.frames > 0 else anim_len
    else:
        # 否则，使用默认或用户指定的旋转
        if args.rotations >= 0:
            final_rotations = args.rotations
        else:
             # 如果没有动画也没指定，使用默认 1.0
             final_rotations = default_rotations
             
        final_frames = args.frames if args.frames > 0 else default_frames
        
    print(f"Animation Mode: Keep={keep_animation}, Frames={final_frames}, Rotations={final_rotations}")

    # 4. 分析场景并设置 Pivot
    # 传递 keep_animation 标志
    scene_center, scene_size = analyze_and_setup_scene(keep_animation=keep_animation)

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

    # 确定帧数 (Test 模式覆盖一切)
    frames_to_render = 1 if args.test else final_frames
    if args.test:
        print("Running in TEST mode: rendering only 1 frame.")

    # 7. 设置动画
    # 只有当不保留原有动画时，才应用转盘动画
    if not keep_animation:
        setup_turntable_animation(frames=frames_to_render, rotations=final_rotations)

    # 7. 渲染设置
    setup_render_settings(scene, args.output, frames=frames_to_render, is_blend_file=is_blend_file)

    # 8. 开始渲染
    print(f"Rendering to {args.output}...")
    bpy.ops.render.render(animation=True)
    print("Render finished.")

if __name__ == "__main__":
    main()
