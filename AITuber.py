############################################
# AITuber メインスクリプト
# このスクリプトは、AIキャラクターとの対話、音声合成、多言語対応機能を提供します。
############################################
import sys
import io
import os

# モジュール検索パスにカレントディレクトリを追加
sys.path.append(os.getcwd())

# WindowsのコンソールでUnicode文字が正しく表示されるように標準出力をUTF-8に設定
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import json
from pathlib import Path

# --- グローバル定数 --- #
CONFIG_FILE_PATH = "config.local.json"  # ローカル設定ファイル
RESPONSE_PATTERNS_FILE_PATH = "response_patterns.json" # 特殊応答パターンファイル
LOG_DIR = "logs"  # ログディレクトリ

# --- APIキーの読み込み --- #
GEMINI_API_KEY = None
try:
    with open(CONFIG_FILE_PATH, "r", encoding="utf-8") as f:
        config_data = json.load(f)
    GEMINI_API_KEY = config_data.get("gemini_api_key")
    if not GEMINI_API_KEY:
        raise ValueError(f"エラー: Gemini APIキーが {CONFIG_FILE_PATH} に設定されていません。")
    print(f"Gemini APIキーを {CONFIG_FILE_PATH} から正常に読み込みました。")
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
TARGET_LANGUAGE = "ja"  # AITuberが使用する言語コード (デフォルト: 日本語、起動時引数で変更可能)
TARGET_LANGUAGE_BCP47 = "ja-JP"  # AITuberが使用する言語のBCP47コード (デフォルト: 日本語)

# 対応言語の定義
SUPPORTED_LANGUAGES_MAP = {  # アプリケーション内部で使用する言語コードとBCP47コードのマッピング
    "ja": "ja-JP",
    "en": "en-US",
    "es": "es-ES"
}
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

    # グローバルスコープでは、デフォルト言語(日本語 'ja') の設定を試みる
    default_lang_settings = config_data_global.get("languages", {}).get("ja", {})
    character_name = default_lang_settings.get("character_name", character_name)
    persona = default_lang_settings.get("persona", persona)
    greeting = default_lang_settings.get("greeting", greeting)
    guidelines = default_lang_settings.get("guidelines", guidelines)

    full_persona = persona
    if guidelines: # ガイドラインが存在する場合のみ結合
        full_persona += "\n\nガイドライン:\n- " + "\n- ".join(guidelines)
    print(f"情報: {CONFIG_FILE_PATH} からグローバル設定（日本語優先）を読み込みました。")

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
        return "es-ES-Wavenet-D" # 女性
        # return "es-ES-Wavenet-B"  # 男性
    else:
        print(f"警告: 言語コード '{language_code}' は音声選択で明示的に設定されていません。en-USのデフォルト音声を使用します。")
        return "en-US-Chirp-HD-F"

def translate_text(text, target_language):
    """
    テキストを指定された言語に翻訳します。
    target_language: 'ja-JP', 'en-US', 'es-ES' など
    """
    try:
        # deep-translatorは 'ja' のような短い言語コードを期待する
        target_lang_short = target_language.split('-')[0]
        # GoogleTranslatorインスタンスを都度生成
        translated = GoogleTranslator(source='auto', target=target_lang_short).translate(text)
        return translated
    except Exception as e:
        print(f"翻訳エラーが発生しました: {e}")
        return text # エラー時は元のテキストを返す

def log_to_file(speaker, message, language=None):
    """
    会話ログをファイルに保存します。
    """
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        language_info = f" [{language}]" if language else ""
        log_entry = f"[{timestamp}]{language_info} {speaker}: {message}\n"
        
        with open(LOG_FILE_PATH, "a", encoding="utf-8") as log_file:
            log_file.write(log_entry)
    except Exception as e:
        print(f"ログの保存中にエラーが発生しました: {e}")

