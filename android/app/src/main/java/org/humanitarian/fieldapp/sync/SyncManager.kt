package org.humanitarian.fieldapp.sync

import android.content.Context
import org.humanitarian.fieldapp.network.ApiClient
import org.humanitarian.fieldapp.network.ApiResult
import org.humanitarian.fieldapp.offline.OfflineQueue
import org.humanitarian.fieldapp.offline.QueuedReport

data class SyncResult(
    val synced: Int,
    val failed: Int,
    val remaining: Int
)

object SyncManager {

    // Attempts to POST every queued report to the backend.
    // Successful reports are removed; failed ones stay queued.
    suspend fun syncQueue(context: Context): SyncResult {
        val queued = OfflineQueue.getQueuedReports(context)
        if (queued.isEmpty()) {
            return SyncResult(0, 0, 0)
        }

        var synced = 0
        val remainingReports = mutableListOf<QueuedReport>()

        for (item in queued) {
            when (ApiClient.postNeed(item.report)) {
                is ApiResult.Success -> synced++
                is ApiResult.Error -> remainingReports.add(item)
            }
        }

        OfflineQueue.replaceQueue(context, remainingReports)

        return SyncResult(
            synced = synced,
            failed = remainingReports.size,
            remaining = remainingReports.size
        )
    }
}