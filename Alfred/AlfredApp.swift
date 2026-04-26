import SwiftUI

@main
struct AlfredApp: App {
    @StateObject private var locationManager = LocationManager.shared
    @StateObject private var backgroundManager = BackgroundManager.shared
    @StateObject private var healthKit = HealthKitManager.shared
    @Environment(\.scenePhase) private var scenePhase

    var body: some Scene {
        WindowGroup {
            AlfredView()
                .onAppear {
                    // UI test mode：launch arg --prompt "xxx" → 自動 set onboarded + sendMessage
                    if let idx = CommandLine.arguments.firstIndex(of: "--prompt"),
                       idx + 1 < CommandLine.arguments.count {
                        let prompt = CommandLine.arguments[idx + 1]
                        UserDefaults.standard.set(true, forKey: "alfred_onboarded")
                        NSLog("[Alfred] UI test mode prompt: %@", prompt)
                        Task {
                            try? await Task.sleep(nanoseconds: 2_000_000_000)
                            await AlfredViewModel.shared.sendMessage(prompt)
                        }
                    }

                    // onboarding 完成前不啟動任何背景任務，避免搶話
                    if UserDefaults.standard.bool(forKey: "alfred_onboarded") {
                        backgroundManager.start()
                        Task { await healthKit.requestPermissions() }
                    }
                }
                .preferredColorScheme(.dark)
        }
        .onChange(of: scenePhase) { _, phase in
            BackgroundManager.shared.isAppActive = (phase == .active)
            if phase == .active && UserDefaults.standard.bool(forKey: "alfred_onboarded") {
                Task { await LocationManager.shared.checkContext() }
            }
        }
    }
}
