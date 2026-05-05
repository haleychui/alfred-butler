import Foundation
import UserNotifications

// MARK: - Background Manager
// 提醒輪詢（60 秒）+ 家人警報（30 秒）+ 拜訪前提醒（30 分）+ 健康監控 + 用藥提醒

@MainActor
class BackgroundManager: ObservableObject {
    static let shared = BackgroundManager()

    @Published var familyMembers: [FamilyMember] = []
    var isAppActive: Bool = false

    private var reminderTask: Task<Void, Never>?
    private var alertTask: Task<Void, Never>?
    private var visitTask: Task<Void, Never>?
    private var familyTask: Task<Void, Never>?
    private var medicationTask: Task<Void, Never>?
    private var healthStatusTask: Task<Void, Never>?
    private var acknowledgedAlerts: Set<Int> = []
    private var medicationNotifiedToday: Set<String> = []

    func start() {
        requestNotificationPermission()
        startReminderPolling()
        startAlertPolling()
        startVisitPolling()
        startFamilyPolling()
        startMedicationPolling()
        startHealthStatusPolling()
    }

    func stop() {
        reminderTask?.cancel()
        alertTask?.cancel()
        visitTask?.cancel()
        familyTask?.cancel()
        medicationTask?.cancel()
        healthStatusTask?.cancel()
    }

    // MARK: - 提醒輪詢（60 秒）
    private func startReminderPolling() {
        reminderTask = Task {
            while !Task.isCancelled {
                await pollReminders()
                try? await Task.sleep(nanoseconds: 60_000_000_000)
            }
        }
    }

    private func pollReminders() async {
        do {
            let reminders = try await AlfredAPI.shared.pendingReminders()
            for reminder in reminders {
                scheduleLocalNotification(
                    id: "reminder-\(reminder.id)",
                    title: "阿福提醒",
                    body: reminder.title,
                    triggerAt: reminder.triggerAt
                )
            }
        } catch {
            print("[BackgroundManager] reminder poll error:", error)
        }
    }

    // MARK: - 家人警報（30 秒）
    private func startAlertPolling() {
        alertTask = Task {
            while !Task.isCancelled {
                await pollFamilyAlerts()
                try? await Task.sleep(nanoseconds: 30_000_000_000)
            }
        }
    }

    private func pollFamilyAlerts() async {
        do {
            let alerts = try await AlfredAPI.shared.familyAlerts()
            for alert in alerts {
                guard !acknowledgedAlerts.contains(alert.id) else { continue }
                acknowledgedAlerts.insert(alert.id)

                if isAppActive {
                    // App 在前景：阿福主畫面直接開口說
                    await AlfredViewModel.shared.speakAloud(alert.message)
                } else {
                    // 背景：推播通知
                    fireImmediateNotification(
                        id: "alert-\(alert.id)",
                        title: alert.severity == "critical" ? "🚨 \(alert.name)" : "⚠️ \(alert.name)",
                        body: alert.message
                    )
                }
                try? await AlfredAPI.shared.ackAlert(id: alert.id)
            }
        } catch {
            print("[BackgroundManager] alert poll error:", error)
        }
    }

    // MARK: - 家人位置（60 秒）
    private func startFamilyPolling() {
        familyTask = Task {
            while !Task.isCancelled {
                await pollFamilyMembers()
                try? await Task.sleep(nanoseconds: 60_000_000_000)
            }
        }
    }

    private func pollFamilyMembers() async {
        do {
            let members = try await AlfredAPI.shared.familyMembers()
            familyMembers = members
        } catch {
            print("[BackgroundManager] family members poll error:", error)
        }
    }

    // MARK: - 拜訪前提醒（30 分）
    private func startVisitPolling() {
        visitTask = Task {
            while !Task.isCancelled {
                await pollVisitPrep()
                try? await Task.sleep(nanoseconds: 1_800_000_000_000)
            }
        }
    }

    private func pollVisitPrep() async {
        do {
            let visits = try await AlfredAPI.shared.visitPrep()
            for visit in visits {
                fireImmediateNotification(
                    id: "visit-\(visit.eventTitle)-\(visit.minutesAway)",
                    title: "拜訪提醒 · \(visit.person)",
                    body: visit.message
                )
            }
        } catch {
            print("[BackgroundManager] visit poll error:", error)
        }
    }

