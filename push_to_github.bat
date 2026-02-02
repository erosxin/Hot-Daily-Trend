@echo off
echo GitHub Actions 设置脚本
echo ====================

set REPO_DIR=%~dp0
set GITHUB_TOKEN=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
set REPO_URL=https://github.com/erosxin/Hot-Daily-Trend.git

echo.
echo 1. 检查 git...
where git >nul 2>nul
if errorlevel 1 (
    echo 错误: 未安装 git，请先安装 https://git-scm.com/
    pause
    exit /b 1
)

echo 2. 配置 git...
git config --global user.name "Eros"
git config --global user.email "eros@cleversports.asia"

echo 3. 添加远程仓库...
git remote add origin %REPO_URL% 2>nul
if errorlevel 1 (
    echo 远程 origin 已存在，跳过
)

echo 4. 获取远程分支...
git fetch origin

echo 5. 切换到 main 分支...
git checkout main 2>nul
if errorlevel 1 (
    echo 创建并切换到 main 分支
    git checkout -b main
)

echo 6. 拉取最新代码...
git pull origin main --rebase || echo 拉取失败，继续提交...

echo 7. 添加更改...
git add .

echo 8. 提交...
git commit -m "Add GitHub Actions for daily AI news email" || echo 没有需要提交的更改

echo 9. 推送到 GitHub...
git push -u origin main

echo.
echo ====================
echo 完成！请去 GitHub 检查 Actions 是否运行
echo https://github.com/erosxin/Hot-Daily-Trend/actions
echo.
pause
