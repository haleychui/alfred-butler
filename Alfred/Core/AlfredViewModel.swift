import Foundation
import Combine
import AVFoundation
import UIKit

// MARK: - Alfred Core ViewModel
// 整個 App 的大腦。語音錄音 → STT → Chat (SSE) → TTS → 播放

@MainActor
class AlfredViewModel: NSObject, ObservableObject {

    static let shared = AlfredViewModel()

    // MARK: - Published state
    @Published var alfredText: String = ""       // 阿福說的話（打字效果中）
    @Published var userText: String = ""         // 主人說的話
    @Published var state: AlfredState = .idle    // idle / listening / thinking / speaking
    @Published var card: CardData? = nil         // 卡片（合約分析、報告等）
    @Published var isFirstLaunch: Bool = false
    @Published var translationOverlay: TranslationOverlay? = nil  // 翻譯大字顯示
    @Published var showFamily: Bool = false
    @Published var showOffice: Bool = false
    @Published var showTranslate: Bool = false
    @Published var showAttendance: Bool = false

    enum AlfredState { case idle, listening, thinking, speaking }

    // MARK: - Private
    private let api = AlfredAPI.shared
    private let audio = AudioEngine.shared
    private var history: [[String: String]] = []
    private var typewriterTimer: Timer?

    // MARK: - Startup
    func onAppear() {
        // UI test mode：launch arg 含 --prompt 時跳過 greet，避免跟 test sendMessage 打架
        if CommandLine.arguments.contains("--prompt") { return }
        Task { await greet() }
    }

    func greet() async {
        // 一開機就拿 token，不等 onboarding（tts/transcribe 一開始就會用到）
        if api.token == nil {
            let deviceId = UIDevice.current.identifierForVendor?.uuidString ?? UUID().uuidString
            _ = try? await api.deviceLogin(deviceId: deviceId)
        }
        let isOnboarded = UserDefaults.standard.bool(forKey: "alfred_onboarded")

        if !isOnboarded {
            // Onboarding 絕對不播任何聲音（mp3 內容含啟動語會「自己念完」），純文字 + 立刻 idle
            isFirstLaunch = true
            alfredText = "主人您好，我是您的全能管家，能為您協助做很多事情。\n\n請您先讓我認識您，壓著中間對話按鈕，按照以下的文字說出來：\n\n「阿福，我是你的主人，我會有很多地方需要你的幫忙，你要幫我把每一件事情處理好。」"
            state = .idle
        } else {
            do {
                let resp = try await api.greet()
                isFirstLaunch = resp.firstTime ?? false
                await showAndSpeak(resp.text)
            } catch {
                print("[Alfred] greet error:", error)
            }
        }
    }

    // MARK: - Voice Input (按住錄音)
    func startListening() {
        // 按住即打斷阿福，不論當前狀態
        audio.stopPlayback()
        typewriterTimer?.invalidate()
        audio.startRecording()
        state = .listening
        userText = ""
        // onboarding 期間保留啟動語提示，主人才看得到要念什麼
        if UserDefaults.standard.bool(forKey: "alfred_onboarded") {
            alfredText = ""
        }
    }

    func stopListening() {
        guard state == .listening else { return }
        state = .thinking
        Task {
            guard let audioData = audio.stopRecording() else {
                state = .idle; return
            }

            // 立刻說「阿福已經收到」（用 ElevenLabs 跟 chat 同個聲音）
            let ackTask = Task { await self.speakAck() }

            do {
                NSLog("[Alfred] transcribe start, audio %d bytes", audioData.count)
                let transcript = try await api.transcribe(audioData: audioData)
                NSLog("[Alfred] transcribe result: '%@'", transcript)
                guard !transcript.isEmpty else {
                    NSLog("[Alfred] transcript empty, abort")
                    await ackTask.value
                    state = .idle
                    return
                }
                userText = "「\(transcript)」"
                await ackTask.value
                NSLog("[Alfred] sendMessage start")
                await sendMessage(transcript)
                NSLog("[Alfred] sendMessage done, state=%@", String(describing: state))
            } catch {
                NSLog("[Alfred] transcribe error: %@", String(describing: error))
                await ackTask.value
                state = .idle
            }
        }
    }

    private func speakAck() async {
        do {
            let audioData = try await api.tts(text: "阿福已經收到")
            await audio.play(data: audioData)
        } catch {
            NSLog("[Alfred] ack TTS error: %@", String(describing: error))
        }
    }

