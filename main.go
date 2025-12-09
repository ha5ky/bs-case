package main

import (
	"bytes"
	"encoding/base64"
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
)

// Nano Banana API 配置
// 使用 Nano Banana Pro (Gemini 3 Pro Image) 以获得更高质量的纹理
const apiEndpoint = "https://generativelanguage.googleapis.com/v1beta/models/gemini-3-pro-image-preview:generateContent"

type GenerateRequest struct {
	Contents []Content `json:"contents"`
}

type Content struct {
	Parts []Part `json:"parts"`
}

type Part struct {
	Text string `json:"text"`
}

// 简单的响应结构解析，实际结构可能更复杂，这里简化处理
type GenerateResponse struct {
	Candidates []struct {
		Content struct {
			Parts []struct {
				InlineData *struct {
					MimeType string `json:"mime_type"`
					Data     string `json:"data"`
				} `json:"inline_data"`
			} `json:"parts"`
		} `json:"content"`
	} `json:"candidates"`
}

func generateImage(prompt, apiKey string) (string, error) {
	fmt.Printf("Generating texture with Nano Banana Pro (Gemini 3 Pro Image)... Prompt: %s\n", prompt)

	reqBody := GenerateRequest{
		Contents: []Content{{
			Parts: []Part{{Text: prompt}},
		}},
	}
	jsonData, err := json.Marshal(reqBody)
	if err != nil {
		return "", err
	}

	url := fmt.Sprintf("%s?key=%s", apiEndpoint, apiKey)
	req, err := http.NewRequest("POST", url, bytes.NewBuffer(jsonData))
	if err != nil {
		return "", err
	}
	req.Header.Set("Content-Type", "application/json")

	client := &http.Client{}
	resp, err := client.Do(req)
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()

	if resp.StatusCode != 200 {
		body, _ := io.ReadAll(resp.Body)
		return "", fmt.Errorf("API request failed with status %d: %s", resp.StatusCode, string(body))
	}

	// 解析响应
	var genResp GenerateResponse
	if err = json.NewDecoder(resp.Body).Decode(&genResp); err != nil {
		return "", err
	}

	// 提取 Base64 图片
	if len(genResp.Candidates) == 0 || len(genResp.Candidates[0].Content.Parts) == 0 || genResp.Candidates[0].Content.Parts[0].InlineData == nil {
		return "", fmt.Errorf("no image data found in response")
	}

	b64Data := genResp.Candidates[0].Content.Parts[0].InlineData.Data
	imgData, err := base64.StdEncoding.DecodeString(b64Data)
	if err != nil {
		return "", err
	}

	// 保存文件
	filename := "generated_texture.png"
	if err := os.WriteFile(filename, imgData, 0644); err != nil {
		return "", err
	}

	absPath, _ := filepath.Abs(filename)
	fmt.Printf("Texture generated successfully: %s\n", absPath)
	return absPath, nil
}

func main() {
	// 默认尝试 Mac 的标准安装路径
	defaultBlenderPath := "/Applications/Blender.app/Contents/MacOS/Blender"
	// 如果环境变量中有 BLENDER_PATH，则优先使用
	if envPath := os.Getenv("BLENDER_PATH"); envPath != "" {
		defaultBlenderPath = envPath
	}

	blenderPath := flag.String("blender", defaultBlenderPath, "Path to Blender executable")
	projectPath := flag.String("project", "", "Path to the .blend project file (optional template)")
	modelPath := flag.String("model", "", "Path to the 3D model file (obj, fbx, glb, etc.)")
	texturePath := flag.String("texture", "", "Path to the texture image to replace")
	prompt := flag.String("prompt", "", "Prompt to generate texture using Nano Banana API")
	outputPath := flag.String("output", "output.mp4", "Output video file path")
	duration := flag.Int("duration", 5, "Duration of the video in seconds")
	flag.Parse()

	// 验证 Blender 路径
	if _, err := os.Stat(*blenderPath); os.IsNotExist(err) {
		log.Fatalf("Blender executable not found at %s. \nPlease install Blender or provide the correct path using --blender flag.", *blenderPath)
	}

	// 1. 如果有 prompt，先调用 API 生成图片
	finalTexturePath := *texturePath
	if *prompt != "" {
		apiKey := os.Getenv("GEMINI_API_KEY")
		if apiKey == "" {
			log.Fatal("Error: GEMINI_API_KEY environment variable is required when using --prompt")
		}

		generatedPath, err := generateImage(*prompt, apiKey)
		if err != nil {
			log.Fatalf("Failed to generate image: %v", err)
		}
		finalTexturePath = generatedPath
	}

	// 获取当前工作目录，确保脚本路径正确
	cwd, err := os.Getwd()
	if err != nil {
		log.Fatalf("Failed to get current working directory: %v", err)
	}
	scriptPath := filepath.Join(cwd, "render_script.py")

	// 确保输出目录是绝对路径
	absOutputPath, err := filepath.Abs(*outputPath)
	if err != nil {
		log.Printf("Warning: could not resolve absolute path for output: %v", err)
		absOutputPath = *outputPath
	}

	// 构建参数
	// 模式 1 (默认): blender --background --python render_script.py -- [args]
	// 模式 2 (模板): blender project.blend --background --python render_script.py -- --keep-scene [args]

	args := []string{}

	if *projectPath != "" {
		absProjectPath, err := filepath.Abs(*projectPath)
		if err != nil {
			log.Printf("Warning: could not resolve absolute path for project: %v", err)
			absProjectPath = *projectPath
		}
		args = append(args, absProjectPath)
	}

	args = append(args, "--background", "--python", scriptPath, "--")

	// 如果使用了项目模板，添加 --keep-scene 标志告诉 Python 脚本
	if *projectPath != "" {
		args = append(args, "--keep-scene")
	}

	args = append(args,
		"--output", absOutputPath,
		"--duration", fmt.Sprintf("%d", *duration),
	)

	if *modelPath != "" {
		absModelPath, err := filepath.Abs(*modelPath)
		if err != nil {
			log.Printf("Warning: could not resolve absolute path for model: %v", err)
			absModelPath = *modelPath
		}
		args = append(args, "--model", absModelPath)
	}

	if finalTexturePath != "" {
		absTexturePath, err := filepath.Abs(finalTexturePath)
		if err != nil {
			log.Printf("Warning: could not resolve absolute path for texture: %v", err)
			absTexturePath = finalTexturePath
		}
		args = append(args, "--texture", absTexturePath)
	}

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
}