def preprocess_text_for_tts(text):
    """
    テキストを音声合成用に前処理します。
    記号や不要な文字を削除または置換します。
    """
    # 削除する記号のリスト
    symbols_to_remove = ['（', '）', '「', '」', '『', '』', '【', '】', 
                       '♪', '♥', '♡', '❤', '★', '☆', '✨', '♦', '♠', '♣',
                       '〜', '～',
                       # マークダウン記号を追加
                       '*', '#', '`', '_', '-', '+', '=', '|', '\\', '/', 
                       '>', '<', '[', ']', '{', '}', '(', ')', ':', ';',
                       '!', '?', '.', ',', '@', '$', '%', '^', '&']
    
    # 空白に置換する記号のリスト
    symbols_to_space = ['・', '…', '⋯', '―', '－', '—']
    
    # 特定の記号を削除
    for symbol in symbols_to_remove:
        text = text.replace(symbol, '')
    
    # 特定の記号を空白に置換
    for symbol in symbols_to_space:
        text = text.replace(symbol, ' ')
    
    # マークダウン形式のテキストを処理（例: **太字** や *イタリック* などのパターン）
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)  # **太字** -> 太字
    text = re.sub(r'\*(.+?)\*', r'\1', text)        # *イタリック* -> イタリック
    text = re.sub(r'`(.+?)`', r'\1', text)           # `コード` -> コード
    text = re.sub(r'\[(.+?)\]\(.+?\)', r'\1', text)  # [リンクテキスト](URL) -> リンクテキスト
    
    # 連続する空白を1つにまとめる
    text = ' '.join(text.split())
    
    return text

def get_tts_provider():
    """
    設定ファイルからTTSプロバイダーを取得します
    """
    try:
        with open(CONFIG_FILE_PATH, "r", encoding="utf-8") as f:
            config_data = json.load(f)
        
        tts_settings = config_data.get("tts_settings", {})
        return tts_settings.get("provider", "gcp")
    except Exception as e:
        print(f"TTSプロバイダーの取得に失敗しました: {e}")
        return "gcp"  # デフォルトはGCP

def get_tts_settings():
    """
    設定ファイルからTTS設定を取得します
    """
    try:
        with open(CONFIG_FILE_PATH, "r", encoding="utf-8") as f:
            config = json.load(f)
        
        return config.get("tts_settings", {})
    except Exception as e:
        print(f"TTS設定の取得に失敗しました: {e}")
        return {}  # デフォルトは空の辞書

