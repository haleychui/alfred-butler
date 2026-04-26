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
                    backgroundManager.start()
                    Task { await healthKit.requestPermissions() }
                }
                .preferredColorScheme(.dark)
        }
        .onChange(of: scenePhase) { _, phase in
            BackgroundManager.shared.isAppActive = (phase == .active)
            if phase == .active {
                Task { await LocationManager.shared.checkContext() }
            }
        }
    }
}
