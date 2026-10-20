# -*- coding: utf-8 -*-
import subprocess
import sys
import os

# Add source path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dictare_transcriere_romana import cai, instalare

# Run LibreOffice installation
cai.pregateste_directoare()

# Import the libreoffice module and run installation
from dictare_transcriere_romana.instalare import libreoffice

result = libreoffice.instaleaza(
    progres=lambda mesaj, fractiune: print(f"Progress {fractiune:.0%}: {mesaj}")
)

with open("libreoffice_install_out.txt", "w", encoding="utf-8") as f:
    f.write("Return value: " + str(result) + "\n")

# Check what was installed
lo_path = cai.libreoffice_soffice()
with open("libreoffice_check.txt", "w", encoding="utf-8") as f:
    f.write("soffice path: " + str(lo_path) + "\n")
    f.write("soffice exists: " + str(lo_path.exists()) + "\n")
    
    # Check for Romanian language pack
    if lo_path.exists():
        # Get LibreOffice version
        try:
            ver_result = subprocess.run([str(lo_path), "--version"], capture_output=True, text=True, timeout=30)
            f.write("Version: " + ver_result.stdout.strip() + "\n")
            f.write("Version stderr: " + ver_result.stderr.strip() + "\n")
        except Exception as e:
            f.write("Version error: " + str(e) + "\n")
        
        # Check for Romanian dictionary
        lo_dir = lo_path.parent
        f.write("LibreOffice dir: " + str(lo_dir) + "\n")
        for root, dirs, files in os.walk(lo_dir):
            for file in files:
                if "ro" in file.lower() and ("dict" in file.lower() or "lang" in file.lower() or "rom" in file.lower()):
                    f.write("Found RO related: " + os.path.join(root, file) + "\n")