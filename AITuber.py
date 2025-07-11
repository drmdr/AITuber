############################################
# AITuber メインスクリプト
# このスクリプトは、AIキャラクターとの対話、音声合成、多言語対応機能を提供します。
############################################
import sys
import io
import os
import argparse

# モジュール検索パスにカレントディレクトリを追加
sys.path.append(os.getcwd())

# WindowsのコンソールでUnicode文字が正しく表示されるように標準出力をUTF-8に設定
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# コマンドライン引数の処理
def parse_arguments():
    parser = argparse.ArgumentParser(description='AITuberシステム')
    parser.add_argument('--language', type=str, choices=['ja', 'en', 'es'], default='ja',
                        help='AITuberが使用する言語 (ja: 日本語, en: 英語, es: スペイン語)')
    parser.add_argument('--mode', type=str, choices=['interactive', 'script'], default=None,
                        help='動作モード (interactive: インタラクティブモード, script: 原稿読み上げモード)')
    parser.add_argument('--script-dir', type=str, default='scripts',
                        help='原稿ファイルが格納されているディレクトリパス')
    return parser.parse_args()

import json
from pathlib import Path

# --- グローバル定数 --- #
CONFIG_FILE_PATH = "config.local.json"  # ローカル設定ファイル
RESPONSE_PATTERNS_FILE_PATH = "response_patterns.json" # 特殊応答パターンファイル
LOG_DIR = "logs"  # ログディレクトリ

# --- 設定ファイルの読み込み --- #
GEMINI_API_KEY = None
AUDIO_OUTPUT_DEVICE_INDEX = None  # 音声出力デバイスのインデックス

try:
    with open(CONFIG_FILE_PATH, "r", encoding="utf-8") as f:
        config_data = json.load(f)
    
    # Gemini APIキーの読み込み
    GEMINI_API_KEY = config_data.get("gemini_api_key")
    if GEMINI_API_KEY:
        print("Gemini APIキーを config.local.json から正常に読み込みました。")
        try:
            import google.generativeai as genai
            genai.configure(api_key=GEMINI_API_KEY)
            print("Gemini APIクライアントを正常に初期化しました。")
        except Exception as e:
            print(f"エラー: Gemini APIクライアントの初期化に失敗しました: {e}")
    else:
        print("警告: config.local.json に Gemini APIキーが見つかりません。")
    
    # 音声出力デバイスの設定読み込み
    AUDIO_OUTPUT_DEVICE_INDEX = config_data.get("audio_output_device_index")
    if AUDIO_OUTPUT_DEVICE_INDEX is not None:
        print(f"音声出力デバイスインデックスを設定しました: {AUDIO_OUTPUT_DEVICE_INDEX}")
except FileNotFoundError:
    print(f"エラー: 設定ファイル {CONFIG_FILE_PATH} が見つかりません。プログラムを終了します。")
    exit()
except ValueError as e:
    print(e)
    print("プログラムを終了します。")
    exit()
except json.JSONDecodeError:
    print(f"エラー: {CONFIG_FILE_PATH} のJSON形式が正しくありません。プログラムを終了します。")
    exit()

# --- 標準ライブラリ・外部ライブラリのインポート --- #

from google_aistudio_tts import GoogleAIStudioTTS  # Gemini API TTS (Google AI Studio TTS) クライアント
# 翻訳ライブラリとして deep-translator を使用
try:
    from deep_translator import GoogleTranslator
    # 翻訳クライアントの初期化は translate_text 関数内で行う
    print("deep-translator library loaded successfully.")
except ImportError:
    print("deep-translatorライブラリがインストールされていません。翻訳機能は使用できません。")
    print("pip install deep-translator を実行してインストールしてください。")

import numpy as np  # 音声データ処理用 (現在は未使用の可能性あり)
import traceback  # エラー発生時のスタックトレース表示用
import sounddevice as sd  # 音声再生用
import argparse  # コマンドライン引数の解析用
# import pytchat  # YouTubeライブチャット読み上げ用 (現在はコメントアウト)
import time  # 時間関連処理用
from time import sleep  # 一定時間待機用
import os  # OS依存機能（ファイルパス操作など）用
import random  # 乱数生成用（応答の多様性などに利用可能性あり）
from datetime import datetime  # 日時情報取得用（ログ記録など）
import re  # 正規表現操作用（ユーザー入力の解析など）

