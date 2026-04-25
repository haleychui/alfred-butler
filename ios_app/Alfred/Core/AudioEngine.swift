import AVFoundation
import Foundation

// MARK: - Audio Engine
// 錄音 + TTS 播放

@MainActor
class AudioEngine: NSObject, ObservableObject {
    static let shared = AudioEngine()

    @Published var isRecording = false
    @Published var isPlaying = false

    private var recorder: AVAudioRecorder?
    private var player: AVAudioPlayer?
    private var recURL: URL?

    override init() {
        super.init()
        setupSession()
    }

    func setupSession() {
        let s = AVAudioSession.sharedInstance()
        try? s.setCategory(.playAndRecord, mode: .default,
                           options: [.defaultToSpeaker, .allowBluetooth])
        try? s.setActive(true)
    }

    // MARK: - Recording
    func startRecording() {
        let url = FileManager.default.temporaryDirectory
            .appendingPathComponent("alfred_\(Date().timeIntervalSince1970).m4a")
        recURL = url
        let settings: [String: Any] = [
            AVFormatIDKey: Int(kAudioFormatMPEG4AAC),
            AVSampleRateKey: 16000,
            AVNumberOfChannelsKey: 1,
            AVEncoderAudioQualityKey: AVAudioQuality.high.rawValue
        ]
        recorder = try? AVAudioRecorder(url: url, settings: settings)
        recorder?.record()
        isRecording = true
    }

    func stopRecording() -> Data? {
        recorder?.stop()
        isRecording = false
        guard let url = recURL else { return nil }
        return try? Data(contentsOf: url)
    }

    // MARK: - Playback
    func play(data: Data) async {
        guard !data.isEmpty else { return }
        let url = FileManager.default.temporaryDirectory
            .appendingPathComponent("alfred_tts_\(Date().timeIntervalSince1970).mp3")
        try? data.write(to: url)

        return await withCheckedContinuation { continuation in
            do {
                player = try AVAudioPlayer(contentsOf: url)
                player?.delegate = self
                player?.play()
                isPlaying = true
                // delegate audioPlayerDidFinishPlaying 會 resume
                self._continuation = continuation
            } catch {
                continuation.resume()
            }
        }
    }

    private var _continuation: CheckedContinuation<Void, Never>?
}

extension AudioEngine: AVAudioPlayerDelegate {
    nonisolated func audioPlayerDidFinishPlaying(_ player: AVAudioPlayer, successfully flag: Bool) {
        Task { @MainActor in
            self.isPlaying = false
            self._continuation?.resume()
            self._continuation = nil
        }
    }
}
