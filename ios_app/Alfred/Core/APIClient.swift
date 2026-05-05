import Foundation

// MARK: - Alfred API Client
// 所有後端 API 呼叫集中在這裡

class APIClient {
    static let shared = APIClient()

    private let baseURL = "https://YOUR_BACKEND_HOST/api"
    private let session = URLSession.shared

    // MARK: - Chat

    struct ChatRequest: Encodable {
        let message: String
        let history: [[String: String]]
    }

    struct ChatResponse: Decodable {
        let text: String?
        let card: CardData?
        let action: ActionData?
    }

    struct CardData: Decodable {
        let title: String?
        let content: String?
        let type: String?
    }

    struct ActionData: Decodable {
        let type: String?
        let url: String?
        let title: String?
        let translated: String?
        let lang: String?
        let langName: String?
        let direction: String?
        let label: String?
        // sub_app fields
        let app: String?
        let lat: String?
        let lng: String?
        let query: String?
        let original: String?
        let sourceLang: String?
        let targetLang: String?
        let driving: Bool?

        enum CodingKeys: String, CodingKey {
            case type, url, title, translated, lang, direction, label, app, lat, lng, query, original, driving
            case langName   = "lang_name"
            case sourceLang = "source_lang"
            case targetLang = "target_lang"
        }
    }

    func chat(message: String, history: [[String: String]] = []) async throws -> ChatResponse {
        let req = ChatRequest(message: message, history: history)
        return try await post(path: "/chat", body: req)
    }

    // MARK: - Greeting

    struct GreetResponse: Decodable {
        let text: String
    }

    func greet() async throws -> GreetResponse {
        return try await get(path: "/greet")
    }

    // MARK: - TTS

    func tts(text: String) async throws -> Data {
        let body = ["text": text]
        return try await postRaw(path: "/tts", body: body)
    }

    // MARK: - Transcribe

    func transcribe(audioData: Data, filename: String = "audio.m4a") async throws -> String {
        let boundary = UUID().uuidString
        var request = URLRequest(url: URL(string: "\(baseURL)/transcribe")!)
        request.httpMethod = "POST"
        request.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")

        var body = Data()
        body.append("--\(boundary)\r\n".data(using: .utf8)!)
        body.append("Content-Disposition: form-data; name=\"file\"; filename=\"\(filename)\"\r\n".data(using: .utf8)!)
        body.append("Content-Type: audio/m4a\r\n\r\n".data(using: .utf8)!)
        body.append(audioData)
        body.append("\r\n--\(boundary)--\r\n".data(using: .utf8)!)
        request.httpBody = body

        let (data, _) = try await session.data(for: request)
        let result = try JSONDecoder().decode([String: String].self, from: data)
        return result["transcript"] ?? ""
    }

    // MARK: - Translation

    struct TranslateResponse: Decodable {
        let original: String
        let translated: String
        let targetLang: String
        let targetLangName: String

        enum CodingKeys: String, CodingKey {
            case original, translated
            case targetLang = "target_lang"
            case targetLangName = "target_lang_name"
        }
    }

    func translate(text: String, targetLang: String) async throws -> TranslateResponse {
        let body: [String: String] = ["text": text, "target_lang": targetLang, "mode": "interpret"]
        return try await post(path: "/translate", body: body)
    }

    func translateTTS(text: String, targetLang: String) async throws -> Data {
        let boundary = UUID().uuidString
        var request = URLRequest(url: URL(string: "\(baseURL)/translate/tts")!)
        request.httpMethod = "POST"
        request.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")

        var body = Data()
        for (key, value) in ["text": text, "target_lang": targetLang, "mode": "interpret"] {
            body.append("--\(boundary)\r\n".data(using: .utf8)!)
            body.append("Content-Disposition: form-data; name=\"\(key)\"\r\n\r\n".data(using: .utf8)!)
            body.append("\(value)\r\n".data(using: .utf8)!)
        }
        body.append("--\(boundary)--\r\n".data(using: .utf8)!)
        request.httpBody = body

        let (data, _) = try await session.data(for: request)
        return data
    }

    // MARK: - Location

