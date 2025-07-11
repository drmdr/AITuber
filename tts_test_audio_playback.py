import json
import google.generativeai as genai
import sounddevice as sd
import soundfile as sf
import numpy as np
import io
import sys

# 標準出力のエンコーディングをUTF-8に設定
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# --- Config ---
CONFIG_FILE = 'config.local.json'
API_KEY_NAME = 'gemini_api_key'
AUDIO_DEVICE_KEY = 'audio_output_device_index'

def load_config():
    """Loads API key and audio device index from config.local.json."""
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            config = json.load(f)
        api_key = config.get(API_KEY_NAME)
        device_index = config.get(AUDIO_DEVICE_KEY)

        if not api_key:
            print(f"エラー: '{API_KEY_NAME}' が {CONFIG_FILE} に見つかりません。")
            return None, None
        if device_index is None: # 0は有効なデバイスIDの可能性があるため、Noneと比較
            print(f"エラー: '{AUDIO_DEVICE_KEY}' が {CONFIG_FILE} に見つかりません。")
            return None, None
            
        print("APIキーとオーディオデバイス情報を正常に読み込みました。")
        return api_key, int(device_index)
    except FileNotFoundError:
        print(f"エラー: 設定ファイルが見つかりません: {CONFIG_FILE}")
        return None, None
    except Exception as e:
        print(f"設定ファイルの読み込み中にエラーが発生しました: {e}")
        return None, None

def play_audio(data, samplerate, device_index):
    """Plays audio data on the specified audio device."""
    try:
        print(f"デバイス {device_index} で音声を再生します...")
        sd.play(data, samplerate, device=device_index)
        sd.wait() # 再生が完了するまで待機
        print("再生が完了しました。")
    except Exception as e:
        print(f"音声の再生中にエラーが発生しました: {e}")

def main():
    """Main function to generate text, TTS, and play audio."""
    api_key, device_index = load_config()
    if not api_key or device_index is None:
        return

    try:
        print("Gemini APIを設定しています...")
        genai.configure(api_key=api_key)
        print("APIの設定が完了しました。")

        # 1. 読み上げるテキストを定義
        generated_text = "音声再生の最終テストです。これが成功すれば、本体への組み込みを開始します。"
        print(f"読み上げるテキスト: {generated_text}")

        # 2. 生成されたテキストを音声に変換
        print("TTSモデルを初期化しています...")
        tts_model = genai.GenerativeModel("models/gemini-2.5-flash-preview-tts")
        print("モデルの初期化が完了しました。")

        print("テキストの音声を生成しています...")
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

        audio_data_bytes = audio_response.candidates[0].content.parts[0].inline_data.data

        if not audio_data_bytes:
            print("エラー: APIから音声データが返されませんでした。")
            return

        # 3. 音声データを再生
        # APIから返されるのはヘッダなしのRAW PCMデータのため、soundfileを使わずに直接処理します。
        # サンプルレート24000, 16-bit signed, mono と仮定します。
        samplerate = 24000
        audio_array = np.frombuffer(audio_data_bytes, dtype=np.int16)

        # sounddeviceが期待するfloat32形式に正規化します。
        audio_array_float32 = audio_array.astype(np.float32) / 32768.0

        play_audio(audio_array_float32, samplerate, device_index)

    except Exception as e:
        print(f"処理中にエラーが発生しました: {e}")

if __name__ == "__main__":
    main()
