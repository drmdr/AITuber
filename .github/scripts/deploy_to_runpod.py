#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import time
import json
import subprocess
import requests
from pathlib import Path

# RunPod APIの設定
RUNPOD_API_KEY = os.environ.get('RUNPOD_API_KEY')
RUNPOD_API_URL = 'https://api.runpod.io/v2'
SSH_PRIVATE_KEY = os.environ.get('SSH_PRIVATE_KEY')

# デプロイ設定
POD_TYPE = 'NVIDIA RTX A4000'  # 使用するGPUタイプ
CONTAINER_DISK_SIZE_GB = 50    # コンテナディスクサイズ（GB）
VOLUME_DISK_SIZE_GB = 100      # ボリュームディスクサイズ（GB）
POD_NAME = 'AITuber-Monamin'   # Podの名前

def setup_ssh_key():
    """SSH秘密鍵を設定する"""
    ssh_dir = Path.home() / '.ssh'
    ssh_dir.mkdir(exist_ok=True, mode=0o700)
    
    key_path = ssh_dir / 'runpod_key'
    with open(key_path, 'w') as f:
        f.write(SSH_PRIVATE_KEY)
    
    os.chmod(key_path, 0o600)
    return key_path

def get_pod_status(pod_id):
    """PodのステータスをAPIから取得する"""
    headers = {'Authorization': f'Bearer {RUNPOD_API_KEY}'}
    response = requests.get(f'{RUNPOD_API_URL}/pod/{pod_id}', headers=headers)
    
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error getting pod status: {response.text}")
        return None

def create_pod():
    """RunPodにPodを作成する"""
    headers = {
        'Authorization': f'Bearer {RUNPOD_API_KEY}',
        'Content-Type': 'application/json'
    }
    
    # Podの設定
    data = {
        'name': POD_NAME,
        'gpuCount': 1,
        'gpuType': POD_TYPE,
        'containerDiskSizeGB': CONTAINER_DISK_SIZE_GB,
        'volumeDiskSizeGB': VOLUME_DISK_SIZE_GB,
        'dockerArgs': '--shm-size=1g',
        'containerImage': 'runpod/pytorch:2.0.1-py3.10-cuda11.8.0-devel',
        'startScript': 'cd /workspace && git clone https://github.com/drmdr/AITuber-Monamin.git && cd AITuber-Monamin && pip install -r requirements.txt && mkdir -p models'
    }
    
    response = requests.post(f'{RUNPOD_API_URL}/pods', headers=headers, json=data)
    
    if response.status_code == 200:
        pod_info = response.json()
        print(f"Pod created successfully: {pod_info['id']}")
        return pod_info
    else:
        print(f"Error creating pod: {response.text}")
        return None

def get_existing_pod():
    """既存のPodを検索する"""
    headers = {'Authorization': f'Bearer {RUNPOD_API_KEY}'}
    response = requests.get(f'{RUNPOD_API_URL}/pods', headers=headers)
    
    if response.status_code == 200:
        pods = response.json().get('pods', [])
        for pod in pods:
            if pod.get('name') == POD_NAME:
                return pod
        return None
    else:
        print(f"Error getting pods: {response.text}")
        return None

def start_pod(pod_id):
    """停止中のPodを起動する"""
    headers = {
        'Authorization': f'Bearer {RUNPOD_API_KEY}',
        'Content-Type': 'application/json'
    }
    
    response = requests.post(f'{RUNPOD_API_URL}/pod/{pod_id}/start', headers=headers)
    
    if response.status_code == 200:
        print(f"Pod {pod_id} started successfully")
        return True
    else:
        print(f"Error starting pod: {response.text}")
        return False

