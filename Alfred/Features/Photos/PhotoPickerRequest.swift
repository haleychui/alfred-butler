import Foundation

// 阿福從對話 action 帶下來的相片查詢請求
struct PhotoPickerRequest: Identifiable, Hashable {
    let id = UUID()
    let keyword: String?           // 例：「寵物」「合照」（V1 沒做語意搜尋，留 metadata）
    let range: String?             // "today" / "yesterday" / "last_week" / "last_month" / nil

    func dateRange() -> (Date, Date)? {
        let cal = Calendar.current
        let now = Date()
        switch range {
        case "today":
            let s = cal.startOfDay(for: now)
            return (s, now)
        case "yesterday":
            let yest = cal.date(byAdding: .day, value: -1, to: now)!
            let s = cal.startOfDay(for: yest)
            let e = cal.date(byAdding: .day, value: 1, to: s)!
            return (s, e)
        case "last_week":
            let s = cal.date(byAdding: .day, value: -7, to: now)!
            return (s, now)
        case "last_month":
            let s = cal.date(byAdding: .month, value: -1, to: now)!
            return (s, now)
        default:
            return nil
        }
    }
}
