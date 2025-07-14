# ===== X Poster System - ツイート文・画像生成OK (2025-07-14) =====
# テキスト生成: gemini-1.5-flash モデル使用
# 画像生成: gemini-2.0-flash-preview-image-generation モデル使用
# =====================================================

import json
import random
import time
import tweepy
import gspread
from google.oauth2.service_account import Credentials
import google.generativeai as genai
from google import genai as genai_client
from google.genai import types
import traceback
from PIL import Image
from io import BytesIO
import logging
import os
from datetime import datetime, timedelta
import pytz
from dotenv import load_dotenv
from pathlib import Path
import requests
import base64

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Define base_dir for constructing paths relative to the project root
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Load environment variables from .env file
dotenv_path = os.path.join(base_dir, '.env')
load_dotenv(dotenv_path=dotenv_path)

# --- Configuration Loading ---
CONFIG_FILE = os.path.join(base_dir, "config.public.json")
logging.info(f"Attempting to load configuration from: {CONFIG_FILE}")
if not os.path.exists(CONFIG_FILE):
    raise FileNotFoundError(f"{CONFIG_FILE} not found. This file is required for the X Poster script.")

def load_config():
    """Loads configuration from config.json and environment variables."""
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            config = json.load(f)

        config['gemini_api_key'] = os.environ.get('GEMINI_API_KEY', config.get('gemini_api_key'))
        
        if 'x_poster' not in config:
            config['x_poster'] = {}
        x_poster_config = config['x_poster']
        x_poster_config['api_key'] = os.environ.get('X_API_KEY', x_poster_config.get('api_key'))
        x_poster_config['api_secret_key'] = os.environ.get('X_API_SECRET_KEY', x_poster_config.get('api_secret_key'))
        x_poster_config['access_token'] = os.environ.get('X_ACCESS_TOKEN', x_poster_config.get('access_token'))
        x_poster_config['access_token_secret'] = os.environ.get('X_ACCESS_TOKEN_SECRET', x_poster_config.get('access_token_secret'))

        if 'google_sheets' not in x_poster_config:
            x_poster_config['google_sheets'] = {}
        gs_config = x_poster_config['google_sheets']
        
        google_creds_env = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
        if google_creds_env:
            gs_config['credentials_file'] = google_creds_env

        gs_config['google_cloud_project_id'] = os.environ.get('GOOGLE_CLOUD_PROJECT_ID', gs_config.get('google_cloud_project_id'))
        
        env_spreadsheet_id = os.environ.get('SPREADSHEET_ID')
        if env_spreadsheet_id:
            gs_config['spreadsheet_id'] = env_spreadsheet_id

        if 'morning_greeting' not in x_poster_config:
            x_poster_config['morning_greeting'] = {}
        morning_greet_config = x_poster_config['morning_greeting']
        morning_greet_config['image_generation_enabled'] = morning_greet_config.get('image_generation_enabled', False)

        # Validate essential keys
        if not config.get('gemini_api_key'): raise ValueError("Missing 'gemini_api_key'")
        if not all(k in x_poster_config for k in ['api_key', 'api_secret_key', 'access_token', 'access_token_secret']):
            raise ValueError("Missing X API credentials")
        if not gs_config.get('credentials_file'): raise ValueError("Missing 'credentials_file' for Google Sheets")
        if not gs_config.get('spreadsheet_id'): raise ValueError("Missing 'spreadsheet_id' for Google Sheets")
        if morning_greet_config['image_generation_enabled']:
            if not gs_config.get('google_cloud_project_id'):
                raise ValueError("Missing 'google_cloud_project_id' for Vertex AI Image Generation")
            if not x_poster_config.get('character_description'):
                raise ValueError("Missing 'character_description' in config for image generation")
        
        return config
    except (FileNotFoundError, json.JSONDecodeError, ValueError) as e:
        logging.error(f"Configuration error: {e}")
        raise

# --- Google Sheets Interaction ---
def get_services_from_sheet(config):
    """Fetches service names and descriptions from Google Sheets."""
    gs_config = config['x_poster']['google_sheets']
    try:
        creds_path = gs_config['credentials_file']
        if not os.path.isabs(creds_path):
            creds_path = os.path.join(os.path.dirname(CONFIG_FILE), creds_path)
        creds = Credentials.from_service_account_file(creds_path, scopes=['https://www.googleapis.com/auth/spreadsheets.readonly'])
        client = gspread.authorize(creds)
        spreadsheet = client.open_by_key(gs_config['spreadsheet_id'])
        sheet = spreadsheet.worksheet(gs_config['sheet_name'])
        records = sheet.get_all_records()
        services = [{"name": r[gs_config['service_name_column']], "description": r[gs_config['service_description_column']]} for r in records if r.get(gs_config['service_name_column']) and r.get(gs_config['service_description_column'])]
        if not services: logging.warning("No services found in the Google Sheet.")
        return services
    except Exception as e:
        logging.error(f"Error accessing Google Sheets: {e}")
        return []

