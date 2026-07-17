import os
import sys
import onnxruntime
import PyInstaller.__main__

print("====== Starting Custom Build Script ======")

# onnxruntime のインストールディレクトリを動的に特定
ort_dir = onnxruntime.__path__[0]
capi_dir = os.path.join(ort_dir, "capi")

print(f"onnxruntime installed at: {ort_dir}")
print(f"Searching for DLLs in: {capi_dir}")

add_binaries = []
if os.path.exists(capi_dir):
    for f in os.listdir(capi_dir):
        if f.lower().endswith('.dll') or f.lower().endswith('.pyd'):
            full_path = os.path.join(capi_dir, f)
            # 必須のDLLを強制的に "onnxruntime/capi" フォルダとしてバンドルする
            # Windowsの PyInstaller ではパスの区切り文字として ; を使用
            add_binaries.append(f"--add-binary={full_path};onnxruntime/capi")
            print(f"  -> Force bundling: {f}")
else:
    print("WARNING: capi directory not found!")

# PyInstaller の引数を構築
args = [
    'main.py',
    '--name=AI_BG_Remover_Heavy',
    '--icon=icon.ico',
    '-y',
    '--exclude-module=tensorflow',
    '--exclude-module=tensorboard',
    '--exclude-module=keras',
    '--exclude-module=pandas',
    '--exclude-module=matplotlib',
    '--exclude-module=IPython',
    '--exclude-module=torch',
    '--exclude-module=torchvision',
    '--copy-metadata=pymatting',
    '--copy-metadata=rembg',
    '--copy-metadata=pooch',
    '--copy-metadata=customtkinter',
    '--collect-submodules=onnxruntime', # スクリプトモジュールのみ収集
]

args.extend(add_binaries)

print("Starting PyInstaller...")
PyInstaller.__main__.run(args)
print("Build Complete.")
