############################################
API_KEY="AIzaSyDJl4VD4qFXN4ERixcN0P7McoyH3dSC8R4"#←自分で入れてね♡
import google.generativeai as genai
import json # 追加
genai.configure(api_key=API_KEY)

from pathlib import Path
from google.cloud import texttospeech
# Google AIスタジオのTTSを使用するためのモジュールをインポート
from google_aistudio_tts import GoogleAIStudioTTS
# Google Cloud Translation APIの代わりにgoogletransを使用
try:
    from googletrans import Translator
    translator = Translator()
    print("googletrans library loaded successfully.")
except ImportError:
    print("googletransライブラリがインストールされていません。翻訳機能は使用できません。")
    print("pip install googletrans==4.0.0-rc1 を実行してインストールしてください。")
    translator = None

import numpy as np
import traceback # エラー追跡用
import sounddevice as sd
# import pytchat # ★コメントアウト
import time 
from time import sleep
import os
import random
from datetime import datetime
import re


# bert_models.load_model(Languages.JP, "ku-nlp/deberta-v2-large-japanese-char-wwm")
# bert_models.load_tokenizer(Languages.JP, "ku-nlp/deberta-v2-large-japanese-char-wwm")

# model_file = r"C:\Users\drmdr\Documents\Surfwind\AITuber\sbv2\Style-Bert-VITS2\model_assets\koharune-ami\koharune-ami.safetensors"#←自分のpath
# config_file = r"C:\Users\drmdr\Documents\Surfwind\AITuber\sbv2\Style-Bert-VITS2\model_assets\koharune-ami\config.json"#←自分のpath
# style_file = r"C:\Users\drmdr\Documents\Surfwind\AITuber\sbv2\Style-Bert-VITS2\model_assets\koharune-ami\style_vectors.npy"#←自分のpath

assets_root = Path("model_assets")

# livechat = pytchat.create(video_id = "9JXQ1XvHz-k") # ★コメントアウト

GEMINI_API_KEY = "YOUR_API_KEY"

# 設定ファイルのパス設定
CONFIG_FILE_PATH = "config.json"
RESPONSE_PATTERNS_FILE_PATH = "response_patterns.json"

# ログファイルのパス設定
LOG_DIR = "logs"
LOG_FILE_PATH = os.path.join(LOG_DIR, "conversation_log.txt")

# ログディレクトリが存在しない場合は作成
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)
    
# 言語設定
DEFAULT_LANGUAGE = "ja-JP"  # デフォルト言語
SUPPORTED_LANGUAGES = {
    "ja": "ja-JP",  # 日本語
    "en": "en-US",  # 英語
    "es": "es-ES"   # スペイン語
}

# 言語コマンドの正規表現パターン
LANGUAGE_COMMAND_PATTERN = r"^!(ja|en|es)\s+(.+)$"
# 特殊応答パターンを読み込む関数
def load_response_patterns():
    try:
        with open(RESPONSE_PATTERNS_FILE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"特殊応答パターンファイルの読み込みに失敗しました: {e}")
        return {"patterns": []}

# テンプレートを取得する関数
def get_template(template_key, language_code="ja-JP"):
    try:
        # config.jsonからテンプレートを取得
        with open(CONFIG_FILE_PATH, "r", encoding="utf-8") as f:
            config_data = json.load(f)
            
        templates = config_data.get("templates", {})
        template_group = templates.get(template_key, {})
        
        # 指定された言語のテンプレートがあれば返す
        if language_code in template_group:
            return template_group[language_code]
        
        # 言語コードの先頭部分だけでマッチするか確認
        lang_prefix = language_code.split('-')[0]
        for lang_code in template_group.keys():
            if lang_code.startswith(lang_prefix):
                return template_group[lang_code]
        
        # 日本語があればそれを返す
        if "ja-JP" in template_group:
            return template_group["ja-JP"]
        
        # 英語があればそれを返す
        if "en-US" in template_group:
            return template_group["en-US"]
        
        # どれもなければ最初のテンプレートを返す
        if template_group:
            return next(iter(template_group.values()))
            
    except Exception as e:
        print(f"テンプレートの取得中にエラーが発生しました: {e}")
    
    return None