    // MARK: - 用藥提醒（每小時檢查一次）
    private func startMedicationPolling() {
        medicationTask = Task {
            while !Task.isCancelled {
                await checkMedicationReminders()
                try? await Task.sleep(nanoseconds: 3_600_000_000_000)
            }
        }
    }

    private func checkMedicationReminders() async {
        do {
            let meds = try await AlfredAPI.shared.getMedications()
            guard !meds.isEmpty else { return }

            let hour = Calendar.current.component(.hour, from: Date())
            let todayKey = Calendar.current.startOfDay(for: Date()).description

            for med in meds {
                guard let timeOfDay = med.timeOfDay else { continue }
                let shouldRemind: Bool
                switch timeOfDay {
                case "morning":  shouldRemind = hour == 8
                case "noon":     shouldRemind = hour == 12
                case "evening":  shouldRemind = hour == 18
                case "night":    shouldRemind = hour == 21
                default:         shouldRemind = false
                }

                let key = "\(todayKey)-\(med.id)"
                guard shouldRemind && !medicationNotifiedToday.contains(key) else { continue }
                medicationNotifiedToday.insert(key)

                let msg = "主人，\(med.name)\(med.dosage.map { " \($0)" } ?? "")該吃了。"
                if isAppActive {
                    await AlfredViewModel.shared.speakAloud(msg)
                } else {
                    fireImmediateNotification(id: "med-\(key)", title: "用藥提醒", body: msg)
                }
            }
        } catch {
            print("[BackgroundManager] medication check error:", error)
        }
    }

    // MARK: - 健康狀態輪詢（60 秒，補強 HealthKit observer 的盲點）
    private func startHealthStatusPolling() {
        healthStatusTask = Task {
            // 延遲 10 秒再開始，讓 HealthKit observer 先跑
            try? await Task.sleep(nanoseconds: 10_000_000_000)
            while !Task.isCancelled {
                await checkHealthStatus()
                try? await Task.sleep(nanoseconds: 60_000_000_000)
            }
        }
    }

    private func checkHealthStatus() async {
        do {
            let status = try await AlfredAPI.shared.getHealthStatus()
            // 若後端狀態已升到 escalate_family，iOS 要確認是否需要打 119
            if status.state == "escalate_family" || status.state == "escalate_119" {
                if isAppActive {
                    let msg = "主人，我已通知您的緊急聯絡人。如需要我幫您撥打 119，請說「打 119」。"
                    await AlfredViewModel.shared.speakAloud(msg)
                } else {
                    fireImmediateNotification(
                        id: "health-escalate-\(Date().timeIntervalSince1970)",
                        title: "健康警報",
                        body: "緊急聯絡人已通知。如需要請說「打 119」。"
                    )
                }
            }
        } catch {
            // 靜默失敗，不打擾主人
        }
    }

    // MARK: - 通知工具
    private func requestNotificationPermission() {
        UNUserNotificationCenter.current().requestAuthorization(options: [.alert, .sound, .badge]) { _, _ in }
    }

    private func scheduleLocalNotification(id: String, title: String, body: String, triggerAt: String) {
        let formatter = ISO8601DateFormatter()
        guard let date = formatter.date(from: triggerAt), date > Date() else { return }
        let content = UNMutableNotificationContent()
        content.title = title
        content.body = body
        content.sound = .default
        let comps = Calendar.current.dateComponents([.year, .month, .day, .hour, .minute], from: date)
        let trigger = UNCalendarNotificationTrigger(dateMatching: comps, repeats: false)
        let request = UNNotificationRequest(identifier: id, content: content, trigger: trigger)
        UNUserNotificationCenter.current().add(request) { err in
            if let err { print("[BackgroundManager] schedule error:", err) }
        }
    }

    private func fireImmediateNotification(id: String, title: String, body: String) {
        let content = UNMutableNotificationContent()
        content.title = title
        content.body = body
        content.sound = .default
        let trigger = UNTimeIntervalNotificationTrigger(timeInterval: 1, repeats: false)
        let request = UNNotificationRequest(identifier: id, content: content, trigger: trigger)
        UNUserNotificationCenter.current().add(request) { err in
            if let err { print("[BackgroundManager] fire error:", err) }
        }
    }
}
