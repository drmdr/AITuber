import json
import random
import time
import tweepy
import gspread
from google.oauth2.service_account import Credentials
import google.generativeai as genai
from PIL import Image
from io import BytesIO
from google.generativeai import types
import logging
import os
from datetime import datetime, timedelta
import pytz
from dotenv import load_dotenv
from pathlib import Path
import requests

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
def generate_ai_comment(config, service_name, service_description, max_length_for_japanese_comment):
    """Generates a bilingual (JA/EN) comment and categorizes the service using Gemini AI."""
    try:
        genai.configure(api_key=config['gemini_api_key'])
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        character_name = config.get('character_name', 'AI')
        persona = config.get('persona', '')
        is_nft_related = any(k in service_description.lower() for k in ["nft", "token", "collectible", "mint"])
        question_prompt = "「持ってる人いる？」「ミントした？」" if is_nft_related else "「使ったことある？」「みんなはどう思う？」"
        prompt = f"""
あなたは「{character_name}」という名前のVTuberです。
以下のペルソナと指示に従って、与えられたサービスに関する分析とコメント作成を行ってください。

# ペルソナ
{persona}

# 指示
1.  **カテゴリ分類**: 与えられたサービスが以下のどれに最も当てはまるか判断してください。
    - NFT (NFTコレクション、NFTマーケットプレイスなど)
    - Webサービス (一般的なWebアプリケーション、ツールなど)
    - DApp (分散型アプリケーション)
    - その他 (上記に当てはまらないプロジェクトや技術など)
2.  **コメント作成**: 
    - サービス概要を単に要約するのではなく、あなた自身の言葉でそのサービスの魅力や面白い点を解説してください。
    - 「これめっちゃ欲しいわ」「絶対使いたい！」のように、あなたの欲求や感情を表現してください。
    - {question_prompt}  # ここで動的に質問文言を挿入
    - あなたのペルソナ（関西弁など）を完全に維持してください。
    - コメント本文に「Gmonamin」などの挨拶は含めないでください。
    - 日本語のコメントは、必ず**{max_length_for_japanese_comment}文字以内**に収めてください。短く、キャッチーな内容を心がけてください。
    - 英語のコメントも、同様に簡潔にしてください。

# 対象サービス
サービス名: {service_name}
サービス概要: {service_description}

# 出力形式
必ず以下のJSON形式で回答してください。他のテキストは一切含めないでください。
{{
  "category": "ここにカテゴリを記述 (NFT, Webサービス, DApp, その他)",
  "ja": "ここに日本語のコメントを記述",
  "en": "ここに英語のコメントを記述"
}}
"""

        response = model.generate_content(prompt)
        cleaned_response = response.text.strip().removeprefix('```json').removesuffix('```')
        ai_data = json.loads(cleaned_response)
        if isinstance(ai_data, dict) and all(k in ai_data for k in ['category', 'ja', 'en']):
            return ai_data
        raise ValueError("AI response format error.")
    except Exception as e:
        logging.error(f"Error generating AI comment: {e}")
        return {"category": "サービス", "ja": "今日はこのサービスに注目やで！", "en": "Let's check out this service today!"}

