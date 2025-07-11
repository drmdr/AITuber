import json
import google.generativeai as genai
import wave
import sys
import io

# 標準出力のエンコーディングをUTF-8に設定
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# --- Config ---
CONFIG_FILE = 'config.local.json'
API_KEY_NAME = 'gemini_api_key'

def load_api_key():
    """Loads API key from config.local.json."""
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            config = json.load(f)
        api_key = config.get(API_KEY_NAME)
        if not api_key:
            print(f"エラー: '{API_KEY_NAME}' が {CONFIG_FILE} に見つかりません。")
            return None
        print("APIキーを正常に読み込みました。")
        return api_key
    except FileNotFoundError:
        print(f"エラー: 設定ファイルが見つかりません: {CONFIG_FILE}")
        return None
    except Exception as e:
        print(f"APIキーの読み込み中にエラーが発生しました: {e}")
        return None

def save_wave_file(filename, pcm, channels=1, rate=24000, sample_width=2):
   """Saves PCM audio data to a WAV file."""
   with wave.open(filename, "wb") as wf:
      wf.setnchannels(channels)
      wf.setsampwidth(sample_width)
      wf.setframerate(rate)
      wf.writeframes(pcm)
   print(f"音声を {filename} に保存しました。")

def main():
    """Main function to generate text, then generate TTS audio from it, and save."""
    api_key = load_api_key()
    if not api_key:
        return

    try:
        print("Gemini APIを設定しています...")
        genai.configure(api_key=api_key)
        print("APIの設定が完了しました。")

        # 1. Geminiで読み上げるテキストを生成
        print("読み上げるテキストを生成しています...")
        text_model = genai.GenerativeModel('gemini-1.5-flash-latest')
        text_response = text_model.generate_content("自己紹介と今日の意気込みを30文字程度で簡潔に述べてください。")
        generated_text = text_response.text
        print(f"生成されたテキスト: {generated_text}")

        # 2. 生成されたテキストを音声に変換
        print("TTSモデルを初期化しています...")
        tts_model = genai.GenerativeModel("models/gemini-2.5-flash-preview-tts")
        print("モデルの初期化が完了しました。")

        print("生成されたテキストの音声を生成しています...")
        generation_config = {
            "response_modalities": ["AUDIO"],
            "speech_config": {
                "voice_config": {
                    "prebuilt_voice_config": {
                        "voice_name": "zephyr"
                    }
                }
            }
        }

        audio_response = tts_model.generate_content(
           generated_text,
           generation_config=generation_config
        )
        print("APIからの音声応答を受信しました。")

        audio_data = audio_response.candidates[0].content.parts[0].inline_data.data

        if not audio_data:
            print("エラー: APIから音声データが返されませんでした。")
            return

        # 3. 音声データをファイルに保存
        file_name='output_gemini_text.wav'
        save_wave_file(file_name, audio_data)

    except Exception as e:
        print(f"処理中にエラーが発生しました: {e}")

if __name__ == "__main__":
    main()
