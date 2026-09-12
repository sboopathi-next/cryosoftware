package com.antigravity.os.bridge;

import android.accessibilityservice.AccessibilityServiceInfo;
import android.app.AppOpsManager;
import android.app.usage.UsageStats;
import android.app.usage.UsageStatsManager;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.content.SharedPreferences;
import android.content.pm.ApplicationInfo;
import android.content.pm.PackageManager;
import android.content.pm.ResolveInfo;
import android.net.Uri;
import android.os.BatteryManager;
import android.os.Build;
import android.os.Process;
import android.os.VibrationEffect;
import android.os.Vibrator;
import android.provider.Settings;
import android.view.accessibility.AccessibilityManager;
import android.webkit.JavascriptInterface;
import android.webkit.WebView;
import androidx.core.app.NotificationManagerCompat;
import com.antigravity.os.services.AppBlockerAccessibilityService;
import com.antigravity.os.services.AntigravityNotificationListener;
import com.antigravity.os.utils.NotificationHelper;
import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.Calendar;
import java.util.Collections;
import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

public class WebBridgeInterface {
    private final Context context;
    private final WebView webView;
    private final SharedPreferences prefs;

    public WebBridgeInterface(Context context, WebView webView) {
        this.context = context;
        this.webView = webView;
        this.prefs = context.getSharedPreferences(AppBlockerAccessibilityService.PREFS_NAME, Context.MODE_PRIVATE);
    }

    // -------------------------------------------------------------
    // App Drawer & Launching
    // -------------------------------------------------------------

    @JavascriptInterface
    public String getInstalledApps() {
        JSONArray appsList = new JSONArray();
        PackageManager pm = context.getPackageManager();
        Intent mainIntent = new Intent(Intent.ACTION_MAIN, null);
        mainIntent.addCategory(Intent.CATEGORY_LAUNCHER);

        List<ResolveInfo> resolveInfos = pm.queryIntentActivities(mainIntent, 0);
        List<JSONObject> appObjects = new ArrayList<>();

        for (ResolveInfo info : resolveInfos) {
            try {
                String pkg = info.activityInfo.packageName;
                if (pkg.equals(context.getPackageName())) continue;

                String label = info.loadLabel(pm).toString();
                boolean isSystem = (info.activityInfo.applicationInfo.flags & ApplicationInfo.FLAG_SYSTEM) != 0;

                JSONObject obj = new JSONObject();
                obj.put("name", label);
                obj.put("packageName", pkg);
                obj.put("isSystem", isSystem);
                appObjects.add(obj);
            } catch (Exception ignored) {}
        }

        // Sort alphabetically by app name
        Collections.sort(appObjects, new Comparator<JSONObject>() {
            @Override
            public int compare(JSONObject a, JSONObject b) {
                try {
                    return a.getString("name").compareToIgnoreCase(b.getString("name"));
                } catch (Exception e) {
                    return 0;
                }
            }
        });

        for (JSONObject obj : appObjects) {
            appsList.put(obj);
        }

        return appsList.toString();
    }

    @JavascriptInterface
    public boolean launchApp(String packageName) {
        try {
            PackageManager pm = context.getPackageManager();
            Intent launchIntent = pm.getLaunchIntentForPackage(packageName);
            if (launchIntent != null) {
                launchIntent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                context.startActivity(launchIntent);
                return true;
            }
        } catch (Exception e) {
            e.printStackTrace();
        }
        return false;
    }

    // -------------------------------------------------------------
    // Permission Checks & System Settings Redirects
    // -------------------------------------------------------------

    @JavascriptInterface
    public boolean isDefaultLauncher() {
        Intent intent = new Intent(Intent.ACTION_MAIN);
        intent.addCategory(Intent.CATEGORY_HOME);
        ResolveInfo resolveInfo = context.getPackageManager().resolveActivity(intent, PackageManager.MATCH_DEFAULT_ONLY);
        if (resolveInfo != null && resolveInfo.activityInfo != null) {
            return context.getPackageName().equals(resolveInfo.activityInfo.packageName);
        }
        return false;
    }

