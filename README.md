# Blender AI Render Tool

这是一个强大的自动化 3D 渲染工具，结合了 **Golang** 的流程控制、**Blender** 的渲染能力以及 **Google Nano Banana Pro (Gemini 3 Pro)** 的 AI 生成能力。

它可以帮助你：
1.  **自动渲染**: 将 3D 模型文件（.glb, .fbx, .obj）一键渲染为 MP4 视频。
2.  **AI 换肤**: 通过文字描述（Prompt），调用 AI 生成高清纹理，并自动应用到模型上。
3.  **模板工作流**: 支持基于现有的 `.blend` 项目文件进行渲染，保留设计师精心调节的灯光和运镜。

## ✨ 核心功能

*   🎥 **自动布景**: 如果没有提供模板，工具会自动创建相机、灯光和 360° 转台动画。
*   🤖 **AI 纹理生成**: 集成 Google Nano Banana Pro API，通过文本描述生成高质量纹理。
*   🎨 **智能材质替换**: 自动识别模型的主材质节点并替换贴图。
*   🔄 **全格式支持**: 支持 glTF/GLB, FBX, OBJ 等常见 3D 格式。

## 🛠 前置要求

在使用本工具之前，请确保你的环境满足以下要求：

1.  **Blender**: 安装 [Blender](https://www.blender.org/download/) (推荐 3.0+ 版本)。
    *   MacOS 默认路径: `/Applications/Blender.app/Contents/MacOS/Blender`
    *   如果安装在其他位置，运行时需通过 `--blender` 指定。
2.  **Go**: 安装 [Go 语言环境](https://go.dev/dl/) (1.16+)。
3.  **API Key (可选)**: 如果需要使用 AI 生成纹理功能，需要申请 Google Gemini API Key。

## 🚀 快速开始

### 1. 安装依赖

```bash
# 初始化 Go 模块 (如果尚未初始化)
go mod tidy
```

### 2. 设置 API Key (可选)

如果你想体验 AI 纹理生成功能：

```bash
export GEMINI_API_KEY="你的_Google_API_Key"
```

### 3. 运行工具

你可以直接通过 `go run` 运行，或者编译后运行。

#### 场景 A: 快速预览模型 (自动布光 + 旋转动画)

```bash
# 直接渲染一个模型，生成 output.mp4
go run main.go --model ./assets/chair.glb --output result.mp4
```

#### 场景 B: AI 自动换肤

```bash
# 生成一个"赛博朋克风格"的纹理，贴在模型上并渲染
go run main.go \
  --model ./assets/shirt.glb \
  --prompt "cyberpunk neon city pattern, seamless texture, high quality" \
  --output shirt_cyberpunk.mp4
```

#### 场景 C: 使用自定义图片换肤

```bash
# 使用本地图片覆盖模型材质
go run main.go --model ./assets/frame.glb --texture ./my_photo.png
```

#### 场景 D: 高级模板渲染 (商业工作流)

如果你有一个设计师做好的场景 `studio.blend` (包含灯光、相机运镜)，你想把里面的商品替换掉：

```bash
# 基于 studio.blend 模板，导入 shoe.glb，并保持原有的灯光和相机
go run main.go \
  --project ./templates/studio.blend \
  --model ./assets/shoe.glb \
  --output final_ad.mp4
```

## 📝 参数说明

| 参数 | 必选 | 默认值 | 说明 |
|------|------|--------|------|
| `--model` | 否 | - | 3D 模型文件路径 (.glb, .fbx, .obj)。如果不传且无模板，将渲染默认立方体。 |
| `--output` | 否 | output.mp4 | 输出视频文件路径。 |
| `--duration` | 否 | 5 | 视频时长（秒）。 |
| `--prompt` | 否 | - | **[AI]** 生成纹理的提示词。启用此项会自动调用 Nano Banana Pro API。 |
| `--texture` | 否 | - | 指定本地图片路径作为纹理。如果同时指定了 `--prompt`，此参数会被生成图覆盖。 |
| `--project` | 否 | - | **[高级]** 指定 `.blend` 项目文件作为基础模板。 |
| `--blender` | 否 | (Mac默认路径) | Blender 可执行文件的绝对路径。 |

## 🧠 技术原理

1.  **Go 主控**: `main.go` 负责解析参数、调用 Google API 下载图片、构建 Blender 命令行。
2.  **Blender 脚本**: `render_script.py` 运行在 Blender 内部。
    *   它使用 `bpy` (Blender Python API) 操作场景。
    *   **智能材质系统**: 脚本会遍历模型材质，寻找连接到 `Principled BSDF` -> `Base Color` 的节点，并进行替换。
    *   **渲染引擎**: 默认使用 **Eevee** 引擎进行快速渲染。

## ⚠️ 常见问题

*   **找不到 Blender?**
    *   请使用 `--blender /path/to/blender` 指定正确路径。
*   **渲染全黑?**
    *   检查模型是否在相机视野内。如果使用 `--project` 模板模式，请确保模板里的相机对准了世界原点(0,0,0)。
*   **纹理贴图错乱?**
    *   AI 生成的纹理是平铺的，依赖模型自身的 **UV 展开**。如果模型没有 UV，贴图会显示异常。
