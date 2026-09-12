package com.antigravity.os.services;

import android.accessibilityservice.AccessibilityService;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.view.accessibility.AccessibilityEvent;
import com.antigravity.os.HomeLauncherActivity;
import org.json.JSONArray;
import java.util.HashSet;
import java.util.Set;

public class AppBlockerAccessibilityService extends AccessibilityService {
    public static final String PREFS_NAME = "antigravity_launcher_prefs";
    public static final String KEY_BLOCKED_PACKAGES = "blocked_packages";
    public static final String KEY_BLOCKING_ENABLED = "blocking_enabled";

    // Standard default distraction apps
    public static final Set<String> DEFAULT_BLOCKED = new HashSet<>();
    static {
        DEFAULT_BLOCKED.add("com.instagram.android");
        DEFAULT_BLOCKED.add("com.zhiliaoapp.musically");
        DEFAULT_BLOCKED.add("com.google.android.youtube");
        DEFAULT_BLOCKED.add("com.facebook.katana");
        DEFAULT_BLOCKED.add("com.twitter.android");
        DEFAULT_BLOCKED.add("com.snapchat.android");
    }

    @Override
    public void onAccessibilityEvent(AccessibilityEvent event) {
        if (event.getEventType() != AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED) {
            return;
        }

        CharSequence pkgCharSequence = event.getPackageName();
        if (pkgCharSequence == null) return;
        String currentPkg = pkgCharSequence.toString();

        if (currentPkg.equals(getPackageName()) || currentPkg.equals("com.android.settings") || currentPkg.contains("systemui")) {
            return;
        }

        SharedPreferences prefs = getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE);
        boolean isBlockingActive = prefs.getBoolean(KEY_BLOCKING_ENABLED, true);
        if (!isBlockingActive) return;

        Set<String> blockedSet = new HashSet<>(DEFAULT_BLOCKED);
        String savedBlocked = prefs.getString(KEY_BLOCKED_PACKAGES, null);
        if (savedBlocked != null) {
            try {
                JSONArray arr = new JSONArray(savedBlocked);
                blockedSet.clear();
                for (int i = 0; i < arr.length(); i++) {
                    blockedSet.add(arr.getString(i));
                }
            } catch (Exception ignored) {}
        }

        if (blockedSet.contains(currentPkg)) {
            // Intercept and bring Antigravity OS Home Launcher to the foreground with Friction details
            Intent lockIntent = new Intent(this, HomeLauncherActivity.class);
            lockIntent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP | Intent.FLAG_ACTIVITY_SINGLE_TOP);
            lockIntent.putExtra("intercepted_app", currentPkg);
            lockIntent.putExtra("reason", "friction_governor");
            startActivity(lockIntent);
        }
    }

    @Override
    public void onInterrupt() {
        // Accessibility service interrupted
    }
}
