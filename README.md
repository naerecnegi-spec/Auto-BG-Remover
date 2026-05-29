# Auto BG Remover

高精度なAI背景切り抜きツール。ブラウザ上で動作する軽量なWeb版と、ローカルで本格的な処理が行える高機能なWindows専用Desktop版を提供しています。

## ディレクトリ構成

- `web/` : ブラウザ完結型のWeb版ツール (Vite + JavaScript)
- `desktop/` : Windows向けの本格的EXE版ツール (Python + rembg)

## Web版の使い方
1. `web/` フォルダに移動し、`npm install` を実行します。
2. `npm run dev` でローカルサーバーを立ち上げます。
3. `npm run build` で本番用ファイルを `dist/` に生成し、Cloudflare Pagesなどにアップロードできます。

## Desktop版の使い方 (開発者向け)
1. `desktop/` フォルダに移動し、`pip install -r requirements.txt` を実行します。
2. `python main.py` でアプリを起動できます。
3. EXEファイルを作成する場合は、`build.bat` を実行してください。（※GitHub上で自動ビルド・配布する仕組みも用意しています）
