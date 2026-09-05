# 한글 깨짐 방지==============================================
chcp 65001

[Console]::InputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

git config --global core.quotepath false
git config --global i18n.commitEncoding utf-8
git config --global i18n.logOutputEncoding utf-8
#==============================================

#cd C:\AI\AgentStudio
cd F:\Source\repos\Theanova\AI\AgentStudio

git add -A

git commit -m "로컬 파일 기준 강제 동기화"

git push origin main --force