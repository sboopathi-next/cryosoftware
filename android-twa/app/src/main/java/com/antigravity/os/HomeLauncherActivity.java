package com.antigravity.os;

import android.annotation.SuppressLint;
import android.content.Intent;
import android.graphics.Color;
import android.os.Build;
import android.os.Bundle;
import android.view.View;
import android.view.Window;
import android.view.WindowManager;
import android.webkit.ConsoleMessage;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.FrameLayout;
import androidx.appcompat.app.AppCompatActivity;
import com.antigravity.os.bridge.WebBridgeInterface;
import com.antigravity.os.utils.NotificationHelper;

public class HomeLauncherActivity extends AppCompatActivity {
    private WebView webView;
    private WebBridgeInterface bridge;
    private static final String DEFAULT_LAUNCH_URL = "https://cryosoftware.vercel.app/?source=launcher";

    @SuppressLint("SetJavaScriptEnabled")
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        // Configure system UI for immersive dark theme
        configureSystemUi();

        // Create root container & WebView
        FrameLayout rootLayout = new FrameLayout(this);
        rootLayout.setBackgroundColor(Color.parseColor("#070a11"));

        webView = new WebView(this);
        webView.setBackgroundColor(Color.parseColor("#070a11"));
        rootLayout.addView(webView, new FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT,
                FrameLayout.LayoutParams.MATCH_PARENT
        ));

        setContentView(rootLayout);

        // Configure WebSettings
        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setDatabaseEnabled(true);
        settings.setCacheMode(WebSettings.LOAD_DEFAULT);
        settings.setLoadsImagesAutomatically(true);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_ALWAYS_ALLOW);
        settings.setUseWideViewPort(true);
        settings.setLoadWithOverviewMode(true);
        settings.setSupportZoom(false);

        // Hardware Acceleration
        webView.setLayerType(View.LAYER_TYPE_HARDWARE, null);

        // Attach Native Bridge
        bridge = new WebBridgeInterface(this, webView);
        webView.addJavascriptInterface(bridge, "AntigravityNative");

        webView.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                String url = request.getUrl().toString();
                if (url.startsWith("https://cryosoftware.vercel.app") || url.startsWith("http://localhost")) {
                    return false;
                }
                // External links handled by system or internal
                return false;
            }

            @Override
            public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError error) {
                super.onReceivedError(view, request, error);
            }
        });

        webView.setWebChromeClient(new WebChromeClient() {
            @Override
            public boolean onConsoleMessage(ConsoleMessage consoleMessage) {
                return super.onConsoleMessage(consoleMessage);
            }
        });

        // Initialize Notification Channels
        NotificationHelper.createNotificationChannel(this);

        // Load Mission Control Dashboard
        webView.loadUrl(DEFAULT_LAUNCH_URL);

        handleIntent(getIntent());
    }

    private void configureSystemUi() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP) {
            Window window = getWindow();
            window.addFlags(WindowManager.LayoutParams.FLAG_DRAWS_SYSTEM_BAR_BACKGROUNDS);
            window.setStatusBarColor(Color.parseColor("#070a11"));
            window.setNavigationBarColor(Color.parseColor("#070a11"));
        }
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        setIntent(intent);
        handleIntent(intent);
    }

    private void handleIntent(Intent intent) {
        if (intent == null) return;

        if (intent.hasExtra("intercepted_app")) {
            String blockedPkg = intent.getStringExtra("intercepted_app");
            String reason = intent.getStringExtra("reason");
            if (webView != null && blockedPkg != null) {
                // Post-message to frontend to trigger Friction/Breathe Modal
                String js = String.format("if (window.onAppIntercepted) { window.onAppIntercepted('%s', '%s'); }",
                        blockedPkg.replace("'", "\\'"), reason != null ? reason : "");
                webView.post(() -> webView.evaluateJavascript(js, null));
            }
        }
    }

    @Override
    public void onBackPressed() {
        // As a Home Launcher, Back Button navigates web history if available, but never closes the launcher
        if (webView != null && webView.canGoBack()) {
            webView.goBack();
        } else {
            // Stay on dashboard home
            if (webView != null) {
                webView.evaluateJavascript("if (window.onHomePressed) { window.onHomePressed(); }", null);
            }
        }
    }

    @Override
    protected void onResume() {
        super.onResume();
        if (webView != null) {
            webView.evaluateJavascript("if (window.onLauncherResumed) { window.onLauncherResumed(); }", null);
        }
    }
}
