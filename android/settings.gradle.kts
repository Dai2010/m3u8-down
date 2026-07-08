pluginManagement {
    repositories {
        val useOfficialRepos = providers.environmentVariable("CI_MAVEN_REPOS").orNull == "official"
        if (useOfficialRepos) {
            google()
            mavenCentral()
            gradlePluginPortal()
            maven("https://maven.aliyun.com/repository/public")
        } else {
            maven("https://maven.aliyun.com/repository/google")
            maven("https://maven.aliyun.com/repository/gradle-plugin")
            maven("https://maven.aliyun.com/repository/public")
            google()
            mavenCentral()
            gradlePluginPortal()
        }
    }
}

dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        val useOfficialRepos = providers.environmentVariable("CI_MAVEN_REPOS").orNull == "official"
        if (useOfficialRepos) {
            google()
            mavenCentral()
            maven("https://maven.aliyun.com/repository/public")
        } else {
            maven("https://maven.aliyun.com/repository/google")
            maven("https://maven.aliyun.com/repository/public")
            maven("https://maven.aliyun.com/repository/central")
            google()
            mavenCentral()
        }
    }
}

rootProject.name = "M3U8DownloaderAndroid"
include(":app")