# 自己紹介のパターンをチェックする関数
def is_self_introduction_request(text):
    # 自己紹介を要求するパターン
    patterns = [
        r'自己紹介',  # 自己紹介
        r'あなた(に|は)ついて教えて',  # あなたについて教えて
        r'自分(に|は)ついて教えて',  # 自分について教えて
        r'introduce yourself',  # 英語の自己紹介要求
        r'tell (me|us) about yourself',  # 英語の自己紹介要求
        r'who are you',  # 英語の自己紹介要求
        r'pres[eé]ntate',  # スペイン語の自己紹介要求
        r'cu[eé]ntame sobre ti',  # スペイン語の自己紹介要求
        r'qui[eé]n eres'  # スペイン語の自己紹介要求
    ]
    
    for pattern in patterns:
        if re.search(pattern, text.lower()):
            return True
    
    return False

# 特殊応答パターンに一致するか確認し、一致すれば応答を返す関数
def check_special_response(text, patterns_data):
    for pattern_info in patterns_data.get("patterns", []):
        pattern_str = pattern_info.get("pattern", "")
        case_insensitive = pattern_info.get("case_insensitive", False)
        
        if not pattern_str:
            continue
            
        flags = re.IGNORECASE if case_insensitive else 0
        pattern = re.compile(pattern_str, flags)
        
        if pattern.match(text.strip()):
            responses = pattern_info.get("responses", [])
            if responses:
                return random.choice(responses)
    
    return None

try:
    with open(CONFIG_FILE_PATH, "r", encoding="utf-8") as f:
        config = json.load(f)
    character_name = config.get("character_name", "AITuber")
    persona = config.get("persona", "あなたは親切なAIアシスタントです。")
    greeting = config.get("greeting", "こんにちは！")
    guidelines = config.get("guidelines", [])
    
    # ペルソナとガイドラインを組み合わせる
    persona_intro = f"{persona} うち、話すときはいつもエセ関西弁やねん。"
    full_persona = f"あなたは以下の設定のキャラクターとして応答してください。\n\n--- キャラクター設定 ---\n名前: {character_name}\n基本ペルソナ: {persona_intro}\n挨拶: {greeting}\n\n--- 応答ガイドライン ---\n"
    for guideline in guidelines:
        full_persona += f"- {guideline}\n"
    full_persona += "--- 設定ここまで ---"
except FileNotFoundError:
    print(f"エラー: {CONFIG_FILE_PATH} が見つかりません。デフォルト設定を使用します。")
    character_name = "AITuber"
    persona = "あなたは親切なAIアシスタントです。"
    greeting = "こんにちは！"
    guidelines = ["必ずエセ関西弁で話してください。例：～やで、～やねん、～なんや、～やろ、～ちゃう？など。"]
    full_persona = persona + "\n\nガイドライン:\n- " + guidelines[0] + "\n"
except json.JSONDecodeError:
    print(f"エラー: {CONFIG_FILE_PATH} の形式が正しくありません。デフォルト設定を使用します。")
    character_name = "AITuber"
    persona = "あなたは親切なAIアシスタントです。"
    greeting = "こんにちは！"
    guidelines = ["必ずエセ関西弁で話してください。例：～やで、～やねん、～なんや、～やろ、～ちゃう？など。"]
    full_persona = persona + "\n\nガイドライン:\n- " + guidelines[0] + "\n"

# Google Cloudの認証情報を確認する関数
def check_gcp_credentials():
    import os
    cred_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if not cred_path:
        print("\n\n\u8b66告: GOOGLE_APPLICATION_CREDENTIALS 環境変数が設定されていません\n")
        print("以下のコマンドを実行して設定してください:")
        print("$env:GOOGLE_APPLICATION_CREDENTIALS=\"C:\\path\\to\\your-credentials.json\"")
        return False
    elif not os.path.exists(cred_path):
        print(f"\n\n\u8b66告: 認証情報ファイルが見つかりません: {cred_path}\n")
        return False
    return True

# GCP TTSクライアントの初期化
try:
    # 認証情報を確認
    if check_gcp_credentials():  # 認証情報が有効
        try:
            gcp_tts_client = texttospeech.TextToSpeechClient()
            print("Google Cloud TextToSpeechClient initialized successfully.")
        except Exception as e:
            print("\n\nWarning: Failed to initialize Google Cloud TextToSpeechClient.\n")
            print(f"エラーの詳細: {e}")
            traceback.print_exc()
            print("\n認証情報が有効であるか、GCPプロジェクトでText-to-Speech APIが有効になっているか確認してください\n")
            print("音声なしで続行します\n")
            gcp_tts_client = None
