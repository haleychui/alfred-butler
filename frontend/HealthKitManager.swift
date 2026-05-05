import Foundation
import HealthKit

// MARK: - HealthKit Manager
// 申請權限、即時心率 observer（背景推送）、SpO2、跌倒偵測、運動記錄同步

@MainActor
class HealthKitManager: ObservableObject {
    static let shared = HealthKitManager()

    private let store = HKHealthStore()

    @Published var isAvailable: Bool = HKHealthStore.isHealthDataAvailable()
    @Published var isAuthorized: Bool = false
    @Published var latestHeartRate: Int? = nil
    @Published var latestSpo2: Double? = nil

    private var hrObserverQuery: HKObserverQuery?
    private var spo2ObserverQuery: HKObserverQuery?

    private let readTypes: Set<HKObjectType> = {
        var types: Set<HKObjectType> = []
        let quantityIDs: [HKQuantityTypeIdentifier] = [
            .heartRate,
            .oxygenSaturation,
            .stepCount,
            .distanceWalkingRunning,
            .distanceCycling,
            .activeEnergyBurned,
            .restingHeartRate,
            .vo2Max
        ]
        for id in quantityIDs {
            if let t = HKQuantityType.quantityType(forIdentifier: id) { types.insert(t) }
        }
        // 跌倒事件（watchOS Fall Detection）
        if let fallType = HKObjectType.categoryType(forIdentifier: .appleStandHour) {
            types.insert(fallType)
        }
        if let workout = HKObjectType.workoutType() as? HKObjectType { types.insert(workout) }
        return types
    }()

    // MARK: - Request Permissions + Start Observers
    func requestPermissions() async {
        guard isAvailable else { return }
        do {
            try await store.requestAuthorization(toShare: [], read: readTypes)
            isAuthorized = true
            startHeartRateObserver()
            startSpo2Observer()
            await syncRecentWorkouts()
        } catch {
            print("[HealthKit] permission error:", error)
        }
    }

    // MARK: - Real-time Heart Rate Observer (Background Delivery)
    func startHeartRateObserver() {
        guard let hrType = HKQuantityType.quantityType(forIdentifier: .heartRate) else { return }

        // 啟用背景推送：App 背景時 HealthKit 仍會喚醒 App
        store.enableBackgroundDelivery(for: hrType, frequency: .immediate) { success, error in
            if !success { print("[HealthKit] HR background delivery failed:", error ?? "unknown") }
        }

        hrObserverQuery = HKObserverQuery(sampleType: hrType, predicate: nil) { [weak self] _, completionHandler, error in
            guard error == nil else {
                completionHandler()
                return
            }
            Task { [weak self] in
                await self?.fetchAndPushLatestHR()
                completionHandler()
            }
        }
        if let q = hrObserverQuery { store.execute(q) }
    }

    // MARK: - SpO2 Observer
    func startSpo2Observer() {
        guard let spo2Type = HKQuantityType.quantityType(forIdentifier: .oxygenSaturation) else { return }

        store.enableBackgroundDelivery(for: spo2Type, frequency: .hourly) { success, error in
            if !success { print("[HealthKit] SpO2 background delivery failed:", error ?? "unknown") }
        }

        spo2ObserverQuery = HKObserverQuery(sampleType: spo2Type, predicate: nil) { [weak self] _, completionHandler, error in
            guard error == nil else {
                completionHandler()
                return
            }
            Task { [weak self] in
                await self?.fetchAndPushLatestSpo2()
                completionHandler()
            }
        }
        if let q = spo2ObserverQuery { store.execute(q) }
    }