def play_audio_google_aistudio(text_to_speak, language_code=None, max_retries=3):
    # 引数で言語が指定されなかった場合、グローバルのターゲット言語を使用
    if language_code is None:
        language_code = TARGET_LANGUAGE_BCP47
    """
    Google AIスタジオのText-to-Speech を使用して音声を合成し、再生します。
    エラーが発生した場合はリトライします。
    """
    # google_aistudio_tts_clientがない場合はエラーを表示するが終了しない
    if not google_aistudio_tts_client:
        print("\n\n警告: Google AIスタジオ TTS クライアントが初期化されていません。音声なしで続行します。\n")
        return

    # デバッグ情報表示
    print(f"\n[DEBUG] 入力テキストの長さ: {len(text_to_speak)} 文字")
    print(f"[DEBUG] 入力テキストの最初の100文字: {text_to_speak[:100]}")
    
    # テキストを前処理
    processed_text = preprocess_text_for_tts(text_to_speak)
    print(f"[DEBUG] 処理後テキストの長さ: {len(processed_text)} 文字")
    
    # TTS設定を取得
    tts_settings = get_tts_settings()
    voice_name = tts_settings.get("voice", "Zephyr")
    prompt = tts_settings.get("prompt", "Speak with the bright, innocent, and charming voice of a cheerful anime girl or VTuber. Use a clear, slightly high-pitched tone with a youthful and expressive energy. Your voice should sound honest, cute, and friendly. Emphasize emotional warmth and playfulness in your delivery.")
    
    # テキストを文章単位で分割する
    # 日本語と英語の文章の区切り文字で分割
    sentence_endings = ['.', '!', '?', '。', '！', '？']  # 英語と日本語の区切り文字
    
    # 文章を分割する正規表現パターン
    pattern = f"([^{''.join(sentence_endings)}]*[{''.join(sentence_endings)}])"
    
    # 文章を分割
    sentences = re.findall(pattern, processed_text)
    
    # 残りのテキストがあれば追加
    remaining = re.sub(pattern, '', processed_text)
    if remaining:
        sentences.append(remaining)
    
    # 各文章を適切な長さのチャンクに結合
    max_chars = 200  # 各チャンクの最大文字数
    text_chunks = []
    current_chunk = ""
    
    for sentence in sentences:
        # 現在のチャンクに文章を追加しても最大文字数を超えない場合
        if len(current_chunk) + len(sentence) <= max_chars:
            current_chunk += sentence
        else:
            # 現在のチャンクが空でなければ追加
            if current_chunk:
                text_chunks.append(current_chunk)
            
            # 文章自体が最大文字数を超える場合は分割
            if len(sentence) > max_chars:
                # 長い文章を分割
                for i in range(0, len(sentence), max_chars):
                    text_chunks.append(sentence[i:i+max_chars])
                current_chunk = ""
            else:
                # 新しいチャンクとして設定
                current_chunk = sentence
    
    # 最後のチャンクがあれば追加
    if current_chunk:
        text_chunks.append(current_chunk)
    
    # チャンクが空の場合は元のテキストをそのまま使用
    if not text_chunks:
        text_chunks = [processed_text]
    
    print(f"[DEBUG] テキストを{len(text_chunks)}個のチャンクに分割しました")
    
    # 各チャンクを処理
    for i, chunk in enumerate(text_chunks):
        print(f"[DEBUG] チャンク {i+1}/{len(text_chunks)} の長さ: {len(chunk)} 文字")
        
        # リトライロジックを実装
        for retry in range(max_retries):
            try:
                print(f"[DEBUG] 音声合成リクエスト開始 (チャンク {i+1}/{len(text_chunks)}, 試行 {retry+1}/{max_retries})")
                
                # Google AIスタジオで音声合成
                audio_data = google_aistudio_tts_client.synthesize_speech(chunk, voice_name, prompt)
                
                if audio_data:
                    print(f"[DEBUG] 音声合成成功: オーディオデータサイズ {len(audio_data)} バイト")
                    
                    # 音声再生
                    play_audio(audio_data)
                    print(f"[DEBUG] 音声再生完了 (チャンク {i+1}/{len(text_chunks)})")
                    
                    # 成功した場合はリトライループを抜ける
                    break
                else:
                    raise Exception("音声データの取得に失敗しました")
                
            except Exception as e:
                if retry < max_retries - 1:
                    print(f"音声合成に失敗しました。リトライ中... ({retry+1}/{max_retries})")
                    print(f"エラーの詳細: {e}")
                    traceback.print_exc()  # トレースバックを表示
                    time.sleep(1)  # リトライ前に少し待機
                else:
                    print(f"音声合成に失敗しました。最大リトライ回数に達しました。")
                    print(f"エラーの詳細: {e}")
                    traceback.print_exc()  # トレースバックを表示

