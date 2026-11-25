package ai.loadlink.driver

import ai.loadlink.driver.services.LocationForegroundService
import android.Manifest
import android.annotation.SuppressLint
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.PowerManager
import android.provider.Settings
import android.webkit.WebResourceRequest
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat

class MainActivity : AppCompatActivity() {

    private lateinit var webView: WebView

    private val permissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) { permissions ->
        val fineGranted = permissions[Manifest.permission.ACCESS_FINE_LOCATION] ?: false
        val coarseGranted = permissions[Manifest.permission.ACCESS_COARSE_LOCATION] ?: false

        if (fineGranted || coarseGranted) {
            promptBackgroundLocationRationale()
            checkBatteryOptimizationWhitelist()
            startLocationService()
        } else {
            Toast.makeText(this, "Location permission required for freight corridor compliance.", Toast.LENGTH_LONG).show()
        }
    }

    private val backgroundLocationLauncher = registerForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { granted ->
        if (!granted) {
            Toast.makeText(this, "Background location recommended to prevent OS killing telematics while screen is locked.", Toast.LENGTH_SHORT).show()
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setupWebView()
        requestCorePermissions()
    }

    @SuppressLint("SetJavaScriptEnabled")
    private fun setupWebView() {
        webView = WebView(this).apply {
            // Security hardening: Disable local file and content access to prevent CWE-200
            settings.allowFileAccess = false
            settings.allowContentAccess = false
            settings.setSupportMultipleWindows(false)
            settings.javaScriptEnabled = true
            settings.domStorageEnabled = true
            settings.cacheMode = WebSettings.LOAD_DEFAULT
            settings.databaseEnabled = true

            // Restrict navigation strictly to authorized application domains
            webViewClient = object : WebViewClient() {
                override fun shouldOverrideUrlLoading(view: WebView?, request: WebResourceRequest?): Boolean {
                    val url = request?.url ?: return true
                    val host = url.host ?: return true
                    val scheme = url.scheme ?: return true

                    // Only permit HTTP for local development emulator; enforce HTTPS for all remote domains
                    val isAllowedDevHost = BuildConfig.DEBUG && (host == "10.0.2.2" || host == "localhost" || host == "127.0.0.1")
                    val isAllowedProdHost = host.endsWith("loadlink.ai") && scheme == "https"

                    if (isAllowedDevHost || isAllowedProdHost) {
                        return false // Allow WebView to navigate
                    }

                    // For external emergency links (e.g. tel:, mailto:) handle via platform intent
                    if (scheme == "tel" || scheme == "mailto" || scheme == "smsto") {
                        val externalIntent = Intent(Intent.ACTION_VIEW, url)
                        try {
                            startActivity(externalIntent)
                        } catch (e: Exception) {
                            // Ignored if no handler app installed
                        }
                        return true
                    }

                    // Block all unknown/unauthorized schemes and remote origins
                    return true
                }
            }
        }
        setContentView(webView)

        // Load Driver Portal (configured per build variant via BuildConfig.PORTAL_BASE_URL)
        val driverPortalUrl = BuildConfig.PORTAL_BASE_URL
        webView.loadUrl(driverPortalUrl)
    }

    /**
     * Step 1: Request only essential foreground location and notification permissions at startup.
     * SEND_SMS is NEVER requested at startup to comply with Google Play Protect PHA policies.
     */
    private fun requestCorePermissions() {
        val permissions = mutableListOf(
            Manifest.permission.ACCESS_FINE_LOCATION,
            Manifest.permission.ACCESS_COARSE_LOCATION
        )

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            permissions.add(Manifest.permission.POST_NOTIFICATIONS)
        }

        permissionLauncher.launch(permissions.toTypedArray())
    }

    /**
     * Step 2: Android 11+ compliant multi-step permission flow.
     * Explains the legitimate logistical rationale to the driver before requesting background location.
     */
    private fun promptBackgroundLocationRationale() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            val bgGranted = ContextCompat.checkSelfPermission(
                this, Manifest.permission.ACCESS_BACKGROUND_LOCATION
            ) == PackageManager.PERMISSION_GRANTED

            if (!bgGranted) {
                AlertDialog.Builder(this)
                    .setTitle("Corridor Compliance & Safety")
                    .setMessage(
                        "LoadLink monitors freight movement along approved corridors. " +
                        "Allow 'All the time' location access so your trips and automated checkpoint milestones " +
                        "are not interrupted when your screen turns off or while using navigation."
                    )
                    .setPositiveButton("Configure in Settings") { _, _ ->
                        backgroundLocationLauncher.launch(Manifest.permission.ACCESS_BACKGROUND_LOCATION)
                    }
                    .setNegativeButton("Continue in Foreground Only", null)
                    .show()
            }
        }
    }

    @SuppressLint("BatteryLife")
    private fun checkBatteryOptimizationWhitelist() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            val powerManager = getSystemService(Context.POWER_SERVICE) as PowerManager
            if (!powerManager.isIgnoringBatteryOptimizations(packageName)) {
                val intent = Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS).apply {
                    data = Uri.parse("package:$packageName")
                }
                try {
                    startActivity(intent)
                } catch (e: Exception) {
                    // Ignored if device policy forbids dialog
                }
            }
        }
    }

    private fun startLocationService() {
        val prefs = getSharedPreferences("loadlink_driver_state", Context.MODE_PRIVATE)
        val driverId = prefs.getString("driver_id", "driver-authenticated")
        val truckId = prefs.getString("truck_id", "truck-assigned")
        val serviceIntent = Intent(this, LocationForegroundService::class.java).apply {
            action = LocationForegroundService.ACTION_START
            putExtra(LocationForegroundService.EXTRA_DRIVER_ID, driverId)
            putExtra(LocationForegroundService.EXTRA_TRUCK_ID, truckId)
        }
        ContextCompat.startForegroundService(this, serviceIntent)
    }

    /**
     * Native SMS Intent fallback: Opens default system messaging app with pre-filled SOS payload.
     * Requires NO SEND_SMS permission; driver explicitly confirms dispatch.
     */
    fun dispatchNativeEmergencySms(gatewayNumber: String, messageBody: String) {
        val uri = Uri.parse("smsto:${Uri.encode(gatewayNumber)}")
        val smsIntent = Intent(Intent.ACTION_SENDTO, uri).apply {
            putExtra("sms_body", messageBody)
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        }
        try {
            startActivity(smsIntent)
        } catch (e: Exception) {
            Toast.makeText(this, "Messaging app not available on this device.", Toast.LENGTH_SHORT).show()
        }
    }

    override fun onDestroy() {
        webView.destroy()
        super.onDestroy()
    }
}
