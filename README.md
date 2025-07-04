# AITuber & X Poster Project

このプロジェクトは、AIを活用したVTuberシステム「AITuber」と、連携するX(旧Twitter)自動投稿システム「X Poster」を含みます。

## 概要

- **AITuberシステム**: ユーザーとのインタラクティブな対話を実現するVTuberアプリケーションです。キャラクターの感情表現や音声合成機能などを備えています。
- **X Posterシステム**: Google Sheetsから取得した情報を元に、AI(Gemini)が紹介文を生成し、X(旧Twitter)へ定期的に自動投稿します。

## 主な技術スタック

- Python
- OpenAI API (AITuberの対話生成)
- Gemini API TTS (Google AI Studio TTS) (音声合成)
- Tweepy (X API連携)
- gspread (Google Sheets API連携)
- Google Generative AI (Gemini API)
- GitHub Actions (X Posterの自動実行)

## セットアップ方法

### 1. リポジトリのクローン

```bash
git clone https://github.com/drmdr/AITuber.git
cd AITuber
```

### 2. 仮想環境の作成と有効化

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
# source .venv/bin/activate
```

### 3. 依存ライブラリのインストール

プロジェクトルートの `requirements.txt` と `x_poster` ディレクトリ内の `requirements.txt` の両方をインストールする必要があります。

```bash
pip install -r requirements.txt
pip install -r x_poster/requirements.txt
```

### 4. 設定ファイルの準備

- **AITuberシステム用**: プロジェクトのルートに `config.local.json` ファイルを作成し、以下の内容を参考に設定してください。このファイルは `.gitignore` に登録されているため、Gitの管理対象外です。

  この設定ファイルでは、AITuberが話す各言語（日本語、英語、スペイン語）のキャラクター名、ペルソナ（性格設定）、起動時の挨拶などを定義します。

  ```json
  // config.local.json の例 (AITuber用)
  {
    "gemini_api_key": "YOUR_GEMINI_API_KEY",
    "google_cloud_project_id_aituber": "415545278337",

    "languages": {
        "ja": {
            "character_name": "モナミン",
            "persona": "あなたは親しみやすいAIアシスタント、モナミンです。",
            "greeting": "こんにちは！モナミンだよ！何かお話しませんか？",
            "guidelines": [
                "常に日本語で応答してください。",
                "ユーザーの質問には、丁寧かつ簡潔に答えてください。",
                "自分の名前は「モナミン」です。"
            ],
            "self_introduction_triggers": ["自己紹介して", "あなたについて教えて", "名前は？"],
            "self_introduction_template": "こんにちは！私はAIチューバーのモナミンです。皆さんとお話しできるのを楽しみにしています！"
        },
        "en": {
            "character_name": "Monamin",
            "persona": "You are a friendly AI assistant, Monamin.",
            "greeting": "Hello! I'm Monamin! What would you like to talk about?",
            "guidelines": [
                "Always respond in English.",
                "Answer user questions politely and concisely.",
                "My name is Monamin."
            ],
            "self_introduction_triggers": ["introduce yourself", "tell me about you", "what is your name"],
            "self_introduction_template": "Hello! I'm Monamin, the AITuber. I'm excited to talk with all of you!"
        },
        "es": {
            "character_name": "Monamin",
            "persona": "Eres un amigable asistente de IA, Monamin.",
            "greeting": "¡Hola! ¡Soy Monamin! ¿De qué te gustaría hablar?",
            "guidelines": [
                "Responde siempre en español.",
                "Responde a las preguntas de los usuarios de forma educada y concisa.",
                "Mi nombre es Monamin."
            ],
            "self_introduction_triggers": ["preséntate", "háblame de ti", "¿cómo te llamas?"],
            "self_introduction_template": "¡Hola! Soy Monamin, la AITuber. ¡Estoy emocionada de hablar con todos ustedes!"
        }
    }
  }
  ```

- **X Posterシステム用**: `config.public.json` はリポジトリに含まれています。機密情報はGitHub ActionsのSecrets経由で渡されます。ローカルでテスト実行する場合は、以下の環境変数を設定してください。
  - `GOOGLE_APPLICATION_CREDENTIALS`: Google CloudサービスアカウントキーのJSONファイルへのパス (例: `credentials/aituber-post-52b1cd18b086.json`)
  - `GEMINI_API_KEY`: Google Gemini APIキー
  - `X_API_KEY`: X (Twitter) APIキー
  - `X_API_SECRET_KEY`: X (Twitter) APIシークレットキー
  - `X_ACCESS_TOKEN`: X (Twitter) アクセストークン
  - `X_ACCESS_TOKEN_SECRET`: X (Twitter) アクセストークンシークレット
  - `SPREADSHEET_ID`: 投稿ネタを管理しているGoogle SheetsのスプレッドシートID

  `.env` ファイルを作成してローカル環境変数を管理することも可能です (X Posterスクリプトは `.env` を読み込みます)。
  ```env
  # .env ファイルの例 (X Posterローカル実行用)
  GOOGLE_APPLICATION_CREDENTIALS="credentials/aituber-post-52b1cd18b086.json"
  GEMINI_API_KEY="YOUR_GEMINI_API_KEY"
  X_API_KEY="YOUR_X_API_KEY"
  X_API_SECRET_KEY="YOUR_X_API_SECRET_KEY"
  X_ACCESS_TOKEN="YOUR_X_ACCESS_TOKEN"
  X_ACCESS_TOKEN_SECRET="YOUR_X_ACCESS_TOKEN_SECRET"
  SPREADSHEET_ID="YOUR_SPREADSHEET_ID"
  ```

### 5. 認証情報ファイル

- **X Posterシステム用Google Cloudサービスアカウントキー**: `credentials/aituber-post-52b1cd18b086.json` を配置します。このファイルはGoogle Cloud Project ID `737410221351` に関連付けられています。

## X Posterシステムの機能

- **概要**: Google Sheetsから定期的にサービス情報を取得し、AI(Gemini)が魅力的な紹介ツイートを生成してX(旧Twitter)に自動投稿します。
- **ツイート内容の動的生成**: 
    - サービスの概要を分析し、そのサービスが「NFT関連」か「一般的なWebサービス/DApp」かを自動で判定します。
    - 判定結果に基づき、ツイートの結びの言葉を変化させます。
        - **NFT関連の場合**: 「持ってる人いる？」「ミントした？」といった、コミュニティに問いかけるような言葉を選びます。
        - **その他の場合**: 「使ったことある？」「みんなはどう思う？」といった、利用体験を尋ねる言葉を選びます。
    - この機能は `x_poster/morning_greet_poster.py` 内のプロンプトエンジニアリングによって実現されています。
- **多言語対応**: 日本語のツイートを投稿した後、一定時間をおいてから、独立したツイートとして英語のツイートを投稿します。
- **画像生成機能**: Vertex AIの画像生成モデル(Imagen)を利用し、ツイート内容に合わせた画像をAIが生成して添付します。この機能は設定ファイル (`config.public.json`) で有効/無効を切り替えることができます。

## 実行方法

### AITuberシステム

- Windows: 起動したい言語に応じて、以下のバッチファイルのいずれかをダブルクリックして起動します。
     - **日本語で起動**: `run_AITuber.bat`
     - **英語で起動**: `run_AITuber_EN.bat`
     - **スペイン語で起動**: `run_AITuber_ES.bat`
- または、仮想環境を有効化した後、ターミナルで以下を実行します。
  ```bash
  python AITuber.py
  ```

### X Posterシステム

- **自動実行**: GitHub Actionsにより、masterブランチへのプッシュ時、またはスケジュールされた時間に自動的に実行されます (詳細は `.github/workflows/x_auto_tweet.yml` を参照)。
- **手動実行 (ローカル)**: 必要な環境変数を設定した後、ターミナルで以下を実行します。
  ```bash
  python x_poster/morning_greet_poster.py
  ```
  手動実行時に強制的に投稿を行いたい場合は、環境変数 `FORCE_POST=true` を設定してください。

## ドキュメント

より詳細な情報については、`docs` ディレクトリ内のドキュメントを参照してください。

- `docs/structure.md`: プロジェクトのファイル構造
- `docs/spec.md`: プロジェクトの仕様

## 貢献

バグ報告や改善提案は、GitHubのIssuesにお願いします。

## ライセンス

(ライセンス情報をここに記述)
