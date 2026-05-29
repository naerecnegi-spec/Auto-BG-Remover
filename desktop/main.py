import os
import threading
from pathlib import Path
from PIL import Image
import customtkinter as ctk
from tkinter import filedialog
from tkinterdnd2 import TkinterDnD, DND_FILES
from rembg import remove, new_session
import sys
import io

# --noconsoleオプションで起動した際に、ライブラリ内のprint出力でエラーになるのを防ぐ
if sys.stdout is None:
    sys.stdout = io.StringIO()
if sys.stderr is None:
    sys.stderr = io.StringIO()

# CustomTkinterとTkinterDnDを組み合わせたクラス
class CTk(ctk.CTk, TkinterDnD.DnDWrapper):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.TkdndVersion = TkinterDnD._require(self)

class App(CTk):
    def __init__(self):
        super().__init__()

        self.title("Auto BG Remover (Heavy Duty)")
        self.geometry("600x450")
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

        # プログレスとステータス
        self.status_label = ctk.CTkLabel(self.main_frame, text="待機中...", text_color="gray")
        self.status_label.pack(pady=(10, 0))

        self.progressbar = ctk.CTkProgressBar(self.main_frame, mode="indeterminate")
        self.progressbar.pack(fill="x", padx=40, pady=(5, 20))
        self.progressbar.set(0)

    def browse_output_dir(self):
        dir_path = filedialog.askdirectory()
        if dir_path:
            self.output_var.set(dir_path)

    def get_model_name(self):
        val = self.model_var.get()
        return self.MODELS.get(val, "u2net")

    def on_drop(self, event):
        if self.processing:
            return
            
        # TkinterDnDは複数ファイルの場合、中括弧で囲んで返してくることがあるのでパースする
        files = self.split_dnd_files(event.data)
        image_files = [f for f in files if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp'))]

        if not image_files:
            self.status_label.configure(text="画像ファイルが見つかりません", text_color="red")
            return

        self.processing = True
        self.progressbar.start()
        self.model_menu.configure(state="disabled")
        
        # 別スレッドで処理を開始
        threading.Thread(target=self.process_files, args=(image_files,), daemon=True).start()

    def split_dnd_files(self, data):
        # 簡易的なDnDファイルリストパース
        import re
        if '{' in data:
            return re.findall(r'\{([^}]+)\}', data)
        return data.split()

    def process_files(self, files):
        model_name = self.get_model_name()
        total = len(files)
        
        try:
            self.status_label.configure(text=f"AIモデル({model_name})をロード中... (初回はダウンロードに時間がかかります)", text_color="orange")
            
            # セッションの初期化・キャッシュ利用
            if model_name not in self.sessions:
                self.sessions[model_name] = new_session(model_name)
            session = self.sessions[model_name]

            for i, file_path in enumerate(files):
                self.status_label.configure(text=f"処理中... ({i+1}/{total}) - {Path(file_path).name}", text_color="white")
                
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
                with open(input_path, 'rb') as i_file:
                    input_data = i_file.read()
                    
                    if model_name == "isnet-anime":
                        # アニメ特化の場合は半透明(中途半端な透明度)を2値化して消す
                        img = Image.open(io.BytesIO(input_data))
                        out_img = remove(img, session=session)
                        
                        out_img = out_img.convert("RGBA")
                        r, g, b, a = out_img.split()
                        # アルファ値が128より大きければ完全不透明(255)、それ以外は完全透明(0)
                        a = a.point(lambda p: 255 if p > 128 else 0)
                        out_img = Image.merge("RGBA", (r, g, b, a))
                        
                        out_img.save(output_path, format="PNG")
                    else:
                        output_data = remove(input_data, session=session)
                        with open(output_path, 'wb') as o_file:
                            o_file.write(output_data)

            self.status_label.configure(text=f"完了！ {total}枚の画像を処理しました", text_color="green")

        except Exception as e:
            self.status_label.configure(text=f"エラーが発生しました: {str(e)}", text_color="red")
            print(e)
        finally:
            self.processing = False
            self.progressbar.stop()
            self.progressbar.set(1)
            self.model_menu.configure(state="normal")

if __name__ == "__main__":
    app = App()
    app.mainloop()