def play_audio_gcp(text_to_speak, language_code="ja-JP", max_retries=3):
    """
    Google Cloud Text-to-Speech を使用して音声を合成し、再生します。
    エラーが発生した場合はリトライします。
    """
    # gcp_tts_clientがない場合はエラーを表示するが終了しない
    if not gcp_tts_client:
        print("\n\n警告: GCP TTS クライアントが初期化されていません。音声なしで続行します。\n")
        return

    # デバッグ情報表示
    print(f"\n[DEBUG] 入力テキストの長さ: {len(text_to_speak)} 文字")
    print(f"[DEBUG] 入力テキストの最初の100文字: {text_to_speak[:100]}")
    
    # テキストを前処理
    processed_text = preprocess_text_for_tts(text_to_speak)
    print(f"[DEBUG] 処理後テキストの長さ: {len(processed_text)} 文字")
    
    # テキストを文章単位で分割する
    # 日本語と英語の文章の区切り文字で分割
    sentence_endings = ['.', '!', '?', '。', '！', '？']  # 英語と日本語の区切り文字
    
    # 文章を分割する正規表現パターン
    pattern = f"([^{''.join(sentence_endings)}]*[{''.join(sentence_endings)}])"
    
    # 文章を分割
    sentences = re.findall(pattern, processed_text)
    
    # 残りのテキストがあれば追加
    remaining = re.sub(pattern, '', processed_text)
    if remaining:
        sentences.append(remaining)
    
    # 各文章を適切な長さのチャンクに結合
    max_chars = 200  # 各チャンクの最大文字数
    text_chunks = []
    current_chunk = ""
    
    for sentence in sentences:
        # 現在のチャンクに文章を追加しても最大文字数を超えない場合
        if len(current_chunk) + len(sentence) <= max_chars:
            current_chunk += sentence
        else:
            # 現在のチャンクが空でなければ追加
            if current_chunk:
                text_chunks.append(current_chunk)
            
            # 文章自体が最大文字数を超える場合は分割
            if len(sentence) > max_chars:
                # 長い文章を分割
                for i in range(0, len(sentence), max_chars):
                    text_chunks.append(sentence[i:i+max_chars])
                current_chunk = ""
            else:
                # 新しいチャンクとして設定
                current_chunk = sentence
    
    # 最後のチャンクがあれば追加
    if current_chunk:
        text_chunks.append(current_chunk)
    
    # チャンクが空の場合は元のテキストをそのまま使用
    if not text_chunks:
        text_chunks = [processed_text]
    
    print(f"[DEBUG] テキストを{len(text_chunks)}個のチャンクに分割しました")
    
    # 各チャンクを処理
    for i, chunk in enumerate(text_chunks):
        print(f"[DEBUG] チャンク {i+1}/{len(text_chunks)} の長さ: {len(chunk)} 文字")
        
        # 合成入力の設定
        synthesis_input = texttospeech.SynthesisInput(text=chunk)
        
        # 音声設定
        voice_name = get_gcp_voice_name(language_code)
        voice = texttospeech.VoiceSelectionParams(
            language_code=language_code,
            name=voice_name
        )
        print(f"[DEBUG] 使用する音声: {voice_name} (言語: {language_code})")
        
        # オーディオ設定
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.LINEAR16,
            sample_rate_hertz=GCP_SAMPLE_RATE
        )
        
        # リトライロジックを実装
        for retry in range(max_retries):
            try:
                print(f"[DEBUG] 音声合成リクエスト開始 (チャンク {i+1}/{len(text_chunks)}, 試行 {retry+1}/{max_retries})")
                
                # 音声合成リクエスト
                response = gcp_tts_client.synthesize_speech(
                    input=synthesis_input,
                    voice=voice,
                    audio_config=audio_config
                )
                
                # 音声データを取得
                audio_data = response.audio_content
                print(f"[DEBUG] 音声合成成功: オーディオデータサイズ {len(audio_data)} バイト")
                
                # 音声再生
                play_audio(audio_data)
                print(f"[DEBUG] 音声再生完了 (チャンク {i+1}/{len(text_chunks)})")
                
                # 成功した場合はリトライループを抜ける
                break
                
            except Exception as e:
                if retry < max_retries - 1:
                    print(f"音声合成に失敗しました。リトライ中... ({retry+1}/{max_retries})")
                    print(f"エラーの詳細: {e}")
                    traceback.print_exc()  # トレースバックを表示
                    time.sleep(1)  # リトライ前に少し待機
                else:
                    print(f"音声合成に失敗しました。最大リトライ回数に達しました。")
                    print(f"エラーの詳細: {e}")
                    traceback.print_exc()  # トレースバックを表示

