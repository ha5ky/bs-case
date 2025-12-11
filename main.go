package main

import (
	"context"
	"flag"
	"fmt"
	"log"
	"os"
	"os/exec"
	"path/filepath"

	"google.golang.org/genai"
)

// Nano Banana API 配置
// 使用 Nano Banana Pro (Gemini 3 Pro Image) 以获得更高质量的纹理
const modelName = "gemini-3-pro-image-preview"

func generateImage(ctx context.Context, prompt, apiKey, filename, imagePath, aspectRatio, imageSize string) (string, error) {
	fmt.Printf("Generating texture with Nano Banana Pro (%s)... Prompt: %s\n", modelName, prompt)

	client, err := genai.NewClient(ctx, &genai.ClientConfig{APIKey: apiKey})
	if err != nil {
		return "", fmt.Errorf("failed to create client: %w", err)
	}

	var parts []*genai.Part
	parts = append(parts, &genai.Part{Text: prompt})

	if imagePath != "" {
		fmt.Printf("Reading input image from: %s\n", imagePath)
		imgData, err := os.ReadFile(imagePath)
		if err != nil {
			return "", fmt.Errorf("failed to read input image: %w", err)
		}

		// 简单检测图片类型，默认 png，如果是 jpg 则使用 jpeg
		mimeType := "image/png"
		ext := filepath.Ext(imagePath)
		if ext == ".jpg" || ext == ".jpeg" {
			mimeType = "image/jpeg"
		} else if ext == ".webp" {
			mimeType = "image/webp"
		}

		parts = append(parts, &genai.Part{
			InlineData: &genai.Blob{
				MIMEType: mimeType,
				Data:     imgData,
			},
		})
	}

	contents := []*genai.Content{
		{Parts: parts},
	}

	config := &genai.GenerateContentConfig{
		ImageConfig: &genai.ImageConfig{
			AspectRatio: aspectRatio,
			ImageSize:   imageSize,
		},
	}

	resp, err := client.Models.GenerateContent(ctx, modelName, contents, config)
	if err != nil {
		return "", fmt.Errorf("failed to generate content: %w", err)
	}

	if len(resp.Candidates) == 0 || resp.Candidates[0].Content == nil || len(resp.Candidates[0].Content.Parts) == 0 {
		return "", fmt.Errorf("no content generated")
	}

	// 假设第一个部分包含图像数据
	part := resp.Candidates[0].Content.Parts[0]

	// 检查是否有 InlineData
	if part.InlineData == nil {
		return "", fmt.Errorf("no inline data found in response part")
	}

	// InlineData.Data 已经是 []byte (库已处理 Base64 解码)
	imgData := part.InlineData.Data

	// 保存文件
	if err := os.WriteFile(filename, imgData, 0644); err != nil {
		return "", fmt.Errorf("failed to write image file: %w", err)
	}

	absPath, _ := filepath.Abs(filename)
	fmt.Printf("Texture generated successfully: %s\n", absPath)
	return absPath, nil
}