except Exception as e:
    print("\n\nWarning: An unexpected error occurred during Google Cloud authentication check.\n")
    print(f"エラーの詳細: {e}")
    traceback.print_exc()
    print("音声なしで続行します\n")
    gcp_tts_client = None
    
# Google AIスタジオのTTSクライアントの初期化
try:
    # 設定ファイルからAPIキーを読み込む
    with open(CONFIG_FILE_PATH, "r", encoding="utf-8") as f:
        config_data = json.load(f)
    
    tts_settings = config_data.get("tts_settings", {})
    api_key = tts_settings.get("api_key", "")
    
    if api_key:
        google_aistudio_tts_client = GoogleAIStudioTTS(api_key=api_key)
        print("Google AIスタジオのTTSクライアントをAPIキーで初期化しました。")
    else:
        google_aistudio_tts_client = GoogleAIStudioTTS()
        print("Google AIスタジオのTTSクライアントを初期化しました（APIキーなし）。")
        print("警告: APIキーが設定されていないため、認証が必要な機能は使用できません。")
except Exception as e:
    print(f"Failed to initialize Google AI Studio TTS client: {e}")
    traceback.print_exc()
    google_aistudio_tts_client = None

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
    if not translator:
        print("翻訳ライブラリが初期化されていないため、翻訳できません。")
        return text
        
    try:
        # 言語コードから国コードを削除（ja-JP → ja）
        target = target_language.split('-')[0]
        
        # googletransで翻訳を実行
        result = translator.translate(text, dest=target)
        translated_text = result.text
        
        print(f"翻訳: {target_language}")
        return translated_text
    except Exception as e:
        print(f"翻訳中にエラーが発生しました: {e}")
        return text

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

def play_audio_google_aistudio(text_to_speak, language_code="ja-JP", max_retries=3):
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
model = genai.GenerativeModel(
    model_name="gemini-2.0-flash-exp", # モデル名を元に戻す
    generation_config=generation_config,
    safety_settings=safety_settings
  )

# chat_session の初期化を修正
chat_session = model.start_chat(
    history=[
        {
            "role": "user",
            "parts": [full_persona], # ペルソナとガイドラインを組み合わせたものを使用
        },
        {
            "role": "model",
            "parts": [greeting], # config.json の greeting を最初の応答として設定
        }
    ]
)

def interactive_mode():
    # 挨拶メッセージの取得と再生
    greeting_message = get_template("greeting")
    if greeting_message:
        print(f"{character_name}: {greeting_message}")
        log_to_file(character_name, greeting_message, DEFAULT_LANGUAGE)
        tts_provider = get_tts_provider()
        if tts_provider == "google_aistudio":
            play_audio_google_aistudio(greeting_message, language_code=DEFAULT_LANGUAGE)
        else:
            play_audio_gcp(greeting_message, language_code=DEFAULT_LANGUAGE)
    else:
        print(f"{character_name}: こんにちは！何かお手伝いできることはありますか？") # デフォルトの挨拶
        log_to_file(character_name, "こんにちは！何かお手伝いできることはありますか？", DEFAULT_LANGUAGE)
        tts_provider = get_tts_provider()
        if tts_provider == "google_aistudio":
            play_audio_google_aistudio("こんにちは！何かお手伝いできることはありますか？", language_code=DEFAULT_LANGUAGE)
        else:
            play_audio_gcp("こんにちは！何かお手伝いできることはありますか？", language_code=DEFAULT_LANGUAGE)

    # モデルの準備
    generation_config = {
        "temperature": 0.7, # 応答のランダム性を調整 (0.0-1.0)
        "top_p": 0.95,      # Top-pサンプリング (0.0-1.0)
        "top_k": 40,        # Top-kサンプリング (整数)
        "max_output_tokens": 1024, # 最大出力トークン数
    }

    model = genai.GenerativeModel(
        model_name="gemini-1.5-flash-latest",
        generation_config=generation_config,
        safety_settings=[
            {
                "category": "HARM_CATEGORY_HARASSMENT",
                "threshold": "BLOCK_NONE",
            },
            {
                "category": "HARM_CATEGORY_HATE_SPEECH",
                "threshold": "BLOCK_NONE",
            },
            {
                "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                "threshold": "BLOCK_NONE",
            },
            {
                "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                "threshold": "BLOCK_NONE",
            },
        ]
        # system_instructionパラメータは削除（古いバージョンではサポートされていないため）
    )

    # ペルソナを最初のユーザーメッセージとして設定
    chat_session = model.start_chat(
        history=[
            {
                "role": "user",
                "parts": [full_persona],
            },
            {
                "role": "model",
                "parts": [greeting],
            }
        ]
    )

    current_language = DEFAULT_LANGUAGE  # 現在の言語を保持する変数

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
                if lang_code in SUPPORTED_LANGUAGES:
                    current_language = SUPPORTED_LANGUAGES[lang_code]
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
                        response = chat_session.send_message(user_input)
                        response_text = response.text
            else:
                # 通常の応答処理
                ai_input = user_input
                if current_language == "en-US":
                    ai_input = f"Respond in English.\nUser: {user_input}"
                elif current_language == "es-ES":
                    ai_input = f"Respond in Spanish.\nUser: {user_input}"
                # 他の言語のサポートを追加する場合は、ここにelif節を追加します。

                response = chat_session.send_message(ai_input)
                response_text = response.text
            
            # デフォルト言語（日本語）以外の場合は翻訳
            if current_language != DEFAULT_LANGUAGE:
                original_text = response_text
                response_text = translate_text(original_text, current_language)
                
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