def generate_and_save_image(config, text_prompt, character_name, persona, service_name):
    """Generates an image using the Gemini API based on a detailed text prompt and saves it to a temporary file."""
    try:
        logging.info("Initializing Gemini API for image generation...")
        # Gemini API uses the key set in the environment, so direct initialization is simple
        client = genai.Client()

        character_description = config.get('x_poster', {}).get('character_description', 'A female AITuber character.')

        # --- Prompt Generation for Gemini API ---
        style_and_quality = "A high-quality, vibrant, and clean anime style character illustration. masterpiece, best quality, ultra-detailed, 4K, HDR, beautiful detailed eyes, perfect face."
        subject_and_pose = f"Create an image of a cheerful and cute Japanese anime girl named {character_name}. {character_description}. She should be the main focus, smiling happily and engaging with the viewer."
        scene_context = f"The background should be related to the featured app: '{service_name}'."

        # Randomly apply Chibi style
        if random.random() < 0.3: # 30% chance
            style_and_quality = "chibi style, super deformed, cute, " + style_and_quality

        # Gemini's image generation is part of a multimodal prompt, so we structure it as a conversation.
        # We don't have a direct negative prompt parameter like Imagen, so we include it in the main prompt.
        full_prompt = (
            f"{style_and_quality} {subject_and_pose} {scene_context} "
            f"Please avoid the following: low quality, worst quality, jpeg artifacts, blurry, noisy, text, watermark, signature, "
            f"ugly, deformed, disfigured, malformed, bad anatomy, extra limbs, missing limbs, "
            f"extra fingers, mutated hands, poorly drawn hands, poorly drawn face, dirty face, messy, distorted."
        )

        logging.info(f"Generating image with Gemini prompt: {full_prompt}")

        response = client.models.generate_content(
            model="gemini-1.5-flash", # Using a capable Gemini model
            contents=full_prompt,
            generation_config=genai.types.GenerationConfig(
                response_mime_type='image/png' # Request image output
            )
        )

        if not response.candidates or not response.candidates[0].content.parts:
            logging.error("Image generation failed. The response contained no image data.")
            return None

        # Extract image data
        image_part = response.candidates[0].content.parts[0]
        if image_part.mime_type != 'image/png':
            logging.error(f"Unexpected response format. Expected 'image/png', got '{image_part.mime_type}'.")
            return None

        image_data = image_part.blob.data
        image = Image.open(BytesIO(image_data))
        
        image_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"temp_image_{int(time.time())}.png")
        image.save(image_path)
        logging.info(f"Image saved to {image_path}")
        return image_path

    except Exception as e:
        logging.error(f"An error occurred during image generation with Gemini: {e}")
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
    
    greeting_text = config.get('greeting', 'Gmonamin!')
    hashtags_text = "#Monad #AITuber #Monamin"
    max_len = 140 - (len(greeting_text) + len(f"今日の注目サービスは「{service_name}」やで！") + len(hashtags_text) + 6)
    
    ai_data = generate_ai_comment(config, service_name, service_description, max(10, max_len))
    category, ai_comment_ja, ai_comment_en = ai_data.get('category', 'サービス'), ai_data.get('ja', "注目やで！"), ai_data.get('en', "Check it out!")

    intro_text = f"今日の注目{category}は「{service_name}」やで！"
    japanese_tweet_text = f"{greeting_text}\n\n{intro_text}\n\n{ai_comment_ja}\n\n{hashtags_text}"

    image_path = None
    image_generation_enabled = config.get('x_poster', {}).get('morning_greeting', {}).get('image_generation_enabled', False)

    try:
        if image_generation_enabled:
            image_path = generate_and_save_image(
                config, 
                f"{intro_text} {ai_comment_ja}", 
                config.get('character_name'), 
                config.get('persona'),
                service_name
            )

        japanese_tweet_id = post_to_twitter(config, japanese_tweet_text, image_path=image_path)
        if not japanese_tweet_id: logging.error("Failed to post Japanese tweet. Aborting."); return

        record_post_timestamp()
        logging.info("Waiting 10 minutes before English reply...")
        time.sleep(600)

        # English Tweet (with image, as a reply)
        intro_en = f"Today's featured {category} is \"{service_name}\""
        tweet_en = f"Gmonamin! {intro_en}!\n\n{ai_comment_en}\n\n#Monad #AITuber #Monamin_EN"
        post_to_twitter(config, tweet_en, image_path=image_path)

    finally:
        if image_path and os.path.exists(image_path):
            try: os.remove(image_path); logging.info(f"Successfully deleted temp image: {image_path}")
            except OSError as e: logging.error(f"Error deleting temp image {image_path}: {e}")

    logging.info("Post job finished successfully.")

if __name__ == "__main__":
    run_post_job()
