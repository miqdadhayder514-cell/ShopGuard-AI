package com.shopguard.ai.data.network

import com.google.gson.Gson
import com.google.gson.JsonSyntaxException
import com.shopguard.ai.data.model.*
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import java.net.ConnectException
import java.net.SocketTimeoutException
import java.net.UnknownHostException
import java.util.concurrent.TimeUnit
import javax.net.ssl.SSLException

/**
 * HTTP Client for communicating with the local Windows ShopGuard AI FastAPI Agent.
 *
 * Security Features:
 * - Full Tailscale HTTPS compatibility (port 443 with official Let's Encrypt TLS verification).
 * - Protected endpoints authenticate via the exact 'X-API-Key' HTTP header.
 * - API keys are NEVER exposed in URLs or query strings.
 * - Test connection probes 'GET /api/health' without requiring authentication if public health is enabled.
 * - Detailed error handling distinguishing HTTP 400, 401, 403, 404, 422, 5xx, and network/TLS errors.
 */
class ApiClient(
    private val client: OkHttpClient = OkHttpClient.Builder()
        .connectTimeout(6, TimeUnit.SECONDS)
        .readTimeout(10, TimeUnit.SECONDS)
        .writeTimeout(6, TimeUnit.SECONDS)
        .retryOnConnectionFailure(true)
        .build(),
    private val gson: Gson = Gson()
) {
    private val armClient = client.newBuilder()
        .readTimeout(60, TimeUnit.SECONDS)
        .build()
    private val jsonMediaType = "application/json; charset=utf-8".toMediaType()

    suspend fun getStatus(baseUrl: String, apiKey: String): Result<StatusResponse> =
        withContext(Dispatchers.IO) {
            val url = UrlBuilder.buildEndpointUrl(baseUrl, "/api/status")
            executeGet(url, apiKey, StatusResponse::class.java)
        }

    suspend fun getCameras(baseUrl: String, apiKey: String): Result<CamerasResponse> =
        withContext(Dispatchers.IO) {
            val url = UrlBuilder.buildEndpointUrl(baseUrl, "/api/cameras")
            executeGet(url, apiKey, CamerasResponse::class.java)
        }

    suspend fun getSecurityState(baseUrl: String, apiKey: String): Result<SecurityStateResponse> =
        withContext(Dispatchers.IO) {
            val url = UrlBuilder.buildEndpointUrl(baseUrl, "/api/security/state")
            executeGet(url, apiKey, SecurityStateResponse::class.java)
        }

    suspend fun armSecurity(baseUrl: String, apiKey: String, reason: String): Result<ArmOperationResponse> =
        withContext(Dispatchers.IO) {
            val url = UrlBuilder.buildEndpointUrl(baseUrl, "/api/security/arm")
            val bodyJson = gson.toJson(ArmRequest(reason = reason))
            executePost(url, apiKey, bodyJson, ArmOperationResponse::class.java, armClient)
        }

    suspend fun disarmSecurity(baseUrl: String, apiKey: String, reason: String): Result<DisarmOperationResponse> =
        withContext(Dispatchers.IO) {
            val url = UrlBuilder.buildEndpointUrl(baseUrl, "/api/security/disarm")
            val bodyJson = gson.toJson(DisarmRequest(reason = reason))
            executePost(url, apiKey, bodyJson, DisarmOperationResponse::class.java)
        }

    suspend fun getIncidents(baseUrl: String, apiKey: String, limit: Int = 20, offset: Int = 0): Result<IncidentsListResponse> =
        withContext(Dispatchers.IO) {
            val url = UrlBuilder.buildEndpointUrl(baseUrl, "/api/incidents?limit=$limit&offset=$offset")
            executeGet(url, apiKey, IncidentsListResponse::class.java)
        }

    suspend fun getIncidentDetail(baseUrl: String, apiKey: String, incidentId: String): Result<IncidentDetail> =
        withContext(Dispatchers.IO) {
            val url = UrlBuilder.buildEndpointUrl(baseUrl, "/api/incidents/$incidentId")
            executeGet(url, apiKey, IncidentDetail::class.java)
        }

    suspend fun testCameraConnection(baseUrl: String, apiKey: String, req: CameraTestRequest): Result<CameraTestResponse> =
        withContext(Dispatchers.IO) {
            val url = UrlBuilder.buildEndpointUrl(baseUrl, "/api/cameras/test")
            val bodyJson = gson.toJson(req)
            executePost(url, apiKey, bodyJson, CameraTestResponse::class.java)
        }

    suspend fun addCamera(baseUrl: String, apiKey: String, req: CameraCreateRequest): Result<CameraOperationResponse> =
        withContext(Dispatchers.IO) {
            val url = UrlBuilder.buildEndpointUrl(baseUrl, "/api/cameras")
            val bodyJson = gson.toJson(req)
            executePost(url, apiKey, bodyJson, CameraOperationResponse::class.java)
        }

    suspend fun updateCamera(baseUrl: String, apiKey: String, cameraId: String, req: CameraUpdateRequest): Result<CameraOperationResponse> =
        withContext(Dispatchers.IO) {
            val url = UrlBuilder.buildEndpointUrl(baseUrl, "/api/cameras/$cameraId")
            val bodyJson = gson.toJson(req)
            executePut(url, apiKey, bodyJson, CameraOperationResponse::class.java)
        }

    suspend fun deleteCamera(baseUrl: String, apiKey: String, cameraId: String): Result<CameraOperationResponse> =
        withContext(Dispatchers.IO) {
            val url = UrlBuilder.buildEndpointUrl(baseUrl, "/api/cameras/$cameraId")
            executeDelete(url, apiKey, CameraOperationResponse::class.java)
        }

    suspend fun getHealth(baseUrl: String, apiKey: String): Result<HealthResponse> =
        withContext(Dispatchers.IO) {
            val url = UrlBuilder.buildEndpointUrl(baseUrl, "/api/health")
            executeGet(url, apiKey, HealthResponse::class.java)
        }

    suspend fun registerFcmToken(
        baseUrl: String,
        apiKey: String,
        token: String,
        deviceName: String = "Android Device",
        appVersion: String = "1.0.0"
    ): Result<NotificationOperationResponse> =
        withContext(Dispatchers.IO) {
            val url = UrlBuilder.buildEndpointUrl(baseUrl, "/api/notifications/register-token")
            val bodyJson = gson.toJson(DeviceTokenRegisterRequest(token, deviceName, appVersion))
            executePost(url, apiKey, bodyJson, NotificationOperationResponse::class.java)
        }

    suspend fun unregisterFcmToken(
        baseUrl: String,
        apiKey: String,
        token: String
    ): Result<NotificationOperationResponse> =
        withContext(Dispatchers.IO) {
            val url = UrlBuilder.buildEndpointUrl(baseUrl, "/api/notifications/unregister-token")
            val bodyJson = gson.toJson(DeviceTokenUnregisterRequest(token))
            executePost(url, apiKey, bodyJson, NotificationOperationResponse::class.java)
        }

    /**
     * Probes the Windows Agent by calling GET /api/health.
     *
     * - Target: GET /api/health (never /api/status).
     * - Authentication: Sends X-API-Key only if apiKey is not blank.
     *   If blank, allows unauthenticated public health read.
     * - No API key is ever appended to the URL or query parameters.
     * - Returns rich diagnostic information on both success and failure.
     */
    suspend fun testConnection(baseUrl: String, apiKey: String): ConnectionTestResult =
        withContext(Dispatchers.IO) {
            val startTime = System.currentTimeMillis()
            val healthUrl = UrlBuilder.buildEndpointUrl(baseUrl, "/api/health")

            try {
                val reqBuilder = Request.Builder()
                    .url(healthUrl)
                    .get()

                // Health endpoint: only send X-API-Key if key is provided.
                // Never put API key in query parameters or URL.
                if (apiKey.isNotBlank()) {
                    reqBuilder.header("X-API-Key", apiKey.trim())
                }

                val response = client.newCall(reqBuilder.build()).execute()
                val latency = System.currentTimeMillis() - startTime
                val code = response.code
                val rawBody = response.body?.string() ?: ""

                if (response.isSuccessful) {
                    val health = try {
                        gson.fromJson(rawBody, HealthResponse::class.java)
                    } catch (e: JsonSyntaxException) {
                        null
                    }

                    ConnectionTestResult(
                        isSuccess = true,
                        statusCode = code,
                        message = "Connected to ShopGuard AI Agent (${latency}ms)",
                        rawResponseBody = rawBody,
                        latencyMs = latency,
                        healthResponse = health,
                        detectedState = health?.securityState ?: "DISARMED",
                        overallHealth = health?.overallHealth ?: "HEALTHY",
                        aiModelLoaded = health?.aiModelLoaded ?: true,
                        mode = health?.mode ?: "CCTV",
                        camerasCount = health?.cameras?.size ?: 0,
                        errorType = ConnectionErrorType.NONE
                    )
                } else {
                    val errorType = when (code) {
                        400 -> ConnectionErrorType.BAD_REQUEST_400
                        401 -> ConnectionErrorType.UNAUTHORIZED_401
                        403 -> ConnectionErrorType.FORBIDDEN_403
                        404 -> ConnectionErrorType.NOT_FOUND_404
                        422 -> ConnectionErrorType.UNPROCESSABLE_ENTITY_422
                        in 500..599 -> ConnectionErrorType.SERVER_ERROR_5XX
                        else -> ConnectionErrorType.UNKNOWN
                    }

                    val diagnosticMessage = when (code) {
                        400 -> "HTTP 400 Bad Request: Host rejected the request. Ensure you are using HTTPS on port 443 without duplicated protocols, ports, or paths."
                        401 -> "HTTP 401 Unauthorized: The agent rejected authentication. Verify your Agent Secret API Key."
                        403 -> "HTTP 403 Forbidden: Access denied by local agent security policy."
                        404 -> "HTTP 404 Not Found: /api/health endpoint not found. Verify the ShopGuard AI agent is running on this host."
                        422 -> "HTTP 422 Unprocessable Entity: Parameter or payload validation failed."
                        502 -> "HTTP 502 Bad Gateway: The Tailscale Serve/proxy could not reach the Windows agent. Start the agent on Windows, verify http://127.0.0.1:8000/api/health locally, then configure `tailscale serve 8000` and check `tailscale serve status`."
                        in 500..599 -> "HTTP $code Server Error: The agent encountered an internal server error."
                        else -> "HTTP $code: ${response.message.ifBlank { "Request failed" }}"
                    }

                    ConnectionTestResult(
                        isSuccess = false,
                        statusCode = code,
                        message = diagnosticMessage,
                        rawResponseBody = rawBody.ifBlank { response.message },
                        latencyMs = latency,
                        errorType = errorType
                    )
                }
            } catch (e: Exception) {
                val latency = System.currentTimeMillis() - startTime
                val (errorType, message) = when (e) {
                    is SocketTimeoutException -> Pair(
                        ConnectionErrorType.NETWORK_TIMEOUT,
                        "Connection timed out (${latency}ms). Check network/Tailscale connection."
                    )
                    is UnknownHostException -> Pair(
                        ConnectionErrorType.NETWORK_UNREACHABLE,
                        "Unknown host: '${e.message}'. Could not resolve hostname."
                    )
                    is ConnectException -> Pair(
                        ConnectionErrorType.NETWORK_UNREACHABLE,
                        "Connection refused. Ensure ShopGuard AI agent is running on the host."
                    )
                    is SSLException -> Pair(
                        ConnectionErrorType.TLS_ERROR,
                        "TLS/SSL Handshake failed: ${e.localizedMessage}. Verify Tailscale HTTPS certificate."
                    )
                    else -> Pair(
                        ConnectionErrorType.UNKNOWN,
                        "Connection failed: ${e.localizedMessage ?: e.javaClass.simpleName}"
                    )
                }

                ConnectionTestResult(
                    isSuccess = false,
                    statusCode = -1,
                    message = message,
                    rawResponseBody = e.stackTraceToString().take(300),
                    latencyMs = latency,
                    errorType = errorType
                )
            }
        }

    private fun <T> executeGet(url: String, apiKey: String, clazz: Class<T>): Result<T> {
        return try {
            val reqBuilder = Request.Builder().url(url).get()
            // Send exact X-API-Key header for protected endpoints
            if (apiKey.isNotBlank()) {
                reqBuilder.header("X-API-Key", apiKey.trim())
            }
            val response = client.newCall(reqBuilder.build()).execute()
            val rawBody = response.body?.string() ?: ""
            if (!response.isSuccessful) {
                return Result.failure(parseApiException(response.code, rawBody, response.message, url))
            }
            if (rawBody.isBlank()) {
                return Result.failure(SecurityApiException(response.code, "EMPTY_BODY", "Empty response body from $url", emptyList(), ""))
            }
            Result.success(gson.fromJson(rawBody, clazz))
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    private fun <T> executePost(
        url: String,
        apiKey: String,
        bodyJson: String,
        clazz: Class<T>,
        requestClient: OkHttpClient = client
    ): Result<T> {
        return try {
            val reqBody = bodyJson.toRequestBody(jsonMediaType)
            val reqBuilder = Request.Builder().url(url).post(reqBody)
            if (apiKey.isNotBlank()) {
                reqBuilder.header("X-API-Key", apiKey.trim())
            }
            val response = requestClient.newCall(reqBuilder.build()).execute()
            val rawBody = response.body?.string() ?: ""
            if (!response.isSuccessful) {
                return Result.failure(parseApiException(response.code, rawBody, response.message, url))
            }
            if (rawBody.isBlank()) {
                return Result.failure(SecurityApiException(response.code, "EMPTY_BODY", "Empty response body from $url", emptyList(), ""))
            }
            Result.success(gson.fromJson(rawBody, clazz))
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    private fun <T> executePut(url: String, apiKey: String, bodyJson: String, clazz: Class<T>): Result<T> {
        return try {
            val reqBody = bodyJson.toRequestBody(jsonMediaType)
            val reqBuilder = Request.Builder().url(url).put(reqBody)
            if (apiKey.isNotBlank()) {
                reqBuilder.header("X-API-Key", apiKey.trim())
            }
            val response = client.newCall(reqBuilder.build()).execute()
            val rawBody = response.body?.string() ?: ""
            if (!response.isSuccessful) {
                return Result.failure(parseApiException(response.code, rawBody, response.message, url))
            }
            if (rawBody.isBlank()) {
                return Result.failure(SecurityApiException(response.code, "EMPTY_BODY", "Empty response body from $url", emptyList(), ""))
            }
            Result.success(gson.fromJson(rawBody, clazz))
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    private fun <T> executeDelete(url: String, apiKey: String, clazz: Class<T>): Result<T> {
        return try {
            val reqBuilder = Request.Builder().url(url).delete()
            if (apiKey.isNotBlank()) {
                reqBuilder.header("X-API-Key", apiKey.trim())
            }
            val response = client.newCall(reqBuilder.build()).execute()
            val rawBody = response.body?.string() ?: ""
            if (!response.isSuccessful) {
                return Result.failure(parseApiException(response.code, rawBody, response.message, url))
            }
            if (rawBody.isBlank()) {
                return Result.failure(SecurityApiException(response.code, "EMPTY_BODY", "Empty response body from $url", emptyList(), ""))
            }
            Result.success(gson.fromJson(rawBody, clazz))
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    private fun parseApiException(code: Int, rawBody: String, defaultMessage: String, url: String): Exception {
        var errorCode = "HTTP_$code"
        var parsedMessage = defaultMessage
        var reasonsList: List<String> = emptyList()

        try {
            val jsonObj = gson.fromJson(rawBody, com.google.gson.JsonObject::class.java)
            if (jsonObj != null && jsonObj.has("detail")) {
                val detailElem = jsonObj.get("detail")
                if (detailElem.isJsonObject) {
                    val detailObj = detailElem.asJsonObject
                    if (detailObj.has("error")) errorCode = detailObj.get("error").asString
                    if (detailObj.has("message")) parsedMessage = detailObj.get("message").asString
                    if (detailObj.has("reasons") && detailObj.get("reasons").isJsonArray) {
                        reasonsList = detailObj.get("reasons").asJsonArray.mapNotNull { it.asString }
                    }
                } else if (detailElem.isJsonPrimitive) {
                    parsedMessage = detailElem.asString
                }
            }
        } catch (_: Exception) {}

        val userMessage = when (code) {
            401 -> "Authentication Failed (HTTP 401): Invalid or missing Agent Secret API Key. Check Settings → Device Connection."
            400 -> {
                val reasonsStr = if (reasonsList.isNotEmpty()) " (${reasonsList.joinToString("; ")})" else ""
                "Arming Rejected: ${parsedMessage.ifBlank { "System prerequisites check failed." }}$reasonsStr"
            }
            409 -> "State Conflict (HTTP 409): ${parsedMessage.ifBlank { "System is already in the requested state." }}"
            404 -> "Endpoint Not Found (HTTP 404): $url"
            422 -> "Validation Error (HTTP 422): $parsedMessage"
            in 500..599 -> "Agent Server Error (HTTP $code): ${parsedMessage.ifBlank { "Internal error occurred." }}"
            else -> "HTTP $code: ${parsedMessage.ifBlank { defaultMessage }}"
        }

        return SecurityApiException(
            statusCode = code,
            errorCode = errorCode,
            message = userMessage,
            reasons = reasonsList,
            rawBody = rawBody
        )
    }
}

/**
 * Structured exception capturing API response codes, server messages, and rejection reasons.
 */
data class SecurityApiException(
    val statusCode: Int,
    val errorCode: String = "UNKNOWN",
    override val message: String,
    val reasons: List<String> = emptyList(),
    val rawBody: String = ""
) : Exception(message)
