import google.generativeai as genai
import os
import json
import sounddevice as sd
import soundfile as sf
import tempfile
import sys
import io

# 標準出力のエンコーディングをUTF-8に設定
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# --- Config ---
CONFIG_FILE = 'config.local.json'
API_KEY_NAME = 'gemini_api_key'

def load_api_key():
    """config.local.jsonからAPIキーを読み込む"""
    if not os.path.exists(CONFIG_FILE):
        print(f"エラー: 設定ファイルが見つかりません: {CONFIG_FILE}")
        return None
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            config = json.load(f)
        api_key = config.get(API_KEY_NAME)
        if not api_key:
            print(f"エラー: {CONFIG_FILE} に {API_KEY_NAME} が見つかりません。")
            return None
        print("APIキーを正常に読み込みました。")
        return api_key
    except Exception as e:
        print(f"設定ファイルの読み込み中にエラーが発生しました: {e}")
        return None

def main():
    """TTSのテストを実行するメイン関数"""
    api_key = load_api_key()
    if not api_key:
        return

    try:
        genai.configure(api_key=api_key)
        print("Gemini APIクライアントを正常に初期化しました。")
    except Exception as e:
        print(f"Gemini APIクライアントの初期化に失敗しました: {e}")
        return

    text_to_speak = "This is a test of the text-to-speech functionality."
    print(f'合成するテキスト: "{text_to_speak}"')

    try:
        print("TTSモデルを初期化します...")
        # 正しいモデル名を使用
        tts_model = genai.GenerativeModel('models/gemini-2.5-flash-preview-tts')

        print("音声合成API `generate_content` を呼び出します...")
        # 応答形式として音声を指定
        generation_config = genai.types.GenerationConfig(
            response_mime_type="audio/wav"
        )
        response = tts_model.generate_content(
            text_to_speak,
            generation_config=generation_config
        )

        # 音声データを取得
        audio_data = response.candidates[0].content.parts[0].blob.data
        print("音声合成に成功しました。")

        # 一時ファイルに保存して再生
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
            temp_filename = temp_file.name
            temp_file.write(audio_data)
        
        print(f"一時ファイルを作成しました: {temp_filename}")
        data, samplerate = sf.read(temp_filename)
        print("音声ファイルを読み込みました。再生します...")
        sd.play(data, samplerate)
        sd.wait()
        print("再生が完了しました。")
        os.remove(temp_filename)

    except Exception as e:
        print(f"音声合成中に予期せぬエラーが発生しました: {e}")

if __name__ == "__main__":
    main()