# YouTubeライブチャットID (現在はコメントアウト)
# LIVE_VIDEO_ID = "9JXQ1XvHz-k"
# livechat = pytchat.create(video_id=LIVE_VIDEO_ID)





LOG_FILE_PATH = os.path.join(LOG_DIR, "conversation_log.txt")  # 会話ログファイルのフルパス

# --- ログディレクトリの準備 --- #
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR) # ログディレクトリが存在しない場合は作成

# --- グローバル変数 (言語設定など) --- #
# 対応言語の定義
SUPPORTED_LANGUAGES_MAP = {  # アプリケーション内部で使用する言語コードとBCP47コードのマッピング
    "ja": "ja-JP",
    "en": "en-US",
    "es": "es-ES"
}

# コマンドライン引数を解析
args = parse_arguments()

# コマンドライン引数から言語設定を取得
TARGET_LANGUAGE = args.language  # AITuberが使用する言語コード (デフォルト: 日本語、起動時引数で変更可能)

# 言語コードからBCP47コードを設定
if TARGET_LANGUAGE in SUPPORTED_LANGUAGES_MAP:
    TARGET_LANGUAGE_BCP47 = SUPPORTED_LANGUAGES_MAP[TARGET_LANGUAGE]  # AITuberが使用する言語のBCP47コード
else:
    TARGET_LANGUAGE_BCP47 = "ja-JP"  # 不正な言語コードの場合は日本語を使用

# コマンドライン引数から動作モードを取得
SELECTED_MODE = args.mode  # コマンドライン引数で指定された動作モード
LANGUAGE_NAMES = {  # 各言語コードに対応する表示名
    "ja": "Japanese",
    "en": "English",
    "es": "Spanish"
}

# ユーザー入力による言語切り替えコマンドの正規表現パターン (例: !en Hello)
LANGUAGE_COMMAND_PATTERN = r"^!(ja|en|es)\s+(.+)$"

# --- 特殊応答パターンの読み込み --- #
def load_response_patterns():
    """response_patterns.json から特殊応答パターンを読み込みます。

    Returns:
        dict: 読み込まれた応答パターン。ファイルが存在しないか不正な場合は空の辞書。
    """
    try:
        with open(RESPONSE_PATTERNS_FILE_PATH, "r", encoding="utf-8") as f:
            patterns = json.load(f)
            print(f"{RESPONSE_PATTERNS_FILE_PATH} を正常に読み込みました。")
            return patterns
    except FileNotFoundError:
        print(f"警告: 特殊応答パターンファイル '{RESPONSE_PATTERNS_FILE_PATH}' が見つかりません。特殊応答は無効になります。")
        return {}
    except json.JSONDecodeError:
        print(f"警告: 特殊応答パターンファイル '{RESPONSE_PATTERNS_FILE_PATH}' のJSON形式が正しくありません。特殊応答は無効になります。")
        return {}

