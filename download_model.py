# -*- coding: utf-8 -*-
import subprocess
import sys
import os

_DATE = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "Dictare&Transcriere Română")
python_venv = os.path.join(_DATE, "mediu", "Scripts", "python.exe")
model_path = os.path.join(_DATE, "model", "large-v3-turbo.pt")
model_dir = os.path.join(_DATE, "model")

os.makedirs(model_dir, exist_ok=True)

# Download model using whisper
result = subprocess.run([
    python_venv, "-c",
    "import whisper; model = whisper.load_model('large-v3-turbo', download_root=r'" + model_dir + r"'); print('Model loaded successfully')"
], capture_output=True, text=True, timeout=7200)

with open("download_model_out.txt", "w", encoding="utf-8") as f:
    f.write("returncode: " + str(result.returncode) + "\n")
    f.write("stdout: " + result.stdout + "\n")
    f.write("stderr: " + result.stderr + "\n")

# Check file exists and size
import os
if os.path.exists(model_path):
    size = os.path.getsize(model_path)
    with open("model_info.txt", "w", encoding="utf-8") as f:
        f.write("Model path: " + model_path + "\n")
        f.write("Model size: " + str(size) + " bytes (" + str(round(size/1024/1024, 1)) + " MB)\n")
        f.write("Model exists: True\n")
else:
    with open("model_info.txt", "w", encoding="utf-8") as f:
        f.write("Model exists: False\n")

# Test transcription with a simple audio file (we'll create a test)
# First check if model loads and can transcribe
test_code = """
import whisper
import numpy as np
model = whisper.load_model('large-v3-turbo', download_root=r'" + model_dir + r"')
print('Model loaded for transcription test')

# Create a simple test - 1 second of silence at 16kHz
audio = np.zeros(16000, dtype=np.float32)
result = model.transcribe(audio, language='ro', fp16=False)
print('Transcription result:', result['text'])
"""

result2 = subprocess.run([python_venv, "-c", test_code], capture_output=True, text=True, timeout=300)
with open("transcribe_test_out.txt", "w", encoding="utf-8") as f:
    f.write("returncode: " + str(result2.returncode) + "\n")
    f.write("stdout: " + result2.stdout + "\n")
    f.write("stderr: " + result2.stderr + "\n")