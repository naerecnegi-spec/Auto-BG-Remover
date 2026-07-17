@echo off
echo Building EXE...
pyinstaller -y --icon="icon.ico" --name "AI_BG_Remover_Heavy" --exclude-module tensorflow --exclude-module tensorboard --exclude-module keras --exclude-module pandas --exclude-module matplotlib --exclude-module IPython --exclude-module torch --exclude-module torchvision --copy-metadata pymatting --copy-metadata rembg --copy-metadata pooch --copy-metadata customtkinter --collect-all onnxruntime main.py
echo Done!
pause
