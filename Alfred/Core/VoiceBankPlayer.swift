import Foundation
import AVFoundation

/// VoiceBankPlayer — 從 2500+ 預錄 mp3 隨機 / 規則挑播
///
/// 跟 AlfredViewModel.speakLocally 並列：
///   - speakLocally(text)：AVSpeechSynthesizer，沒預錄音檔時的 fallback
///   - VoiceBankPlayer.playRandom(in: "ack_short")：從同類別隨機抽一個 mp3 播
///
/// 用途：在已知情境（ack / mode_enter / mood_care / 等）下，直接播
/// ElevenLabs Michael Caine clone 預錄音色，0 網路、0 LLM。
@MainActor
final class VoiceBankPlayer {

    static let shared = VoiceBankPlayer()

    private var manifest: [String: [String]] = [:]  // category → [filename without .mp3]
    private var player: AVAudioPlayer?

    private init() {
        loadManifest()
    }

    /// 從 manifest 載入 category → ids 對應
    private func loadManifest() {
        guard let url = Bundle.main.url(forResource: "voice_bank_manifest", withExtension: "json"),
              let data = try? Data(contentsOf: url),
              let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let lines = json["lines"] as? [[String: Any]]
        else {
            NSLog("[VoiceBank] manifest load failed")
            return
        }
        var map: [String: [String]] = [:]
        for line in lines {
            guard let id = line["id"] as? String,
                  let cat = line["category"] as? String else { continue }
            map[cat, default: []].append(id)
        }
        self.manifest = map
        let totalIds = map.values.reduce(0) { $0 + $1.count }
        NSLog("[VoiceBank] loaded %d categories, %d total ids", map.count, totalIds)
    }

    /// 從指定 category 隨機抽一個 mp3 播
    func playRandom(in category: String) async -> Bool {
        guard let ids = manifest[category], !ids.isEmpty else {
            NSLog("[VoiceBank] no ids in category=%@", category)
            return false
        }
        let id = ids.randomElement()!
        return await play(id: id)
    }

    /// 播指定 id 的 mp3
    func play(id: String) async -> Bool {
        guard let url = Bundle.main.url(forResource: id, withExtension: "mp3", subdirectory: "voice_bank")
              ?? Bundle.main.url(forResource: id, withExtension: "mp3")
        else {
            NSLog("[VoiceBank] mp3 not found: %@", id)
            return false
        }
        do {
            // 確保 audio session category 跟 AudioEngine 一致
            let session = AVAudioSession.sharedInstance()
            try session.setCategory(.playAndRecord, mode: .default,
                                    options: [.defaultToSpeaker, .allowBluetoothHFP])
            try session.setActive(true)
            try session.overrideOutputAudioPort(.speaker)

            let p = try AVAudioPlayer(contentsOf: url)
            p.volume = 1.0  // 最大音量（mp3 本身已 ffmpeg 放大）
            p.prepareToPlay()
            p.play()
            self.player = p
            // 等播完
            let dur = p.duration
            try await Task.sleep(nanoseconds: UInt64(dur * 1_000_000_000))
            return true
        } catch {
            NSLog("[VoiceBank] play failed: %@", String(describing: error))
            return false
        }
    }

    /// 看 category 有幾個 id（debug 用）
    func count(in category: String) -> Int {
        manifest[category]?.count ?? 0
    }
}
