package org.pact.app

import android.content.Context
import org.pact.codec.Tables

/**
 * The selection taxonomy, read straight out of the codec tables.
 *
 * There is deliberately no list of situations or injury levels written out in
 * this file. A second copy in the UI layer would drift from
 * `shared/codec/pact_tables.v1.json` the moment either changed, and the
 * failure mode is a chip that encodes to a code the backend rejects -- which
 * would surface as a rejected emergency, not a UI bug.
 */
object Options {

    @Volatile private var loaded = false

    /** Call once at startup. The asset is copied from shared/codec at build
     *  time by the syncCodecTables task, so it cannot be a stale duplicate. */
    @Synchronized
    fun load(context: Context) {
        if (loaded) return
        val text = context.assets.open("pact_tables.v1.json")
            .bufferedReader().use { it.readText() }
        Tables.loadFromText(text)
        loaded = true
    }

    data class Choice(val code: String, val label: String) {
        /** "building_collapse" -> "Building collapse" */
        val pretty: String get() = label.replace('_', ' ')
            .replaceFirstChar { it.uppercase() }
    }

    private fun enum(name: String, drop: Set<String> = emptySet()): List<Choice> =
        Tables.codes(name).filterNot { it.first in drop }.map { Choice(it.first, it.second) }

    // "9" is the unknown/unspecified code in several dimensions. It stays
    // available -- someone who does not know how badly a stranger is hurt must
    // still be able to send -- but it is listed last rather than mixed in.
    private fun enumUnknownLast(name: String): List<Choice> {
        val all = enum(name)
        return all.filterNot { it.code == "9" } + all.filter { it.code == "9" }
    }

    val situations: List<Choice> get() = enumUnknownLast("situation")
    val people: List<Choice> get() = enum("people")
    val injuries: List<Choice> get() = enumUnknownLast("injury")
    val mobility: List<Choice> get() = enumUnknownLast("mobility")
    val urgency: List<Choice> get() = enum("urgency")

    val needs: List<Choice>
        get() = Tables.bitKeys("needs").map { Choice(it.second, it.first) }

    val vulnerabilities: List<Choice>
        get() = Tables.bitKeys("vulnerability").map { Choice(it.second, it.first) }
}

/**
 * What the person selected. Every field is a code from the tables; there is no
 * free text anywhere in this class, which is the point -- see memory_draft.md
 * 15. A text box would produce something the codec cannot carry and something
 * an intercepted SMS could identify a person by.
 */
data class Selection(
    val situation: String? = null,
    val people: String? = null,
    val injury: String? = null,
    val mobility: String? = null,
    val urgency: String = "H",
    val needs: Set<String> = emptySet(),            // resource keys
    val vulnerabilities: Set<String> = emptySet(),  // vulnerability keys
) {
    /** Enough to send. Needs and a severity picture are the minimum that makes
     *  a request actionable; everything else has a defensible default. */
    val complete: Boolean get() =
        situation != null && people != null && injury != null &&
        mobility != null && needs.isNotEmpty()

    /** The map shape Payload.encode expects. Bitfields go in as key lists and
     *  the codec turns them into bits, so this never computes a bitmask. */
    fun toCodecMap(): Map<String, Any?> = mapOf(
        "situation" to situation,
        "people" to people,
        "injury" to injury,
        "mobility" to mobility,
        "urgency" to urgency,
        "needs" to needs.toList(),
        "vulnerability" to vulnerabilities.toList(),
    )
}
