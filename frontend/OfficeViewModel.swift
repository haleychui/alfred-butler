import Foundation

@MainActor
class OfficeViewModel: ObservableObject {
    static let shared = OfficeViewModel()

    @Published var eodWrap: EODWrap?
    @Published var roomPulse: RoomPulse?
    @Published var thanksNudge: ThanksNudge?
    @Published var supplies: [OfficeSupply] = []
    @Published var silenceRadar: SilenceRadar?
    @Published var timezoneFatigue: TimezoneFatigue?
    @Published var managerLens: ManagerLens?
    @Published var rooms: [OfficeRoom] = []
    @Published var isLoading = false
    @Published var lastUpdated: Date?
    @Published var errorMessage: String?

    private let session = URLSession.shared

    // MARK: - Refresh all
    func refresh() async {
        isLoading = true
        errorMessage = nil
        await withTaskGroup(of: Void.self) { group in
            group.addTask { await self.fetchEOD() }
            group.addTask { await self.fetchRoomPulse() }
            group.addTask { await self.fetchThanksNudge() }
            group.addTask { await self.fetchSupplies() }
            group.addTask { await self.fetchSilenceRadar() }
            group.addTask { await self.fetchManagerLens() }
        }
        lastUpdated = Date()
        isLoading = false
    }

    // MARK: - Private fetchers
    private func fetch<T: Decodable>(_ path: String) async -> T? {
        let req = AuthManager.shared.authorizedRequest(path: path)
        guard let (data, _) = try? await session.data(for: req) else { return nil }
        return try? JSONDecoder().decode(T.self, from: data)
    }

    private func fetchEOD() async {
        eodWrap = await fetch("/office/eod-wrap")
    }

    private func fetchRoomPulse() async {
        roomPulse = await fetch("/office/room-pulse")
    }

    private func fetchThanksNudge() async {
        thanksNudge = await fetch("/office/thanks-nudge")
    }

    private func fetchSupplies() async {
        supplies = (await fetch("/office/supplies")) ?? []
    }

    private func fetchSilenceRadar() async {
        silenceRadar = await fetch("/office/silence-radar")
    }

    private func fetchManagerLens() async {
        managerLens = await fetch("/office/manager-lens")
    }

    // MARK: - Actions
    func checkinRoom(_ bookingId: Int) async {
        let req = AuthManager.shared.authorizedRequest(
            path: "/office/bookings/\(bookingId)/checkin", method: "POST")
        _ = try? await session.data(for: req)
        await fetchRoomPulse()
    }

    func releaseRoom(_ bookingId: Int) async {
        let req = AuthManager.shared.authorizedRequest(
            path: "/office/bookings/\(bookingId)/release", method: "POST")
        _ = try? await session.data(for: req)
        await fetchRoomPulse()
    }

    // MARK: - Computed helpers
    var lowSupplies: [OfficeSupply] {
        supplies.filter { $0.low }
    }

    var hasAnyAlert: Bool {
        (eodWrap?.totalIssues ?? 0) > 0
        || (roomPulse?.count ?? 0) > 0
        || !(thanksNudge?.pending.isEmpty ?? true)
        || !lowSupplies.isEmpty
        || !(silenceRadar?.silentColleagues.isEmpty ?? true)
    }

    var lastUpdatedText: String {
        guard let d = lastUpdated else { return "尚未載入" }
        let f = DateFormatter()
        f.dateFormat = "HH:mm"
        return "更新 \(f.string(from: d))"
    }
}
