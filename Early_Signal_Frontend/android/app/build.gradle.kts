// android/app/build.gradle.kts

plugins {
    id("com.android.application")
    id("com.google.gms.google-services") // Firebase plugin
    id("kotlin-android")
    id("dev.flutter.flutter-gradle-plugin")
}

android {
    namespace = "com.example.earlysignal_app"
    compileSdk = 35 // ✅ Explicitly set this to latest tested version
    ndkVersion = "27.0.12077973"

    defaultConfig {
        applicationId = "com.example.earlysignal_app"
        minSdk = 23 // ✅ Required by latest Firebase SDK
        targetSdk = 35
        versionCode = 1
        versionName = "1.0"
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_11
        targetCompatibility = JavaVersion.VERSION_11
    }

    kotlinOptions {
        jvmTarget = JavaVersion.VERSION_11.toString()
    }

    buildTypes {
        release {
            signingConfig = signingConfigs.getByName("debug")
        }
    }
}

flutter {
    source = "../.."
}