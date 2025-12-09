import bpy
import sys
import argparse
import os
import math

def reset_scene():
    """清除场景中的所有对象"""
    bpy.ops.wm.read_factory_settings(use_empty=True)

def setup_camera(scene, location, rotation):
    """设置摄像机"""
    bpy.ops.object.camera_add(location=location, rotation=rotation)
    camera = bpy.context.object
    scene.camera = camera
    return camera

def setup_lighting(location, energy):
    """设置灯光"""
    bpy.ops.object.light_add(type='SUN', location=location)
    light = bpy.context.object
    light.data.energy = energy
    return light

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
        # 如果是 blend 文件，通常直接打开即可，但这会替换当前场景
        # 这里我们假设是导入对象，或者是打开文件
        # 为了简单起见，如果脚本作为打开 blend 文件的参数运行，这里不需要做太多
        pass
    else:
        print(f"不支持的文件格式: {ext}")
        sys.exit(1)

def auto_center_view(camera):
    """简单的自动对焦逻辑：将所有选中的物体居中"""
    bpy.ops.object.select_all(action='SELECT')
    # 排除摄像机和灯光
    for obj in bpy.context.selected_objects:
        if obj.type in ['CAMERA', 'LIGHT']:
            obj.select_set(False)
            
    if not bpy.context.selected_objects:
        return

    bpy.ops.view3d.camera_to_view_selected()

def replace_texture(image_path):
    """
    将指定图片应用到模型材质的 Base Color 上。
    尝试针对场景中所有网格物体。
    """
    if not os.path.exists(image_path):
        print(f"纹理图片不存在: {image_path}")
        return

    # 1. 加载新图片
    try:
        new_image = bpy.data.images.load(image_path)
    except Exception as e:
        print(f"无法加载图片 {image_path}: {e}")
        return

    # 2. 遍历场景中的网格物体
    objects_to_process = [obj for obj in bpy.context.scene.objects if obj.type == 'MESH']

    # 3. 遍历物体和材质
    for obj in objects_to_process:
        if not obj.data.materials:
            # 如果没有材质，创建一个新材质
            mat = bpy.data.materials.new(name=f"{obj.name}_Material")
            mat.use_nodes = True
            obj.data.materials.append(mat)
        
        for mat in obj.data.materials:
            if not mat or not mat.use_nodes:
                continue
            
            nodes = mat.node_tree.nodes
            # 寻找 Principled BSDF 节点
            bsdf = next((n for n in nodes if n.type == 'BSDF_PRINCIPLED'), None)
            
            if not bsdf:
                # 如果没有 BSDF 节点，尝试找其他 Shader 节点或者跳过
                continue

            # 寻找连接到 Base Color 的 Image Texture 节点
            tex_node = None
            
            # 检查 Base Color 输入是否有连接
            # 注意：不同版本的 Blender 属性名可能不同，但在 Principled BSDF 中通常是 'Base Color'
            base_color_input = bsdf.inputs.get('Base Color')
            if base_color_input and base_color_input.links:
                link = base_color_input.links[0]
                if link.from_node.type == 'TEX_IMAGE':
                    tex_node = link.from_node
            
            # 如果没找到现有的图片节点，就创建一个新的
            if not tex_node:
                tex_node = nodes.new('ShaderNodeTexImage')
                tex_node.location = (-300, 300)
                # 连接到 Base Color
                if base_color_input:
                    mat.node_tree.links.new(tex_node.outputs['Color'], base_color_input)
            
            # 4. 替换图片
            tex_node.image = new_image
            print(f"已将图片 {image_path} 应用到物体 {obj.name} 的材质 {mat.name}")

def configure_render(scene, output_path, resolution_x=1920, resolution_y=1080, fps=24, duration_sec=5):
    """配置渲染设置"""
    scene.render.engine = 'BLENDER_EEVEE' # 使用 Eevee 渲染引擎，速度快
    scene.render.resolution_x = resolution_x
    scene.render.resolution_y = resolution_y
    scene.render.fps = fps
    
    # 设置输出格式为 FFmpeg 视频
    scene.render.image_settings.file_format = 'FFMPEG'
    scene.render.ffmpeg.format = 'MPEG4'
    scene.render.ffmpeg.codec = 'H264'
    scene.render.ffmpeg.constant_rate_factor = 'MEDIUM'
    scene.render.ffmpeg.ffmpeg_preset = 'GOOD'
    
    scene.render.filepath = output_path

    # 设置动画时长
    scene.frame_start = 1
    scene.frame_end = fps * duration_sec

