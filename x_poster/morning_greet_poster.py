import json
import random
import time
import tweepy
import gspread
from google.oauth2.service_account import Credentials
import google.generativeai as genai
import logging
import os
from datetime import datetime, timedelta
import pytz

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Configuration Loading ---
def find_config_file():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for name in ["config.local.json", "config.public.json", "config.json"]:
        candidate = os.path.join(base_dir, name)
        if os.path.exists(candidate):
            return candidate
    raise FileNotFoundError("No config file found (tried config.local.json, config.public.json, config.json)")

CONFIG_FILE = find_config_file()

def load_config():
    """Loads configuration from config.json and environment variables."""
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            config = json.load(f)

        # Override with environment variables if they exist (for sensitive data)
        config['gemini_api_key'] = os.environ.get('GEMINI_API_KEY', config.get('gemini_api_key'))
        
        if 'x_poster' not in config:
            config['x_poster'] = {}
        config['x_poster']['api_key'] = os.environ.get('X_API_KEY', config.get('x_poster', {}).get('api_key'))
        config['x_poster']['api_secret_key'] = os.environ.get('X_API_SECRET_KEY', config.get('x_poster', {}).get('api_secret_key'))
        config['x_poster']['access_token'] = os.environ.get('X_ACCESS_TOKEN', config.get('x_poster', {}).get('access_token'))
        config['x_poster']['access_token_secret'] = os.environ.get('X_ACCESS_TOKEN_SECRET', config.get('x_poster', {}).get('access_token_secret'))

        if 'google_sheets' not in config['x_poster']:
            config['x_poster']['google_sheets'] = {}
        # Use environment variable for credentials file path if set, otherwise use config
        # This allows GitHub Actions to use a specific path for the credentials file it creates
        config['x_poster']['google_sheets']['credentials_file'] = os.environ.get('GS_CREDENTIALS_FILE_PATH', config.get('x_poster', {}).get('google_sheets', {}).get('credentials_file'))

        # Validate essential keys after potential overrides
        if not config.get('gemini_api_key'):
            raise ValueError("Missing 'gemini_api_key' in config or environment variables.")
        if not config.get('x_poster', {}).get('api_key') or \
           not config.get('x_poster', {}).get('api_secret_key') or \
           not config.get('x_poster', {}).get('access_token') or \
           not config.get('x_poster', {}).get('access_token_secret'):
            raise ValueError("Missing X API credentials in config or environment variables.")
        if not config.get('x_poster', {}).get('google_sheets', {}).get('credentials_file'):
            raise ValueError("Missing 'credentials_file' for Google Sheets in config or environment variables.")
        if not config.get('x_poster', {}).get('google_sheets', {}).get('spreadsheet_id'):
            raise ValueError("Missing 'spreadsheet_id' for Google Sheets in config.")
        if 'character_name' not in config or 'persona' not in config or 'greeting' not in config:
            logging.warning("Character details (name, persona, greeting) might be missing in config.json")
        
        return config
    except FileNotFoundError:
        logging.error(f"Configuration file not found: {CONFIG_FILE}")
        raise
    except json.JSONDecodeError:
        logging.error(f"Error decoding JSON from configuration file: {CONFIG_FILE}")
        raise
    except ValueError as e:
        logging.error(f"Configuration error: {e}")
        raise

