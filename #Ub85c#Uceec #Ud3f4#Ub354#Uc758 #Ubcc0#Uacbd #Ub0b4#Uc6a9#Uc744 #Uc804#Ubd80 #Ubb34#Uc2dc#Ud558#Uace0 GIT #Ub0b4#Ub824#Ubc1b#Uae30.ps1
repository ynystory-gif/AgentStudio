#로컬 폴더의 변경 내용을 전부 무시하고 
#GitHub 원격 저장소의 main 브랜치 내용으로 
#강제로 맞추려면
cd C:\AI\AgentStudio
git fetch origin
git reset --hard origin/main
git clean -fd

#브랜치가 main인지 확인
git branch --show-current

#정상적으로 GitHub 내용이 내려왔는지 확인
git status

#기존 파일은 유지하기
Add-Content .git\info\exclude '~$*.pptx'

#정상적으로 GitHub 내용이 내려왔는지 확인
git status

git fetch origin
git reset --hard origin/main



