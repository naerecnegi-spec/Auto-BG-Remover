import os
import threading
from pathlib import Path
from PIL import Image
import customtkinter as ctk
from tkinter import filedialog
from tkinterdnd2 import TkinterDnD, DND_FILES
import sys
import io
import re

# PyInstaller環境下でonnxruntime等のDLLが見つからない問題を解決
if hasattr(sys, '_MEIPASS'):
    try:
        # build_script.py で onnxruntime/capi に強制バンドルしているのでそこを探す
        ort_capi_path = os.path.join(sys._MEIPASS, "onnxruntime", "capi")
        os.add_dll_directory(ort_capi_path)
        os.environ["PATH"] = ort_capi_path + os.pathsep + os.environ.get("PATH", "")
        print(f"Added DLL search path: {ort_capi_path}", flush=True)
    except Exception as e:
        print(f"Error while setting DLL path: {e}", flush=True)

# 標準出力をフックしてダウンロード進捗を取得するためのモッククラス
class RedirectText(io.StringIO):
    def __init__(self, original_stream=None):
        super().__init__()
        self.callback = None
        self.log_callback = None
        self.original_stream = original_stream
    
    def write(self, s):
        if self.callback:
            try:
                self.callback(s)
            except: pass
            
        if self.log_callback:
            try:
                self.log_callback(s)
            except: pass
            
        if self.original_stream:
            try:
                self.original_stream.write(s)
                self.original_stream.flush()
            except: pass
            
        return super().write(s)

    def flush(self):
        if self.original_stream:
            try:
                self.original_stream.flush()
            except: pass
        super().flush()

# 無条件でリダイレクトし、元のストリームにも出力する
stdout_redirector = RedirectText(sys.stdout)
stderr_redirector = RedirectText(sys.stderr)

sys.stdout = stdout_redirector
sys.stderr = stderr_redirector

# CustomTkinterとTkinterDnDを組み合わせたクラス
class CTk(ctk.CTk, TkinterDnD.DnDWrapper):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.TkdndVersion = TkinterDnD._require(self)