def manuscript_mode():
    print("原稿読み上げモードを開始します。")
    log_to_file("System", "原稿読み上げモードを開始しました")
    manuscript_file_path = Path("scripts") / "manuscript.txt"

    try:
        with open(manuscript_file_path, "r", encoding="utf-8") as f:
            manuscript_content = f.read()
        
        if not manuscript_content.strip():
            print(f"{manuscript_file_path} が空です。")
            log_to_file("System", f"{manuscript_file_path} が空です。")
            return

        paragraphs = [p.strip() for p in manuscript_content.split('\n\n') if p.strip()]

        if not paragraphs:
            print("原稿に読み上げ可能な段落がありません。")
            log_to_file("System", "原稿に読み上げ可能な段落がありません。")
            return

        print(f"\n--- {manuscript_file_path} の内容 ---")
        for i, para in enumerate(paragraphs):
            print(f"\n[段落 {i+1}]\n{para}")
            log_to_file("Manuscript", f"[段落 {i+1}] {para}") # 原稿内容もログに記録
            tts_provider = get_tts_provider()
            if tts_provider == "google_aistudio":
                play_audio_google_aistudio(para, language_code=DEFAULT_LANGUAGE)
            else:
                play_audio_gcp(para, language_code=DEFAULT_LANGUAGE)
        print("\n--- 原稿の読み上げが完了しました --- ")
        log_to_file("System", "原稿の読み上げが完了しました")

    except FileNotFoundError:
        print(f"エラー: 原稿ファイルが見つかりません。次のパスに `manuscript.txt` を配置してください: {manuscript_file_path.parent.resolve()}")
        log_to_file("Error", f"原稿ファイルが見つかりません: {manuscript_file_path}")
    except Exception as e:
        error_message = f"原稿読み上げモードでエラーが発生しました: {e}"
        print(error_message)
        log_to_file("Error", error_message)
        traceback.print_exc()

if __name__ == "__main__":
    # ログディレクトリが存在しない場合は作成
    if not os.path.exists(LOG_DIR):
        os.makedirs(LOG_DIR)

    while True:
        print("\nモードを選択してください:")
        print("1: インタラクティブモード (AIと会話)")
        print("2: 原稿読み上げモード (scripts/manuscript.txt を読み上げ)")
        print("exit: 終了")
        mode_choice = input("選択: ")

        if mode_choice == '1':
            log_to_file("System", "インタラクティブモードが選択されました")
            interactive_mode()
            # ループを継続してモード選択に戻る
        elif mode_choice == '2':
            log_to_file("System", "原稿読み上げモードが選択されました")
            manuscript_mode()
            # ループを継続してモード選択に戻る
        elif mode_choice.lower() == 'exit':
            print("終了します。")
            break
        else:
            print("無効な選択です。1, 2, または exit を入力してください。")