import Foundation

// MARK: - EOD Wrap
struct EODWrap: Decodable {
    let pendingTodos: Int
    let openPromises: Int
    let pendingThanks: Int
    let lowSupplies: Int
    let openSubCommits: Int

    var totalIssues: Int {
        pendingTodos + openPromises + pendingThanks + lowSupplies + openSubCommits
    }

    enum CodingKeys: String, CodingKey {
        case pendingTodos    = "pending_todos"
        case openPromises    = "open_promises"
        case pendingThanks   = "pending_thanks"
        case lowSupplies     = "low_supplies"
        case openSubCommits  = "open_sub_commits"
    }
}

// MARK: - Room Pulse
struct RoomPulse: Decodable {
    let abandonedBookings: [AbandonedBooking]
    let count: Int
    enum CodingKeys: String, CodingKey {
        case abandonedBookings = "abandoned_bookings"
        case count
    }
}

struct AbandonedBooking: Decodable, Identifiable {
    let bookingId: Int
    let title: String
    let startTime: String
    let room: String?
    var id: Int { bookingId }
    enum CodingKeys: String, CodingKey {
        case bookingId = "booking_id"
        case title
        case startTime = "start_time"
        case room
    }
}

// MARK: - Thanks
struct ThanksNudge: Decodable {
    let pending: [ThanksItem]
}

struct ThanksItem: Decodable, Identifiable {
    let id: Int
    let person: String
    let reason: String
    let date: String
}

// MARK: - Supplies
struct OfficeSupply: Decodable, Identifiable {
    let id: Int
    let item: String
    let category: String
    let quantity: Double
    let threshold: Double
    let unit: String
    let lastOrdered: String?
    let low: Bool
    enum CodingKeys: String, CodingKey {
        case id, item, category, quantity, threshold, unit, low
        case lastOrdered = "last_ordered"
    }
}

// MARK: - Silence Radar
struct SilenceRadar: Decodable {
    let silentColleagues: [SilentColleague]
    let thresholdDays: Int
    enum CodingKeys: String, CodingKey {
        case silentColleagues = "silent_colleagues"
        case thresholdDays    = "threshold_days"
    }
}

struct SilentColleague: Decodable, Identifiable {
    let name: String
    let role: String?
    let dept: String?
    let daysSince: Int?
    var id: String { name }
    enum CodingKeys: String, CodingKey {
        case name, role, dept
        case daysSince = "days_since"
    }
}

// MARK: - Timezone Fatigue
struct TimezoneFatigue: Decodable {
    let lateNightEvents: [LateNightEvent]
    let total30days: Int
    let alert: Bool
    enum CodingKeys: String, CodingKey {
        case lateNightEvents = "late_night_events"
        case total30days     = "total_30days"
        case alert
    }
}

struct LateNightEvent: Decodable, Identifiable {
    let title: String
    let date: String
    let time: String
    var id: String { "\(date)-\(time)-\(title)" }
}

// MARK: - Rooms
struct OfficeRoom: Decodable, Identifiable {
    let id: Int
    let name: String
    let capacity: Int
    let floor: String?
    let notes: String?
}

// MARK: - Manager Lens
struct ManagerLens: Decodable {
    let subordinates: [SubordinateSummary]
    let openSubCommits: [SubCommit]
    let openPromises: [PromiseSummary]
    enum CodingKeys: String, CodingKey {
        case subordinates
        case openSubCommits = "open_sub_commits"
        case openPromises   = "open_promises"
    }
}

struct SubordinateSummary: Decodable, Identifiable {
    let id: Int
    let name: String
    let role: String?
    let last1on1: String?
    enum CodingKeys: String, CodingKey {
        case id, name, role
        case last1on1 = "last_1on1"
    }
}

struct SubCommit: Decodable, Identifiable {
    let sub: String
    let content: String
    let deadline: String?
    var id: String { "\(sub)-\(content)" }
}

struct PromiseSummary: Decodable, Identifiable {
    let to: String
    let content: String
    let deadline: String?
    var id: String { "\(to)-\(content)" }
}