class App(CTk):
    def __init__(self):
        super().__init__()

        self.title("Auto BG Remover (Heavy Duty)")
        self.geometry("600x750")
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        
        icon_path = Path(__file__).parent / "icon.ico"
        if icon_path.exists():
            self.iconbitmap(icon_path)

        self.sessions = {}
        self.processing = False

        self.MODELS = {
            "アニメ特化 (isnet-anime)": "isnet-anime",
            "実写人物特化 (u2net_human_seg)": "u2net_human_seg",
            "実写・物撮り高精度 (isnet-general)": "isnet-general-use",
            "汎用 (u2net)": "u2net"
        }

        self.setup_ui()

    def setup_ui(self):
        # メインフレーム
        self.main_frame = ctk.CTkFrame(self)
        self.main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        # タイトル
        self.title_label = ctk.CTkLabel(self.main_frame, text="✨ 人物特化 高精度切り抜きAI", font=ctk.CTkFont(size=24, weight="bold"))
        self.title_label.pack(pady=(20, 10))

        # モデル選択
        self.model_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.model_frame.pack(fill="x", padx=20, pady=10)
        
        self.model_label = ctk.CTkLabel(self.model_frame, text="使用するAIモデル:")
        self.model_label.pack(side="left", padx=(0, 10))

        self.model_var = ctk.StringVar(value="アニメ特化 (isnet-anime)")
        self.model_menu = ctk.CTkOptionMenu(
            self.model_frame, 
            variable=self.model_var,
            values=list(self.MODELS.keys()),
            width=250
        )
        self.model_menu.pack(side="left")

        # 保存先フォルダ選択
        self.output_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.output_frame.pack(fill="x", padx=20, pady=(0, 10))
        
        self.output_label = ctk.CTkLabel(self.output_frame, text="保存先フォルダ:")
        self.output_label.pack(side="left", padx=(0, 10))

        self.output_var = ctk.StringVar(value="")
        self.output_entry = ctk.CTkEntry(self.output_frame, textvariable=self.output_var, width=300, placeholder_text="(空の場合は元画像と同じ場所)")
        self.output_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))

        self.output_btn = ctk.CTkButton(self.output_frame, text="参照...", width=80, command=self.browse_output_dir)
        self.output_btn.pack(side="left")

        # ドラッグ＆ドロップエリア
        self.drop_area = ctk.CTkFrame(self.main_frame, corner_radius=15, fg_color=("gray85", "gray25"))
        self.drop_area.pack(fill="both", expand=True, padx=20, pady=10)
        
        self.drop_label = ctk.CTkLabel(self.drop_area, text="ここに画像ファイルを\nドラッグ＆ドロップ", font=ctk.CTkFont(size=18))
        self.drop_label.place(relx=0.5, rely=0.5, anchor="center")

        # ドラッグ＆ドロップの設定
        self.drop_area.drop_target_register(DND_FILES)
        self.drop_area.dnd_bind('<<Drop>>', self.on_drop)

        # ステータス
        self.status_label = ctk.CTkLabel(self.main_frame, text="画像ドロップ待機中... (準備OK)", font=ctk.CTkFont(size=12))
        self.status_label.pack(pady=10)

        self.progressbar = ctk.CTkProgressBar(self.main_frame, mode="determinate")
        self.progressbar.pack(fill="x", padx=40, pady=(5, 10))
        self.progressbar.set(0)

        # ログ画面
        self.log_textbox = ctk.CTkTextbox(self.main_frame, height=150, state="disabled", font=ctk.CTkFont(family="Consolas", size=10))
        self.log_textbox.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        # 標準出力からダウンロード進捗を取得するフックを登録
        stdout_redirector.callback = self.handle_stdout
        stderr_redirector.callback = self.handle_stdout
        stdout_redirector.log_callback = self.append_log
        stderr_redirector.log_callback = self.append_log

    def append_log(self, text):
        def _append():
            self.log_textbox.configure(state="normal")
            self.log_textbox.insert("end", text)
            self.log_textbox.see("end")
            self.log_textbox.configure(state="disabled")
        self.after(0, _append)

    def handle_stdout(self, text):
        import re
        # poochやtqdmが出力するパーセンテージ（例: " 45%|" " 45.0% "）を抽出
        match = re.search(r'(\d+(?:\.\d+)?)\s*%', text)
        if match:
            percent = float(match.group(1))
            self.after(0, self.update_download_progress, percent)

    def update_download_progress(self, percent):
        self.progressbar.configure(mode="determinate")
        self.progressbar.set(percent / 100.0)
        self.status_label.configure(text=f"AIモデルをダウンロード中... {percent:.1f}%", text_color="orange")

    def browse_output_dir(self):
        dir_path = filedialog.askdirectory()
        if dir_path:
            self.output_var.set(dir_path)

    def get_model_name(self):
        val = self.model_var.get()
        return self.MODELS.get(val, "u2net")

    def on_drop(self, event):
        try:
            if self.processing:
                return
                
            files = self.split_dnd_files(event.data)
            image_files = [f for f in files if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp'))]

            if not image_files:
                self.status_label.configure(text="画像ファイルが見つかりません", text_color="red")
                return

            self.processing = True
            self.progressbar.set(0)
            self.model_menu.configure(state="disabled")
            
            # 別スレッドで処理を開始
            print("on_drop: スレッド起動準備完了", flush=True)
            threading.Thread(target=self.process_files, args=(image_files,), daemon=True).start()
        except Exception as e:
            print(f"on_drop エラー: {e}", flush=True)

    def split_dnd_files(self, data):
        # 簡易的なDnDファイルリストパース
        import re
        if '{' in data:
            return re.findall(r'\{([^}]+)\}', data)
        return data.split()

    def process_files(self, files):
        import time
        import traceback
        
        print("====== 処理スレッド開始 ======")
        model_name = self.get_model_name()
        total = len(files)
        
        try:
            self.after(0, lambda: self.progressbar.configure(mode="indeterminate"))
            self.after(0, self.progressbar.start)
            self.after(0, lambda: self.status_label.configure(text=f"AIモデル({model_name})を準備中... (初回は時間がかかります)", text_color="orange"))
            
            # UIの更新を確実に反映させるための強制待機
            print("UI描画キューの処理を待機します (0.5秒)")
            time.sleep(0.5)
            
            print("rembg ライブラリのインポートを開始します...")
            from rembg import remove, new_session
            print("rembg ライブラリのインポートが完了しました")
            
            # セッションの初期化・キャッシュ利用
            if model_name not in self.sessions:
                print(f"ONNXセッションの生成を開始します: モデル={model_name}")
                import onnxruntime as ort
                ort.set_default_logger_severity(0) # 0: Verbose, 1: Info, 2: Warning, 3: Error, 4: Fatal
                print("利用可能なONNXプロバイダ:", ort.get_available_providers())
                
                self.sessions[model_name] = new_session(
                    model_name,
                    providers=['CUDAExecutionProvider']
                )
                print("ONNXセッションの生成に成功しました")
            session = self.sessions[model_name]

            self.after(0, self.progressbar.stop)
            self.after(0, lambda: self.progressbar.configure(mode="determinate"))

            for i, file_path in enumerate(files):
                # 画像処理の進捗を更新
                self.after(0, self.progressbar.set, i / total)
                self.after(0, lambda i=i: self.status_label.configure(text=f"処理中... ({i+1}/{total}) - {Path(file_path).name}", text_color="white"))
                
                input_path = Path(file_path)
                
                # 保存先の決定
                out_dir_str = self.output_var.get().strip()
                if out_dir_str:
                    out_dir = Path(out_dir_str)
                    # ディレクトリが存在しない場合は作成
                    out_dir.mkdir(parents=True, exist_ok=True)
                else:
                    out_dir = input_path.parent
                    
                output_path = out_dir / f"removed_{input_path.stem}.png"

                # 処理実行
                print(f"[{i+1}/{total}] {input_path.name} の背景削除を実行中...")
                with open(input_path, 'rb') as i_file:
                    input_data = i_file.read()
                    
                    # 全モデル共通で半透明(中途半端な透明度)を2値化して消す
                    img = Image.open(io.BytesIO(input_data))
                    out_img = remove(img, session=session)
                    
                    out_img = out_img.convert("RGBA")
                    r, g, b, a = out_img.split()
                    # アルファ値が128より大きければ完全不透明(255)、それ以外は完全透明(0)
                    a = a.point(lambda p: 255 if p > 128 else 0)
                    out_img = Image.merge("RGBA", (r, g, b, a))
                    
                    out_img.save(output_path, format="PNG")
                    print(f"[{i+1}/{total}] {output_path.name} の保存に成功しました")

            self.after(0, lambda: self.status_label.configure(text=f"完了！ {total}枚の画像を処理しました (画像ドロップ待機中...)", text_color="green"))
            print("====== すべての処理が正常に完了しました ======")
            
        except Exception as e:
            print(f"\n【重大なエラー発生】: {e}")
            import traceback
            traceback.print_exc()
            e_msg = str(e)
            self.after(0, lambda msg=e_msg: self.status_label.configure(text=f"処理中にエラーが発生しました: {msg}", text_color="red"))
        finally:
            self.processing = False
            self.after(0, lambda: self.model_menu.configure(state="normal"))
            self.after(0, self.progressbar.stop)
            self.after(0, lambda: self.progressbar.configure(mode="determinate"))
            self.after(0, lambda: self.progressbar.set(1.0))

if __name__ == "__main__":
    app = App()
    app.mainloop()