def play_audio(audio_data):
    # 音声データをNumPy配列に変換
    try:
        audio_np = np.frombuffer(audio_data, dtype=np.int16)
    except Exception as e:
        print(f"GCP TTS からの音声データの変換に失敗しました: {e}")
        traceback.print_exc()
        return
    
    # 音声データが空かチェック
    if audio_np.size == 0:
        print("GCP TTS から空の音声データを受信しました。再生するものがありません。")
        return

    try:
        devices = sd.query_devices()
        output_devices = [device for device in devices if device['max_output_channels'] > 0]

        syncroom_device_id = None
        shure_device_id = None
        realtek_device_id = None
        default_device_id = None

        for device in output_devices:
            if 'Yamaha SYNCROOM Driver' in device['name']:
                syncroom_device_id = device['index']
                break 
            elif 'Shure' in device['name']:
                shure_device_id = device['index']
            elif 'Realtek' in device['name']:
                realtek_device_id = device['index']
            
            if isinstance(sd.default.device, (list, tuple)) and len(sd.default.device) > 1:
                 if sd.default.device[1] == device['index']:
                    default_device_id = device['index']
            elif isinstance(sd.default.device, int):
                 if sd.default.device == device['index']:
                    default_device_id = device['index']

        device_id_to_use = None
        selected_device_name = "None"

        if syncroom_device_id is not None:
            device_id_to_use = syncroom_device_id
            selected_device_name = sd.query_devices(syncroom_device_id)['name']
        elif shure_device_id is not None:
            device_id_to_use = shure_device_id
            selected_device_name = sd.query_devices(shure_device_id)['name']
        elif realtek_device_id is not None:
            device_id_to_use = realtek_device_id
            selected_device_name = sd.query_devices(realtek_device_id)['name']
        elif default_device_id is not None:
            device_id_to_use = default_device_id
            selected_device_name = sd.query_devices(default_device_id)['name']
        else:
            if output_devices:
                device_id_to_use = output_devices[0]['index']
                selected_device_name = output_devices[0]['name']
                print(f"フォールバックデバイスを使用します: {selected_device_name}")
            else:
                print("利用可能な出力オーディオデバイスが見つかりません。")
                return 

        print(f"オーディオデバイスを使用します: {selected_device_name} (ID: {device_id_to_use})")

        if device_id_to_use is not None:
            sd.play(audio_np, GCP_SAMPLE_RATE, device=device_id_to_use)
            sd.wait()
            print("再生が完了しました。")
        else:
            print("音声再生デバイスが特定できなかったため、再生をスキップします。")

    except Exception as e:
        print(f"GCP TTS の再生中にエラーが発生しました: {e}")
        traceback.print_exc()

generation_config = {
    "temperature": 1,
    "top_p": 0.95,
    "top_k": 40,
    "max_output_tokens": 8192,
    "response_mime_type": "text/plain",
  }
safety_settings = [
    {
        "category": "HARM_CATEGORY_HARASSMENT",
        "threshold": "BLOCK_NONE"
    },
    {
        "category": "HARM_CATEGORY_HATE_SPEECH",
        "threshold": "BLOCK_NONE"
    },
    {
        "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
        "threshold": "BLOCK_NONE"
    },
    {
        "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
        "threshold": "BLOCK_NONE"
    }
  ]