# --- Google Sheets Interaction ---
def get_services_from_sheet(config):
    """Fetches service names and descriptions from Google Sheets."""
    gs_config = config['x_poster']['google_sheets']
    try:
        creds_path = gs_config['credentials_file']
        # If the path is relative, make it absolute based on config file's directory
        if not os.path.isabs(creds_path):
            creds_path = os.path.join(os.path.dirname(CONFIG_FILE), creds_path)

        creds = Credentials.from_service_account_file(
            creds_path,
            scopes=['https://www.googleapis.com/auth/spreadsheets.readonly']
        )
        client = gspread.authorize(creds)
        spreadsheet = client.open_by_key(gs_config['spreadsheet_id'])
        sheet = spreadsheet.worksheet(gs_config['sheet_name'])
        
        records = sheet.get_all_records() # Assumes first row is header
        
        services = []
        for record in records:
            service_name = record.get(gs_config['service_name_column'])
            service_desc = record.get(gs_config['service_description_column'])
            if service_name and service_desc:
                services.append({"name": service_name, "description": service_desc})
            else:
                logging.warning(f"Skipping row due to missing service name or description: {record}")
        
        if not services:
            logging.warning("No services found in the Google Sheet.")
        return services
    except Exception as e:
        logging.error(f"Error accessing Google Sheets: {e}")
        return []

# --- AI Comment Generation ---
def generate_ai_comment(config, service_name, service_description):
    """Generates a bilingual (JA/EN) comment using Gemini AI based on character persona."""
    try:
        genai.configure(api_key=config['gemini_api_key'])
        model = genai.GenerativeModel('gemini-1.5-flash-latest')

        character_name = config.get('character_name', 'AI')
        persona = config.get('persona', '')

        prompt = f"""
あなたは「{character_name}」という名前のVTuberです。
以下のペルソナと指示に従って、与えられたNFTサービスに関するコメントを生成してください。

# ペルソナ
{persona}

# 指示
- サービス概要を単に要約するのではなく、あなた自身の言葉でそのNFTの魅力や面白い点を解説してください。
- 「このNFTめっちゃ欲しいわ」「絶対集めたい！」のように、あなたの欲求や感情を表現してください。
- 「持ってる人いる？」「みんなはどう思う？」のように、フォロワーに質問を投げかけ、コメントを促してください。
- あなたのペルソナ（関西弁など）を完全に維持してください。
- コメント本文に「Gmonamin」などの挨拶は含めないでください。
- 日本語のコメントは70〜100文字程度、英語のコメントは150〜200文字程度で作成してください。

# 対象サービス
サービス名: {service_name}
サービス概要: {service_description}

# 出力形式
必ず以下のJSON形式で回答してください。他のテキストは一切含めないでください。
{{
  "ja": "ここに日本語のコメントを記述",
  "en": "ここに英語のコメントを記述"
}}
"""

        response = model.generate_content(prompt)

        # Extract JSON from the response text, removing markdown backticks if present
        cleaned_response = response.text.strip()
        if cleaned_response.startswith("```json"):
            cleaned_response = cleaned_response[7:]
        if cleaned_response.endswith("```"):
            cleaned_response = cleaned_response[:-3]

        comment_data = json.loads(cleaned_response)

        if isinstance(comment_data, dict) and 'ja' in comment_data and 'en' in comment_data:
            logging.info(f"Successfully generated AI comments: {comment_data}")
            return comment_data
        else:
            logging.error(f"AI response was not in the expected format: {comment_data}")
            raise ValueError("AI response format error.")

    except Exception as e:
        logging.error(f"Error generating AI comment: {e}")
        # Return a bilingual fallback comment
        return {
            "ja": "今日はこのサービスに注目やで！",
            "en": "Let's check out this service today!"
        }

# --- Twitter Posting ---
def post_to_twitter(config, message, in_reply_to_tweet_id=None):
    """Posts a message to Twitter, optionally as a reply."""
    x_config = config['x_poster']
    try:
        client = tweepy.Client(
            consumer_key=x_config['api_key'],
            consumer_secret=x_config['api_secret_key'],
            access_token=x_config['access_token'],
            access_token_secret=x_config['access_token_secret']
        )
        
        kwargs = {'text': message}
        if in_reply_to_tweet_id:
            kwargs['in_reply_to_tweet_id'] = in_reply_to_tweet_id
            
        response = client.create_tweet(**kwargs)
        tweet_id = response.data['id']
        logging.info(f"Tweet posted successfully! Tweet ID: {tweet_id}")
        return tweet_id
    except tweepy.TweepyException as e:
        logging.error(f"Error posting to Twitter: {e}")
        return None
    except Exception as e:
        logging.error(f"An unexpected error occurred during Twitter posting: {e}")
        return None