    @JavascriptInterface
    public void openDefaultLauncherSettings() {
        try {
            Intent intent;
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.N) {
                intent = new Intent(Settings.ACTION_MANAGE_DEFAULT_APPS_SETTINGS);
            } else {
                intent = new Intent(Settings.ACTION_HOME_SETTINGS);
            }
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            context.startActivity(intent);
        } catch (Exception e) {
            // Fallback to app details
            openAppSettings();
        }
    }

    @JavascriptInterface
    public boolean hasUsageAccess() {
        AppOpsManager appOps = (AppOpsManager) context.getSystemService(Context.APP_OPS_SERVICE);
        if (appOps == null) return false;
        int mode = appOps.checkOpNoThrow(AppOpsManager.OPSTR_GET_USAGE_STATS, Process.myUid(), context.getPackageName());
        return mode == AppOpsManager.MODE_ALLOWED;
    }

    @JavascriptInterface
    public void openUsageSettings() {
        Intent intent = new Intent(Settings.ACTION_USAGE_ACCESS_SETTINGS);
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        context.startActivity(intent);
    }

    @JavascriptInterface
    public boolean hasOverlayPermission() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            return Settings.canDrawOverlays(context);
        }
        return true;
    }

    @JavascriptInterface
    public void openOverlaySettings() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            Intent intent = new Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                    Uri.parse("package:" + context.getPackageName()));
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            context.startActivity(intent);
        }
    }

    @JavascriptInterface
    public boolean hasAccessibilityPermission() {
        AccessibilityManager am = (AccessibilityManager) context.getSystemService(Context.ACCESSIBILITY_SERVICE);
        if (am == null) return false;
        List<AccessibilityServiceInfo> enabledServices = am.getEnabledAccessibilityServiceList(AccessibilityServiceInfo.FEEDBACK_ALL_MASK);
        for (AccessibilityServiceInfo service : enabledServices) {
            if (service.getId().contains(context.getPackageName())) {
                return true;
            }
        }
        return false;
    }

    @JavascriptInterface
    public void openAccessibilitySettings() {
        Intent intent = new Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS);
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        context.startActivity(intent);
    }

    @JavascriptInterface
    public boolean hasNotificationListenerPermission() {
        Set<String> packageNames = NotificationManagerCompat.getEnabledListenerPackages(context);
        return packageNames.contains(context.getPackageName());
    }

    @JavascriptInterface
    public void openNotificationListenerSettings() {
        Intent intent = new Intent(Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS);
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        context.startActivity(intent);
    }

    @JavascriptInterface
    public void openAppSettings() {
        Intent intent = new Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS);
        intent.setData(Uri.parse("package:" + context.getPackageName()));
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        context.startActivity(intent);
    }

    @JavascriptInterface
    public String getPermissionStatus() {
        JSONObject status = new JSONObject();
        try {
            status.put("isDefaultLauncher", isDefaultLauncher());
            status.put("hasUsageAccess", hasUsageAccess());
            status.put("hasOverlayPermission", hasOverlayPermission());
            status.put("hasAccessibilityPermission", hasAccessibilityPermission());
            status.put("hasNotificationListenerPermission", hasNotificationListenerPermission());
            status.put("isNativeAndroid", true);
        } catch (Exception ignored) {}
        return status.toString();
    }

    // -------------------------------------------------------------
    // App Blocker & Focus Management
    // -------------------------------------------------------------

    @JavascriptInterface
    public String getBlockedApps() {
        String saved = prefs.getString(AppBlockerAccessibilityService.KEY_BLOCKED_PACKAGES, null);
        if (saved != null) return saved;

        JSONArray arr = new JSONArray();
        for (String pkg : AppBlockerAccessibilityService.DEFAULT_BLOCKED) {
            arr.put(pkg);
        }
        return arr.toString();
    }

    @JavascriptInterface
    public boolean setBlockedApps(String jsonArrayString) {
        try {
            new JSONArray(jsonArrayString); // Validate JSON format
            prefs.edit().putString(AppBlockerAccessibilityService.KEY_BLOCKED_PACKAGES, jsonArrayString).apply();
            return true;
        } catch (Exception e) {
            return false;
        }
    }

    @JavascriptInterface
    public boolean isBlockingEnabled() {
        return prefs.getBoolean(AppBlockerAccessibilityService.KEY_BLOCKING_ENABLED, true);
    }

    @JavascriptInterface
    public void setBlockingEnabled(boolean enabled) {
        prefs.edit().putBoolean(AppBlockerAccessibilityService.KEY_BLOCKING_ENABLED, enabled).apply();
    }

    @JavascriptInterface
    public boolean isFocusMode() {
        return prefs.getBoolean(AntigravityNotificationListener.KEY_FOCUS_MODE, false);
    }

    @JavascriptInterface
    public void setFocusMode(boolean enabled) {
        prefs.edit().putBoolean(AntigravityNotificationListener.KEY_FOCUS_MODE, enabled).apply();
    }

    // -------------------------------------------------------------
    // Screen Time & Usage Stats
    // -------------------------------------------------------------

    @JavascriptInterface
    public String getAppUsageStats() {
        JSONArray statsArray = new JSONArray();
        if (!hasUsageAccess()) return statsArray.toString();

        try {
            UsageStatsManager usm = (UsageStatsManager) context.getSystemService(Context.USAGE_STATS_SERVICE);
            if (usm == null) return statsArray.toString();

            Calendar calendar = Calendar.getInstance();
            calendar.set(Calendar.HOUR_OF_DAY, 0);
            calendar.set(Calendar.MINUTE, 0);
            calendar.set(Calendar.SECOND, 0);
            long startOfDay = calendar.getTimeInMillis();
            long now = System.currentTimeMillis();

            List<UsageStats> usageStatsList = usm.queryUsageStats(UsageStatsManager.INTERVAL_DAILY, startOfDay, now);
            PackageManager pm = context.getPackageManager();

            Map<String, Long> aggregatedMap = new HashMap<>();
            for (UsageStats u : usageStatsList) {
                if (u.getTotalTimeInForeground() > 60000) { // More than 1 min
                    long existing = aggregatedMap.containsKey(u.getPackageName()) ? aggregatedMap.get(u.getPackageName()) : 0;
                    aggregatedMap.put(u.getPackageName(), existing + u.getTotalTimeInForeground());
                }
            }

            for (Map.Entry<String, Long> entry : aggregatedMap.entrySet()) {
                String pkg = entry.getKey();
                long totalMs = entry.getValue();
                long minutes = totalMs / (1000 * 60);

                String appName = pkg;
                try {
                    ApplicationInfo ai = pm.getApplicationInfo(pkg, 0);
                    appName = pm.getApplicationLabel(ai).toString();
                } catch (Exception ignored) {}

                JSONObject obj = new JSONObject();
                obj.put("packageName", pkg);
                obj.put("name", appName);
                obj.put("minutes", minutes);
                statsArray.put(obj);
            }
        } catch (Exception e) {
            e.printStackTrace();
        }

        return statsArray.toString();
    }

    // -------------------------------------------------------------
    // Notifications & System Alerts
    // -------------------------------------------------------------

    @JavascriptInterface
    public void sendSystemNotification(String title, String message, int id) {
        NotificationHelper.sendNotification(context, title, message, id);
    }

    // -------------------------------------------------------------
    // Haptics & Device Hardware
    // -------------------------------------------------------------

    @JavascriptInterface
    public void triggerHaptic(int durationMs) {
        try {
            Vibrator vibrator = (Vibrator) context.getSystemService(Context.VIBRATOR_SERVICE);
            if (vibrator != null && vibrator.hasVibrator()) {
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                    vibrator.vibrate(VibrationEffect.createOneShot(durationMs, VibrationEffect.DEFAULT_AMPLITUDE));
                } else {
                    vibrator.vibrate(durationMs);
                }
            }
        } catch (Exception ignored) {}
    }

    @JavascriptInterface
    public int getBatteryLevel() {
        try {
            IntentFilter ifilter = new IntentFilter(Intent.ACTION_BATTERY_CHANGED);
            Intent batteryStatus = context.registerReceiver(null, ifilter);
            if (batteryStatus != null) {
                int level = batteryStatus.getIntExtra(BatteryManager.EXTRA_LEVEL, -1);
                int scale = batteryStatus.getIntExtra(BatteryManager.EXTRA_SCALE, -1);
                return (int) ((level / (float) scale) * 100);
            }
        } catch (Exception ignored) {}
        return 100;
    }
}