def interactive_mode():
    """インタラクティブモードのメインループ"""
    global TARGET_LANGUAGE, TARGET_LANGUAGE_BCP47, full_persona, character_name, persona, greeting, guidelines

    chat_session = None
    try:
        # 正しいインポート方法に修正
        from google import genai
        genai.configure(api_key=GEMINI_API_KEY)

        # モデルとチャットセッションの初期化を1つにまとめる
        model = genai.GenerativeModel(
            model_name="gemini-1.5-flash-latest",
            system_instruction=full_persona, # ★キャラクター設定をシステム命令として渡す
            generation_config={
                "temperature": 0.7,
                "top_p": 0.95,
                "top_k": 40,
                "max_output_tokens": 1024,
            },
            safety_settings=[
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
            ]
        )

        chat_session = model.start_chat(
            history=[
                # 履歴の初期設定はシンプルに。システム命令でペルソナは設定済み。
                # 必要であれば、最初の挨拶を履歴に追加することも可能。
                # {
                #     "role": "user",
                #     "parts": ["こんにちは"], # 最初のユーザー発話のダミー
                # },
                # {
                #     "role": "model",
                #     "parts": [greeting],
                # }
            ]
        )
        print("対話用Geminiモデルをペルソナで正常に初期化しました。")

    except Exception as e:
        print(f"エラー: 対話用Geminiモデルの初期化に失敗しました。 {e}")
        print("警告: AIとの対話機能は無効になります。")
        # この後のループで chat_session が None であることをチェックする

    # 挨拶は main() で既に実行されているため、ここでは不要
    # print(f"{character_name}: {greeting}") # 重複するのでコメントアウト

    current_language = TARGET_LANGUAGE_BCP47  # 現在の言語を保持する変数

    # メインループ
    while True:
        try:
            user_input = input("あなた: ")
            if user_input.lower() == 'exit':
                print("終了します。")
                break
            elif user_input.lower() == 'log': # ログファイルの場所を表示
                log_path_message = f"ログファイルの場所: {os.path.abspath(LOG_FILE_PATH)}"
                print(log_path_message)
                continue
            
            # 言語コマンドの処理
            language_match = re.match(LANGUAGE_COMMAND_PATTERN, user_input)
            if language_match:
                lang_code = language_match.group(1)  # ja, en, es
                message_text = language_match.group(2)  # コマンド後のメッセージ
                
                # 言語コードを完全な形式に変換
                if lang_code in SUPPORTED_LANGUAGES_MAP:
                    current_language = SUPPORTED_LANGUAGES_MAP[lang_code]
                    print(f"言語を {current_language} に切り替えました")
                    
                    # 言語切り替えメッセージをログに記録
                    log_to_file("System", f"言語を {current_language} に切り替えました")
                    
                    # メッセージがある場合は処理を続行、なければ次の入力へ
                    if not message_text.strip():
                        continue
                        
                    # 言語コマンドの後のメッセージを使用
                    user_input = message_text
            
            # ユーザー入力をログに記録
            log_to_file("User", user_input)
            
            # 特殊応答パターンの処理
            response_patterns = load_response_patterns()
            special_response = check_special_response(user_input, response_patterns)
            
            # 自己紹介リクエストかチェック
            is_intro_request = is_self_introduction_request(user_input)
            
            if special_response:
                # 特殊応答パターンに一致した場合
                response_text = special_response
            elif is_intro_request:
                # 日本語の場合はテンプレートを使わず、Geminiで生成
                if current_language == "ja-JP":
                    # 通常の応答処理で自己紹介を生成
                    response = chat_session.send_message(user_input)
                    response_text = response.text
                    print("日本語の自己紹介をGeminiで生成しました")
                else:
                    # 日本語以外の場合はテンプレートを使用
                    template = get_template("self_introduction", current_language)
                    if template:
                        response_text = template
                        print(f"自己紹介テンプレートを使用しました: {current_language}")
                    else:
                        # テンプレートがない場合は通常の応答処理
                        if not chat_session:
                            response_text = "申し訳ありません、AIモデルが初期化されていないため、お答えできません。"
                        else:
                            response = chat_session.send_message(user_input)
                            response_text = response.text
            else:
                # 通常の応答処理
                if not chat_session:
                    response_text = "申し訳ありません、AIモデルが初期化されていないため、お答えできません。"
                else:
                    ai_input = user_input
                    if current_language == "en-US":
                        ai_input = f"Respond in English.\nUser: {user_input}"
                    elif current_language == "es-ES":
                        ai_input = f"Respond in Spanish.\nUser: {user_input}"
                    # 他の言語のサポートを追加する場合は、ここにelif節を追加します。

                response = chat_session.send_message(ai_input)
                response_text = response.text
            
            # デフォルト言語（日本語）以外の場合は翻訳
            if current_language != TARGET_LANGUAGE_BCP47:
                print(f"[DEBUG] 翻訳開始: 元の言語={TARGET_LANGUAGE_BCP47}, ターゲット言語={current_language}")
                print(f"[DEBUG] 翻訳前のテキスト: {response_text[:100]}...") # 長い場合は一部のみ表示
                original_text = response_text
                response_text = translate_text(original_text, current_language)
                print(f"[DEBUG] 翻訳後のテキスト: {response_text[:100]}...") # 長い場合は一部のみ表示
                
                # 翻訳前と翻訳後の両方をログに記録
                log_to_file(character_name, original_text, "原文")
                log_to_file(character_name, response_text, current_language)
            else:
                # 翻訳なしの場合は通常通りログに記録
                log_to_file(character_name, response_text, current_language)
            
            # コンソールに全文表示
            print(f"{character_name}: {response_text}")
            
            # 音声合成と再生
            # TTSプロバイダーに応じて適切な関数を呼び出す
            tts_provider = get_tts_provider()
            if tts_provider == "google_aistudio":
                play_audio_google_aistudio(response_text, language_code=current_language)
            else:
                play_audio_gcp(response_text, language_code=current_language)
            
        except Exception as e:
            error_message = f"エラーが発生しました: {e}"
            print(error_message)
            log_to_file("Error", error_message)
            traceback.print_exc()