    struct LocationPoint: Encodable {
        let lat: Double
        let lng: Double
        let speed: Double
        let heading: Double
        let accuracy: Double
        let ts: String
    }

    func uploadLocation(points: [LocationPoint]) async throws {
        let body = ["points": points]
        let _: EmptyResponse = try await post(path: "/location/update", body: body)
    }

    struct LocationContextResponse: Decodable {
        let context: String
        let name: String
        let greeting: String
        let checkinRecorded: Bool?
        let checkoutRecorded: Bool?

        enum CodingKeys: String, CodingKey {
            case context, name, greeting
            case checkinRecorded = "checkin_recorded"
            case checkoutRecorded = "checkout_recorded"
        }
    }

    func locationContext() async throws -> LocationContextResponse {
        return try await get(path: "/location/context")
    }

    // MARK: - Family

    struct FamilyMember: Decodable, Identifiable {
        let id: Int
        let name: String
        let relation: String
        let color: String
        let lat: Double?
        let lng: Double?
        let address: String?
        let lastSeen: String?
        let battery: Int?
        let isHome: Bool

        enum CodingKeys: String, CodingKey {
            case id, name, relation, color, lat, lng, address, battery
            case lastSeen = "last_seen"
            case isHome = "is_home"
        }
    }

    func familyMembers() async throws -> [FamilyMember] {
        return try await get(path: "/family/members")
    }

    func familyLocationUpdate(deviceToken: String, lat: Double, lng: Double, battery: Int) async throws {
        let body: [String: Any] = [
            "device_token": deviceToken,
            "lat": lat,
            "lng": lng,
            "battery": battery
        ]
        let _: EmptyResponse = try await postAny(path: "/family/location", body: body)
    }

    // MARK: - Reminders

    struct Reminder: Decodable, Identifiable {
        let id: Int
        let title: String
        let triggerAt: String

        enum CodingKeys: String, CodingKey {
            case id, title
            case triggerAt = "trigger_at"
        }
    }

    func pendingReminders() async throws -> [Reminder] {
        return try await get(path: "/reminders/pending")
    }

    // MARK: - Visit Prep

    struct VisitReminder: Decodable {
        let eventTitle: String
        let person: String
        let suggestion: String
        let minutesAway: Int
        let message: String

        enum CodingKeys: String, CodingKey {
            case person, suggestion, message
            case eventTitle = "event_title"
            case minutesAway = "minutes_away"
        }
    }

    func visitPrep() async throws -> [VisitReminder] {
        struct Response: Decodable { let reminders: [VisitReminder] }
        let r: Response = try await get(path: "/visit/prep")
        return r.reminders
    }

    // MARK: - Onboard

    func onboardStatus() async throws -> Bool {
        struct Response: Decodable { let completed: Bool }
        let r: Response = try await get(path: "/onboard/status")
        return r.completed
    }

    // MARK: - Generic Helpers

    private struct EmptyResponse: Decodable {}

    func get<T: Decodable>(path: String) async throws -> T {
        let url = URL(string: "\(baseURL)\(path)")!
        let (data, _) = try await session.data(from: url)
        return try JSONDecoder().decode(T.self, from: data)
    }

    func post<T: Decodable, B: Encodable>(path: String, body: B) async throws -> T {
        var request = URLRequest(url: URL(string: "\(baseURL)\(path)")!)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONEncoder().encode(body)
        let (data, _) = try await session.data(for: request)
        return try JSONDecoder().decode(T.self, from: data)
    }

    func postAny<T: Decodable>(path: String, body: [String: Any]) async throws -> T {
        var request = URLRequest(url: URL(string: "\(baseURL)\(path)")!)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONSerialization.data(withJSONObject: body)
        let (data, _) = try await session.data(for: request)
        return try JSONDecoder().decode(T.self, from: data)
    }

    func postRaw<B: Encodable>(path: String, body: B) async throws -> Data {
        var request = URLRequest(url: URL(string: "\(baseURL)\(path)")!)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONEncoder().encode(body)
        let (data, _) = try await session.data(for: request)
        return data
    }
}
