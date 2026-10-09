# 모델 재생성과 검증

모델 폴더 `Curtain Box Camera Mount`를 현재 작업 디렉터리로 사용합니다. 스크립트 경로와 결과물 경로는 체크아웃 위치에 관계없이 이 폴더를 기준으로 잡습니다.

## 환경

- 형상 생성·STEP 검사: **FreeCAD 1.0.2의 Python 3.11**, `FreeCAD`, `Part`, NumPy.
- 3MF 포장: Python 3.10 이상, 표준 라이브러리만 사용.
- 렌더·독립 나사 메시 검사: VTK 9.3. 렌더에는 Pillow와 한국어 글꼴도 필요.

Windows에서 확인한 실행 파일은 `C:\Program Files\FreeCAD 1.0\bin\python.exe`입니다. 일반 Python에 FreeCAD 모듈이 없으면 FreeCAD에 포함된 Python을 사용하세요. 다른 환경에서는 해당 모듈을 가져올 수 있는 Python 실행 파일을 선택합니다.

## 실행 순서

아래 `python`은 위 모듈이 설치된 실행 파일을 뜻합니다.

```text
python tools/build_mount.py
python tools/render_mount.py
python tools/verify_mesh_threads.py
python tools/package_3mf.py --manifest Verification/Print_Manifest.json --split-directory 3MF --prefix CurtainBox_Mount_Print --require-watertight --validate-print-placement --report Verification/3MF_Print_Validation.json
python tools/package_3mf.py --manifest Verification/Assembly_Manifest.json --output Reference/CurtainBox_Mount_Assembly_REFERENCE.3mf --require-watertight --report Verification/3MF_Assembly_Validation.json
python tools/package_3mf.py --manifest Verification/Fit_Manifest.json --output Optional_Tests/Thread_Fit_Test.3mf --require-watertight --validate-print-placement --report Verification/3MF_Fit_Validation.json
python tools/verify_files.py
```

`build_mount.py`는 개별 STL·STEP, 시험 부품, 조립 STEP, FreeCAD 원본, 치수와 CAD 검증 자료를 생성합니다. 조립 상태 메시 중간 파일은 Git에서 제외되는 `Verification/_build/assembled`에 둡니다. 3MF 조립 포장을 하려면 이 중간 파일이 있어야 하므로 빌드를 먼저 실행해야 합니다.

`verify_files.py`는 FreeCAD와 NumPy를 사용합니다. 개별 STEP를 다시 읽어 유효한 단일 솔리드와 STL 방향을 비교하고, STL 연결성·면 방향, 3MF 구성·바닥 배치·겹침, 문서 링크를 검사합니다. 공개 검증 보고서의 파일 경로는 모델 폴더 기준의 상대 경로로 정리합니다.

`verify_mesh_threads.py`는 145 / 150 / 175 / 215 mm 위치에서 STL의 부호 있는 거리로 맞물림을 검사합니다. 올바른 회전 위상의 간섭 표본이 0이고, 잘못된 위상에서는 간섭 표본이 생겨야 통과합니다. CAD Boolean만으로는 나사산 경계에서 거짓 음성이 생길 수 있어 독립 메시 검사를 함께 사용합니다.

렌더의 글꼴은 Windows 맑은 고딕 또는 시스템의 Noto CJK/Nanum 글꼴을 찾습니다. 다른 글꼴은 `CURTAIN_MOUNT_FONT` 환경변수에 경로를 지정할 수 있습니다.

## 편집과 제한

`Verification/Dimensions.json`과 FreeCAD의 `Dimensions` 객체는 기록용이며 자동 재생성 파라미터가 아닙니다. 치수를 변경하려면 `build_mount.py`의 관련 형상 좌표와 조절 범위를 함께 수정한 뒤, 형상·파일·나사 맞물림 검사를 다시 수행하세요.

3MF에 프린터·필라멘트·서포트 설정은 포함하지 않습니다. 파일 검증이 실제 슬라이싱, 프린팅, 카메라 체결이나 하중 시험을 대신하지는 않습니다. 재생성은 출력 파일을 덮어쓰므로 직접 CAD를 편집했다면 사본을 먼저 보관하세요.
