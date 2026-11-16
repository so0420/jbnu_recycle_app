# 안드로이드 APK 빌드 (Windows). 경로에 한글이 있으면 Gradle 이 거부하므로 R: 가상 드라이브를 쓴다.
# 필요: JDK 21 (C:\Users\<사용자>\.jdks\jdk-21*), Android SDK (C:\Users\<사용자>\Android\Sdk)
# 서명 키: ~/.android-keys/recycle-release.properties (없으면 서명 안 된 release 가 나온다)
$ErrorActionPreference = "Stop"
$front = Resolve-Path "$PSScriptRoot\..\frontend"
$jdk = Get-ChildItem "$env:USERPROFILE\.jdks" -Directory -Filter "jdk-21*" | Select-Object -First 1
$env:JAVA_HOME = $jdk.FullName
$env:ANDROID_HOME = "$env:USERPROFILE\Android\Sdk"
Push-Location $front
npm run build
npx cap sync android
Pop-Location
subst R: /D 2>$null
subst R: $front
Set-Content -Path R:\android\local.properties -Value ("sdk.dir=" + ($env:ANDROID_HOME -replace '\','/')) -Encoding ascii
[Environment]::CurrentDirectory = "R:\android"
& R:\android\gradlew.bat -p R:\android assembleRelease --no-daemon -q
Copy-Item R:\android\app\build\outputs\apk\release\app-release.apk "$front\..\recycle.apk" -Force
subst R: /D
Write-Host "완료: $front\..\recycle.apk"