# --- 設定ファイルからテンプレート文字列を取得 --- #
def get_template(template_key, language_code="ja-JP"):
    """config.local.json から指定されたキーと言語に対応するテンプレート文字列を取得します。

    指定された言語のテンプレートが存在しない場合は、デフォルト言語（日本語）のテンプレートを返します。

    Args:
        template_key (str): 取得したいテンプレートのキー。
        language_code (str, optional): 取得したいテンプレートの言語コード (BCP47形式、例: "ja-JP")。
                                      デフォルトは "ja-JP"。

    Returns:
        str or None: テンプレート文字列。見つからない場合はNone。
    """
    # print(f"DEBUG: get_template called with template_key: {template_key}, language_code: {language_code}") # デバッグ用
    try:
        with open(CONFIG_FILE_PATH, "r", encoding="utf-8") as f:
            config = json.load(f)

        # config.local.json の languages セクションのキーは 'ja', 'en' のような短縮形
        # language_code (BCP47) から短縮形コードを取得
        short_lang_code = None
        for k, v in SUPPORTED_LANGUAGES_MAP.items():
            if v == language_code:
                short_lang_code = k
                break

        # デフォルト言語（日本語）の短縮コードを取得
        default_short_lang_code = [k for k, v in SUPPORTED_LANGUAGES_MAP.items() if v == "ja-JP"][0]

        # 1. 指定された言語のテンプレートを試みる
        if short_lang_code:
            lang_specific_templates = config.get("languages", {}).get(short_lang_code, {}).get("templates", {})
            template = lang_specific_templates.get(template_key)
            if template is not None: # 空文字列も有効なテンプレートとして扱うため is not None でチェック
                # print(f"DEBUG: Template found for '{template_key}' in '{short_lang_code}': {template}")
                return template
            # print(f"DEBUG: Template NOT found for '{template_key}' in '{short_lang_code}', falling back to default language.")

        # 2. デフォルト言語（日本語）のテンプレートを試みる (フォールバック)
        default_lang_templates = config.get("languages", {}).get(default_short_lang_code, {}).get("templates", {})
        default_template = default_lang_templates.get(template_key)
        if default_template is not None:
            # print(f"DEBUG: Returning default template for '{template_key}': {default_template}")
            return default_template

        # print(f"DEBUG: Template for '{template_key}' not found in specified or default language.")
        return None  # どちらの言語にもテンプレートが見つからない場合

    except FileNotFoundError:
        print(f"エラー: 設定ファイル '{CONFIG_FILE_PATH}' が見つかりません。テンプレートを取得できませんでした。")
        return None
    except json.JSONDecodeError:
        print(f"エラー: 設定ファイル '{CONFIG_FILE_PATH}' のJSON形式が正しくありません。テンプレートを取得できませんでした。")
        return None

# --- 自己紹介リクエストの判定 --- #
def is_self_introduction_request(text):
    """ユーザーの入力テキストが自己紹介のリクエストかどうかを判定します。

    判定には、現在のAITuberの言語設定 (`TARGET_LANGUAGE_BCP47`) に基づいて
    `config.local.json` から取得した自己紹介トリガーフレーズを使用します。
    トリガーフレーズは `get_template` 関数経由で取得されます。

    Args:
        text (str): ユーザーの入力テキスト。

    Returns:
        bool: 自己紹介のリクエストであればTrue、そうでなければFalse。
    """
    # print(f"DEBUG: is_self_introduction_request called with text: {text}") # デバッグ用
    trigger_phrases_key = "self_introduction_triggers"
    # get_template はリストを返すことを想定 (config.local.json の templates セクションで定義)
    trigger_phrases = get_template(trigger_phrases_key, TARGET_LANGUAGE_BCP47)

    # print(f"DEBUG: Self-introduction trigger phrases for {TARGET_LANGUAGE_BCP47}: {trigger_phrases}") # デバッグ用

    if isinstance(trigger_phrases, list): # trigger_phrases がリストであることを確認
        for phrase in trigger_phrases:
            if isinstance(phrase, str) and phrase.lower() in text.lower(): # phraseが文字列であることも確認し、部分一致で判定
                # print(f"DEBUG: Self-introduction request detected with phrase: {phrase}") # デバッグ用
                return True
    # print(f"DEBUG: No self-introduction request detected or trigger phrases are not a list/valid.") # デバッグ用
    return False