# --- AI Content Generation ---
def generate_ai_comment(config, service_name, service_description):
    """Generates a tweet using Gemini AI based on service info."""
    try:
        genai.configure(api_key=config['gemini_api_key'])
        model = genai.GenerativeModel('gemini-1.5-flash')

        character_name = config.get('character_name', 'ウチ')
        persona = config.get('persona', 'フレンドリーなキャラクター')
        
        # Dynamic closing phrase based on service description
        closing_phrase_options = {
            "NFT": ["「持ってる人いる？」", "「ミントした？」"],
            "default": ["「使ったことある？」", "「みんなはどう思う？」"]
        }
        
        category = "NFT" if "nft" in service_description.lower() else "default"
        closing_phrase = random.choice(closing_phrase_options[category])

        prompt = f"""
あなたは「{character_name}」という名前のキャラクターです。
ペルソナ: {persona}

以下のサービスについて、あなたのキャラクターとして140文字以内で紹介ツイートを作成してください。
サービス名: {service_name}
概要: {service_description}

ツイートの最後は必ず「{closing_phrase}」で締めくくってください。
"""
        
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        logging.error(f"Error generating AI comment: {e}")
        return f"【{service_name}】は面白そうなサービスやな！みんなもチェックしてみてな！"

def generate_and_save_image(config, text_prompt, character_name, persona, service_name):
    """Generates an image using the Gemini API based on a detailed text prompt and saves it to a temporary file."""
    try:
        logging.info("Initializing Gemini API for image generation...")
        api_key = config.get('gemini_api_key')
        if not api_key:
            raise ValueError("Gemini API key not found in configuration.")
        
        # 画像生成用のクライアントを初期化
        client = genai_client.Client(api_key=api_key)
        
        # 画像生成のためのプロンプト作成
        image_generation_prompt = (
            f"{persona}\n\n" 
            f"あなたは「{character_name}」です。以下のツイート内容を元に、文脈に合った画像を生成してください。"
            f"画像は日本の萌えアニメ風のスタイルで、一人の女の子を描いてください。" 
            f"画像に文字は含めないでください。\n\n" 
            f"ツイート内容: {text_prompt}\n"
            f"紹介しているサービス: {service_name}"
        )

        logging.info(f"Generating image with prompt: {image_generation_prompt[:200]}...")
        
        # 画像生成専用モデルとパラメータを使用
        try:
            # 画像生成用のモデルを使用
            response = client.models.generate_content(
                model="gemini-2.0-flash-preview-image-generation",  # 画像生成専用モデル
                contents=image_generation_prompt,
                config=types.GenerateContentConfig(
                    response_modalities=['TEXT', 'IMAGE']  # テキストと画像の両方を返すように指定
                )
            )
            
            # 応答から画像データを抽出
            for part in response.candidates[0].content.parts:
                if part.text is not None:
                    logging.info(f"Image generation model returned text: {part.text[:100]}...")
                elif part.inline_data is not None:
                    # 画像データを取得して保存
                    image = Image.open(BytesIO(part.inline_data.data))
                    temp_image_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"temp_image_{int(time.time())}.png")
                    image.save(temp_image_path)
                    logging.info(f"Image saved temporarily to {temp_image_path}")
                    return temp_image_path
            
            # 画像が見つからない場合
            logging.error("No image data found in the response")
            return None
                
        except Exception as api_error:
            logging.error(f"Error with Gemini API call: {api_error}")
            logging.error(f"Stack trace: {traceback.format_exc()}")
            
            # 別のモデルでのフォールバック試行
            try:
                logging.info("Attempting fallback to gemini-1.5-flash model for image generation...")
                # gemini-1.5-flashモデルを使用して画像生成を試みる
                response = client.models.generate_content(
                    model="gemini-1.5-flash",
                    contents=image_generation_prompt,
                    config=types.GenerateContentConfig(
                        response_modalities=['TEXT', 'IMAGE']
                    )
                )
                
                # 応答から画像データを抽出
                for part in response.candidates[0].content.parts:
                    if part.text is not None:
                        logging.info(f"Fallback model returned text: {part.text[:100]}...")
                    elif part.inline_data is not None:
                        # 画像データを取得して保存
                        image = Image.open(BytesIO(part.inline_data.data))
                        temp_image_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"temp_image_{int(time.time())}.png")
                        image.save(temp_image_path)
                        logging.info(f"Image saved temporarily to {temp_image_path} (fallback model)")
                        return temp_image_path
                
                logging.error("No image data found in fallback model response")
                return None
                
            except Exception as fallback_error:
                logging.error(f"Error with fallback model: {fallback_error}")
                logging.error(f"Fallback stack trace: {traceback.format_exc()}")
                return None

    except Exception as e:
        logging.error(f"An error occurred during image generation with Gemini: {e}")
        logging.error(f"Stack trace: {traceback.format_exc()}")
        return None

