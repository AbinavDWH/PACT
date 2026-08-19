package org.pact.codec

import java.io.File

/**
 * Loads shared/codec/pact_tables.v1.json.
 *
 * Hand-rolled JSON parsing so this module compiles on plain JVM (for the parity
 * test) with zero dependencies, and on Android without pulling in a parser.
 * Call [loadFrom] once at startup; on Android that is the copied asset, on JVM
 * it is the shared file.
 */
object Tables {
    data class Field(val name: String, val chars: Int)
    data class Layout(val versionChar: String, val length: Int, val fields: List<Field>)

    private var root: Json.Obj? = null

    fun loadFrom(path: String) { root = Json.parse(File(path).readText()) as Json.Obj }
    fun loadFromText(text: String) { root = Json.parse(text) as Json.Obj }

    private fun r(): Json.Obj = root ?: error("Tables.loadFrom() not called")

    private fun dimensions(): Json.Obj = r()["dimensions"] as Json.Obj

    /** Follows `resources -> needs` aliases. */
    private fun dim(name: String): Json.Obj {
        var d = dimensions()[name] as Json.Obj
        while ((d["kind"] as? String) == "alias") d = dimensions()[d["of"] as String] as Json.Obj
        return d
    }

    fun layout(kind: String): Layout? {
        val l = (r()["layouts"] as Json.Obj)[kind] as? Json.Obj ?: return null
        val fields = (l["fields"] as Json.Arr).items.map {
            val f = it as Json.Obj
            Field(f["name"] as String, (f["chars"] as Double).toInt())
        }
        return Layout(l["version_char"] as String, (l["length"] as Double).toInt(), fields)
    }

    fun isBitfield(name: String): Boolean = (dim(name)["kind"] as? String) == "bitfield"

    fun value(name: String, ch: String): String? {
        val v = (dim(name)["values"] as Json.Obj)[ch] ?: return null
        return if (v is String) v else ((v as Json.Obj)["label"] as? String)
    }

    fun rep(name: String, ch: String): Int? {
        val v = (dim(name)["values"] as Json.Obj)[ch]
        return ((v as? Json.Obj)?.get("rep") as? Double)?.toInt()
    }

    fun hasCode(name: String, ch: String): Boolean =
        (dim(name)["values"] as Json.Obj).map.containsKey(ch)

    fun codeForLabel(name: String, label: String): String? =
        (dim(name)["values"] as Json.Obj).map.entries.firstOrNull { (_, v) ->
            (if (v is String) v else (v as? Json.Obj)?.get("label")) == label
        }?.key

    private fun bitMap(name: String): List<Json.Obj> =
        (dim(name)["map"] as Json.Arr).items.map { it as Json.Obj }

    fun keysFromBits(name: String, value: Long): List<String> =
        bitMap(name).filter { (value shr (it["bit"] as Double).toInt()) and 1L == 1L }
                    .map { it["key"] as String }

    fun bitsFromKeys(name: String, keys: List<String>): Long {
        var out = 0L
        for (e in bitMap(name)) {
            if (e["key"] in keys || e["code"] in keys) out = out or (1L shl (e["bit"] as Double).toInt())
        }
        return out
    }

    fun accuracy(): Map<String, Double?> =
        (r()["accuracy"] as Json.Obj).map.mapValues { (_, v) -> v as? Double }

    fun locationCodes(): Map<String, String> =
        (r()["location_codes"] as Json.Obj).map.mapValues { (_, v) -> v as String }

    fun statusCodes(): Map<String, String> =
        (r()["status_codes"] as Json.Obj).map.mapValues { (_, v) -> v as String }
}

/** Minimal JSON reader. Enough for the tables and the parity vectors. */
object Json {
    class Obj(val map: LinkedHashMap<String, Any?>) {
        operator fun get(k: String): Any? = map[k]
    }
    class Arr(val items: List<Any?>)

    fun parse(text: String): Any? = Parser(text).let { p -> p.ws(); p.value() }

    private class Parser(val s: String) {
        var i = 0
        fun ws() { while (i < s.length && s[i].isWhitespace()) i++ }
        fun value(): Any? {
            ws()
            return when (s[i]) {
                '{' -> obj(); '[' -> arr(); '"' -> str()
                't' -> { i += 4; true }
                'f' -> { i += 5; false }
                'n' -> { i += 4; null }
                else -> num()
            }
        }
        fun obj(): Obj {
            val m = LinkedHashMap<String, Any?>(); i++       // {
            ws()
            if (s[i] == '}') { i++; return Obj(m) }
            while (true) {
                ws(); val k = str(); ws(); i++               // :
                m[k] = value(); ws()
                if (s[i] == ',') { i++; continue }
                i++; return Obj(m)                           // }
            }
        }
        fun arr(): Arr {
            val out = ArrayList<Any?>(); i++                 // [
            ws()
            if (s[i] == ']') { i++; return Arr(out) }
            while (true) {
                out.add(value()); ws()
                if (s[i] == ',') { i++; continue }
                i++; return Arr(out)                         // ]
            }
        }
        fun str(): String {
            val sb = StringBuilder(); i++                    // "
            while (s[i] != '"') {
                if (s[i] == '\\') {
                    i++
                    when (s[i]) {
                        'n' -> sb.append('\n'); 't' -> sb.append('\t')
                        'r' -> sb.append('\r'); 'b' -> sb.append('\b')
                        'u' -> { sb.append(s.substring(i + 1, i + 5).toInt(16).toChar()); i += 4 }
                        else -> sb.append(s[i])
                    }
                } else sb.append(s[i])
                i++
            }
            i++
            return sb.toString()
        }
        fun num(): Double {
            val start = i
            while (i < s.length && (s[i].isDigit() || s[i] in "-+.eE")) i++
            return s.substring(start, i).toDouble()
        }
    }
}
