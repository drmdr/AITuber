import tweepy
import json
import os
import sys

# 標準出力・標準エラーのエンコーディングをUTF-8に設定 (Windows向け)
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

# 設定ファイルのパス
CONFIG_FILE = os.path.join(os.path.dirname(__file__), '..', 'config.json')

def load_x_config():
    """設定ファイルからX Poster関連の設定を読み込む"""
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            config = json.load(f)
        if 'x_poster' not in config:
            raise ValueError("設定ファイルに 'x_poster' の設定がありません。")
        if 'api_key' not in config['x_poster'] or \
           'api_secret_key' not in config['x_poster'] or \
           'access_token' not in config['x_poster'] or \
           'access_token_secret' not in config['x_poster']:
            raise ValueError("'x_poster' 設定にAPIキーまたはアクセストークンが不足しています。")
        return config['x_poster']
    except FileNotFoundError:
        print(f"エラー: 設定ファイル ({CONFIG_FILE}) が見つかりません。")
        return None
    except json.JSONDecodeError as e:
        print(f"エラー: 設定ファイル ({CONFIG_FILE}) の形式が正しくありません。エラー: {e}")
        return None
    except ValueError as e:
        print(f"エラー: {e}")
        return None

def get_tweepy_client(x_config):
    """Tweepy API v2 クライアントを初期化して返す"""
    client = tweepy.Client(
        consumer_key=x_config['api_key'],
        consumer_secret=x_config['api_secret_key'],
        access_token=x_config['access_token'],
        access_token_secret=x_config['access_token_secret']
    )
    return client

def fetch_latest_tweets_from_targets(client, target_accounts, tweets_per_account=1):
    """ターゲットアカウントリストから最新のツイートを取得する"""
    fetched_tweets_data = []
    if not target_accounts:
        print("ターゲットアカウントが設定されていません。")
        return fetched_tweets_data

    for screen_name_orig in target_accounts:
        screen_name = screen_name_orig.lstrip('@') # 先頭の@を削除
        try:
            print(f"\nアカウント '{screen_name}' の情報を取得中...")
            user_response = client.get_user(username=screen_name, user_fields=['id', 'name', 'username'])
            if user_response.data:
                user = user_response.data
                print(f"ユーザーID: {user.id}, 名前: {user.name}, スクリーン名: {user.username}")
                
                print(f"'{screen_name}' の最新ツイートを取得中 (最大{tweets_per_account}件)...")
                tweets_response = client.get_users_tweets(
                    id=user.id, 
                    max_results=tweets_per_account, 
                    tweet_fields=['id', 'text', 'created_at', 'author_id']
                )
                
                if tweets_response.data:
                    for tweet in tweets_response.data:
                        print(f"  ツイートID: {tweet.id}")
                        print(f"  投稿日時: {tweet.created_at}")
                        print(f"  本文:\n{tweet.text}\n")
                        fetched_tweets_data.append({
                            'author_name': user.name,
                            'author_username': user.username,
                            'tweet_id': tweet.id,
                            'text': tweet.text,
                            'created_at': str(tweet.created_at)
                        })
                else:
                    print(f"'{screen_name}' からツイートを取得できませんでした（ツイートがないか、保護されています）。")
            else:
                print(f"アカウント '{screen_name}' が見つかりませんでした。")
        except tweepy.TweepyException as e:
            print(f"アカウント '{screen_name}' の処理中にエラーが発生しました: {e}")
        except Exception as e:
            print(f"予期せぬエラーが発生しました ({screen_name}): {e}")
            
    return fetched_tweets_data

if __name__ == "__main__":
    print("Monadニュースポスター処理を開始します...")
    x_config = load_x_config()
    if not x_config:
        print("設定の読み込みに失敗したため、処理を終了します。")
        sys.exit(1)

    target_accounts = x_config.get('target_monad_accounts', [])
    if not target_accounts:
        print("ターゲットアカウントが設定されていません。処理を終了します。")
        sys.exit(1)

    print(f"ターゲットアカウント: {', '.join(target_accounts)}")

    client = get_tweepy_client(x_config)
    if not client:
        print("Tweepyクライアントの初期化に失敗したため、処理を終了します。")
        sys.exit(1)
    
    print("\n最新ツイートの取得を開始します...")
    latest_tweets = fetch_latest_tweets_from_targets(client, target_accounts, tweets_per_account=1)

    if latest_tweets:
        print("\n--- 取得したツイート概要 ---")
        for i, tweet_data in enumerate(latest_tweets, 1):
            print(f"{i}. {tweet_data['author_name']} (@{tweet_data['author_username']}) at {tweet_data['created_at']}:")
            print(f"   {tweet_data['text'][:100]}...") # 最初の100文字だけ表示
    else:
        print("\n取得できたツイートはありませんでした。")
    
    print("\nMonadニュースポスター処理を終了します。")