    // MARK: - Send message (SSE stream)
    func sendMessage(_ message: String) async {
        let wasOnboarded = UserDefaults.standard.bool(forKey: "alfred_onboarded")
        let isActivation = message.contains("我是你的主人") && message.contains("幫我把每一件事情處理好")

        // ── Onboarding 階段：不走正常 chat，避免 alfredText 被清空 ─────────────
        if !wasOnboarded {
            // 嚴比對：必須同時念到「主人」+「處理」，避免單字「主人」誤觸通過
            let normalized = message.replacingOccurrences(of: "妳", with: "你")
            let isStrictActivation = normalized.contains("主人") && normalized.contains("處理")
            NSLog("[Alfred onboarding] heard: %@ → strict_match: %@", message, isStrictActivation ? "YES" : "NO")

            if isStrictActivation {
                UserDefaults.standard.set(true, forKey: "alfred_onboarded")
                isFirstLaunch = false
                if api.token == nil {
                    let deviceId = UIDevice.current.identifierForVendor?.uuidString ?? UUID().uuidString
                    _ = try? await api.deviceLogin(deviceId: deviceId)
                }
                alfredText = "好的，主人。從今天起我陪在您身邊。需要什麼跟我說一聲就好。"
                await speakText(alfredText)
            } else {
                alfredText = "對不起主人，請依畫面上的句子說一遍：\n\n「阿福，我是你的主人，我會有很多地方需要你的幫忙，你要幫我把每一件事情處理好。」"
                await speakText("對不起主人，請依畫面上的句子說一遍。")
            }
            return
        }

        state = .thinking
        history.append(["role": "user", "content": message])
        if history.count > 20 { history = Array(history.suffix(20)) }

        alfredText = ""
        var fullText = ""

        NSLog("[Alfred] chatStream start, msg='%@'", message)
        do {
            let stream = try await api.chatStream(message: message,
                                                   history: Array(history.suffix(10)))
            for try await chunk in stream {
                if chunk.thinking != nil {
                    // 工具呼叫中：保持 thinking 狀態，不更新文字
                    state = .thinking
                }
                if let delta = chunk.delta {
                    if state == .thinking { state = .speaking }
                    fullText += delta
                    alfredText = fullText          // 即時更新
                }
                if chunk.done == true {
                    if let c = chunk.card { card = c }
                    if let action = chunk.action {
                        await handleAction(action, fullText: fullText)
                        return  // action 接管後續播放
                    }
                }
            }
            NSLog("[Alfred] chatStream done, fullText len=%d", fullText.count)
            history.append(["role": "assistant", "content": fullText])
            await speakText(fullText)
            NSLog("[Alfred] speakText done")
        } catch {
            NSLog("[Alfred] chat error: %@", String(describing: error))
            state = .idle
        }
    }

    // MARK: - Action Handler
    private func handleAction(_ action: [String: String], fullText: String) async {
        let type = action["type"] ?? ""
        switch type {
        case "speak_translation":
            let translated = action["translated"] ?? ""
            let lang = action["lang"] ?? "en"
            // 先播阿福說的話（中文引導語）
            await speakText(fullText)
            // 顯示大字翻譯給對方看
            translationOverlay = TranslationOverlay(text: translated, lang: lang)
            // 播翻譯語音
            do {
                let audioData = try await api.translateAndSpeak(text: translated, targetLang: lang)
                await audio.play(data: audioData)
            } catch {
                print("[Alfred] translation TTS error:", error)
            }
            // 3 秒後自動收起翻譯覆層
            try? await Task.sleep(nanoseconds: 3_000_000_000)
            translationOverlay = nil
            state = .idle

        case "request_upload":
            await speakText(fullText)
            state = .idle

        case "show_family", "show_office", "show_translate", "show_attendance":
            // 零介面原則：不開 sheet，純語音回答（card / photo 才需要 UI）
            await speakText(fullText)
            state = .idle

        default:
            await speakText(fullText)
            state = .idle
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

    // 警報主動觸發：app 在前景時讓阿福直接開口
    func speakAloud(_ text: String) async {
        guard state == .idle else { return }
        alfredText = text
        await speakText(text)
        // 說完 5 秒後淡出，不佔版面
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
    let url: String?
    enum CodingKeys: String, CodingKey { case title, content, type, url }
}

struct GreetResponse: Decodable {
    let text: String
    let firstTime: Bool?
    enum CodingKeys: String, CodingKey {
        case text
        case firstTime = "first_time"
    }
}

struct StreamChunk: Decodable {
    let delta: String?
    let done: Bool?
    let text: String?
    let card: CardData?
    let action: [String: String]?
    let thinking: String?  // 工具執行中的進度提示
}