def download_models(pod_info):
    """必要なモデルファイルをダウンロードする"""
    ssh_key_path = setup_ssh_key()
    ssh_host = pod_info.get('sshHost')
    ssh_port = pod_info.get('sshPort', 22)
    
    if not ssh_host:
        print("SSH host information not available")
        return False
    
    # モデルダウンロードスクリプトを作成
    download_script = '''
#!/bin/bash
# 必要なモデルファイルをダウンロードするスクリプト
set -e

MODELS_DIR="/workspace/AITuber-Monamin/models"
LOG_FILE="/workspace/model_download.log"

mkdir -p "$MODELS_DIR"
echo "$(date): モデルのダウンロードを開始します" >> "$LOG_FILE"

# 音声モデルのダウンロード（例）
if [ ! -f "$MODELS_DIR/voice_model.bin" ]; then
    echo "音声モデルをダウンロードしています..." >> "$LOG_FILE"
    # 実際のダウンロードURLに置き換えてください
    # wget -O "$MODELS_DIR/voice_model.bin" "https://example.com/path/to/voice_model.bin"
    # 仮のファイルを作成（実際のURLが分かるまでのプレースホルダー）
    touch "$MODELS_DIR/voice_model.bin"
    echo "音声モデルのダウンロードが完了しました" >> "$LOG_FILE"
fi

# Whisperモデルのダウンロード
if [ ! -d "$MODELS_DIR/whisper-medium" ]; then
    echo "Whisperモデルをダウンロードしています..." >> "$LOG_FILE"
    mkdir -p "$MODELS_DIR/whisper-medium"
    python -c "import whisper; whisper.load_model('medium')" >> "$LOG_FILE" 2>&1
    echo "Whisperモデルのダウンロードが完了しました" >> "$LOG_FILE"
fi

# その他必要なモデルファイルのダウンロードをここに追加

echo "$(date): すべてのモデルのダウンロードが完了しました" >> "$LOG_FILE"
'''
    
    try:
        # スクリプトを一時ファイルに保存
        temp_script = '/tmp/download_models.sh'
        with open(temp_script, 'w') as f:
            f.write(download_script)
        
        # スクリプトをPodに転送
        scp_cmd = [
            'scp',
            '-i', str(ssh_key_path),
            '-o', 'StrictHostKeyChecking=no',
            '-P', str(ssh_port),
            temp_script,
            f'root@{ssh_host}:/workspace/download_models.sh'
        ]
        
        subprocess.run(scp_cmd, check=True)
        
        # スクリプトに実行権限を付与して実行
        ssh_cmd = [
            'ssh',
            '-i', str(ssh_key_path),
            '-o', 'StrictHostKeyChecking=no',
            '-p', str(ssh_port),
            f'root@{ssh_host}',
            'chmod +x /workspace/download_models.sh && /workspace/download_models.sh'
        ]
        
        subprocess.run(ssh_cmd, check=True)
        print("Model download script executed successfully")
        return True
    except Exception as e:
        print(f"Failed to download models: {e}")
        return False

def deploy_code(pod_info):
    """SSHを使用してコードをデプロイする"""
    ssh_key_path = setup_ssh_key()
    ssh_host = pod_info.get('sshHost')
    ssh_port = pod_info.get('sshPort', 22)
    
    if not ssh_host:
        print("SSH host information not available")
        return False
    
    # SSHコマンドを構築
    ssh_cmd = [
        'ssh',
        '-i', str(ssh_key_path),
        '-o', 'StrictHostKeyChecking=no',
        '-p', str(ssh_port),
        f'root@{ssh_host}',
        'cd /workspace/AITuber-Monamin && git pull && pip install -r requirements.txt'
    ]
    
    try:
        result = subprocess.run(ssh_cmd, check=True, capture_output=True, text=True)
        print("Deployment successful:")
        print(result.stdout)
        
        # モデルファイルのダウンロード
        download_models(pod_info)
        
        return True
    except subprocess.CalledProcessError as e:
        print(f"Deployment failed: {e}")
        print(f"Error output: {e.stderr}")
        return False