func main() {
	blenderPath := flag.String("blender", "", "Path to Blender executable (optional)")
	// projectPath := flag.String("project", "", "Path to the .blend project file (optional template)") // 暂时不需要
	modelPath := flag.String("input", "1.glb", "Path to the 3D model file (obj, fbx, glb, etc.)")
	texturePath := flag.String("texture", "", "Path to the texture image to replace (deprecated, use --texture_front etc.)")
	textureTarget := flag.String("texture_target", "front", "Target part to replace texture: front, back, background (deprecated)")

	textureFront := flag.String("texture_front", "", "Path to the texture image for front")
	textureBack := flag.String("texture_back", "", "Path to the texture image for back")
	textureBackground := flag.String("texture_background", "", "Path to the texture image for background")

	textureOutput := flag.String("texture_output", "generated_texture.png", "Filename for the generated texture image")
	imageInput := flag.String("image_input", "", "Path to the input image for generation (optional)")
	prompt := flag.String("prompt", "", "Extract the card face part of this card and turn it into a flat image without altering the content.")
	apiKey := flag.String("api_key", "", "your apiKey")
	outputPath := flag.String("output", "output.mp4", "Output video file path")
	frames := flag.Int("frames", 0, "Number of frames to render (0 = auto/from file)")
	rotations := flag.Float64("rotations", -1.0, "Number of full rotations (-1 = auto/from file)")
	proxyAddr := flag.String("proxy", "http://127.0.0.1:7897", "Proxy address (e.g., http://127.0.0.1:7897)")
	aspectRatio := flag.String("aspect_ratio", "1:1", "Aspect ratio for generated image (e.g., 1:1, 16:9, 4:3)")
	imageSize := flag.String("image_size", "1K", "Image size/resolution (e.g., 1K, 2K)")
	flag.Parse()

	// 设置代理
	if *proxyAddr != "" {
		os.Setenv("HTTP_PROXY", *proxyAddr)
		os.Setenv("HTTPS_PROXY", *proxyAddr)
		fmt.Printf("Using proxy: %s\n", *proxyAddr)
	}

	// 验证 Blender 路径 (仅当提供了路径时)
	if *blenderPath != "" {
		if _, err := os.Stat(*blenderPath); os.IsNotExist(err) {
			log.Fatalf("Blender executable not found at %s. \nPlease provide the correct path using --blender flag.", *blenderPath)
		}
	}

	// 获取当前工作目录，确保脚本路径正确
	cwd, err := os.Getwd()
	if err != nil {
		log.Fatalf("Failed to get current working directory: %v", err)
	}
	scriptPath := filepath.Join(cwd, "render_script.py")

	// 确保输入输出目录是绝对路径
	absOutputPath, err := filepath.Abs(*outputPath)
	if err != nil {
		log.Printf("Warning: could not resolve absolute path for output: %v", err)
		absOutputPath = *outputPath
	}

	absModelPath, err := filepath.Abs(*modelPath)
	if err != nil {
		log.Printf("Warning: could not resolve absolute path for input model: %v", err)
		absModelPath = *modelPath
	}

	var generatedTexturePath string
	if *prompt != "" {
		// apiKey := os.Getenv("GEMINI_API_KEY")
		if *apiKey == "" {
			// Fallback to a default key if not set (for testing convenience)
			fmt.Println("Warning: GEMINI_API_KEY not set, using fallback key.")
		}

		if *apiKey == "" {
			log.Fatal("GEMINI_API_KEY environment variable is not set. Please set it to use Nano Banana API.")
		}

		var err error
		generatedTexturePath, err = generateImage(context.Background(), *prompt, *apiKey, *textureOutput, *imageInput, *aspectRatio, *imageSize)
		if err != nil {
			log.Fatalf("Failed to generate texture: %v", err)
		}
	}

	absTexturePath := ""
	// if generatedTexturePath != "" {
	// 	absTexturePath = generatedTexturePath
	// } else if *texturePath != "" {
	if *texturePath != "" {
		absTexturePath, err = filepath.Abs(*texturePath)
		if err != nil {
			log.Printf("Warning: could not resolve absolute path for texture: %v", err)
			absTexturePath = *texturePath
		}
	}

	// 解析多个纹理路径
	absTextureFront := ""
	if *textureFront != "" {
		absTextureFront, err = filepath.Abs(*textureFront)
		if err != nil {
			log.Printf("Warning: could not resolve absolute path for texture front: %v", err)
			absTextureFront = *textureFront
		}
	} else if generatedTexturePath != "" && *textureTarget == "front" {
		absTextureFront = generatedTexturePath
	}

	absTextureBack := ""
	if *textureBack != "" {
		absTextureBack, err = filepath.Abs(*textureBack)
		if err != nil {
			log.Printf("Warning: could not resolve absolute path for texture back: %v", err)
			absTextureBack = *textureBack
		}
	} else if generatedTexturePath != "" && *textureTarget == "back" {
		absTextureBack = generatedTexturePath
	}

	absTextureBackground := ""
	if *textureBackground != "" {
		absTextureBackground, err = filepath.Abs(*textureBackground)
		if err != nil {
			log.Printf("Warning: could not resolve absolute path for texture background: %v", err)
			absTextureBackground = *textureBackground
		}
	} else if generatedTexturePath != "" && *textureTarget == "background" {
		absTextureBackground = generatedTexturePath
	}

	// 构建参数
	// blender --background --python render_script.py -- --input [file] --output [file] --frames [num] [--texture [file]]

	args := []string{
		"--background",
		"--python", scriptPath,
		"--",
		"--input", absModelPath,
		"--output", absOutputPath,
		"--frames", fmt.Sprintf("%d", *frames),
		"--rotations", fmt.Sprintf("%f", *rotations),
	}

	if absTexturePath != "" {
		args = append(args, "--texture", absTexturePath)
		args = append(args, "--texture_target", *textureTarget)
	}

	if absTextureFront != "" {
		args = append(args, "--texture_front", absTextureFront)
	}
	if absTextureBack != "" {
		args = append(args, "--texture_back", absTextureBack)
	}
	if absTextureBackground != "" {
		args = append(args, "--texture_background", absTextureBackground)
	}

	if *blenderPath != "" {
		cmd := exec.Command(*blenderPath, args...)

		// 连接标准输出和标准错误，以便看到 Blender 的日志
		cmd.Stdout = os.Stdout
		cmd.Stderr = os.Stderr

		fmt.Printf("Running command: %s %v\n", *blenderPath, args)
		fmt.Println("Rendering started... This may take a while.")

		err = cmd.Run()
		if err != nil {
			log.Fatalf("Blender rendering failed: %v", err)
		}

		fmt.Println("Rendering finished successfully!")
	} else {
		fmt.Println("Blender path not specified, skipping video rendering.")
		if *prompt != "" {
			fmt.Println("Texture generation completed.")
		}
	}
}
