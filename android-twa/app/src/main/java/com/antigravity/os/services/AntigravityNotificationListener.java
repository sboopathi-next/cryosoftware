package com.antigravity.os.services;

import android.content.Context;
import android.content.SharedPreferences;
import android.service.notification.NotificationListenerService;
import android.service.notification.StatusBarNotification;
import org.json.JSONArray;
import java.util.HashSet;
import java.util.Set;

public class AntigravityNotificationListener extends NotificationListenerService {
    public static final String PREFS_NAME = "antigravity_launcher_prefs";
    public static final String KEY_FOCUS_MODE = "focus_mode_active";
    public static final String KEY_BLOCKED_NOTIFS = "blocked_notif_packages";

    @Override
    public void onNotificationPosted(StatusBarNotification sbn) {
        if (sbn == null) return;
        String packageName = sbn.getPackageName();
        if (packageName == null || packageName.equals(getPackageName())) return;

        SharedPreferences prefs = getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE);
        boolean focusMode = prefs.getBoolean(KEY_FOCUS_MODE, false);

        if (focusMode) {
            Set<String> blockedPkgs = new HashSet<>(AppBlockerAccessibilityService.DEFAULT_BLOCKED);
            String savedBlocked = prefs.getString(KEY_BLOCKED_NOTIFS, null);
            if (savedBlocked != null) {
                try {
                    JSONArray arr = new JSONArray(savedBlocked);
                    blockedPkgs.clear();
                    for (int i = 0; i < arr.length(); i++) {
                        blockedPkgs.add(arr.getString(i));
                    }
                } catch (Exception ignored) {}
            }

            if (blockedPkgs.contains(packageName)) {
                // Cancel/Suppress distracting notification during deep focus
                try {
                    cancelNotification(sbn.getKey());
                } catch (Exception ignored) {}
            }
        }
    }

    @Override
    public void onNotificationRemoved(StatusBarNotification sbn) {
        // Notification removed
    }
}
