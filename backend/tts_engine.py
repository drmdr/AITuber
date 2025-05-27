import os
import json
import torch
import numpy as np
import soundfile as sf
import requests
from tqdm import tqdm
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class StyleBertVITS2:
    def __init__(self, config_path):
        """
        Style-Bert-VITS2の音声合成エンジンを初期化します。
        
        Args:
            config_path (str): 設定ファイルのパス
        """
        self.config = self._load_config(config_path)
        self.model_config = self.config["style_bert_vits2"]
        self.device = self.model_config["device"]
        
        # モデルが存在しない場合はダウンロードするためのディレクトリを作成
        os.makedirs(self.model_config["model_path"], exist_ok=True)
        
        # モデルの読み込み
        self._load_model()
        
        logger.info("Style-Bert-VITS2の初期化が完了しました。")
    
    def _load_config(self, config_path):
        """設定ファイルを読み込みます。"""
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def _load_model(self):
        """Style-Bert-VITS2のモデルを読み込みます。"""
        try:
            # ここでStyle-Bert-VITS2のモデルを読み込む処理を実装
            # 実際のStyle-Bert-VITS2のAPIに合わせて調整が必要
            
            # モデルが存在するか確認
            model_config_path = self.model_config["config_path"]
            if not os.path.exists(model_config_path):
                logger.warning(f"モデル設定ファイルが見つかりません: {model_config_path}")
                logger.info("モデルのダウンロードが必要です。公式リポジトリからダウンロードしてください。")
                return
            
            # モデルの設定を読み込む
            with open(model_config_path, 'r', encoding='utf-8') as f:
                model_config = json.load(f)
            
            # モデルのパラメータを設定
            self.sample_rate = model_config.get("audio", {}).get("sampling_rate", 24000)
            
            # デバイスの設定
            if self.device == "cuda" and not torch.cuda.is_available():
                logger.warning("CUDAが利用できないため、CPUを使用します。")
                self.device = "cpu"
            
            # モデルをロード（実際のStyle-Bert-VITS2のコードに合わせて調整が必要）
            logger.info(f"モデルを{self.device}にロードしています...")
            # ここに実際のモデル読み込みコードを追加
            
            logger.info("モデルの読み込みが完了しました。")
        
        except Exception as e:
            logger.error(f"モデルの読み込み中にエラーが発生しました: {str(e)}")
            raise
    
    def synthesize(self, text, output_path=None):
        """
        テキストから音声を合成します。
        
        Args:
            text (str): 合成するテキスト
            output_path (str, optional): 出力ファイルパス。Noneの場合は音声データを返します。
            
        Returns:
            np.ndarray or None: 音声データまたはNone（output_pathが指定された場合）
        """
        try:
            logger.info(f"テキストを音声に変換しています: {text[:30]}...")
            
            # パラメータの設定
            language = self.model_config["language"]
            speaker_id = self.model_config["speaker_id"]
            style_id = self.model_config["style_id"]
            noise_scale = self.model_config["noise_scale"]
            noise_scale_w = self.model_config["noise_scale_w"]
            length_scale = self.model_config["length_scale"]
            
            # Style-Bert-VITS2サーバーにHTTPリクエストを送信
            server_url = self.model_config.get("server_url", "http://127.0.0.1:8080")
            voice_api_url = f"{server_url}/voice"
            
            params = {
                "text": text,
                "language": language,
                "speaker_id": speaker_id,
                "style": style_id,  # スタイルIDをスタイルとして使用
                "noise": noise_scale,
                "noisew": noise_scale_w,
                "length": length_scale,
                "sdp_ratio": 0.2,  # デフォルト値
                "auto_split": True,  # 長いテキストを自動分割
                "split_interval": 0.5  # 分割間隔
            }
            
            logger.info(f"Style-Bert-VITS2サーバーにリクエストを送信: {voice_api_url}")
            response = requests.get(voice_api_url, params=params)
            
            if response.status_code != 200:
                logger.error(f"サーバーからエラーレスポンスを受信: {response.status_code} {response.text}")
                raise Exception(f"サーバーエラー: {response.status_code}")
            
            # レスポンスから音声データを取得
            audio_data = response.content
            
            if output_path:
                # 音声ファイルとして保存
                with open(output_path, 'wb') as f:
                    f.write(audio_data)
                logger.info(f"音声ファイルを保存しました: {output_path}")
                return None
            else:
                # 音声データをnumpy配列に変換
                import io
                with io.BytesIO(audio_data) as buf:
                    sample_rate, audio = sf.read(buf)
                return audio
                
        except Exception as e:
            logger.error(f"音声合成中にエラーが発生しました: {str(e)}")
            raise
    
    def download_model(self, url, save_path):
        """
        モデルをダウンロードします。
        
        Args:
            url (str): ダウンロードURL
            save_path (str): 保存先パス
        """
        try:
            logger.info(f"モデルをダウンロードしています: {url}")
            
            response = requests.get(url, stream=True)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            block_size = 1024
            
            with open(save_path, 'wb') as f, tqdm(
                desc=os.path.basename(save_path),
                total=total_size,
                unit='iB',
                unit_scale=True,
                unit_divisor=1024,
            ) as bar:
                for data in response.iter_content(block_size):
                    size = f.write(data)
                    bar.update(size)
            
            logger.info(f"モデルのダウンロードが完了しました: {save_path}")
        
        except Exception as e:
            logger.error(f"モデルのダウンロード中にエラーが発生しました: {str(e)}")
            if os.path.exists(save_path):
                os.remove(save_path)
            raise
