# 합성 신호 검사

프로젝트 루트에서 보조 도구 환경을 사용합니다.

```powershell
. .\scripts\workspace.ps1
& .\.venv\Scripts\python.exe -m unittest discover -s scripts/tests -v
```

검사는 임시 합성 WAV로 전체 디코드의 비유한 tail 탐지, PCM24 믹스와 peak 한계, 덮어쓰기 방지, 프로젝트 출력 경계, 표본율·채널·길이 불일치 거부를 확인합니다. 임시 파일은 프로젝트 `.tmp`에만 만듭니다.

Python 3.12.10 / NumPy 2.4.6 / SoundFile 0.14.0에서 3개 검사를 통과했습니다. 별도 합성 통합 검사로 FFmpeg WAV·MP3 미리듣기와 MP3 믹스도 확인했습니다. 학습·실제 가수 음원·청취 품질을 검증하는 테스트는 아닙니다.
