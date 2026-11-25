# HOM-104 풀배열 키보드 PCB (rev 0.1)

사진 속 풀배열 기판을 바탕으로 새로 설계한 KiCad 7 프로젝트입니다.
배열과 기능(키마다 스위치, 다이오드, LED, 저항)은 원본과 같고, MCU와 회로는 새로 설계했습니다.

| 항목 | 내용 |
|---|---|
| 배열 | ANSI 104키 표준 풀배열, 키 간격 19.05 mm |
| 기판 크기 | 434.6 × 129.8 mm, 2층, 모서리 R2 |
| 매트릭스 | 6행 × 21열, COL2ROW, 키마다 1N4148W 다이오드 |
| 스위치 | Cherry MX 호환 PCB 마운트 (5핀). 2u, 2.25u, 2.75u, 6.25u 스태빌라이저 구멍 포함 |
| 백라이트 | 키마다 3 mm LED + 1 kΩ, AO3400A MOSFET으로 PWM 밝기 조절 (전체 약 210 mA) |
| MCU | RP2040 + W25Q128JVS 16 MB 플래시 + 12 MHz 크리스털 |
| USB | USB-C (HRO TYPE-C-31-M-12), USBLC6 ESD 보호, 500 mA 폴리퓨즈, AP2112K 3.3 V LDO |
| 기타 | BOOT/RESET 버튼, SWD 3핀 헤더, Caps/Num Lock 표시 LED, M2 마운팅홀 12개 |
| 펌웨어 | QMK (`firmware/qmk/hom104`) |

부품 배치: 스위치와 LED(THT)는 윗면, SMD 부품은 모두 뒷면에 있습니다.
MCU부는 사진의 기판처럼 넘패드 위 빈 공간에 모았습니다.

## 파일

- `hom-keyboard.kicad_pro / .kicad_sch / .kicad_pcb`: KiCad 7 프로젝트
- `hom-keyboard-schematic.pdf`: 회로도 PDF
- `hom-keyboard-bom.csv`: 부품 목록
- `docs/`: 회로도와 PCB 미리보기 이미지
- `firmware/qmk/hom104/`: QMK 키보드 정의 (`keyboard.json`, 기본 키맵)
- `tools/`: 생성 스크립트

## 다시 생성하기

```sh
# KiCad 7 (pcbnew 파이썬 모듈 포함)이 필요합니다
/usr/bin/python3 tools/build.py            # 회로도, PCB 배치, QMK 설정 생성
/usr/bin/python3 tools/verify_netlist.py   # KiCad 넷리스트를 설계와 대조
/usr/bin/python3 tools/drc.py hom-keyboard.kicad_pcb build/drc.txt
/usr/bin/python3 tools/route.py freerouting-1.9.0.jar   # 자동 배선 + GND 면 채우기
```

`build.py`는 먼저 회로도를 쓰고, KiCad가 그 회로도에서 뽑은 넷리스트로 PCB를 만듭니다.
그래서 회로도와 PCB의 연결은 항상 일치합니다.

## 현재 상태

- [x] 회로도 (넷리스트 검증 오류 0)
- [x] PCB 외곽, 부품 배치, 넷 연결, 마운팅홀 (배치 DRC: 겹침과 간격 오류 0)
- [x] QMK 펌웨어 설정
- [ ] 자동 배선 (Freerouting): 아직 안 함
- [ ] 거버 출력과 제작 주문

## 원본과 다른 점

- 사진만으로는 칩 모델을 읽을 수 없어서 MCU와 LED 구동부를 RP2040 기반으로 새로 설계했습니다.
- 뒷면 배선은 원본을 복제한 것이 아니고 새로 배선합니다.
- 외곽과 나사 구멍은 표준 치수로 잡았습니다. 기존 케이스에 맞추려면 실측값으로 `tools/build.py`의 `MARGIN`과 마운팅홀 위치(`add_mounting_holes`)를 수정하세요.