    // MARK: - Fetch latest HR and push to backend
    func fetchAndPushLatestHR() async {
        guard let hrType = HKQuantityType.quantityType(forIdentifier: .heartRate) else { return }

        let hr: Int? = await withCheckedContinuation { cont in
            let query = HKSampleQuery(
                sampleType: hrType, predicate: nil, limit: 1,
                sortDescriptors: [NSSortDescriptor(key: HKSampleSortIdentifierStartDate, ascending: false)]
            ) { _, samples, _ in
                let bpm = (samples?.first as? HKQuantitySample)
                    .map { Int($0.quantity.doubleValue(for: HKUnit(from: "count/min"))) }
                cont.resume(returning: bpm)
            }
            store.execute(query)
        }

        guard let hr else { return }
        await MainActor.run { self.latestHeartRate = hr }

        // 取得目前活動類型（是否在運動）
        let activity = await currentActivity()

        // 推送到後端，收到 action 後處理
        await pushVitals(heartRate: hr, spo2: latestSpo2, activity: activity)
    }

    // MARK: - Fetch latest SpO2 and push
    func fetchAndPushLatestSpo2() async {
        guard let spo2Type = HKQuantityType.quantityType(forIdentifier: .oxygenSaturation) else { return }

        let spo2: Double? = await withCheckedContinuation { cont in
            let query = HKSampleQuery(
                sampleType: spo2Type, predicate: nil, limit: 1,
                sortDescriptors: [NSSortDescriptor(key: HKSampleSortIdentifierStartDate, ascending: false)]
            ) { _, samples, _ in
                let val = (samples?.first as? HKQuantitySample)
                    .map { $0.quantity.doubleValue(for: HKUnit.percent()) * 100 }
                cont.resume(returning: val)
            }
            store.execute(query)
        }

        guard let spo2 else { return }
        await MainActor.run { self.latestSpo2 = spo2 }
        await pushVitals(heartRate: latestHeartRate, spo2: spo2, activity: "unknown")
    }

    // MARK: - Push vitals to backend and handle response
    func pushVitals(heartRate: Int?, spo2: Double?, activity: String, wristOn: Bool = true) async {
        do {
            let response = try await AlfredAPI.shared.pushHealthVitals(
                heartRate: heartRate,
                spo2: spo2,
                wristOn: wristOn,
                activity: activity
            )
            await handleHealthAction(response)
        } catch {
            print("[HealthKit] push vitals error:", error)
        }
    }

    // MARK: - Handle backend health action
    @MainActor
    func handleHealthAction(_ response: HealthVitalsResponse) async {
        switch response.action {
        case "checkin":
            // 阿福主動說話確認主人狀況
            if let msg = response.message {
                await AlfredViewModel.shared.speakAloud(msg)
                // 開始 30 秒計時，若主人說話就算 ack
                AlfredViewModel.shared.pendingHealthCheckin = true
            }
        case "emergency_call":
            // 沒有回應，家人已通知，詢問主人是否要打 119
            if let msg = response.message {
                await AlfredViewModel.shared.speakAloud(msg)
            }
            if response.call119 == true {
                triggerEmergencyCall()
            }
        default:
            break
        }
    }

    // MARK: - 119 Emergency Call
    func triggerEmergencyCall() {
        guard let url = URL(string: "tel://119") else { return }
        DispatchQueue.main.async {
            UIApplication.shared.open(url)
        }
    }

    // MARK: - Fall Detection (from Watch, triggered by iOS)
    func reportFallDetected(lat: Double? = nil, lng: Double? = nil) async {
        do {
            let response = try await AlfredAPI.shared.reportFallDetected(lat: lat, lng: lng)
            await handleHealthAction(response)
        } catch {
            print("[HealthKit] fall report error:", error)
        }
    }

    // MARK: - Detect current workout activity
    func currentActivity() async -> String {
        guard let workoutType = HKObjectType.workoutType() as? HKWorkoutType else { return "unknown" }
        let recent = await withCheckedContinuation { (cont: CheckedContinuation<HKWorkout?, Never>) in
            let predicate = HKQuery.predicateForSamples(
                withStart: Date().addingTimeInterval(-3600), end: Date())
            let query = HKSampleQuery(
                sampleType: workoutType, predicate: predicate, limit: 1,
                sortDescriptors: [NSSortDescriptor(key: HKSampleSortIdentifierStartDate, ascending: false)]
            ) { _, samples, _ in
                cont.resume(returning: samples?.first as? HKWorkout)
            }
            store.execute(query)
        }
        guard let w = recent, w.endDate > Date().addingTimeInterval(-600) else { return "still" }
        switch w.workoutActivityType {
        case .running: return "running"
        case .cycling: return "cycling"
        default: return "workout"
        }
    }