def create_turntable_animation(scene, duration_sec, fps):
    """创建一个简单的转台动画：让所有物体绕 Z 轴旋转，或者让摄像机绕物体旋转"""
    # 这里简单起见，我们在场景中心创建一个空物体，作为所有导入模型的父级，然后旋转空物体
    
    bpy.ops.object.select_all(action='DESELECT')
    
    # 选择所有网格物体
    mesh_objects = [obj for obj in scene.objects if obj.type == 'MESH']
    if not mesh_objects:
        # 如果没有模型，创建一个立方体演示
        bpy.ops.mesh.primitive_cube_add()
        mesh_objects = [bpy.context.object]
    
    # 创建空物体作为父级
    bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0, 0, 0))
    parent_empty = bpy.context.object
    
    for obj in mesh_objects:
        obj.select_set(True)
    
    parent_empty.select_set(True)
    bpy.context.view_layer.objects.active = parent_empty
    bpy.ops.object.parent_set(type='OBJECT', keep_transform=True)
    
    # 设置关键帧
    parent_empty.rotation_euler = (0, 0, 0)
    parent_empty.keyframe_insert(data_path="rotation_euler", frame=1)
    
    parent_empty.rotation_euler = (0, 0, 2 * math.pi) # 360度
    parent_empty.keyframe_insert(data_path="rotation_euler", frame=scene.frame_end + 1)
    
    # 将插值模式设置为线性
    if parent_empty.animation_data and parent_empty.animation_data.action:
        for fcurve in parent_empty.animation_data.action.fcurves:
            for keyframe in fcurve.keyframe_points:
                keyframe.interpolation = 'LINEAR'

def main():
    # 获取 -- 之后的参数
    if "--" not in sys.argv:
        args = []
    else:
        args = sys.argv[sys.argv.index("--") + 1:]

    parser = argparse.ArgumentParser(description="Blender 渲染脚本")
    parser.add_argument("--model", help="模型文件路径", required=False)
    parser.add_argument("--output", help="输出视频路径 (不带扩展名)", required=True)
    parser.add_argument("--duration", type=int, default=5, help="视频时长(秒)")
    parser.add_argument("--texture", help="要替换的纹理图片路径", required=False)
    parser.add_argument("--keep-scene", action="store_true", help="保留现有场景（不重置），用于模板渲染")
    
    try:
        args = parser.parse_args(args)
    except SystemExit:
        # argparse 会在 --help 时调用 sys.exit()，在 Blender 中这会关闭 Blender
        return

    # 1. 场景初始化
    scene = bpy.context.scene
    if not args.keep_scene:
        # 如果不是基于模板，则重置场景并设置默认环境
        reset_scene()
        scene = bpy.context.scene
        # 3. 设置摄像机和灯光 (仅在非模板模式下自动设置)
        camera = setup_camera(scene, location=(0, -10, 5), rotation=(math.radians(60), 0, 0))
        setup_lighting(location=(5, -5, 10), energy=10)
        # 4. 摄像机追踪
        bpy.ops.object.constraint_add(type='TRACK_TO')
        camera.constraints["Track To"].target = bpy.data.objects.get("Empty")
        if not camera.constraints["Track To"].target:
             bpy.ops.object.empty_add(location=(0,0,0))
             camera.constraints["Track To"].target = bpy.context.object
        camera.constraints["Track To"].track_axis = 'TRACK_NEGATIVE_Z'
        camera.constraints["Track To"].up_axis = 'UP_Y'
    else:
        # 模板模式：假设模板里已经有了摄像机
        if not scene.camera:
            print("警告：模板文件中没有活动摄像机，尝试寻找一个...")
            cameras = [obj for obj in scene.objects if obj.type == 'CAMERA']
            if cameras:
                scene.camera = cameras[0]
            else:
                print("错误：模板中没有摄像机，将创建一个默认摄像机")
                setup_camera(scene, location=(0, -10, 5), rotation=(math.radians(60), 0, 0))

    # 2. 导入模型 (如果有)
    if args.model and os.path.exists(args.model):
        import_model(args.model)
    elif not args.keep_scene:
        # 只有在非模板模式且没模型时，才创建立方体
        print("未提供模型或模型不存在，将使用默认立方体演示")
        bpy.ops.mesh.primitive_cube_add(size=2)
    
    # 2.5 替换纹理 (如果有)
    if args.texture:
        replace_texture(args.texture)

    # 5. 配置渲染
    # 注意：如果是模板模式，我们可能不想覆盖分辨率设置，这里需要权衡。
    # 为了简单，我们暂时假设命令行参数优先级更高，总是覆盖输出路径和时长。
    configure_render(scene, args.output, duration_sec=args.duration)
    
    # 6. 创建旋转动画 (仅在非模板模式，或明确要求时)
    # 模板通常自带动画。如果我们在模板模式下强行加动画，可能会破坏原有设计。
    # 策略：如果 args.keep_scene 为 True，跳过自动动画生成，除非我们增加一个强制动画的参数。
    # 目前保持简单：模板模式下不自动生成转台动画。
    if not args.keep_scene:
        create_turntable_animation(scene, args.duration, 24)

    # 7. 开始渲染
    print(f"开始渲染动画到 {args.output}...")
    bpy.ops.render.render(animation=True)
    print("渲染完成")

if __name__ == "__main__":
    main()