# --- 特殊応答の確認 --- #
def check_special_response(text, patterns_data):
    """ユーザーの入力テキストが、`patterns_data` に定義された特殊応答パターンに一致するかどうかを確認します。

    一致した場合、対応する応答文字列を返します。
    `patterns_data` は `load_response_patterns()` 関数によって `response_patterns.json` から読み込まれた
    辞書型のデータであることを想定しています。

    Args:
        text (str): ユーザーの入力テキスト。
        patterns_data (dict): 特殊応答パターンが格納された辞書。
                              期待される構造:
                              {
                                  "patterns": [
                                      {
                                          "keywords": ["keyword1", "keyword2"],
                                          "response": "This is the response."
                                      },
                                      ...
                                  ]
                              }

    Returns:
        str or None: 一致する応答が見つかればその応答文字列。見つからない場合や、
                     `patterns_data` が不正な場合はNone。
    """
    # print(f"DEBUG: check_special_response called with text: '{text}'") # デバッグ用
    if not patterns_data or not isinstance(patterns_data.get("patterns"), list):
        # print("DEBUG: patterns_data is empty, None, or 'patterns' key is not a list. Skipping special response check.")
        return None

    for pattern_group in patterns_data["patterns"]:
        if not isinstance(pattern_group, dict):
            # print(f"DEBUG: Skipping invalid pattern_group (not a dict): {pattern_group}")
            continue  # パターングループが辞書でない場合はスキップ

        keywords = pattern_group.get("keywords", [])
        response_text = pattern_group.get("response", "") # 変数名を response から response_text に変更

        # print(f"DEBUG: Checking keywords: {keywords} for response: {response_text}")

        if not isinstance(keywords, list) or not keywords: # キーワードがリストでない、または空の場合はスキップ
            # print(f"DEBUG: Skipping pattern_group due to invalid or empty keywords: {keywords}")
            continue

        # キーワードのいずれかがテキストに含まれているか確認（大文字・小文字を区別しない、部分一致）
        if any(isinstance(keyword, str) and keyword.lower() in text.lower() for keyword in keywords):
            # print(f"DEBUG: Special response triggered by keywords: {keywords}")
            if isinstance(response_text, str):
                return response_text
            else:
                # print(f"DEBUG: Invalid response_text type (not a string) for triggered keywords: {keywords}, response_text: {response_text}")
                return None # 応答が文字列でない場合はNoneを返す

    # print("DEBUG: No special response triggered.")
    return None

# --- グローバル設定の読み込み --- #
# スクリプトのトップレベルで一度だけ実行され、主にデフォルト言語での初期設定を行う。
# main()関数内では、コマンドライン引数に基づいて再度設定が読み込まれ、これらの値は上書きされる可能性がある。
character_name = "AITuber"  # デフォルトのキャラクター名
persona = "あなたは親切なAIアシスタントです。"  # デフォルトのペルソナ
greeting = "こんにちは！"  # デフォルトの挨拶
guidelines = []  # デフォルトのガイドライン (空のリスト)
full_persona = persona # ペルソナとガイドラインを結合したもの

try:
    with open(CONFIG_FILE_PATH, "r", encoding="utf-8") as f:
        config_data_global = json.load(f) # グローバルスコープ用の変数名

    # デバッグ情報を追加
    print(f"デバッグ: コマンドライン引数で指定された言語: {TARGET_LANGUAGE}")
    
    # コマンドライン引数から指定された言語の設定を読み込む
    selected_lang_settings = config_data_global.get("languages", {}).get(TARGET_LANGUAGE, {})
    print(f"デバッグ: 選択された言語設定の存在: {bool(selected_lang_settings)}")
    
    # 設定が存在しない場合はデフォルト言語(日本語 'ja')にフォールバック
    if not selected_lang_settings:
        selected_lang_settings = config_data_global.get("languages", {}).get("ja", {})
        print(f"警告: {TARGET_LANGUAGE} の設定が見つからないため、日本語設定を使用します。")
    
    character_name = selected_lang_settings.get("character_name", character_name)
    persona = selected_lang_settings.get("persona", persona)
    greeting = selected_lang_settings.get("greeting", greeting)
    guidelines = selected_lang_settings.get("guidelines", guidelines)
    
    print(f"デバッグ: 設定された character_name: {character_name}")
    print(f"デバッグ: 設定された persona の先頭部分: {persona[:30]}...")

    full_persona = persona
    if guidelines: # ガイドラインが存在する場合のみ結合
        full_persona += "\n\nガイドライン:\n- " + "\n- ".join(guidelines)
    print(f"情報: {CONFIG_FILE_PATH} から {LANGUAGE_NAMES.get(TARGET_LANGUAGE, TARGET_LANGUAGE)} 設定を読み込みました。")