    // MARK: - Sync recent 7-day workouts to backend
    func syncRecentWorkouts() async {
        guard isAvailable else { return }
        let anchor = Date().addingTimeInterval(-7 * 24 * 3600)
        let predicate = HKQuery.predicateForSamples(withStart: anchor, end: Date())

        await withCheckedContinuation { (continuation: CheckedContinuation<Void, Never>) in
            let query = HKSampleQuery(
                sampleType: HKObjectType.workoutType(),
                predicate: predicate,
                limit: 50,
                sortDescriptors: [NSSortDescriptor(key: HKSampleSortIdentifierStartDate, ascending: false)]
            ) { _, samples, error in
                guard let workouts = samples as? [HKWorkout], error == nil else {
                    continuation.resume()
                    return
                }
                Task {
                    var payload: [[String: Any]] = []
                    for w in workouts {
                        var item: [String: Any] = [
                            "workout_type": w.workoutActivityType.name,
                            "start_time": ISO8601DateFormatter().string(from: w.startDate),
                            "end_time": ISO8601DateFormatter().string(from: w.endDate),
                            "duration_min": w.duration / 60.0,
                            "calories": w.totalEnergyBurned?.doubleValue(for: .kilocalorie()) ?? 0
                        ]
                        if let dist = w.totalDistance?.doubleValue(for: .meter()) {
                            item["distance_km"] = dist / 1000.0
                        }
                        payload.append(item)
                    }
                    if !payload.isEmpty {
                        try? await AlfredAPI.shared.syncWorkouts(payload)
                    }
                    continuation.resume()
                }
            }
            store.execute(query)
        }
    }

    // MARK: - Fetch today's step count
    func fetchTodaySteps() async -> Int {
        guard isAvailable, let type = HKQuantityType.quantityType(forIdentifier: .stepCount) else { return 0 }
        let start = Calendar.current.startOfDay(for: Date())
        let predicate = HKQuery.predicateForSamples(withStart: start, end: Date())
        return await withCheckedContinuation { continuation in
            let query = HKStatisticsQuery(quantityType: type, quantitySamplePredicate: predicate, options: .cumulativeSum) { _, result, _ in
                let steps = Int(result?.sumQuantity()?.doubleValue(for: .count()) ?? 0)
                continuation.resume(returning: steps)
            }
            store.execute(query)
        }
    }

    // MARK: - Fetch latest heart rate (one-shot, for on-demand query)
    func fetchLatestHeartRate() async -> Int? {
        guard isAvailable, let type = HKQuantityType.quantityType(forIdentifier: .heartRate) else { return nil }
        return await withCheckedContinuation { continuation in
            let query = HKSampleQuery(
                sampleType: type, predicate: nil, limit: 1,
                sortDescriptors: [NSSortDescriptor(key: HKSampleSortIdentifierStartDate, ascending: false)]
            ) { _, samples, _ in
                let bpm = (samples?.first as? HKQuantitySample)
                    .map { Int($0.quantity.doubleValue(for: HKUnit(from: "count/min"))) }
                continuation.resume(returning: bpm)
            }
            store.execute(query)
        }
    }
}

// MARK: - HKWorkoutActivityType name helper
extension HKWorkoutActivityType {
    var name: String {
        switch self {
        case .running:          return "running"
        case .cycling:          return "cycling"
        case .swimming:         return "swimming"
        case .yoga:             return "yoga"
        case .walking:          return "walking"
        case .functionalStrengthTraining, .traditionalStrengthTraining: return "gym"
        case .highIntensityIntervalTraining: return "hiit"
        case .dance:            return "dance"
        case .tennis:           return "tennis"
        case .basketball:       return "basketball"
        case .soccer:           return "soccer"
        default:                return "workout"
        }
    }
}
