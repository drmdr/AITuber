# AITuber with Style-Bert-VITS2

このプロジェクトは、AITuberKitとStyle-Bert-VITS2を組み合わせて、高品質な音声合成を使ったバーチャルYouTuberシステムを構築するためのものです。

## セットアップ

1. 必要なライブラリをインストールします：
```
pip install -r requirements.txt
```

2. Style-Bert-VITS2のモデルをダウンロードして、`models`ディレクトリに配置します。

3. `config.json`ファイルを編集して、使用するモデルとパラメータを設定します。

## 使い方

```
python main.py
```

## 機能

- AITuberKitを使用したアバターの制御
- Style-Bert-VITS2を使用した高品質な音声合成
- テキストから音声への変換と自動リップシンク

## 注意事項

- Style-Bert-VITS2のモデルは別途ダウンロードする必要があります。
- GPUがあると処理が高速化されます。
