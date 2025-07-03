# ==============================================================================
# Gemini API TTS Client
# ------------------------------------------------------------------------------
# このファイルは、Google Gemini APIの公式ドキュメントに基づき実装されています。
# 音声合成のコアロジックであり、安定動作の要です。
# 不用意な変更はシステム全体の動作に影響を与える可能性があるため、
# 仕様変更やAPIのアップデート時以外は、原則として改変しないでください。
# ==============================================================================
import traceback

try:
    from google import genai
    from google.genai import types
    GENAI_AVAILABLE = True
except ImportError:
    genai = None
    types = None
    GENAI_AVAILABLE = False
    # エラーメッセージも、より正確な情報に更新
    print("FATAL: The 'google-genai' package is installed, but the 'google.genai' module could not be imported. Check for installation issues.")

class GoogleAIStudioTTS:
    """
    Google Gemini APIのText-to-Speechを使用して音声を合成するクラス。
    公式の 'google-genai' SDK を使用します。
    """

    def __init__(self, api_key=None):
        """
        APIキーを使用してクライアントを初期化します。
        """
        if not GENAI_AVAILABLE:
            raise ImportError("google-genaiライブラリが見つかりません。pip install google-genai を実行してください。")
        
        if not api_key:
            raise ValueError("APIキーが指定されていません。")
            
        # 公式ドキュメントに準拠し、genai.Clientを使用します。
        self.client = genai.Client(api_key=api_key)
        print("GoogleAIStudioTTS: Gemini API client initialized successfully.")

    def synthesize_speech(self, text, voice_name="Zephyr", prompt=None):
        """
        テキストを音声に変換します。
        
        Args:
            text (str): 音声に変換するテキスト。
            voice_name (str): 使用する音声の名前 (例: "Zephyr")。
            prompt (str, optional): 音声のトーンやスタイルを指定するプロンプト。
        
        Returns:
            bytes: 音声データ。エラーの場合はNone。
        """
        print(f"[DEBUG] Synthesizing speech with Gemini API. Voice: {voice_name}, Text: '{text[:50]}...'")
        
        # プロンプトがあればテキストの前に付与する
        synthesis_text = f"{prompt}: {text}" if prompt else text

        try:
            # 公式ドキュメントに準拠したTTSリクエスト
            response = self.client.models.generate_content(
                model="models/gemini-2.5-flash-preview-tts",
                contents=synthesis_text,
                config=types.GenerateContentConfig(
                    response_modalities=["AUDIO"],
                    speech_config=types.SpeechConfig(
                        voice_config=types.VoiceConfig(
                            prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                voice_name=voice_name,
                            )
                        )
                    ),
                )
            )
            
            # レスポンスから音声データを抽出
            audio_data = response.candidates[0].content.parts[0].inline_data.data
            print(f"[DEBUG] Gemini API: Audio data received ({len(audio_data)} bytes).")
            return audio_data

        except Exception as e:
            print(f"FATAL: An error occurred during Gemini API speech synthesis: {e}")
            traceback.print_exc()
            return None

    def synthesize_to_file(self, text, output_file, voice_name="Zephyr", prompt=None):
        """
        テキストを音声に変換し、ファイルに保存します。
        """
        audio_data = self.synthesize_speech(text, voice_name, prompt)
        if audio_data:
            try:
                with open(output_file, "wb") as f:
                    f.write(audio_data)
                print(f"[DEBUG] Audio content written to {output_file}")
                return True
            except Exception as e:
                print(f"FATAL: Error saving audio file: {e}")
                traceback.print_exc()
        return False
