# プロジェクトファイル構造

このドキュメントでは、AITuberプロジェクトの主要なファイルとディレクトリの構造について説明します。

```
c:\Users\drmdr\Documents\Surfwind\AITuber
├── .env                                # 環境変数設定ファイル (ローカルでのみ使用)
├── .git                                # Gitリポジトリ管理用ディレクトリ
├── .github                             # GitHub Actions ワークフロー定義
│   └── workflows
│       └── x_auto_tweet.yml            # X(旧Twitter)自動投稿ワークフロー
├── .gitignore                          # Gitの追跡対象外ファイル/ディレクトリ指定
├── .venv                               # Python仮想環境 (通常.gitignore対象)
├── AITuber.py                          # AITuberシステムのメインスクリプト
├── backend                             # (詳細不明、おそらくWebバックエンド関連)
├── config.json                         # 設定ファイルのベース (公開情報)
├── config.local.json                   # AITuberシステム用ローカル設定 (Git管理外)
├── config.public.json                  # X Posterシステム用公開設定
├── credentials                         # 認証情報ファイル格納ディレクトリ
│   └── aituber-post-52b1cd18b086.json  # X Poster用Google Cloudサービスアカウントキー
├── docs                                # プロジェクトドキュメント格納用 (このディレクトリ)
│   ├── structure.md                    # ファイル構造 (このファイル)
│   └── spec.md                         # 仕様書
├── google_aistudio_tts.py              # Google AI Studio TTS関連スクリプト
├── logs                                # ログファイル格納ディレクトリ
├── requirements.txt                    # Python依存ライブラリ (AITuberシステム用)
├── response_patterns.json              # AITuberの応答パターン定義
├── run_AITuber.bat                     # AITuber実行用バッチファイル
├── style-bert-vits2                    # 音声合成ライブラリ (Style-Bert-VITS2)
├── x_poster                            # X(旧Twitter)投稿システム関連
│   ├── morning_greet_poster.py         # 朝の挨拶投稿スクリプト
│   ├── requirements.txt                # X Posterシステム用Python依存ライブラリ
│   └── last_post_timestamp.txt       # 最終投稿日時記録ファイル
└── README.md                           # プロジェクト概要、セットアップ方法など
```

## 主要ディレクトリ/ファイル解説

- **`.github/workflows/`**: GitHub Actionsによる自動化処理を定義します。現在はX(旧Twitter)への自動投稿処理 (`x_auto_tweet.yml`) が格納されています。
- **`AITuber.py`**: VTuberとしてのキャラクターの動作、対話処理、各種API連携など、AITuberシステムのコア機能が含まれるメインスクリプトです。
- **`config.local.json`**: AITuberシステムがローカル環境で動作する際に使用する設定ファイルです。APIキーなどの機密情報を含むため、Gitの管理対象外とします。
- **`config.public.json`**: X Posterシステムが使用する設定ファイルです。公開可能な設定情報を記述し、GitHubで管理します。機密情報はGitHub ActionsのSecrets経由で環境変数として渡されます。
- **`credentials/`**: 外部サービス連携に必要な認証情報ファイル（サービスアカウントキーなど）を格納します。
- **`docs/`**: このプロジェクトに関するドキュメントを格納します。
- **`style-bert-vits2/`**: 高品質な音声合成を実現するためのライブラリ/モデルが格納されているディレクトリと思われます。
- **`x_poster/`**: X(旧Twitter)への自動投稿機能に関連するスクリプトや設定ファイルが格納されています。
  - `morning_greet_poster.py`: 指定された時間にGoogle Sheetsから情報を取得し、AIが生成したコメントと共にXに投稿するスクリプトです。
  - `requirements.txt`: X Posterシステムを実行するために必要なPythonライブラリが記述されています。
- **`README.md`**: プロジェクトの概要、セットアップ手順、実行方法などを記述するファイルです。

## 注意点

- `.venv` や `__pycache__`、ログファイル、ローカル設定ファイル (`config.local.json`) などは、`.gitignore` によってGitの追跡対象から除外することが推奨されます。
- `credentials` ディレクトリ内の機密情報ファイルも同様に `.gitignore` で管理対象外とし、必要な場合は安全な方法で共有・配置する必要があります。(X Posterのサービスアカウントキーは現在リポジトリに含まれている可能性がありますが、セキュリティの観点からはGitHub Actions Secretsやローカル環境変数での管理が望ましいです。) 
