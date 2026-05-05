import Foundation
import AVFoundation
import Combine

// MARK: - Alfred Core ViewModel
@MainActor
class AlfredViewModel: NSObject, ObservableObject {

    static let shared = AlfredViewModel()

    // MARK: - Published state
    @Published var alfredText: String = ""
    @Published var userText: String = ""
    @Published var state: AlfredState = .idle
    @Published var card: CardData? = nil
    @Published var isFirstLaunch: Bool = false
    @Published var translationOverlay: TranslationOverlay? = nil

    // ── 阿福主動推開的 sheet（零介面：阿福開，不是用戶按）──────────────
    @Published var showFamily: Bool = false
    @Published var showOffice: Bool = false
    @Published var showTranslate: Bool = false
    @Published var showAttendance: Bool = false

    enum AlfredState { case idle, listening, thinking, speaking }

    private let api = AlfredAPI.shared
    private let audio = AudioEngine.shared
    private var history: [[String: String]] = []

    // MARK: - Startup
    func onAppear() {
        Task { await greet() }
    }

    func greet() async {
        do {
            let resp = try await api.greet()
            isFirstLaunch = resp.firstTime ?? false
            await showAndSpeak(resp.text)
        } catch {
            print("[Alfred] greet error:", error)
        }
    }

    // MARK: - Voice Input
    func startListening() {
        guard state == .idle else { return }
        audio.startRecording()
        state = .listening
        userText = ""
        alfredText = ""
    }

    func stopListening() {
        guard state == .listening else { return }
        state = .thinking
        Task {
            guard let audioData = audio.stopRecording() else { state = .idle; return }
            do {
                let transcript = try await api.transcribe(audioData: audioData)
                guard !transcript.isEmpty else { state = .idle; return }
                userText = "「\(transcript)」"
                await sendMessage(transcript)
            } catch {
                print("[Alfred] transcribe error:", error)
                state = .idle
            }
        }
    }

    // MARK: - Send message (SSE stream)
    func sendMessage(_ message: String) async {
        state = .thinking
        history.append(["role": "user", "content": message])
        if history.count > 20 { history = Array(history.suffix(20)) }

        alfredText = ""
        var fullText = ""

        do {
            let stream = try await api.chatStream(message: message,
                                                   history: Array(history.suffix(10)))
            for try await chunk in stream {
                if chunk.thinking != nil { state = .thinking }
                if let delta = chunk.delta {
                    if state == .thinking { state = .speaking }
                    fullText += delta
                    alfredText = fullText
                }
                if chunk.done == true {
                    if let c = chunk.card { card = c }
                    if let action = chunk.action {
                        await handleAction(action, fullText: fullText)
                        return
                    }
                }
            }
            history.append(["role": "assistant", "content": fullText])
            await speakText(fullText)
        } catch {
            print("[Alfred] chat error:", error)
            state = .idle
        }
    }

    // MARK: - Action Handler（後端推送 sheet 的入口）
    func handleAction(_ action: [String: String], fullText: String) async {
        let type = action["type"] ?? ""
        switch type {

        // ── 零介面 sheet：阿福決定什麼時候打開 ──────────────────────────
        case "show_family":
            await speakText(fullText)
            showFamily = true

        case "show_office":
            await speakText(fullText)
            showOffice = true

        case "show_translate":
            await speakText(fullText)
            showTranslate = true

        case "show_attendance":
            await speakText(fullText)
            showAttendance = true

        // ── 翻譯覆層（給對方看的大字）─────────────────────────────────
        case "speak_translation":
            let translated = action["translated"] ?? ""
            let lang = action["lang"] ?? "en"
            await speakText(fullText)
            translationOverlay = TranslationOverlay(text: translated, lang: lang)
            do {
                let audioData = try await api.translateAndSpeak(text: translated, targetLang: lang)
                await audio.play(data: audioData)
            } catch {
                print("[Alfred] translation TTS error:", error)
            }
            try? await Task.sleep(nanoseconds: 3_000_000_000)
            translationOverlay = nil
            state = .idle

        case "request_upload":
            await speakText(fullText)
            state = .idle

        default:
            await speakText(fullText)
        }
    }

    // MARK: - TTS
    func speakText(_ text: String) async {
        state = .speaking
        do {
            let audioData = try await api.tts(text: text)
            await audio.play(data: audioData)
        } catch {
            print("[Alfred] tts error:", error)
        }
        state = .idle
    }

    func showAndSpeakContext(_ text: String) async {
        alfredText = text
        await speakText(text)
    }

    private func showAndSpeak(_ text: String) async {
        alfredText = text
        await speakText(text)
    }

    func speakAloud(_ text: String) async {
        guard state == .idle else { return }
        alfredText = text
        await speakText(text)
        try? await Task.sleep(nanoseconds: 5_000_000_000)
        if state == .idle { alfredText = "" }
    }
}

// MARK: - Data Models
struct TranslationOverlay: Identifiable {
    let id = UUID()
    let text: String
    let lang: String
}

struct CardData: Decodable, Identifiable {
    var id = UUID()
    let title: String?
    let content: String?
    let type: String?
    enum CodingKeys: String, CodingKey { case title, content, type }
}

struct GreetResponse: Decodable {
    let text: String
    let firstTime: Bool?
    enum CodingKeys: String, CodingKey { case text; case firstTime = "first_time" }
}

struct StreamChunk: Decodable {
    let delta: String?
    let done: Bool?
    let text: String?
    let card: CardData?
    let action: [String: String]?
    let thinking: String?
}
