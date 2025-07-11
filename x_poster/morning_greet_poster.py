import json
import random
import time
import tweepy
import gspread
from google.oauth2.service_account import Credentials
import google.generativeai as genai
from google.genai import types
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
    """Generates a complete tweet post in bilingual format using Gemini AI."""
    api_key = config.get('gemini_api_key')
    if not api_key:
        logging.error("Gemini API key not found in config.")
        return {'ja_tweet': f'今日の注目サービスは「{service_name}」やで！', 'en_tweet': f'Todays featured service is "{service_name}"!'}

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        
        character_name = config.get('character_name', 'モナミン')
        persona = config.get('persona', 'あんたは親しみやすいアシスタント、モナミンや。常にエセ関西弁で、元気で面白い投稿をするんやで。')
        greeting = config.get('greeting', 'Gmonamin!')
        hashtags = "#Monad #AITuber #Monamin"

        prompt = f"""
        あなたは「{character_name}」という名前の、個性的で親しみやすいAI VTuberです。
        ペルソナ: {persona}

        以下のWebサービスについて、あなたが発見した面白いサービスとして、日本のフォロワーに紹介する魅力的なツイートを作成してください。

        サービス名: {service_name}
        概要: {service_description}

        ツイート作成のルール:
        - あなたのペルソナ（エセ関西弁）を完全に維持し、非常にクリエイティブで、毎回異なるユニークな文章を生成してください。
        - 挨拶「{greeting}」から始めてください。
        - サービス名と概要を元に、ユーザーが「面白そう！」「使ってみたい！」と感じるような、具体的で魅力的な紹介文を作成してください。
        - 文章の最後に、必ずハッシュタグ「{hashtags}」を入れてください。
        - 全体で140文字のTwitter制限を超えないように、簡潔にまとめてください。
        - 英語のツイートは、日本語ツイートの魅力を伝えつつ、英語圏のユーザー向けに自然な表現で作成してください。挨拶やハッシュタグも英語に合わせて調整してください。

        出力は必ず以下のJSON形式で、他のテキストは含めないでください:
        {{
            "ja_tweet": "(生成した日本語のツイート全文)",
            "en_tweet": "(生成した英語のツイート全文)"
        }}
        """

        response = model.generate_content(prompt)
        
        # Extract JSON from the response text
        response_text = response.text
        # Handle potential markdown code blocks for JSON
        if '```json' in response_text:
            json_str = response_text.split('```json')[1].split('```')[0].strip()
        else:
            json_str = response_text

        return json.loads(json_str)

    except Exception as e:
        logging.error(f"Error generating AI comment: {e}")
        return {'ja_tweet': f'今日の注目サービスは「{service_name}」やで！', 'en_tweet': f'Todays featured service is "{service_name}"!'}

def generate_and_save_image(config, text_prompt, character_name, persona, service_name):
    """Generates an image using Vertex AI Image Generation API and saves it."""
    try:
        logging.info("Starting image generation with Vertex AI.")
        gcp_project_id = config['x_poster']['google_sheets']['google_cloud_project_id']
        
        # Authenticate with Google Cloud to get access token
        from google.auth import default
        from google.auth.transport.requests import Request
        creds, _ = default(scopes=['https://www.googleapis.com/auth/cloud-platform'])
        if not creds.valid:
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())
        access_token = creds.token

        character_description = config.get('x_poster', {}).get('character_description', 'A female AITuber character.')
        style_and_quality = "A high-quality, vibrant, and clean anime style character illustration. masterpiece, best quality, ultra-detailed, 4K, HDR, beautiful detailed eyes, perfect face."
        subject_and_pose = f"Create an image of a cheerful and cute Japanese anime girl named {character_name}. {character_description}. She should be the main focus, smiling happily and engaging with the viewer."
        is_nft_related = any(keyword in service_name.lower() for keyword in ['nft', 'token', 'crypto', 'blockchain', 'web3', 'dao'])
        scene_context = f"The background should be related to NFT and blockchain technology with {service_name} theme." if is_nft_related else f"The background should be related to the featured app: '{service_name}'."
        if random.random() < 0.3:
            style_and_quality = "chibi style, super deformed, cute, " + style_and_quality

        full_prompt = f"{style_and_quality} {subject_and_pose} {scene_context}"

        logging.info(f"Generating image with prompt: {full_prompt[:100]}...")

        endpoint = f"https://us-central1-aiplatform.googleapis.com/v1/projects/{gcp_project_id}/locations/us-central1/publishers/google/models/imagegeneration:predict"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=utf-8"
        }
        data = {
            "instances": [
                {"prompt": full_prompt}
            ],
            "parameters": {
                "sampleCount": 1
            }
        }

        response = requests.post(endpoint, headers=headers, json=data)
        response.raise_for_status() # Raise an exception for bad status codes

        response_json = response.json()
        if not response_json.get('predictions'):
            logging.error(f"Image generation failed. API response: {response_json}")
            return None

        image_data_base64 = response_json['predictions'][0]['bytesBase64Encoded']
        image_data = base64.b64decode(image_data_base64)

        image = Image.open(BytesIO(image_data))
        image_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"temp_image_{int(time.time())}.png")
        image.save(image_path)
        logging.info(f"Image successfully saved to {image_path}")
        return image_path

    except Exception as e:
        logging.error(f"An error occurred during image generation with Gemini: {e}")
        import traceback
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
    
    ai_data = generate_ai_comment(config, service_name, service_description)
    japanese_tweet_text = ai_data.get('ja_tweet', f'今日の注目サービスは「{service_name}」やで！ #Monad #AITuber #Monamin')
    english_tweet_text = ai_data.get('en_tweet', f'Today\'s featured service is "{service_name}"! #Monad #AITuber #Monamin_EN')

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
        logging.info("Waiting 10 minutes before English reply...")
        time.sleep(600)

        # English Tweet (with image, as a reply)
        post_to_twitter(config, english_tweet_text, image_path=image_path)

    finally:
        if image_path and os.path.exists(image_path):
            try: os.remove(image_path); logging.info(f"Successfully deleted temp image: {image_path}")
            except OSError as e: logging.error(f"Error deleting temp image {image_path}: {e}")

    logging.info("Post job finished successfully.")

if __name__ == "__main__":
    run_post_job()