# --- Main Execution Logic ---
# A file to store the timestamp of the last successful post
TIMESTAMP_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'last_post_timestamp.txt')

def has_posted_within_last_23_hours():
    """Check if a post was made in the last 23 hours to avoid duplicates."""
    if not os.path.exists(TIMESTAMP_FILE):
        return False
    try:
        with open(TIMESTAMP_FILE, 'r') as f:
            last_post_time_str = f.read().strip()
        last_post_time = datetime.fromisoformat(last_post_time_str)
        if datetime.now() - last_post_time < timedelta(hours=23):
            return True
    except (IOError, ValueError) as e:
        logging.warning(f"Could not read or parse timestamp file. Proceeding anyway. Error: {e}")
    return False

def record_post_timestamp():
    """Record the current time as the last post time."""
    try:
        with open(TIMESTAMP_FILE, 'w') as f:
            f.write(datetime.now().isoformat())
    except IOError as e:
        logging.error(f"Failed to write timestamp to {TIMESTAMP_FILE}: {e}")

def run_post_job():
    """The main job to perform the morning greeting post."""
    logging.info("Starting post job...")

    force_post = os.environ.get('FORCE_POST', 'false').lower() == 'true'

    if not force_post and has_posted_within_last_23_hours():
        logging.info("A post has already been made in the last 23 hours. Skipping to avoid duplicates (FORCE_POST is false).")
        return
    elif force_post:
        logging.info("FORCE_POST is true, proceeding with post regardless of recent activity.")

    try:
        config = load_config()
    except Exception:
        logging.error("Failed to load configuration. Aborting job.")
        return

    if not config.get('x_poster', {}).get('morning_greeting', {}).get('enabled', False):
        logging.info("Morning greeting is disabled in config. Skipping.")
        return

    services = get_services_from_sheet(config)
    if not services:
        logging.warning("No services found in the Google Sheet.")
        return

    selected_service = random.choice(services)
    service_name = selected_service['name']
    service_description = selected_service['description']

    ai_comments = generate_ai_comment(config, service_name, service_description)
    ai_comment_ja = ai_comments.get('ja', "注目やで！")
    ai_comment_en = ai_comments.get('en', "Check it out!")

    hashtags = "#Monad #AITuber #Monamin"

    # --- Part 1: Japanese Tweet ---
    logging.info("Constructing Japanese tweet...")
    tweet_ja = f"""{config.get('greeting', 'Gmonamin!')}

今日の注目NFTは「{service_name}」やで！

{ai_comment_ja}

{hashtags}"""
    
    logging.info(f"Generated Japanese Tweet:\n{tweet_ja}")
    japanese_tweet_id = post_to_twitter(config, tweet_ja)

    if not japanese_tweet_id:
        logging.error("Failed to post Japanese tweet. Aborting the rest of the job.")
        return

    # --- Wait for 10 minutes ---
    logging.info("Waiting for 10 minutes before posting the English reply...")
    time.sleep(600) # 600 seconds = 10 minutes

    # --- Part 2: English Tweet ---
    logging.info("Constructing English tweet...")
    hashtags_en = "#Monad #AITuber #Monamin_EN"
    tweet_en = f"""Gmonamin! Today's featured NFT is \"{service_name}\"!

{ai_comment_en}

{hashtags_en}"""

    logging.info(f"Generated English Tweet:\n{tweet_en}")
    post_to_twitter(config, tweet_en) # Post as a new tweet

    record_post_timestamp()
    logging.info("Post job finished successfully.")

if __name__ == "__main__":
    run_post_job()
