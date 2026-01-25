from mcp.server.fastmcp import FastMCP
import os
import sys

# Import the logic from main.py
import main

# Initialize FastMCP server
mcp = FastMCP("TTS-SRT-Skill")

@mcp.tool()
def convert_srt_to_audio(
    tts_url: str,
    srt_file_path: str,
    reference_audio_path: str,
    output_path: str = "output.wav"
) -> str:
    """
    Convert an SRT subtitle file to a single audio file using a remote TTS service.

    Args:
        tts_url: The URL of the TTS service (e.g., http://localhost:8000).
        srt_file_path: Absolute path to the .srt file.
        reference_audio_path: Absolute path to the reference audio file for voice cloning.
        output_path: Path where the generated WAV file will be saved.

    Returns:
        A message indicating success or failure, with the path to the output file.
    """
    try:
        # Resolve absolute paths to ensure robustness
        srt_file_path = os.path.abspath(srt_file_path)
        reference_audio_path = os.path.abspath(reference_audio_path)
        output_path = os.path.abspath(output_path)

        # Run the conversion
        main.srt_to_audio(tts_url, srt_file_path, reference_audio_path, output_path)

        if os.path.exists(output_path):
            return f"Successfully generated audio at: {output_path}"
        else:
            return "Error: Output file was not created. Check stderr logs for details."
    except Exception as e:
        return f"Error executing srt_to_audio: {str(e)}"

if __name__ == "__main__":
    mcp.run()
