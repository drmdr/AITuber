import logging
import sys
import os

# Add project root to the Python path to allow for absolute imports
# This makes the script runnable from anywhere
try:
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    from x_poster.morning_greet_poster import morning_greet_job
except ImportError as e:
    print(f"Error: Failed to import morning_greet_job. Make sure the file structure is correct. Details: {e}")
    sys.exit(1)


if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        stream=sys.stdout  # Log to standard output
    )
    
    main_logger = logging.getLogger(__name__)

    main_logger.info("テストのため、朝の挨拶投稿ジョブを一度だけ実行します。")
    try:
        # Execute the job
        morning_greet_job()
        main_logger.info("テスト投稿ジョブが正常に完了しました。X（旧Twitter）で投稿を確認してください。")
    except Exception as e:
        # Log any exceptions that occur during the job
        main_logger.error(f"テスト投稿中にエラーが発生しました: {e}", exc_info=True)
