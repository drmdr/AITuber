# プロジェクト仕様書

## 1. 概要

このプロジェクトは、AIを活用したVTuberシステム「AITuber」と、連携するX(旧Twitter)自動投稿システム「X Poster」から構成されます。

- **AITuberシステム**: ユーザーとの対話、キャラクターの感情表現、音声合成、外部API連携などを通じて、インタラクティブなVTuber体験を提供します。
- **X Posterシステム**: Google Sheetsから情報を取得し、AI(Gemini)が生成したコメントと共に、定期的にX(旧Twitter)へ自動投稿を行います。

## 2. システム構成

## 3. 共通要件・優先事項

### 3.1. キャラクター設定の厳守

- **最優先事項**: AITuberおよびX PosterのAIが生成する応答は、`config.local.json` または `config.public.json` で定義されたキャラクター設定に厳密に従う必要があります。AIの応答がキャラクター設定から逸脱することは、本システムの品質を著しく損なうため、常に設定を最優先で反映させるように実装してください。

#### 3.1.1. 基本設定（モナミン）

- **名前**: モナミン
- **一人称**: ウチ
- **口調**: フレンドリーで、少しおちゃらけた「えせ関西弁」を使用します。詳細は `config.local.json` の `persona` および `guidelines` を参照してください。
- **挨拶**: `Gmonamin! ウチがモナミンやで！なんかおもろい話でもせえへん？`

#### 3.1.2. 絶対的な禁止・遵守事項

1.  **AIと名乗らない**:
    - キャラクターは自身を「AI」「アシスタント」「プログラム」など、人工的な存在として言及してはなりません。あくまで「モナミン」という一人のキャラクターとして振る舞います。

2.  **設定ファイルの尊重**:
    - `config.local.json` および `config.public.json` に記述された設定は、**ユーザーからの明確な変更指示がない限り、絶対に変更してはなりません。**

3.  **キャラクター定義の優先**:
    - 実装や応答生成において、この仕様書および設定ファイルに定義されたキャラクター設定が、あらゆるロジックや判断に優先されます。不明な点や定義が不十分な点（例：「えせ関西弁」のニュアンス）については、勝手に解釈せず、必ずユーザーに確認してください。

### 3.2. 使用技術の指定

- **音声合成**: AITuberシステムの音声合成には **Gemini API TTS (Google AI Studio TTS)** のみを使用します。Google Cloud Text-to-Speech APIは使用しません。
- この方針は、APIの利用を一本化し、コスト管理と実装の複雑さを軽減することを目的とします。

### 3.3. 音声合成モジュール (`google_aistudio_tts.py`)

音声合成機能は `google_aistudio_tts.py` に実装されています。このモジュールは、Google Gemini APIの公式SDKを利用しており、公式ドキュメントに準拠した安定した実装です。

**重要:** このファイルはシステムの安定動作の要であるため、APIの仕様変更など、明確な理由がない限りは**原則として改変しないでください。**

### 2.1. AITuberシステム

- **メインスクリプト**: `AITuber.py`
- **設定ファイル**: `config.local.json` (ローカル実行時、Git管理外)
  - APIキー (OpenAI, VoiceVox, Googleなど)
  - キャラクター設定 (名前、ペルソナなど)
  - 動作設定 (応答パターン、感情閾値など)
- **主要機能**:
  - テキストベースのチャット応答
  - 感情分析とそれに応じたキャラクターアニメーション制御 (仮)
  - 音声合成 (Gemini API TTS / Google AI Studio TTS)
  - 外部情報取得 (天気、ニュースなど、未実装の可能性あり)
- **使用する可能性のある外部サービス**:
  - OpenAI API (チャット応答生成)
  - VoiceVox API または Style-Bert-VITS2 (日本語音声合成)
  - Google Cloud Speech-to-Text (音声認識、未実装の可能性あり)
  - Gemini API TTS (Google AI Studio TTS)
  - その他、連携する可能性のあるAPI
- **Google Cloud Project ID**: `*******` (monamin-aituber)

### 2.2. X Posterシステム

- **メインスクリプト**: `x_poster/morning_greet_poster.py`
- **設定ファイル**: `config.public.json` (公開設定、GitHub管理)
  - X APIキー/トークン (環境変数経由で設定)
  - Google Sheets API認証情報 (環境変数経由で設定)
  - Gemini APIキー (環境変数経由で設定)
  - スプレッドシートID (環境変数またはconfig.public.json)
  - キャラクター設定 (名前、ペルソナ)
  - 投稿スケジュール (GitHub Actionsワークフローで定義)
- **主要機能**:
  - Google Sheetsからのデータ取得 (サービス名、概要など)
  - Gemini APIによるカテゴリ分類と紹介コメント生成 (日本語・英語)
  - X(旧Twitter)への自動投稿
- **使用する外部サービス**:
  - X API (ツイート投稿)
  - Google Sheets API (データソース)
  - Google Cloud (Gemini API, サービスアカウント認証)
- **Google Cloud Project ID**: `********351` (aituber-post)
- **サービスアカウントキー**: `credentials/aituber-post-52b1cd18b086.json` (ローカルテスト時、またはGitHub Actionsで `GOOGLE_APPLICATION_CREDENTIALS` 環境変数に設定)

## 3. 設定ファイル戦略

- **AITuberシステム**: ローカル実行専用の `config.local.json` を使用します。このファイルは機密情報を含むため、Gitリポジトリにはコミットしません。`.gitignore` で管理対象外とします。
- **X Posterシステム**: 
  - **公開設定**: `config.public.json` に記述し、GitHubリポジトリで管理します。
  - **機密情報**: APIキーや認証情報は、GitHub ActionsのSecretsに登録し、ワークフロー実行時に環境変数としてスクリプトに渡されます。
  - **ローカルテスト**: X Posterをローカルでテストする場合、必要な環境変数 (例: `GOOGLE_APPLICATION_CREDENTIALS`, `X_API_KEY` など) を手動でターミナルに設定する必要があります。

## 4. 実行方法

### 4.1. AITuberシステム

- `run_AITuber.bat` を実行 (Windows環境)
- または、Python仮想環境を有効化した後、`python AITuber.py` を実行。

### 4.2. X Posterシステム

- **自動実行**: GitHub Actionsのワークフロー (`.github/workflows/x_auto_tweet.yml`) により、スケジュール実行またはmasterブランチへのプッシュ時に自動実行されます。
- **手動実行 (ローカル)**: 必要な環境変数を設定した後、`python x_poster/morning_greet_poster.py` を実行。

## 5. 今後の課題・改善点

- AITuberシステムの不具合修正
- AITuberシステムのコードベースのGitHub管理への移行
- ドキュメントの拡充 (READMEの更新など)
- コード内のコメント整理と可読性向上
- Style-Bert-VITS2のモデルファイルなど、大容量ファイルのGit LFSなどでの管理検討 (または`.gitignore`)
