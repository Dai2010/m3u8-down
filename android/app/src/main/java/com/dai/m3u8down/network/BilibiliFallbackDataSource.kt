package com.dai2010.m3u8down.network

import android.net.Uri
import androidx.media3.datasource.BaseDataSource
import androidx.media3.datasource.DataSource
import androidx.media3.datasource.DataSpec
import androidx.media3.datasource.DefaultHttpDataSource
import java.io.IOException

class BilibiliFallbackDataSource(
    private val headers: Map<String, String>,
    private val fallbackUrls: Map<String, List<String>>,
) : BaseDataSource(false) {
    private val httpFactory = DefaultHttpDataSource.Factory().setDefaultRequestProperties(headers)
    private var delegate: DataSource? = null
    private var currentUri: Uri? = null

    override fun open(dataSpec: DataSpec): Long {
        val candidates = listOf(dataSpec.uri.toString()) + fallbackUrls[dataSpec.uri.toString()].orEmpty()
        var lastError: IOException? = null
        for (candidate in candidates.distinct()) {
            val source = httpFactory.createDataSource()
            try {
                throttleBilibiliRequest(candidate)
                val length = source.open(dataSpec.withUri(Uri.parse(candidate)))
                delegate = source
                currentUri = source.uri
                return length
            } catch (exc: IOException) {
                lastError = exc
                runCatching { source.close() }
            }
        }
        throw lastError ?: IOException("B 站媒体轨道没有可用地址")
    }

    override fun read(buffer: ByteArray, offset: Int, length: Int): Int =
        delegate?.read(buffer, offset, length) ?: throw IOException("B 站媒体轨道尚未打开")

    override fun getUri(): Uri? = currentUri

    override fun getResponseHeaders(): Map<String, List<String>> = delegate?.responseHeaders.orEmpty()

    override fun close() {
        val source = delegate
        delegate = null
        currentUri = null
        source?.close()
    }

    class Factory(
        private val headers: Map<String, String>,
        private val fallbackUrls: Map<String, List<String>>,
    ) : DataSource.Factory {
        override fun createDataSource(): DataSource = BilibiliFallbackDataSource(headers, fallbackUrls)
    }
}
