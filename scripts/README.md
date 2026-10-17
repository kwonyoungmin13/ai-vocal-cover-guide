# 오디오 보조 도구

프로젝트 루트에서 `workspace.ps1`을 현재 PowerShell에 적용한 뒤 보조 도구 환경의 Python으로 실행합니다. 설치는 [환경 준비](../docs/01-setup.md)를 따릅니다.

```powershell
. .\scripts\workspace.ps1
& .\.venv\Scripts\python.exe .\scripts\audio_tools.py --help
```

- `inspect`: 전체 오디오 디코드, 프레임·유한값·peak·RMS 검사
- `preview`: 명시한 시작/길이의 WAV 또는 MP3 생성
- `mix`: 표본율·채널·길이 확인 후 보컬/반주 합산, 정적 peak 감쇠

상대경로는 프로젝트 루트 기준이며 출력은 이 프로젝트 내부에만 생성합니다. 기존 파일을 덮어쓰지 않습니다. 분리·학습·RVC 변환은 [단계별 문서](../docs/README.md)의 외부 도구로 실행합니다.

[합성 신호 검사](tests/README.md)에서 검증 방법과 범위를 확인할 수 있습니다.