def setup_auto_shutdown(pod_info):
    """自動シャットダウンを設定する"""
    ssh_key_path = setup_ssh_key()
    ssh_host = pod_info.get('sshHost')
    ssh_port = pod_info.get('sshPort', 22)
    
    if not ssh_host:
        print("SSH host information not available")
        return False
    
    # 自動シャットダウンスクリプトを作成
    shutdown_script = '''#!/bin/bash
# 使用状況をモニタリングして、アイドル状態が続いたら自動シャットダウンするスクリプト
IDLE_THRESHOLD=30  # アイドル時間のしきい値（分）
LOG_FILE="/workspace/auto_shutdown.log"

echo "$(date): 自動シャットダウン監視を開始しました" >> $LOG_FILE

while true; do
    # GPUの使用率を確認
    GPU_USAGE=$(nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader,nounits | awk '{ sum += $1 } END { print sum }')
    
    # CPU使用率を確認
    CPU_USAGE=$(top -bn1 | grep "Cpu(s)" | awk '{print $2 + $4}')
    
    echo "$(date): GPU使用率: $GPU_USAGE%, CPU使用率: $CPU_USAGE%" >> $LOG_FILE
    
    # 使用率が低い場合はカウントアップ
    if (( $(echo "$GPU_USAGE < 5" | bc -l) )) && (( $(echo "$CPU_USAGE < 10" | bc -l) )); then
        IDLE_COUNT=$((IDLE_COUNT + 1))
        echo "$(date): アイドル状態を検出 ($IDLE_COUNT/6)" >> $LOG_FILE
    else
        IDLE_COUNT=0
        echo "$(date): システムはアクティブです" >> $LOG_FILE
    fi
    
    # 30分（6回 x 5分）アイドル状態が続いたらシャットダウン
    if [ $IDLE_COUNT -ge 6 ]; then
        echo "$(date): $IDLE_THRESHOLD分間アイドル状態が続いたため、システムをシャットダウンします" >> $LOG_FILE
        # RunPod APIを使用してPodをシャットダウン
        curl -s -X POST "https://api.runpod.io/v2/pod/$POD_ID/stop" -H "Authorization: Bearer $RUNPOD_API_KEY"
        echo "$(date): シャットダウンコマンドを送信しました" >> $LOG_FILE
        break
    fi
    
    # 5分待機
    sleep 300
done
'''
    
    # スクリプトをPodに転送して設定
    try:
        # スクリプトを一時ファイルに保存
        temp_script = '/tmp/auto_shutdown.sh'
        with open(temp_script, 'w') as f:
            f.write(shutdown_script.replace('$POD_ID', pod_info.get('id')).replace('$RUNPOD_API_KEY', RUNPOD_API_KEY))
        
        # スクリプトをPodに転送
        scp_cmd = [
            'scp',
            '-i', str(ssh_key_path),
            '-o', 'StrictHostKeyChecking=no',
            '-P', str(ssh_port),
            temp_script,
            f'root@{ssh_host}:/workspace/auto_shutdown.sh'
        ]
        
        subprocess.run(scp_cmd, check=True)
        
        # スクリプトに実行権限を付与して自動起動を設定
        ssh_cmd = [
            'ssh',
            '-i', str(ssh_key_path),
            '-o', 'StrictHostKeyChecking=no',
            '-p', str(ssh_port),
            f'root@{ssh_host}',
            'chmod +x /workspace/auto_shutdown.sh && '
            'echo "nohup /workspace/auto_shutdown.sh &" >> /root/.bashrc && '
            'nohup /workspace/auto_shutdown.sh > /dev/null 2>&1 &'
        ]
        
        subprocess.run(ssh_cmd, check=True)
        print("Auto-shutdown script installed successfully")
        
        # 一時ファイルを削除
        os.remove(temp_script)
        return True
    except Exception as e:
        print(f"Failed to setup auto-shutdown: {e}")
        return False

def main():
    """メイン関数"""
    if not RUNPOD_API_KEY:
        print("RUNPOD_API_KEY environment variable is not set")
        sys.exit(1)
    
    if not SSH_PRIVATE_KEY:
        print("SSH_PRIVATE_KEY environment variable is not set")
        sys.exit(1)
    
    # 既存のPodを確認
    existing_pod = get_existing_pod()
    
    if existing_pod:
        pod_id = existing_pod.get('id')
        pod_status = existing_pod.get('status')
        
        print(f"Found existing pod: {pod_id} (Status: {pod_status})")
        
        # Podが停止中なら起動
        if pod_status == 'STOPPED':
            print("Starting the pod...")
            if start_pod(pod_id):
                # Podが起動するまで待機
                print("Waiting for pod to start...")
                for _ in range(30):  # 最大5分待機
                    time.sleep(10)
                    status = get_pod_status(pod_id)
                    if status and status.get('status') == 'RUNNING':
                        break
                
                # 最新のPod情報を取得
                pod_info = get_pod_status(pod_id)
                if pod_info:
                    # コードをデプロイ（モデルダウンロードも含む）
                    deploy_code(pod_info)
                    # 自動シャットダウンを設定
                    setup_auto_shutdown(pod_info)
                else:
                    print("Failed to start the pod")
                    sys.exit(1)
        elif pod_status == 'RUNNING':
            # Podが実行中ならコードをデプロイ（モデルダウンロードも含む）
            print("Pod is already running. Deploying code...")
            deploy_code(existing_pod)
            # 自動シャットダウンを設定
            setup_auto_shutdown(existing_pod)
        else:
            print(f"Pod is in {pod_status} state. Cannot deploy.")
            sys.exit(1)
    else:
        # 新しいPodを作成
        print("Creating a new pod...")
        pod_info = create_pod()
        
        if pod_info:
            pod_id = pod_info.get('id')
            
            # Podが起動するまで待機
            print("Waiting for pod to start...")
            for _ in range(30):  # 最大5分待機
                time.sleep(10)
                status = get_pod_status(pod_id)
                if status and status.get('status') == 'RUNNING':
                    break
            
            # 最新のPod情報を取得
            pod_info = get_pod_status(pod_id)
            if pod_info:
                # 自動シャットダウンを設定
                setup_auto_shutdown(pod_info)
        else:
            print("Failed to create a pod")
            sys.exit(1)
    
    print("Deployment process completed")

if __name__ == "__main__":
    main()
