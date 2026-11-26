// HOM 3x4 Macropad - default keymap (Windows shortcuts)
#include QMK_KEYBOARD_H

const uint16_t PROGMEM keymaps[][MATRIX_ROWS][MATRIX_COLS] = {
    /* Layer 0
     * ┌───────┬───────┬───────┬───────┐
     * │ Copy  │ Paste │  Cut  │ Undo  │
     * ├───────┼───────┼───────┼───────┤
     * │ Vol-  │ Vol+  │ Mute  │ Play  │
     * ├───────┼───────┼───────┼───────┤
     * │ Save  │ Find  │ Redo  │ Fn    │
     * └───────┴───────┴───────┴───────┘
     */
    [0] = LAYOUT_ortho_3x4(
        C(KC_C),  C(KC_V),  C(KC_X),  C(KC_Z),
        KC_VOLD,  KC_VOLU,  KC_MUTE,  KC_MPLY,
        C(KC_S),  C(KC_F),  C(KC_Y),  MO(1)
    ),
    /* Layer 1 (hold Fn)
     * ┌───────┬───────┬───────┬───────┐
     * │ BOOT  │   1   │   2   │   3   │
     * ├───────┼───────┼───────┼───────┤
     * │ Prev  │   4   │   5   │   6   │
     * ├───────┼───────┼───────┼───────┤
     * │ Next  │   7   │   8   │ (Fn)  │
     * └───────┴───────┴───────┴───────┘
     */
    [1] = LAYOUT_ortho_3x4(
        QK_BOOT,  KC_1,     KC_2,     KC_3,
        KC_MPRV,  KC_4,     KC_5,     KC_6,
        KC_MNXT,  KC_7,     KC_8,     _______
    )
};
