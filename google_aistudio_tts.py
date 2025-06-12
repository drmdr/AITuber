import os
import requests
import json
import tempfile
import numpy as np
import soundfile as sf
import base64
import time
import traceback
import requests
import wave

# Google Gemini APIクライアントライブラリをインポート
# エラーが発生した場合は従来の方法を使用するために例外を捕捉
try:
    import google.generativeai as genai
    from google.generativeai import types as genai_types # Avoid name collision if 'types' is used elsewhere
    GENAI_AVAILABLE = True
except ImportError:
    genai = None
    genai_types = None
    GENAI_AVAILABLE = False
    print("Warning: The 'google-generativeai' module (for Gemini API) was not found. TTS functionality in this module might fall back to legacy methods or fail if it's a hard dependency. The main AITuber application will likely fail if it requires this package for its core AI chat functionality.")
    # HTTPリクエストに必要なライブラリ (for legacy TTS if used by the class)
    import requests
    import base64

class GoogleAIStudioTTS:
    """
    Google AIスタジオのText-to-Speech APIを使用して音声を合成するクラス
    """
    
    def __init__(self, api_key=None):
        # APIキーを保存
        self.api_key = api_key
        
        if api_key and GENAI_AVAILABLE:
            # Gemini APIクライアントを初期化
            genai.configure(api_key=api_key)
            print("Google AI Studio TTS configured with API key using google-generativeai.")
        elif not GENAI_AVAILABLE:
            print("Warning: 'google-generativeai' module is not available. Falling back to legacy methods if applicable.")
            # APIキーがない場合は従来のエンドポイント（ログイン必要）
            self.api_url = "https://aistudio.google.com/app/speech/generate"
        else:
            print("Warning: API key not specified. Falling back to legacy methods if applicable.")
            # APIキーがない場合は従来のエンドポイント（ログイン必要）
            self.api_url = "https://aistudio.google.com/app/speech/generate"
        
    def synthesize_speech(self, text, voice_name="Zephyr", prompt=None):
        """
        テキストを音声に変換します。
        text: 音声に変換するテキスト
        voice_name: 使用する音声の名前（デフォルトはZephyr）
        prompt: 音声合成のためのプロンプト（オプション）
        
        戻り値: 音声データ（バイナリ）
        """
        import requests
        import json
        import base64
        import traceback
        
        try:
            print(f"[DEBUG] Google AIスタジオTTS: テキスト '{text[:30]}...' を音声に変換します")
            print(f"[DEBUG] Google AIスタジオTTS: ボイス '{voice_name}', プロンプト '{prompt[:30] if prompt else 'なし'}...'")
            
            # APIリクエストの準備
            if self.api_key:
                # Determine the text to be synthesized, including the prompt if provided
                text_to_synthesize = text
                if prompt:
                    text_to_synthesize = f"{prompt}: {text}"

                # Google Gemini API用のペイロード形式
                # Based on official documentation and error messages
                payload = {
                    "contents": [
                        {
                            "parts": [
                                {
                                    "text": text_to_synthesize
                                }
                            ]
                            # "role": "user" # roleはオプショナルな場合が多いので、一旦含めない
                        }
                    ],
                    "generationConfig": {
                        "response_modalities": ["AUDIO"],
                        "speech_config": {
                            "voice_config": {
                                "prebuilt_voice_config": {
                                    "voice_name": voice_name
                                }
                            }
                        }
                    }
                }
                
                # APIリクエストURLを設定
                # 公式ドキュメントに基づいて正しいモデル名とエンドポイントを使用
                request_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-tts:generateContent?key={self.api_key}"
            else:
                # 従来のAIスタジオ用のペイロード形式
                payload = {
                    "text": text,
                    "voice": voice_name,
                    "prompt": prompt
                }
            
            # ヘッダーを追加
            headers = {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
            
            # APIリクエストURLの準備
            if self.api_key:
                url_to_use = request_url
            else:
                url_to_use = self.api_url
                
            print(f"[DEBUG] Google AIスタジオTTS: APIリクエスト送信中: {url_to_use}")
            
            # APIリクエストを送信
            response = requests.post(
                url_to_use,
                json=payload,
                headers=headers
            )
            
            print(f"[DEBUG] Google AIスタジオTTS: レスポンスステータスコード: {response.status_code}")
            
            # レスポンスのステータスコードを確認
            if response.status_code != 200:
                error_msg = f"APIリクエストが失敗しました。ステータスコード: {response.status_code}"
                print(f"エラー: {error_msg}")
                try:
                    error_response = response.json()
                    print(f"レスポンス: {json.dumps(error_response, indent=2, ensure_ascii=False)[:500]}...")
                except:
                    print(f"レスポンステキスト: {response.text[:500]}...")
                raise Exception(error_msg)
            
            # レスポンスからオーディオデータを取得
            try:
                response_text = response.text
                print(f"[DEBUG] Google AIスタジオTTS: レスポンス受信 (長さ: {len(response_text)} バイト)")
                
                # レスポンスがJSONでない場合はエラー
                if not response_text.strip().startswith('{'):
                    raise Exception(f"無効なレスポンス形式: {response_text[:200]}...")
                
                response_json = response.json()
                
                # 公式ドキュメントに基づいてレスポンス処理を更新
                if self.api_key:
                    # 新しいレスポンス形式の処理
                    if "candidates" in response_json and len(response_json["candidates"]) > 0:
                        candidate = response_json["candidates"][0]
                        if "content" in candidate and "parts" in candidate["content"]:
                            for part in candidate["content"]["parts"]:
                                print(f"[DEBUG] Google AIスタジオTTS: partのキー: {list(part.keys())}")
                                if "inlineData" in part: # 'inline_data' から 'inlineData' に修正
                                    print(f"[DEBUG] Google AIスタジオTTS: inlineDataのキー: {list(part['inlineData'].keys())}") # 同上
                                    if "data" in part["inlineData"]: # 同上
                                        print(f"[DEBUG] Google AIスタジオTTS: inlineData['data']の最初の50文字: {part['inlineData']['data'][:50]}") # 同上
                                        # オーディオデータを取得
                                        audio_data = base64.b64decode(part["inlineData"]["data"]) # 同上
                                        print(f"[DEBUG] Google AIスタジオTTS: オーディオデータ取得成功 ({len(audio_data)} バイト)")
                                        return audio_data
                                    else:
                                        print("[DEBUG] Google AIスタジオTTS: inlineDataに 'data' キーが見つかりません。")
                                else:
                                    print("[DEBUG] Google AIスタジオTTS: partに 'inlineData' キーが見つかりません。")
                        print(f"[DEBUG] Google AIスタジオTTS: レスポンスキー: {list(response_json.keys())}")
                        if "candidates" in response_json:
                            print(f"[DEBUG] 候補数: {len(response_json['candidates'])}")
                            if len(response_json['candidates']) > 0:
                                candidate = response_json['candidates'][0]
                                print(f"[DEBUG] 候補キー: {list(candidate.keys())}")
                                if "content" in candidate:
                                    content = candidate["content"]
                                    print(f"[DEBUG] コンテンツキー: {list(content.keys())}")
                                    if "parts" in content:
                                        parts = content["parts"]
                                        print(f"[DEBUG] パーツ数: {len(parts)}")
                                        for i, part in enumerate(parts):
                                            print(f"[DEBUG] パーツ{i}キー: {list(part.keys())}")
                else:
                    # 従来のAIスタジオのレスポンス形式の処理
                    if "audio" in response_json:
                        # Base64エンコードされたオーディオデータをデコード
                        audio_data = base64.b64decode(response_json["audio"])
                        print(f"[DEBUG] Google AIスタジオTTS: オーディオデータ取得成功 ({len(audio_data)} バイト)")
                        return audio_data
                
                print(f"[DEBUG] Google AIスタジオTTS: オーディオデータが見つかりませんでした。レスポンスキー: {list(response_json.keys())}")
                return None
                
            except Exception as e:
                print(f"[DEBUG] Google AIスタジオTTS: レスポンスの解析中にエラーが発生しました: {e}")
                traceback.print_exc()
                raise
                
        except Exception as e:
            print(f"[DEBUG] Google AIスタジオTTS: 音声合成中にエラーが発生しました: {e}")
            traceback.print_exc()
        
        return None
    
    def synthesize_to_file(self, text, output_file, voice_name="Zephyr", prompt="Read aloud in a warm and friendly tone: Act as an anime voice actor. cute and transparent voice"):
        """
        テキストを音声に変換し、ファイルに保存します
        
        Args:
            text (str): 音声に変換するテキスト
            output_file (str): 出力ファイルのパス
            voice_name (str): 使用する音声の名前（デフォルト: "Zephyr"）
            prompt (str): 音声生成のためのプロンプト
            
        Returns:
            bool: 成功した場合はTrue、失敗した場合はFalse
        """
        audio_data = self.synthesize_speech(text, voice_name, prompt)
        if audio_data:
            try:
                with open(output_file, "wb") as f:
                    f.write(audio_data)
                return True
            except Exception as e:
                print(f"ファイルの保存中にエラーが発生しました: {e}")
        
        return False
