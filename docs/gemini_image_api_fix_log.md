# Gemini画像生成API修正作業ログ

## 概要

AITuberのX（Twitter）投稿システムにおいて、Gemini APIを使った画像生成機能が正常に動作せず、画像が投稿されない問題の修正作業記録です。

## 問題点

1. Gemini APIの画像生成呼び出し方法が正しくなく、エラーが発生していた
2. `google-generativeai`ライブラリのバージョン不整合による問題
3. 画像生成後の投稿処理までの一連の流れに問題がある可能性

## 修正作業の流れ

### 1. 公式ドキュメントに基づく修正（最初の試み）

最初に公式ドキュメントに基づいて以下の修正を行いました：

- `genai.Client()`を使用
- モデル名を`gemini-2.0-flash-preview-image-generation`に設定
- `response_modalities=['TEXT', 'IMAGE']`を指定
- `inline_data.data`から画像データを取得

```python
# 公式ドキュメントに従った画像生成の呼び出し方法
response = client.models.generate_content(
    model="gemini-2.0-flash-preview-image-generation",
    contents=full_prompt,
    config=genai.types.GenerateContentConfig(
        response_modalities=['TEXT', 'IMAGE']
    )
)

# 画像データの抽出（公式ドキュメントに従った方法）
image_part = None
for part in response.candidates[0].content.parts:
    if hasattr(part, 'inline_data'):
        image_part = part
        break
```

### 2. ユーザー提供のブログ実装例に基づく修正（二回目の試み）

ユーザーから提供されたブログ実装例に基づいて修正：

- `genai.Client()`を使用（維持）
- モデル名を`models/gemini-2.0-flash-exp`に変更
- `response_modalities`を`['Text', 'Image']`に変更（大文字小文字の違いに注意）
- テキスト応答があれば、それもログに記録するよう改善

```python
# ユーザー提供のコード例に基づく画像生成リクエスト
response = client.models.generate_content(
    model="models/gemini-2.0-flash-exp",
    contents=full_prompt,
    config=types.GenerateContentConfig(response_modalities=['Text', 'Image'])
)

# 画像データの抽出（ユーザー提供のコード例に基づく方法）
image_part = None
for part in response.candidates[0].content.parts:
    if part.text is not None:
        logging.info(f"Text response from Gemini: {part.text}")
    elif part.inline_data is not None:
        image_part = part
        break
```

### 3. ライブラリバージョン不整合への対応（三回目の試み）

GitHub Actionsの環境で以下のエラーが発生：
```
ERROR - An error occurred during image generation with Gemini: module 'google.generativeai' has no attribute 'Client'
```

古いバージョンの`google-generativeai`ライブラリでも動作するように修正：

- `genai.Client()`の代わりに`genai.GenerativeModel()`を使用
- モデル名を`gemini-1.5-flash`に変更（古いバージョンでサポートされているモデル）
- 画像データの抽出方法を複数パターン対応（`inline_data.data`と`data`の両方をチェック）
- エラーハンドリングを強化

```python
# GenerativeModelを使用（古いバージョンのライブラリでも動作）
genai.configure(api_key=config.get('gemini_api_key'))
model = genai.GenerativeModel("gemini-1.5-flash")

# 古いバージョンのライブラリでも動作する画像生成リクエスト
generation_config = genai.types.GenerationConfig(
    candidate_count=1,
    temperature=0.4,
    top_p=1,
    top_k=32,
)
response = model.generate_content(
    contents=full_prompt,
    generation_config=generation_config
)

# レスポンスから画像データを抽出（複数パターン対応）
if hasattr(response, 'candidates') and response.candidates:
    parts = response.candidates[0].content.parts
    for part in parts:
        if hasattr(part, 'text') and part.text:
            logging.info(f"Text response from Gemini: {part.text}")
        # 画像データの抽出方法はバージョンによって異なる可能性があるため、複数のパターンを試す
        if hasattr(part, 'inline_data') and part.inline_data:
            image_data = part.inline_data.data
            break
        elif hasattr(part, 'data') and part.data:
            image_data = part.data
            break
```

## 現在の状況と今後の課題

- 古いバージョンの`google-generativeai`ライブラリでも動作するコードに修正済み
- GitHub Actionsでの実行結果を確認中
- 画像生成後の投稿処理（Twitter API連携部分）の確認が必要
- 以下の点について追加調査が必要：
  1. `image_data`変数の初期化（現在は未定義の可能性）
  2. Twitter投稿処理での画像添付部分の確認
  3. Gemini APIキーの権限設定（画像生成が許可されているか）

## 参考情報

- `requirements.txt`には`google-generativeai`のバージョン指定がない
- GitHub Actionsの環境では古いバージョンのライブラリがインストールされている可能性
- 画像生成には適切なAPIキーと権限が必要
- 画像生成・保存・Twitter投稿の一連の流れが正しく動作する必要がある