# --- Twitter Posting ---
def post_to_twitter(config, message, image_path=None, in_reply_to_tweet_id=None):
    """Posts a message to Twitter, optionally with an image and as a reply."""
    x_config = config['x_poster']
    try:
        auth = tweepy.OAuth1UserHandler(
            consumer_key=x_config['api_key'],
            consumer_secret=x_config['api_secret_key'],
            access_token=x_config['access_token'],
            access_token_secret=x_config['access_token_secret']
        )
        api_v1 = tweepy.API(auth)
        client_v2 = tweepy.Client(bearer_token=None, consumer_key=x_config['api_key'], consumer_secret=x_config['api_secret_key'], access_token=x_config['access_token'], access_token_secret=x_config['access_token_secret'])

        media_id = None
        if image_path:
            logging.info(f"Uploading media: {image_path}")
            media = api_v1.media_upload(filename=image_path)
            media_id = media.media_id_string
            logging.info(f"Media uploaded successfully. Media ID: {media_id}")

        kwargs = {'text': message}
        if in_reply_to_tweet_id:
            kwargs['in_reply_to_tweet_id'] = in_reply_to_tweet_id
        if media_id:
            kwargs['media_ids'] = [media_id]
            
        response = client_v2.create_tweet(**kwargs)
        tweet_id = response.data['id']
        logging.info(f"Tweet posted successfully! Tweet ID: {tweet_id}")
        return tweet_id
    except Exception as e:
        logging.error(f"Error posting to Twitter: {e}")
        return None

# --- Main Execution Logic ---
TIMESTAMP_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'last_post_timestamp.txt')

def has_posted_within_last_23_hours():
    if not os.path.exists(TIMESTAMP_FILE): return False
    try:
        last_post_time = datetime.fromisoformat(Path(TIMESTAMP_FILE).read_text().strip())
        return datetime.now() - last_post_time < timedelta(hours=23)
    except (IOError, ValueError): return False

def record_post_timestamp():
    try: Path(TIMESTAMP_FILE).write_text(datetime.now().isoformat())
    except IOError as e: logging.error(f"Failed to write timestamp: {e}")

def run_post_job():
    logging.info("Starting post job...")
    if not os.environ.get('FORCE_POST', 'false').lower() == 'true' and has_posted_within_last_23_hours():
        logging.info("Post skipped: already posted within 23 hours.")
        return

    try: config = load_config()
    except Exception: logging.error("Failed to load configuration. Aborting."); return

    if not config.get('x_poster', {}).get('morning_greeting', {}).get('enabled', False):
        logging.info("Morning greeting is disabled. Skipping."); return

    services = get_services_from_sheet(config)
    if not services: logging.warning("No services found. Aborting."); return

    selected_service = random.choice(services)
    service_name, service_description = selected_service['name'], selected_service['description']
    
    japanese_tweet_text = generate_ai_comment(config, service_name, service_description)

    image_path = None
    image_generation_enabled = config.get('x_poster', {}).get('morning_greeting', {}).get('image_generation_enabled', False)

    try:
        if image_generation_enabled:
            image_path = generate_and_save_image(
                config, 
                japanese_tweet_text, # Use the full generated tweet for the image prompt
                config.get('character_name'), 
                config.get('persona'),
                service_name
            )

        japanese_tweet_id = post_to_twitter(config, japanese_tweet_text, image_path=image_path)
        if not japanese_tweet_id: logging.error("Failed to post Japanese tweet. Aborting."); return

        record_post_timestamp()
        # English tweet is temporarily disabled to restore core functionality.
        # logging.info("Waiting 10 minutes before English reply...")
        # time.sleep(600)
        # post_to_twitter(config, english_tweet_text, image_path=image_path)

    finally:
        if image_path and os.path.exists(image_path):
            try: os.remove(image_path); logging.info(f"Successfully deleted temp image: {image_path}")
            except OSError as e: logging.error(f"Error deleting temp image {image_path}: {e}")

    logging.info("Post job finished successfully.")

if __name__ == "__main__":
    run_post_job()
