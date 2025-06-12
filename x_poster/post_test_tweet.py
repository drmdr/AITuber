import tweepy
import json
import os

# 設定ファイルのパス
CONFIG_FILE = os.path.join(os.path.dirname(__file__), '..', 'config.json') # x_posterフォルダの親ディレクトリにあるconfig.json

def load_config():
    """設定ファイルを読み込む"""
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            config = json.load(f)
        if 'x_poster' not in config:
            raise ValueError("設定ファイルに 'x_poster' の設定がありません。")
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

def post_tweet(text):
    """指定されたテキストでツイートを投稿する"""
    config = load_config()
    if not config:
        return

    api_key = config.get('api_key')
    api_secret_key = config.get('api_secret_key')
    access_token = config.get('access_token')
    access_token_secret = config.get('access_token_secret')

    if not all([api_key, api_secret_key, access_token, access_token_secret]):
        print("エラー: X APIの認証情報が設定ファイルに不足しています。")
        print("config.json の x_poster セクションに api_key, api_secret_key, access_token, access_token_secret を設定してください。")
        return

    try:
        # Tweepy v2 (X API v2) を使用する場合
        client = tweepy.Client(
            consumer_key=api_key,
            consumer_secret=api_secret_key,
            access_token=access_token,
            access_token_secret=access_token_secret
        )
        response = client.create_tweet(text=text)
        print(f"ツイートが投稿されました！ Tweet ID: {response.data['id']}")
        print(f"内容: {response.data['text']}")
        print(f"URL: https://twitter.com/user/status/{response.data['id']}") # 'user'部分は実際のユーザー名に置き換えてください
        return True
    except tweepy.TweepyException as e:
        print(f"ツイート投稿中にエラーが発生しました: {e}")
        # エラーレスポンスの詳細を表示 (存在する場合)
        if hasattr(e, 'api_errors') and e.api_errors:
            for error in e.api_errors:
                print(f"  - Code: {error.get('code')}, Message: {error.get('message')}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"  - Status Code: {e.response.status_code}")
            print(f"  - Response Text: {e.response.text}")
        return False
    except Exception as e:
        print(f"予期せぬエラーが発生しました: {e}")
        return False

if __name__ == "__main__":
    # Windows環境で日本語を正しく表示するための設定
    import sys
    import os
    if os.name == 'nt':
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')

    test_message = "これは #AITuber モナミンからのテスト投稿です！ (by Cascade)"
    print(f"テストメッセージを投稿します: \"{test_message}\"")
    post_tweet(test_message)