except (FileNotFoundError, json.JSONDecodeError) as e:
    print(f"警告: 設定ファイル '{CONFIG_FILE_PATH}' が見つかりません、またはJSON形式が正しくありません。グローバル設定にはデフォルト値を使用します。 Error: {e}")
    # character_name, persona, greeting, guidelines は既にデフォルト値が設定されているため、ここでは何もしない
    # (既に定義済みのデフォルト値が使用される)

# --- Google Cloud Platform (GCP) 関連 --- #

# GCP認証情報の確認関数 (現在はGoogle Cloud TTS用だが、Gemini API利用が主軸のため、将来的に削除または見直しの可能性あり)
def check_gcp_credentials():
    """環境変数 GOOGLE_APPLICATION_CREDENTIALS が設定されているかを確認します。

    Returns:
        bool: 設定されていればTrue、されていなければFalse。
    """
    gac_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if not gac_path:
        print("情報: 環境変数 GOOGLE_APPLICATION_CREDENTIALS が設定されていません。Google Cloud TTS (代替TTS) は利用できません。")
        return False
    if not os.path.exists(gac_path):
        print(f"警告: 環境変数 GOOGLE_APPLICATION_CREDENTIALS に指定されたファイルが存在しません: {gac_path}。Google Cloud TTS (代替TTS) は利用できません。")
        return False
    print(f"情報: 環境変数 GOOGLE_APPLICATION_CREDENTIALS が設定されており、ファイルも存在します: {gac_path}")
    return True


# --- Google AI Studio TTS (Gemini API TTS) クライアントの初期化 (メインTTSとして利用) ---
google_aistudio_tts_client = None
if GEMINI_API_KEY: # APIキーが設定されている場合のみ初期化を試みる
    try:
        google_aistudio_tts_client = GoogleAIStudioTTS(api_key=GEMINI_API_KEY)
        print("Google AI Studio TTSクライアント (Gemini API TTS) を正常に初期化しました。(メインTTSとして利用)")
    except Exception as e:
        print(f"警告: Google AI Studio TTSクライアントの初期化に失敗しました。音声合成は利用できません。")
        print(f"エラー詳細: {e}")
        # traceback.print_exc() # 詳細なエラーが必要な場合にコメント解除
else:
    print("警告: Gemini APIキーが設定されていないため、Google AI Studio TTSクライアントは初期化されません。音声合成は利用できません。")
#         # traceback.print_exc() # 詳細なエラーが必要な場合にコメント解除
# else:
#     print("警告: Gemini APIキーが設定されていないため、Google AI Studio TTSクライアントは初期化されません。音声合成は利用できません。")


# googletransの初期化は上部で完了しているので、ここは空

GCP_SAMPLE_RATE = 24000  # Wavenet音声の一般的なサンプルレート。標準音声の場合は16000Hzが多いです。


def get_gcp_voice_name(language_code="ja-JP"):
    """指定された言語コードに適した音声名を返します。"""
    # これらの音声名はお好みでカスタマイズできます。詳細は以下を参照してください:
    # https://cloud.google.com/text-to-speech/docs/voices
    if language_code == "ja-JP":
        return "ja-JP-Neural2-B"  # 女性の声 (Neural2)
        # return "ja-JP-Wavenet-B"  # 男性
    elif language_code == "en-US":
        return "en-US-Chirp-HD-F"  # 女性（高品質音声）
        # return "en-US-Wavenet-D"  # 女性
        # return "en-US-Wavenet-A"  # 男性
    elif language_code == "es-ES":
        return "es-ES-Neural2-A"  # スペイン語 女性
    else:
        return "ja-JP-Neural2-B"  # デフォルトは日本語女性音声

# --- ログ関連関数 --- #
import os
import datetime

