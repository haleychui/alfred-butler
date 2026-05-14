import Foundation
import AVFoundation

@MainActor
class AudioEngine: NSObject {
    static let shared = AudioEngine()

    private var recorder: AVAudioRecorder?
    private var player: AVAudioPlayer?
    private var recordingURL: URL?
    private(set) var isRecording = false

    func startRecording() {
        #if !os(macOS)
        let session = AVAudioSession.sharedInstance()
        do {
            // 2026-05-14 統一三個 player (AudioEngine.startRecording/play + VoiceBankPlayer.play) 用同一份 session 設定
            // 避免 setCategory 切換產生的 noise burst (TTS 雜音 root cause)
            // 原設定: .playAndRecord + .measurement + .allowBluetooth (deprecated)
            // .measurement mode 對聲紋採樣有利但會 disable echo cancellation；統一改 .default 以求穩定播放
            try session.setCategory(.playAndRecord, mode: .default,
                                    options: [.defaultToSpeaker, .allowBluetoothHFP])
            try session.setActive(true)
            try session.overrideOutputAudioPort(.speaker)
        } catch {
            print("[AudioEngine] session error:", error)
            return
        }
        #endif

        // 每次錄音都存到 Documents/voice_log/，永久保留（聲紋 / 對話 review 用）
        let docs = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
        let logDir = docs.appendingPathComponent("voice_log", isDirectory: true)
        try? FileManager.default.createDirectory(at: logDir, withIntermediateDirectories: true)
        let stamp: String = {
            let f = DateFormatter()
            f.dateFormat = "yyyy-MM-dd_HH-mm-ss"
            return f.string(from: Date())
        }()
        let url = logDir.appendingPathComponent("\(stamp)_\(UUID().uuidString.prefix(8)).m4a")
        print("[AudioEngine] recording →", url.lastPathComponent)
        let settings: [String: Any] = [
            AVFormatIDKey: Int(kAudioFormatMPEG4AAC),
            AVSampleRateKey: 16000,
            AVNumberOfChannelsKey: 1,
            AVEncoderAudioQualityKey: AVAudioQuality.medium.rawValue
        ]
        do {
            recorder = try AVAudioRecorder(url: url, settings: settings)
            recorder?.record()
            isRecording = true
            recordingURL = url
        } catch {
            print("[AudioEngine] record error:", error)
        }
    }

    func stopPlayback() {
        player?.stop()
        player = nil
    }

    func stopRecording() -> Data? {
        recorder?.stop()
        recorder = nil
        isRecording = false

        guard let url = recordingURL else { return nil }
        lastRecordingPath = url.lastPathComponent
        recordingURL = nil
        return try? Data(contentsOf: url)
    }

    var lastRecordingPath: String?

    func play(data: Data) async {
        #if !os(macOS)
        let session = AVAudioSession.sharedInstance()
        do {
            // 2026-05-14 修 TTS 雜音 root cause:
            // 原: .playback mode → CRITICAL_README 寫得很清楚不能用,
            //     overrideOutputAudioPort(.speaker) 在 .playback 模式無效, 聲音從耳機出。
            // 改: 統一 .playAndRecord + .default + .allowBluetoothHFP, 跟 VoiceBankPlayer 一致,
            //     避免三個 player 共用 AVAudioSession.sharedInstance() 互相 setCategory 切換產生的 noise burst。
            try session.setCategory(.playAndRecord, mode: .default,
                                    options: [.defaultToSpeaker, .allowBluetoothHFP])
            try session.setActive(true)
            try session.overrideOutputAudioPort(.speaker)
        } catch {
            print("[AudioEngine] playback session error:", error)
        }
        #endif

        await withCheckedContinuation { (cont: CheckedContinuation<Void, Never>) in
            do {
                player = try AVAudioPlayer(data: data)
                player?.delegate = PlayerDelegate.shared
                player?.volume = 1.0
                player?.prepareToPlay()
                PlayerDelegate.shared.onFinish = { cont.resume() }
                player?.play()
            } catch {
                print("[AudioEngine] play error:", error)
                cont.resume()
            }
        }
    }
}

private class PlayerDelegate: NSObject, AVAudioPlayerDelegate {
    static let shared = PlayerDelegate()
    var onFinish: (() -> Void)?
    func audioPlayerDidFinishPlaying(_ player: AVAudioPlayer, successfully flag: Bool) {
        onFinish?()
        onFinish = nil
    }
}
