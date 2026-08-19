package org.pact.app

import android.content.Context
import android.util.Log
import org.json.JSONObject
import java.io.File

/**
 * Durable send queue.
 *
 * An append-only JSON-lines file rather than Room. The queue needs four
 * operations -- append, list, mark sent, count pending -- and Room would cost
 * an annotation processor, a schema directory and a build-time code generation
 * step to provide them. The plan permits this shape (memory_draft.md 23) and
 * the durability requirement is identical: a request typed into a phone with
 * no signal must still be there after the battery dies.
 *
 * Append is the only hot-path write and it is a single `appendText`, so a kill
 * mid-write can lose at most the line being added, never the queue.
 */
class Outbox(context: Context) {

    data class Entry(
        val id: String,
        val payload: String,
        val createdAt: Long,
        val state: String,          // pending | sent_http | sent_sms | failed
        val attempts: Int,
        val transport: String?,
        val note: String?,
    ) {
        val pending: Boolean get() = state == "pending"
    }

    private val file = File(context.filesDir, "outbox.jsonl")

    @Synchronized
    fun add(id: String, payload: String) {
        val line = JSONObject()
            .put("id", id)
            .put("payload", payload)
            .put("created_at", System.currentTimeMillis())
            .put("state", "pending")
            .put("attempts", 0)
            .toString()
        file.appendText(line + "\n")
    }

    @Synchronized
    fun all(): List<Entry> {
        if (!file.exists()) return emptyList()
        // Later lines for the same id supersede earlier ones -- that is what
        // makes an append-only log usable as mutable state without rewriting
        // the file on every status change.
        val latest = LinkedHashMap<String, Entry>()
        file.forEachLine { line ->
            if (line.isBlank()) return@forEachLine
            try {
                val o = JSONObject(line)
                val e = Entry(
                    id = o.getString("id"),
                    payload = o.getString("payload"),
                    createdAt = o.optLong("created_at"),
                    state = o.optString("state", "pending"),
                    attempts = o.optInt("attempts", 0),
                    transport = o.optString("transport").ifBlank { null },
                    note = o.optString("note").ifBlank { null },
                )
                latest[e.id] = e
            } catch (e: Exception) {
                // One corrupt line must not make the whole queue unreadable.
                Log.w(TAG, "skipping unparseable outbox line", e)
            }
        }
        return latest.values.toList()
    }

    fun pending(): List<Entry> = all().filter { it.pending }

    @Synchronized
    fun mark(id: String, state: String, transport: String? = null,
             note: String? = null, attempts: Int? = null) {
        val prev = all().firstOrNull { it.id == id }
        val line = JSONObject()
            .put("id", id)
            .put("payload", prev?.payload ?: "")
            .put("created_at", prev?.createdAt ?: System.currentTimeMillis())
            .put("state", state)
            .put("attempts", attempts ?: ((prev?.attempts ?: 0) + 1))
            .put("transport", transport)
            .put("note", note)
            .toString()
        file.appendText(line + "\n")
        if (file.length() > COMPACT_BYTES) compact()
    }

    /** Rewrites the log with one line per id. Only ever called from a
     *  @Synchronized caller. */
    private fun compact() {
        val snapshot = all()
        val tmp = File(file.parentFile, "outbox.tmp")
        tmp.writeText(snapshot.joinToString("\n") {
            JSONObject()
                .put("id", it.id).put("payload", it.payload)
                .put("created_at", it.createdAt).put("state", it.state)
                .put("attempts", it.attempts).put("transport", it.transport)
                .put("note", it.note).toString()
        } + "\n")
        if (!tmp.renameTo(file)) Log.w(TAG, "outbox compaction rename failed")
    }

    @Synchronized
    fun clear() { file.delete() }

    companion object {
        private const val TAG = "PactOutbox"
        private const val COMPACT_BYTES = 64 * 1024
    }
}
