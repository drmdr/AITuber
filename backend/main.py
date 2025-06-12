import os
import json
import time
import logging
import argparse
import threading
import pygame
import numpy as np
from tts_engine import StyleBertVITS2

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class AITuberApp:
    def __init__(self, config_path="config.json"):
        """
        AITuberアプリケーションを初期化します。
        
        Args:
            config_path (str): 設定ファイルのパス
        """
        self.config_path = config_path
        self.config = self._load_config()
        
        # ディレクトリの作成
        os.makedirs("./models", exist_ok=True)
        os.makedirs("./avatar", exist_ok=True)
        os.makedirs("./output", exist_ok=True)
        
        # Style-Bert-VITS2の初期化
        self.tts_engine = StyleBertVITS2(config_path)
        
        # Pygameの初期化
        self.aituber_config = self.config["aituber"]
        self.running = False
        self.speaking = False
        self.avatar_image = None
        self.mouth_open_image = None
        
        logger.info("AITuberアプリケーションの初期化が完了しました。")
    
    def _load_config(self):
        """設定ファイルを読み込みます。"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"設定ファイルの読み込み中にエラーが発生しました: {str(e)}")
            raise
    
    def init_pygame(self):
        """Pygameを初期化します。"""
        try:
            pygame.init()
            pygame.mixer.init()
            
            # ウィンドウの設定
            width = self.aituber_config["window_width"]
            height = self.aituber_config["window_height"]
            self.screen = pygame.display.set_mode((width, height))
            pygame.display.set_caption("AITuber with Style-Bert-VITS2")
            
            # 背景色の設定
            bg_color = self.aituber_config["background_color"]
            self.bg_color = (int(bg_color[0] * 255), int(bg_color[1] * 255), int(bg_color[2] * 255))
            
            # アバター画像の読み込み
            avatar_path = self.aituber_config.get("avatar_image_path", "./avatar/avatar.png")
            mouth_open_path = self.aituber_config.get("mouth_open_image_path", "./avatar/avatar_mouth_open.png")
            
            # デフォルトのアバター画像を作成
            if not os.path.exists(avatar_path):
                logger.warning(f"アバター画像が見つかりません: {avatar_path}")
                logger.info("デフォルトのアバター画像を作成します。")
                self._create_default_avatar(avatar_path, mouth_open_path)
            
            # 画像の読み込み
            self.avatar_image = pygame.image.load(avatar_path)
            self.avatar_image = pygame.transform.scale(self.avatar_image, (width, height))
            
            if os.path.exists(mouth_open_path):
                self.mouth_open_image = pygame.image.load(mouth_open_path)
                self.mouth_open_image = pygame.transform.scale(self.mouth_open_image, (width, height))
            else:
                self.mouth_open_image = self.avatar_image
            
            logger.info("Pygameの初期化が完了しました。")
            
        except Exception as e:
            logger.error(f"Pygameの初期化中にエラーが発生しました: {str(e)}")
            raise
    
    def _create_default_avatar(self, avatar_path, mouth_open_path):
        """デフォルトのアバター画像を作成します。"""
        try:
            width = self.aituber_config["window_width"]
            height = self.aituber_config["window_height"]
            
            # アバターディレクトリの確認
            avatar_dir = os.path.dirname(avatar_path)
            os.makedirs(avatar_dir, exist_ok=True)
            
            # デフォルトのアバター画像を作成
            surface = pygame.Surface((width, height))
            surface.fill((200, 200, 200))  # 背景色
            
            # 顔の輪郭
            pygame.draw.ellipse(surface, (255, 220, 200), (width//4, height//4, width//2, height//2))
            
            # 目
            eye_size = width // 20
            pygame.draw.ellipse(surface, (0, 0, 0), (width//3, height//3, eye_size, eye_size))
            pygame.draw.ellipse(surface, (0, 0, 0), (width*2//3 - eye_size, height//3, eye_size, eye_size))
            
            # 口（閉じている）
            pygame.draw.line(surface, (0, 0, 0), (width//2 - width//10, height*2//3), (width//2 + width//10, height*2//3), 3)
            
            # 画像を保存
            pygame.image.save(surface, avatar_path)
            
            # 口が開いているバージョン
            mouth_surface = pygame.Surface((width, height))
            mouth_surface.blit(surface, (0, 0))  # 基本の画像をコピー
            
            # 口（開いている）
            pygame.draw.ellipse(mouth_surface, (0, 0, 0), (width//2 - width//10, height*2//3 - height//20, width//5, height//10))
            
            # 画像を保存
            pygame.image.save(mouth_surface, mouth_open_path)
            
            logger.info(f"デフォルトのアバター画像を作成しました: {avatar_path}, {mouth_open_path}")
            
        except Exception as e:
            logger.error(f"デフォルトのアバター画像の作成中にエラーが発生しました: {str(e)}")
            raise
    
    def speak(self, text, output_path=None):
        """
        テキストを音声に変換し、アバターに喋らせます。
        
        Args:
            text (str): 喋らせるテキスト
            output_path (str, optional): 音声ファイルの出力パス
        """
        try:
            # 出力パスが指定されていない場合はデフォルトのパスを使用
            if output_path is None:
                output_path = f"./output/speech_{int(time.time())}.wav"
            
            # テキストを音声に変換
            self.tts_engine.synthesize(text, output_path)
            
            # Pygameが初期化されていない場合は初期化
            if not hasattr(self, 'screen'):
                self.init_pygame()
            
            # 音声を再生しながらアバターの口を動かす
            self._play_audio_with_animation(output_path)
            
            logger.info(f"アバターが発話しました: {text[:30]}...")
            
        except Exception as e:
            logger.error(f"発話中にエラーが発生しました: {str(e)}")
            raise
    
    def _play_audio_with_animation(self, audio_path):
        """
        音声を再生しながらアバターの口を動かします。
        
        Args:
            audio_path (str): 音声ファイルのパス
        """
        try:
            # 音声の読み込み
            pygame.mixer.music.load(audio_path)
            
            # 発話フラグをセット
            self.speaking = True
            
            # 音声再生とアニメーションを別スレッドで実行
            threading.Thread(target=self._animation_thread, args=(audio_path,)).start()
            
        except Exception as e:
            logger.error(f"音声再生中にエラーが発生しました: {str(e)}")
            self.speaking = False
            raise
    
    def _animation_thread(self, audio_path):
        """
        音声再生とアニメーションを行うスレッド。
        
        Args:
            audio_path (str): 音声ファイルのパス
        """
        try:
            # アニメーション設定の取得
            animation_config = self.aituber_config.get("animation", {})
            frame_rate = animation_config.get("frame_rate", 60)
            mouth_speed = animation_config.get("mouth_animation_speed", 5)
            blink_interval = animation_config.get("blink_interval", [2, 5])
            blink_duration = animation_config.get("blink_duration", 0.2)
            enable_eye_animation = animation_config.get("enable_eye_animation", True)
            enable_mouth_animation = animation_config.get("enable_mouth_animation", True)
            enable_smooth_transitions = animation_config.get("enable_smooth_transitions", True)
            
            # 音声の再生
            pygame.mixer.music.play()
            
            # 音声が再生されている間、アニメーションを表示
            clock = pygame.time.Clock()
            mouth_open_ratio = 0.0  # 口の開き具合（0.0〜1.0）
            eye_open_ratio = 1.0   # 目の開き具合（0.0〜1.0）
            frame_count = 0
            last_blink_time = time.time()
            next_blink_time = last_blink_time + np.random.uniform(blink_interval[0], blink_interval[1])
            blinking = False
            blink_start_time = 0
            
            # 音声振幅の取得（仮のランダム値）
            audio_amplitudes = [np.random.random() for _ in range(1000)]
            
            while pygame.mixer.music.get_busy() and self.running:
                current_time = time.time()
                
                # イベント処理
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        self.running = False
                        pygame.mixer.music.stop()
                        return
                
                # 背景を描画
                self.screen.fill(self.bg_color)
                
                # 口のアニメーション（音声の振幅に基づく）
                if enable_mouth_animation:
                    # 現在の音声フレームのインデックスを計算
                    audio_frame_index = min(int(frame_count / frame_rate * 100), len(audio_amplitudes) - 1)
                    target_mouth_open = audio_amplitudes[audio_frame_index] * 0.8 + 0.2  # 0.2〜1.0の範囲に調整
                    
                    if enable_smooth_transitions:
                        # スムーズな口の開閉
                        mouth_open_ratio += (target_mouth_open - mouth_open_ratio) * (mouth_speed / 10.0)
                    else:
                        # 従来の切り替え方式
                        if frame_count % (frame_rate // mouth_speed) == 0:
                            mouth_open_ratio = target_mouth_open if mouth_open_ratio < 0.5 else 0.0
                else:
                    mouth_open_ratio = 0.0
                
                # 目のアニメーション（まばたき）
                if enable_eye_animation:
                    if not blinking and current_time >= next_blink_time:
                        blinking = True
                        blink_start_time = current_time
                    
                    if blinking:
                        blink_elapsed = current_time - blink_start_time
                        if blink_elapsed < blink_duration:
                            # 目を閉じる
                            eye_open_ratio = max(0, 1.0 - (blink_elapsed / (blink_duration * 0.5)) * 2.0)
                        elif blink_elapsed < blink_duration * 2:
                            # 目を開く
                            eye_open_ratio = min(1.0, ((blink_elapsed - blink_duration) / (blink_duration * 0.5)) * 2.0)
                        else:
                            # まばたき完了
                            blinking = False
                            last_blink_time = current_time
                            next_blink_time = current_time + np.random.uniform(blink_interval[0], blink_interval[1])
                            eye_open_ratio = 1.0
                
                # アバターを描画（口の開き具合に応じて画像を選択）
                if mouth_open_ratio > 0.5 and self.mouth_open_image is not None:
                    self.screen.blit(self.mouth_open_image, (0, 0))
                else:
                    self.screen.blit(self.avatar_image, (0, 0))
                
                # 目のアニメーションを描画（まばたき）
                if enable_eye_animation and eye_open_ratio < 0.9:
                    # 目を閉じる描画（単純な例）
                    width = self.aituber_config["window_width"]
                    height = self.aituber_config["window_height"]
                    eye_size = width // 20
                    eye_y = height // 3 + int((1.0 - eye_open_ratio) * eye_size * 0.5)
                    eye_height = max(1, int(eye_size * eye_open_ratio))
                    
                    # 左目
                    pygame.draw.ellipse(self.screen, (0, 0, 0), (width//3, eye_y, eye_size, eye_height))
                    # 右目
                    pygame.draw.ellipse(self.screen, (0, 0, 0), (width*2//3 - eye_size, eye_y, eye_size, eye_height))
                
                # 画面の更新
                pygame.display.flip()
                
                # フレームカウントの更新
                frame_count += 1
                
                # フレームレートの制御
                clock.tick(frame_rate)
            
            # 発話終了後、通常の表示に戻す
            self.screen.fill(self.bg_color)
            self.screen.blit(self.avatar_image, (0, 0))
            pygame.display.flip()
            
            # 発話フラグをリセット
            self.speaking = False
            
        except Exception as e:
            logger.error(f"アニメーション中にエラーが発生しました: {str(e)}")
            self.speaking = False
    
    def run_interactive(self):
        """インタラクティブモードでアプリケーションを実行します。"""
        logger.info("インタラクティブモードを開始します。終了するには 'exit' と入力してください。")
        
        # Pygameの初期化
        if not hasattr(self, 'screen'):
            self.init_pygame()
        
        # パフォーマンス設定の適用
        performance_config = self.aituber_config.get("performance", {})
        reduce_model_complexity = performance_config.get("reduce_model_complexity", False)
        optimize_rendering = performance_config.get("optimize_rendering", False)
        use_hardware_acceleration = performance_config.get("use_hardware_acceleration", False)
        
        # パフォーマンス最適化の適用
        if optimize_rendering:
            # ダブルバッファリングの有効化
            pygame.display.set_mode((self.aituber_config["window_width"], self.aituber_config["window_height"]), pygame.DOUBLEBUF)
            
        if use_hardware_acceleration:
            # ハードウェアアクセラレーションの有効化（可能な場合）
            try:
                pygame.display.set_mode(
                    (self.aituber_config["window_width"], self.aituber_config["window_height"]),
                    pygame.DOUBLEBUF | pygame.HWSURFACE | pygame.SCALED
                )
                logger.info("ハードウェアアクセラレーションを有効化しました。")
            except Exception as e:
                logger.warning(f"ハードウェアアクセラレーションの有効化に失敗しました: {str(e)}")
        
        # アニメーション設定の取得
        animation_config = self.aituber_config.get("animation", {})
        frame_rate = animation_config.get("frame_rate", 60)
        
        # メインループフラグ
        self.running = True
        
        # 入力スレッドの開始
        input_thread = threading.Thread(target=self._input_thread)
        input_thread.daemon = True
        input_thread.start()
        
        # 目のアニメーション用の変数
        enable_eye_animation = animation_config.get("enable_eye_animation", True)
        blink_interval = animation_config.get("blink_interval", [2, 5])
        blink_duration = animation_config.get("blink_duration", 0.2)
        eye_open_ratio = 1.0
        last_blink_time = time.time()
        next_blink_time = last_blink_time + np.random.uniform(blink_interval[0], blink_interval[1])
        blinking = False
        blink_start_time = 0
        
        try:
            # メインループ（Pygameウィンドウの処理）
            clock = pygame.time.Clock()
            while self.running:
                current_time = time.time()
                
                # イベント処理
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        self.running = False
                
                # 発話中でない場合は通常の表示（目のアニメーションあり）
                if not self.speaking:
                    self.screen.fill(self.bg_color)
                    self.screen.blit(self.avatar_image, (0, 0))
                    
                    # 目のアニメーション（まばたき）
                    if enable_eye_animation:
                        if not blinking and current_time >= next_blink_time:
                            blinking = True
                            blink_start_time = current_time
                        
                        if blinking:
                            blink_elapsed = current_time - blink_start_time
                            if blink_elapsed < blink_duration:
                                # 目を閉じる
                                eye_open_ratio = max(0, 1.0 - (blink_elapsed / (blink_duration * 0.5)) * 2.0)
                            elif blink_elapsed < blink_duration * 2:
                                # 目を開く
                                eye_open_ratio = min(1.0, ((blink_elapsed - blink_duration) / (blink_duration * 0.5)) * 2.0)
                            else:
                                # まばたき完了
                                blinking = False
                                last_blink_time = current_time
                                next_blink_time = current_time + np.random.uniform(blink_interval[0], blink_interval[1])
                                eye_open_ratio = 1.0
                        
                        # 目のアニメーションを描画（まばたき）
                        if eye_open_ratio < 0.9:
                            # 目を閉じる描画
                            width = self.aituber_config["window_width"]
                            height = self.aituber_config["window_height"]
                            eye_size = width // 20
                            eye_y = height // 3 + int((1.0 - eye_open_ratio) * eye_size * 0.5)
                            eye_height = max(1, int(eye_size * eye_open_ratio))
                            
                            # 左目
                            pygame.draw.ellipse(self.screen, (0, 0, 0), (width//3, eye_y, eye_size, eye_height))
                            # 右目
                            pygame.draw.ellipse(self.screen, (0, 0, 0), (width*2//3 - eye_size, eye_y, eye_size, eye_height))
                    
                    pygame.display.flip()
                
                # フレームレートの制御
                clock.tick(frame_rate)
                
        except KeyboardInterrupt:
            logger.info("インタラクティブモードを終了します。")
        
        finally:
            self.running = False
            self.close()
    
    def _input_thread(self):
        """ユーザー入力を処理するスレッド。"""
        try:
            while self.running:
                text = input("発話テキスト: ")
                if text.lower() == 'exit':
                    self.running = False
                    break
                
                # 発話中でない場合のみ新しい発話を開始
                if not self.speaking and self.running:
                    self.speak(text)
                
        except Exception as e:
            logger.error(f"入力処理中にエラーが発生しました: {str(e)}")
            self.running = False
    
    def close(self):
        """アプリケーションを終了します。"""
        try:
            # Pygameのクリーンアップ
            pygame.mixer.quit()
            pygame.quit()
            
            logger.info("アプリケーションを終了しました。")
            
        except Exception as e:
            logger.error(f"終了処理中にエラーが発生しました: {str(e)}")

def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(description="AITuberKit with Style-Bert-VITS2")
    parser.add_argument("--config", type=str, default="config.json", help="設定ファイルのパス")
    parser.add_argument("--text", type=str, help="発話させるテキスト（指定した場合はインタラクティブモードにならない）")
    parser.add_argument("--output", type=str, help="音声ファイルの出力パス")
    
    args = parser.parse_args()
    
    try:
        app = AITuberApp(config_path=args.config)
        
        if args.text:
            # テキストが指定された場合は一度だけ発話させる
            app.speak(args.text, args.output)
            app.close()
        else:
            # インタラクティブモードを実行
            app.run_interactive()
            
    except Exception as e:
        logger.error(f"エラーが発生しました: {str(e)}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
