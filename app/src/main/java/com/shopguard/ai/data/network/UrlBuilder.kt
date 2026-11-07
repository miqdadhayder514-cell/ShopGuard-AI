package com.shopguard.ai.data.network

import java.net.URI

/**
 * Utility for constructing and normalizing ShopGuard AI Agent URLs.
 * Ensures the base URL is constructed cleanly without duplicated protocols,
 * ports, or API paths (especially for Tailscale HTTPS on port 443).
 */
object UrlBuilder {

    /**
     * Builds a normalized base URL in the exact format:
     * - For HTTPS: `https://HOSTNAME/` (or `https://HOSTNAME:PORT/` if custom non-443 port)
     * - For HTTP:  `http://HOSTNAME:PORT/` (or `http://HOSTNAME/` if port 80)
     *
     * Rules enforced:
     * 1. Strips existing protocol from input to prevent "http://https://" or "https://https://".
     * 2. Strips trailing slashes and any path (such as "/api" or "/api/health") to prevent path duplication.
     * 3. Detects HTTPS if:
     *    - [rawHost] originally starts with "https://"
     *    - [useHttps] is explicitly true
     *    - [port] is 443
     *    - [rawHost] contains ".ts.net" (Tailscale domain)
     * 4. For HTTPS on port 443, port 443 is omitted to produce exactly `https://HOSTNAME/`.
     * 5. Always ends with a single trailing slash.
     */
    fun buildBaseUrl(
        rawHost: String,
        port: Int? = null,
        useHttps: Boolean? = null
    ): String {
        var input = rawHost.trim()
        if (input.isEmpty()) {
            input = "10.0.2.2"
        }

        // 1. Detect protocol hint from input string
        val hasHttpsPrefix = input.startsWith("https://", ignoreCase = true)
        val hasHttpPrefix = input.startsWith("http://", ignoreCase = true)

        // 2. Determine whether to use HTTPS
        val isHttps = when {
            hasHttpsPrefix -> true
            useHttps == true -> true
            port == 443 -> true
            input.contains(".ts.net", ignoreCase = true) -> true
            hasHttpPrefix -> false
            useHttps == false -> false
            else -> false
        }

        // 3. Strip scheme if present
        var stripped = input
            .replace(Regex("^https?://", RegexOption.IGNORE_CASE), "")
            .trim()

        // 4. Strip any path component (e.g. "/api/health", "/api", "/")
        val slashIndex = stripped.indexOf('/')
        if (slashIndex != -1) {
            stripped = stripped.substring(0, slashIndex).trim()
        }

        // 5. Check if host has embedded port (e.g. "my-host.ts.net:443" or "10.0.2.2:8000")
        var hostPart = stripped
        var extractedPort: Int? = null

        val colonIndex = stripped.lastIndexOf(':')
        if (colonIndex != -1 && !stripped.endsWith("]")) {
            val potentialPort = stripped.substring(colonIndex + 1)
            val parsedPort = potentialPort.toIntOrNull()
            if (parsedPort != null) {
                hostPart = stripped.substring(0, colonIndex)
                extractedPort = parsedPort
            }
        }

        val cleanHost = hostPart.trim().lowercase()
        val effectivePort = extractedPort ?: port

        // 6. Construct exact base URL
        val scheme = if (isHttps) "https" else "http"

        return if (isHttps) {
            if (effectivePort == null || effectivePort == 443 || effectivePort == 80) {
                // Exact format: https://HOSTNAME/
                "https://$cleanHost/"
            } else {
                "https://$cleanHost:$effectivePort/"
            }
        } else {
            if (effectivePort == null || effectivePort == 80) {
                "http://$cleanHost/"
            } else {
                "http://$cleanHost:$effectivePort/"
            }
        }
    }

    /**
     * Builds a full endpoint URL by combining [baseUrl] with [endpointPath],
     * safely eliminating duplicate slashes and redundant "/api" segments.
     *
     * Example:
     * baseUrl = "https://my-host.ts.net/", endpointPath = "/api/health"
     * -> "https://my-host.ts.net/api/health"
     */
    fun buildEndpointUrl(baseUrl: String, endpointPath: String): String {
        val cleanBase = baseUrl.trimEnd('/')
        val cleanPath = "/" + endpointPath.trimStart('/')

        // If baseUrl already ended with "/api" and endpointPath starts with "/api", avoid duplication
        return if (cleanBase.endsWith("/api", ignoreCase = true) && cleanPath.startsWith("/api/", ignoreCase = true)) {
            cleanBase + cleanPath.removePrefix("/api")
        } else {
            cleanBase + cleanPath
        }
    }
}
