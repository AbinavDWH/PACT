package org.humanitarian.fieldapp.sms

fun xorChecksum(text: String): String {
    var value = 0

    for (character in text) {
        value = value.xor(character.code)
    }

    return value.toString(16).uppercase().padStart(2, '0')
}