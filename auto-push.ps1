# AITuber-Monamin プロジェクトの自動プッシュスクリプト
# このスクリプトは定期的にGitHubにコードをプッシュします

# 設定
$repoPath = "C:\Users\drmdr\Documents\Surfwind\AITuber"
$branch = "master"
$commitMessage = "自動プッシュ: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"

# ログファイルの設定
$logFile = Join-Path $repoPath "auto-push.log"

# 関数: ログを記録
function Write-Log {
    param (
        [string]$message
    )
    
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    "$timestamp - $message" | Out-File -Append -FilePath $logFile
    Write-Host "$timestamp - $message"
}

# 開始ログ
Write-Log "自動プッシュスクリプトを開始します"

try {
    # 作業ディレクトリをリポジトリに変更
    Set-Location -Path $repoPath
    Write-Log "リポジトリディレクトリに移動: $repoPath"
    
    # 変更があるか確認
    $status = git status --porcelain
    
    if ($status) {
        Write-Log "変更が検出されました。コミットとプッシュを実行します。"
        
        # 変更をステージング
        git add .
        Write-Log "変更をステージングしました"
        
        # コミット
        git commit -m $commitMessage
        Write-Log "コミットしました: $commitMessage"
        
        # プッシュ
        git push origin $branch
        Write-Log "ブランチ '$branch' をGitHubにプッシュしました"
    } else {
        Write-Log "変更はありません。プッシュは不要です。"
    }
    
    Write-Log "スクリプトが正常に完了しました"
} catch {
    Write-Log "エラーが発生しました: $_"
    exit 1
}
