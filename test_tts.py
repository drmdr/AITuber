import os
import sys
import traceback
from google_aistudio_tts import GoogleAIStudioTTS

def main():
    try:
        # APIキーを設定
        api_key = "AIzaSyDJl4VD4qFXN4ERixcN0P7McoyH3dSC8R4"  # 設定ファイルから読み込んだAPIキー
        
        # Google AIスタジオTTSクライアントを初期化
        tts_client = GoogleAIStudioTTS(api_key=api_key)
        
        # テスト用のテキスト
        test_text = "こんにちは、これはGoogle AIスタジオTTSのテストです。"
        
        # プロンプト設定
        prompt = "Read aloud in a warm and friendly tone: Act as an anime voice actor. cute and transparent voice"
        
        print("Google AIスタジオTTSのテストを開始します...")
        print(f"テキスト: {test_text}")
        print(f"プロンプト: {prompt}")
        
        # 音声合成を実行
        audio_data = tts_client.synthesize_speech(test_text, voice_name="Zephyr", prompt=prompt)
        
        if audio_data:
            # 音声データを保存
            output_file = "test_output.wav"
            with open(output_file, "wb") as f:
                f.write(audio_data)
            print(f"音声合成に成功しました。ファイル '{output_file}' に保存しました。({len(audio_data)} バイト)")
        else:
            print("音声合成に失敗しました。")
    
    except Exception as e:
        print(f"エラーが発生しました: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    main()
