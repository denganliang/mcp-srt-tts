# mcp-srt-tts

[English](#english) | [中文说明](#chinese)

**mcp-srt-tts** is a powerful **Model Context Protocol (MCP)** server that converts SRT subtitles to high-quality speech using a remote TTS engine.

It features **Auto-Flow technology** to intelligently handle timeline overlaps and **Cross-fade smoothing** for natural-sounding audio transitions.

**mcp-srt-tts** 是一个强大的 **MCP (Model Context Protocol)** 工具，它可以调用远程 TTS 引擎，将 SRT 字幕文件批量转换为高质量的语音文件。

它内置了 **Auto-Flow（自动顺延流）** 技术，能智能处理语音重叠问题，并自动应用 **淡入淡出（Cross-fade）** 处理，让合成的语音听起来自然流畅。

---

<a name="english"></a>
## 🇬🇧 English Description

### ✨ Features

- **MCP Support**: Designed to be used directly as a **Skill** in Claude Code or other MCP clients.
- **Auto-Flow Timing**: Automatically detects if a spoken sentence is longer than its subtitle slot and **shifts the timeline** to prevent overlap/chaos while maintaining sequential integrity.
- **Smooth Transitions**: Applies **50ms fade-in/out envelopes** to every segment to eliminate clicks, pops, and hard cuts.
- **Auto-Trim**: Automatically removes trailing silence from the generated audio.
- **Reference Audio**: Supports voice cloning by uploading a reference audio file (timbre) to the TTS server.

### 🔌 TTS Backend Requirement

This tool relies on **Index TTS** for speech synthesis.
Please deploy it yourself: [https://github.com/index-tts/index-tts](https://github.com/index-tts/index-tts)

You will need to provide your deployed TTS server URL as a parameter.

### 📦 Installation

#### 1. Clone the repository
```bash
git clone https://github.com/denganliang/mcp-srt-tts.git
cd mcp-srt-tts
```

#### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 🚀 Usage with Claude Code

You can add this tool as a skill to Claude Code using the `mcp` command.

**Windows:**
```bash
claude mcp add srt-tts -- python "D:\path\to\mcp-srt-tts\mcp_server.py"
```
*(Note: Please replace the path with your actual absolute path)*

**macOS / Linux:**
```bash
claude mcp add srt-tts -- python "/path/to/mcp-srt-tts/mcp_server.py"
```

#### Example Prompt
Once added, you can simply ask Claude in natural language:

> "Convert `movie.srt` to audio using `ref_voice.wav`. My TTS server is at `http://localhost:8000`."

Claude will:
1. Parse the SRT.
2. Upload the reference audio.
3. Synthesize speech for each line.
4. **Auto-adjust timing** to prevent overlaps.
5. Generate the final `output.wav`.

### 🛠 Standalone Usage (CLI)

You can also run it directly as a Python script without MCP:

```bash
python main.py <TTS_URL> <SRT_FILE> <REF_AUDIO> [-o output.wav]
```

---

<a name="chinese"></a>
## 🇨🇳 中文说明

### ✨ 核心功能

- **完美支持 MCP**：专为 Claude Code 设计，安装后可作为 **Skill** 直接通过自然语言调用。
- **Auto-Flow 自动顺延**：脚本会自动检测生成的语音长度。如果语音比字幕时间长，程序会自动**顺延下一句的开始时间**，彻底解决语音重叠（Overlap）和嘈杂混乱的问题，保证每一句话都清晰完整。
- **平滑过渡处理**：对每一段语音的首尾应用 **50ms 淡入淡出（Fade Envelope）**，消除拼接处的爆音和生硬感。
- **自动裁剪**：生成完成后，自动检测并移除末尾多余的静音空白。
- **参考音频支持**：支持上传本地参考音频文件，用于 TTS 的音色克隆。

### 🔌 TTS 后端要求

本工具使用 **Index TTS** 作为语音合成后端。
请自行部署服务：[https://github.com/index-tts/index-tts](https://github.com/index-tts/index-tts)

使用时需将部署好的 TTS 服务地址作为参数传入。

### 📦 安装步骤

#### 1. 克隆仓库
```bash
git clone https://github.com/denganliang/mcp-srt-tts.git
cd mcp-srt-tts
```

#### 2. 安装依赖
```bash
pip install -r requirements.txt
```

### 🚀 在 Claude Code 中使用

使用 `mcp` 命令将此工具注册为 Skill。

**Windows 用户:**
```bash
claude mcp add srt-tts -- python "D:\你的路径\mcp-srt-tts\mcp_server.py"
```
*(注意：请务必使用 `mcp_server.py` 的绝对路径)*

**macOS / Linux 用户:**
```bash
claude mcp add srt-tts -- python "/你的路径/mcp-srt-tts/mcp_server.py"
```

#### 调用示例
添加成功后，你可以直接对 Claude 说：

> “帮我把 `video.srt` 转成语音，参考音色用 `my_voice.wav`，TTS服务地址是 `http://127.0.0.1:8000`”

Claude 会自动完成以下工作：
1. 解析 SRT 字幕。
2. 上传参考音频。
3. 逐行合成语音。
4. **自动调整时间轴**以防止语音重叠。
5. 输出最终的 `output.wav` 文件。

### 🛠 独立运行 (CLI 模式)

如果你不想通过 Claude 调用，也可以直接运行脚本：

```bash
python main.py <TTS服务URL> <SRT文件路径> <参考音频路径> [-o 输出文件名.wav]
```

## 📄 License

MIT License
