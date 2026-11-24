# Keyball61 JLCPCB 주문 패키지

원본: [Yowkees/keyball](https://github.com/Yowkees/keyball) `keyball61/design_data/` (커밋 `4664de9`, 2026-10-30)
라이선스: GPL-3.0 (`LICENSE-keyball-GPL3`). 설계 저작권은 Yowkees에게 있습니다.

미리보기: `docs/preview.png`

## 1. JLCPCB에 올릴 파일 (`jlcpcb/`)

zip 파일을 **풀지 말고 그대로** 하나씩 업로드해서 장바구니에 담습니다. 4개가 각각 별도 주문입니다.

| 파일 | 내용 | 크기 |
|---|---|---|
| `1_main-pcb_LEFT_noball_143x114.zip` | 왼쪽 메인 PCB (트랙볼 없는 쪽) | 약 143 × 114 mm |
| `2_main-pcb_RIGHT_ball_143x114.zip` | 오른쪽 메인 PCB (트랙볼 쪽) | 약 143 × 114 mm |
| `3_top-plate_LEFT_noball.zip` | 왼쪽 상판 (스위치 플레이트, PCB 재질) | 메인 PCB와 비슷 |
| `4_top-plate_RIGHT_ball.zip` | 오른쪽 상판 | 메인 PCB와 비슷 |

- 원작자의 빌드 가이드에서는 메인 PCB를 **"Middle board"**, 상판을 **"Top PCB plate"**라고 부릅니다.
- 상판 zip에는 동박(copper) 레이어가 있지만 전기 회로는 없습니다. 그냥 PCB로 주문하면 됩니다.

### 추천 옵션

| 항목 | 값 |
|---|---|
| Base Material | FR-4 |
| Layers | 2 |
| PCB Qty | 5 (최소 수량) |
| PCB Thickness | 1.6 mm |
| Surface Finish | HASL (with lead / lead-free) 또는 ENIG |
| Mark on PCB (주문번호) | "Remove Mark" 또는 "Specify Location" |
| 그 외 | 기본값 |

- 메인 PCB는 100 × 100 mm를 넘어서 $2 특가가 적용되지 않습니다. 업로드하면 견적이 바로 나옵니다.
- 상판은 엄지 키 부분에 **절단용 브리지(perforation)**가 있습니다. 받은 뒤 잘라내야 합니다 (빌드 가이드 6장).
- 직접 납땜할 거라면 **PCB Assembly는 체크하지 마세요.**

### 배송 (한국)
- 주소에 **개인통관고유부호**를 꼭 넣으세요 (유니패스에서 발급).
- 빠른 배송은 DHL/FedEx, 저렴한 배송은 Global Standard Direct입니다.

## 2. 아크릴 판 (`acrylic/`, 레이저 커팅 업체에 의뢰)

| 파일 | 두께 | 재질 |
|---|---|---|
| `Keyball61_MiddleAcryl_3mm.dxf` | 3 mm | 아크릴 (색은 자유) |
| `Keyball61_Rev1_BallSide_Bottom_Acryl_Clear2mm.dxf` | 2 mm | 투명 아크릴 |
| `Keyball61_Rev1_NoBallSide_Bottom_Acryl_Clear2mm.dxf` | 2 mm | 투명 아크릴 |

JLCPCB의 CNC/레이저 서비스나 국내 레이저 커팅 업체에 DXF를 그대로 보내면 됩니다.

## 3. 공개 파일에 없어서 따로 구해야 하는 것

- **트랙볼 센서 보드**: 원작 키트의 "Trackball reader circuit board"는 공개되지 않았습니다. 따로 사거나 직접 만들어야 합니다 (아래 4번).
- **트랙볼 케이스 (볼 홀더)**: 3D 프린팅으로 출력하거나 BOOTH 등에서 구매합니다.
- **ProMicro 보호판**: 아크릴로 작게 만들거나 생략합니다.
- 나사와 스페이서 (빌드 가이드 부품표 기준)
  - M2 스페이서: 7 mm 17개 이상, 9 mm 4개 (엄지를 로우프로파일로 할 때는 5 mm 5개)
  - M2 나사 3.5 mm: 42개 이상
  - M1.7 나사: 4개 (트랙볼 케이스용)

## 4. 트랙볼 센서 연결 (오른쪽 PCB의 J2, 7핀, 2.54 mm 간격)

KiCad 넷리스트에서 확인한 내용입니다.

| J2 핀 | 신호 |
|---|---|
| 3 | GND |
| 4 | VCC |
| 5 | GND |
| 1, 2, 6, 7 | SPI 신호 (SCLK / MOSI / MISO / NCS). 점퍼로 배치를 선택 |

신호 핀은 PCB 위의 **솔더 점퍼(JP)**로 두 가지 배치 중 하나를 고릅니다. 둘 중 **한 세트만** 납땜으로 연결하세요.

| 배치 | 연결할 점퍼 | J2-1 | J2-2 | J2-6 | J2-7 |
|---|---|---|---|---|---|
| A | JP1, JP3, JP5, JP7 | MISO | MOSI | NCS | SCLK |
| B | JP10, JP12, JP14, JP16 | SCLK | NCS | MOSI | MISO |

컨트롤러 쪽은 SCLK = B1, MOSI = B2, MISO = B3, NCS = B6입니다 (Pro Micro 핀 이름 기준).

- **PMW3360 (유선)**: 4선 SPI라 그대로 맞습니다. 렌즈는 LM19-LSI입니다.
- **PMW3610 (무선)**: 3선 SPI입니다. 센서의 SDIO 하나를 MOSI와 MISO 양쪽에 연결하는 식으로 배선을 바꿔야 할 수 있습니다. 구입한 센서 보드의 핀 배치와 ZMK 드라이버 문서를 보고 확정하세요. 렌즈는 LM18-LSI입니다.

## 5. `alt-kicad-export/` (예비용)

원작자의 KiCad 원본(`keyball61_*_KiCad.zip`)을 KiCad 7.0으로 열어 다시 뽑은 거버입니다. 보드 외곽은 1번, 2번 파일과 같습니다. **보통은 `jlcpcb/`에 있는 원작자 거버를 쓰세요.** 업로드에 문제가 있을 때만 이 파일을 씁니다.