def log_to_file(speaker, message, language=""):
    """会話内容をログファイルに記録します。
    
    Args:
        speaker (str): 発言者名
        message (str): メッセージ内容
        language (str, optional): 言語コードや言語名。デフォルトは空文字列。
    """
    try:
        # ログディレクトリの確認と作成
        log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
        os.makedirs(log_dir, exist_ok=True)
        
        # 日付フォーマットのファイル名を作成
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        log_file = os.path.join(log_dir, f"conversation_{today}.log")
        
        # 現在時刻を取得
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        
        # 言語情報があれば追加
        lang_info = f" ({language})" if language else ""
        
        # ログメッセージのフォーマット
        log_message = f"[{timestamp}] {speaker}{lang_info}: {message}\n\n"
        
        # ファイルに追記
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(log_message)
    except Exception as e:
        # ログ書き込みエラーはプログラム全体に影響しないようにする
        print(f"警告: ログ書き込みエラー: {e}")

# --- TTS関連関数 --- #
import wave

def wave_file(filename, pcm, channels=1, rate=24000, sample_width=2):
    """音声データをWAVファイルとして保存します。
    
    Args:
        filename (str): 保存するファイル名
        pcm (bytes): 音声データ
        channels (int): チャンネル数。デフォルトは1
        rate (int): サンプルレート。デフォルトは24000Hz
        sample_width (int): サンプル幅。デフォルトは2
    """
    with wave.open(filename, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(rate)
        wf.writeframes(pcm)

def get_tts_provider():
    """使用するTTSプロバイダーを返します。
    
    Returns:
        str: TTSプロバイダー名 ("google_aistudio")
    """
    # Gemini API TTS (Google AI Studio TTS) を使用
    return "google_aistudio"

def play_audio_google_aistudio(text, language_code="ja-JP", output_device_index=None):
    """テキストをGemini API TTSで音声合成して再生します。
    
    Args:
        text (str): 音声合成するテキスト
        language_code (str): 言語コード。デフォルトは"ja-JP"
        output_device_index (int, optional): 音声出力デバイスのインデックス。Noneの場合はデフォルトデバイスを使用。
    """
    try:
        from google.generativeai import types
        import os
        import tempfile

        if not GEMINI_API_KEY:
            print("警告: Gemini APIキーが設定されていないため、音声合成をスキップします。")
            return

        print("デバッグ: TTS音声合成を開始します...")

        # TTSに最適化されたsynthesize_speechを使用し、エラー解決とパフォーマンス向上を図る
        response = genai.synthesize_speech(
            model='models/text-to-speech',
            text=text,
            voice_name='zephyr' # ボイスをzephyrに固定
        )

        # 音声データの取得
        audio_data = response['audio_content']

        # 一時ファイルに保存して再生
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
            temp_filename = temp_file.name
            temp_file.write(audio_data)
        
        print(f"音声ファイルを生成しました: {temp_filename}")
        
        # 音声再生
        import sounddevice as sd
        import soundfile as sf
        
        data, samplerate = sf.read(temp_filename)
        
        device_to_use = output_device_index if output_device_index is not None else AUDIO_OUTPUT_DEVICE_INDEX
        
        if device_to_use is not None:
            print(f"オーディオ出力デバイス {device_to_use} で再生します。")
            sd.play(data, samplerate, device=device_to_use)
        else:
            print("デフォルトのオーディオ出力デバイスで再生します。")
            sd.play(data, samplerate)
            
        sd.wait()
        print("音声の再生が完了しました。")
        
        # 一時ファイルの削除
        os.remove(temp_filename)

    except Exception as e:
        print(f"Gemini API TTS の再生中にエラーが発生しました: {e}")
        import traceback
        traceback.print_exc()

# --- 原稿読み上げモード --- #
def script_mode(script_dir="scripts"):
    """原稿読み上げモードのメイン処理
    
    Args:
        script_dir (str): 原稿ファイルが格納されているディレクトリパス。デフォルトは "scripts"
    """
    global TARGET_LANGUAGE, TARGET_LANGUAGE_BCP47, full_persona, character_name, persona, greeting, guidelines
    
    print(f"\n=== 原稿読み上げモードを開始します ===\n")
    print(f"言語: {LANGUAGE_NAMES.get(TARGET_LANGUAGE, 'Unknown')} ({TARGET_LANGUAGE_BCP47})")
    print(f"原稿ディレクトリ: {script_dir}\n")
    
    # 原稿ディレクトリの存在確認
    if not os.path.exists(script_dir):
        print(f"エラー: 原稿ディレクトリ '{script_dir}' が存在しません。")
        print(f"ディレクトリを作成して、その中にテキストファイルを配置してください。")
        os.makedirs(script_dir)
        print(f"ディレクトリ '{script_dir}' を作成しました。")
        return
    
    # テキストファイルの一覧を取得
    text_files = [f for f in os.listdir(script_dir) if f.endswith('.txt')]
    
    if not text_files:
        print(f"エラー: ディレクトリ '{script_dir}' にテキストファイル (.txt) が見つかりません。")
        print("テキストファイルを配置してから再度実行してください。")
        return
    
    # ファイル一覧を表示
    print("利用可能な原稿ファイル:")
    for i, file in enumerate(text_files, 1):
        print(f"{i}. {file}")
    
    # ファイル選択
    while True:
        try:
            choice = input("\n読み上げるファイルの番号を入力してください (終了する場合は 'q' を入力): ")
            
            if choice.lower() == 'q':
                print("原稿読み上げモードを終了します。")
                return
            
            file_index = int(choice) - 1
            if 0 <= file_index < len(text_files):
                selected_file = text_files[file_index]
                break
            else:
                print("無効な選択です。正しい番号を入力してください。")
        except ValueError:
            print("数字を入力してください。")
    
    # 選択されたファイルを読み込み
    file_path = os.path.join(script_dir, selected_file)
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            script_text = f.read()
        
        print(f"\nファイル '{selected_file}' を読み込みました。")
        print(f"\n=== 読み上げ開始: {selected_file} ===\n")
        
        # テキストを段落ごとに分割
        paragraphs = [p.strip() for p in script_text.split('\n\n') if p.strip()]
        
        # 各段落を読み上げ
        for i, paragraph in enumerate(paragraphs):
            if not paragraph.strip():
                continue
                
            print(f"{character_name}: {paragraph}")
            log_to_file(character_name, paragraph)
            
            # 音声合成と再生
            tts_provider = get_tts_provider()
            if tts_provider == "google_aistudio":
                play_audio_google_aistudio(paragraph, language_code=TARGET_LANGUAGE_BCP47, output_device_index=AUDIO_OUTPUT_DEVICE_INDEX)
            else:
                play_audio_gcp(paragraph, language_code=TARGET_LANGUAGE_BCP47)
            
            # 段落間に少し間を空ける
            if i < len(paragraphs) - 1:
                time.sleep(1.5)
        
        print(f"\n=== 読み上げ終了: {selected_file} ===\n")
        
    except Exception as e:
        print(f"ファイルの読み込みまたは処理中にエラーが発生しました: {e}")
        traceback.print_exc()

# --- インタラクティブモード --- #
def interactive_mode():
    """インタラクティブモードのメインループ"""
    global TARGET_LANGUAGE, TARGET_LANGUAGE_BCP47, full_persona, character_name, persona, greeting, guidelines

    chat_session = None
    try:
        # グローバルに初期化済みのgenaiを使用
        model = genai.GenerativeModel(
            'gemini-1.5-flash-latest',
            system_instruction=full_persona
        )
        chat_session = model.start_chat()
        print("情報: 対話用Geminiモデルを正常に初期化しました。")

    except Exception as e:
        print(f"エラー: 対話用Geminiモデルの初期化に失敗しました。 {e}")
        print("警告: AIとの対話機能は無効になります。")

    # 特殊応答パターンの読み込み
    response_patterns = load_response_patterns()

    # 現在の言語設定
    current_language = TARGET_LANGUAGE_BCP47
    
    # メインループ
    while True:
        try:
            # ユーザー入力を受け付ける
            try:
                user_input = input("あなた: ")
            except EOFError:
                print("入力が終了しました。プログラムを終了します。")
                log_to_file("System", "入力終了によりプログラムを終了しました。")
                break
            
            if not user_input.strip():
                continue
            
            if user_input.lower() in ["exit", "quit", "終了", "退出"]:
                print("プログラムを終了します。")
                log_to_file("System", "終了コマンドによりプログラムを終了しました。")
                break
            
            language_match = re.match(LANGUAGE_COMMAND_PATTERN, user_input)
            if language_match:
                lang_code = language_match.group(1)
                user_input = language_match.group(2)
                current_language = SUPPORTED_LANGUAGES_MAP.get(lang_code, TARGET_LANGUAGE_BCP47)
                print(f"言語を {lang_code} ({current_language}) に切り替えました。")
            
            log_to_file("User", user_input)
            
            special_response = check_special_response(user_input, response_patterns)
            is_intro_request = is_self_introduction_request(user_input)
            
            if special_response:
                response_text = special_response
            elif is_intro_request:
                template = get_template("self_introduction", current_language)
                if template:
                    response_text = template
                else:
                    if chat_session:
                        response = chat_session.send_message(user_input)
                        response_text = response.text
                    else:
                        response_text = "申し訳ありません、AIモデルが初期化されていないため、お答えできません。"
            else:
                if chat_session:
                    try:
                        response = chat_session.send_message(user_input)
                        response_text = response.text
                    except Exception as e:
                        response_text = f"申し訳ありません、応答の生成中にエラーが発生しました。 {e}"
                        print(f"チャット応答生成中にエラーが発生しました: {e}")
                else:
                    response_text = "申し訳ありません、AIモデルが初期化されていないため、お答えできません。"
            
            log_to_file(character_name, response_text, current_language)
            
            print(f"{character_name}: {response_text}")
            
            tts_provider = get_tts_provider()
            if tts_provider == "google_aistudio":
                play_audio_google_aistudio(response_text, language_code=current_language, output_device_index=AUDIO_OUTPUT_DEVICE_INDEX)
            
        except Exception as e:
            error_message = f"エラーが発生しました: {e}"
            print(error_message)
            log_to_file("Error", error_message)
            traceback.print_exc()

# --- メインループ --- #
def main():
    """メイン関数。コマンドライン引数を解析し、適切なモードを開始します。"""
    global TARGET_LANGUAGE, TARGET_LANGUAGE_BCP47
    
    # コマンドライン引数の解析
    args = parse_arguments()
    
    # 言語設定の更新
    TARGET_LANGUAGE = args.language
    TARGET_LANGUAGE_BCP47 = SUPPORTED_LANGUAGES_MAP.get(TARGET_LANGUAGE, "ja-JP")
    
    print(f"情報: 言語設定を {TARGET_LANGUAGE} ({TARGET_LANGUAGE_BCP47}) に設定しました。")
    
    # 挨拶を表示
    print(f"{character_name}: {greeting}")
    
    # モード選択
    mode = args.mode
    if mode is None:
        # 対話モードかどうかを確認
        try:
            # モードが指定されていない場合はユーザーに選択させる
            print("モードを選択してください:")
            print("1: インタラクティブモード - リアルタイムで対話")
            print("2: 原稿読み上げモード - スクリプトファイルを読み上げ")
            choice = input("> ")
            if choice == "2":
                mode = "script"
            else:
                mode = "interactive"
        except EOFError:
            # 非対話モードの場合はデフォルトでインタラクティブモードを選択
            print("非対話モードで実行されています。デフォルトでインタラクティブモードを選択します。")
            mode = "interactive"
    
    # 選択されたモードで実行
    try:
        if mode == "script":
            print(f"情報: 原稿読み上げモードを開始します。")
            script_mode(args.script_dir)
        else:
            print(f"情報: インタラクティブモードを開始します。")
            interactive_mode()
    except Exception as e:
        print(f"エラー: モードの実行中に例外が発生しました: {e}")
        import traceback
        traceback.print_exc()

# --- メイン処理 --- #
if __name__ == "__main__":
    try:
        print("デバッグ: プログラム開始")
        main()
    except Exception as e:
        print(f"エラー: プログラム実行中に例外が発生しました: {e}")
        import traceback
        traceback.print_exc()
        # エラー後に一時停止して、ユーザーがエラーメッセージを確認できるようにする
        input("エラーが発生しました。何かキーを押すと終了します...")