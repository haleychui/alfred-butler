import SwiftUI
import UniformTypeIdentifiers

// MARK: - 主畫面（零介面）
// 全螢幕阿福。按住說話，放開阿福回答。就這樣。

struct AlfredView: View {
    @StateObject private var vm = AlfredViewModel.shared
    @State private var isPressing = false
    private let documentTypes: [UTType] = [.pdf, .plainText, .text, .rtf, UTType(filenameExtension: "docx")!]

    var body: some View {
        ZStack {
            // 背景
            Color(hex: "#090909").ignoresSafeArea()

            VStack(spacing: 0) {
                Spacer()

                // 阿福頭像（按住這裡說話）
                AlfredAvatarView(state: vm.state, isPressing: isPressing)
                    .gesture(
                        DragGesture(minimumDistance: 0)
                            .onChanged { _ in
                                if !isPressing {
                                    isPressing = true
                                    vm.startListening()
                                }
                            }
                            .onEnded { _ in
                                if isPressing {
                                    isPressing = false
                                    vm.stopListening()
                                }
                            }
                    )

                Spacer().frame(height: 32)

                // 主人說的話
                if !vm.userText.isEmpty {
                    Text(vm.userText)
                        .font(.system(size: 13))
                        .foregroundColor(Color(hex: "#e8d5b780"))
                        .italic()
                        .padding(.horizontal, 28)
                        .multilineTextAlignment(.center)
                        .transition(.opacity)
                }

                // 阿福說的話
                if !vm.alfredText.isEmpty {
                    Text(vm.alfredText)
                        .font(.system(size: 17, weight: .regular))
                        .foregroundColor(Color(hex: "#e8d5b7"))
                        .padding(.horizontal, 28)
                        .multilineTextAlignment(.center)
                        .lineSpacing(6)
                        .animation(.easeIn(duration: 0.1), value: vm.alfredText)
                }

                Spacer().frame(height: 16)

                // 測試入口：文件分析
                DocumentAnalysisButton {
                    vm.requestDocumentAnalysis()
                }
                .padding(.bottom, 14)

                // 狀態提示
                Text(hintText)
                    .font(.system(size: 11, weight: .medium))
                    .foregroundColor(Color(hex: "#c9a84c60"))
                    .letterSpacing(1.5)
                    .padding(.bottom, 40)
            }
        }
        // 卡片（合約分析、報告等）
        .sheet(item: $vm.card) { card in
            CardView(card: card)
        }
        // 阿福主動推開的功能頁面
        .sheet(isPresented: $vm.showFamily)    { FamilyView() }
        .sheet(isPresented: $vm.showOffice)    { OfficeDashboardView() }
        .sheet(isPresented: $vm.showTranslate) { TranslateView() }
        .sheet(isPresented: $vm.showAttendance){ AttendanceView() }
        // Sub-Apps（天氣 / 地圖 / 翻譯）
        .sheet(item: $vm.subApp) { cfg in
            SubAppView(config: cfg)
        }
        .fileImporter(isPresented: $vm.showDocumentImporter,
                      allowedContentTypes: documentTypes,
                      allowsMultipleSelection: false) { result in
            switch result {
            case .success(let urls):
                guard let url = urls.first else { return }
                Task { await vm.analyzeSelectedDocument(url) }
            case .failure(let error):
                print("[Alfred] file importer error:", error)
            }
        }
        // 翻譯覆層（大字給對方看）
        .overlay {
            if let overlay = vm.translationOverlay {
                TranslationOverlayView(overlay: overlay)
                    .transition(.opacity.combined(with: .scale(scale: 0.95)))
            }
        }
        .animation(.easeInOut(duration: 0.3), value: vm.translationOverlay?.id)
        .onAppear { vm.onAppear() }
    }

    var hintText: String {
        switch vm.state {
        case .idle:      return isPressing ? "正在聆聽" : "按住說話"
        case .listening: return "正在聆聽..."
        case .thinking:  return "思考中"
        case .speaking:  return "A L F R E D"
        }
    }
}



struct DocumentAnalysisButton: View {
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: 8) {
                Image(systemName: "doc.text.magnifyingglass")
                    .font(.system(size: 13, weight: .light))
                Text("文件分析")
                    .font(.system(size: 12, weight: .medium))
                    .kerning(1.5)
            }
            .foregroundColor(Color(hex: "#c9a84c").opacity(0.78))
            .padding(.horizontal, 14)
            .padding(.vertical, 9)
            .background(Color(hex: "#c9a84c").opacity(0.08))
            .overlay(
                Capsule().stroke(Color(hex: "#c9a84c").opacity(0.22), lineWidth: 0.8)
            )
            .clipShape(Capsule())
        }
        .buttonStyle(.plain)
        .accessibilityLabel("文件分析")
    }
}

// MARK: - 阿福頭像 + 動畫
struct AlfredAvatarView: View {
    let state: AlfredViewModel.AlfredState
    let isPressing: Bool

    @State private var pulse = false

    var body: some View {
        ZStack {
            // 光暈環
            ForEach(0..<3) { i in
                Circle()
                    .stroke(Color(hex: "#c9a84c").opacity(ringOpacity(i)), lineWidth: 1)
                    .frame(width: CGFloat(180 + i * 40), height: CGFloat(180 + i * 40))
                    .scaleEffect(pulse ? 1.04 : 1.0)
                    .animation(
                        .easeInOut(duration: 2.4).repeatForever().delay(Double(i) * 0.5),
                        value: pulse
                    )
            }

            // 頭像圓
            Circle()
                .fill(Color(hex: "#c9a84c").opacity(0.08))
                .overlay(
                    Circle().stroke(Color(hex: "#c9a84c").opacity(0.4), lineWidth: 1.5)
                )
                .frame(width: 110, height: 110)
                .scaleEffect(isPressing ? 0.93 : 1.0)
                .animation(.spring(response: 0.2), value: isPressing)
                .overlay(
                    Text("🎩")
                        .font(.system(size: 44))
                )
        }
        .onAppear { pulse = true }
    }

    func ringOpacity(_ i: Int) -> Double {
        switch state {
        case .listening: return [0.4, 0.25, 0.12][i]
        case .speaking:  return [0.35, 0.2, 0.08][i]
        default:         return [0.2, 0.12, 0.05][i]
        }
    }
}

// MARK: - 卡片視圖（邀請函風格）
struct CardView: View {
    let card: CardData
    @Environment(\.dismiss) private var dismiss

    private let gold     = Color(hex: "#c9a84c")
    private let cream    = Color(hex: "#e8d5b7")
    private let bg       = Color(hex: "#0c0905")
    private let bgInner  = Color(hex: "#100d09")

    var typeLabel: String {
        switch card.type {
        case "restaurant", "food": return "推薦清單"
        case "contract":           return "合約摘要"
        case "report":             return "報　　告"
        case "document":           return "文　　件"
        case "meeting":            return "會議記錄"
        default:                   return "備　　忘"
        }
    }

    var body: some View {
        ZStack {
            bg.ignoresSafeArea()

            VStack(spacing: 0) {
                // ── 關閉列 ──────────────────────────────────────
                HStack {
                    Spacer()
                    Button(action: { dismiss() }) {
                        Image(systemName: "xmark")
                            .font(.system(size: 12, weight: .ultraLight))
                            .foregroundColor(gold.opacity(0.5))
                            .frame(width: 36, height: 36)
                            .background(gold.opacity(0.06))
                            .clipShape(Circle())
                    }
                    .padding(.trailing, 24)
                    .padding(.top, 20)
                }

                ScrollView(showsIndicators: false) {
                    VStack(spacing: 0) {
                        // ── 頂部花飾 ────────────────────────────
                        VStack(spacing: 10) {
                            ornamentLine
                            Text("A · L · F · R · E · D")
                                .font(.system(size: 9, weight: .medium))
                                .foregroundColor(gold.opacity(0.45))
                                .kerning(4)
                            ornamentLine
                        }
                        .padding(.top, 12)
                        .padding(.bottom, 28)

                        // ── 類型標籤 ────────────────────────────
                        Text(typeLabel)
                            .font(.system(size: 10, weight: .medium))
                            .foregroundColor(gold.opacity(0.6))
                            .kerning(5)
                            .padding(.bottom, 20)

                        // ── 標題 ────────────────────────────────
                        Text(card.title ?? "")
                            .font(.system(size: 22, weight: .thin))
                            .foregroundColor(cream)
                            .multilineTextAlignment(.center)
                            .lineSpacing(6)
                            .padding(.horizontal, 24)
                            .padding(.bottom, 28)

                        // ── 金線分隔 ─────────────────────────────
                        goldDivider
                            .padding(.bottom, 28)

                        // ── 內容區 ──────────────────────────────
                        contentBody
                            .padding(.horizontal, 4)

                        // ── 底部裝飾 ─────────────────────────────
                        VStack(spacing: 10) {
                            goldDivider
                                .padding(.top, 32)
                            Text(Date().formatted(.dateTime.year().month().day().locale(.init(identifier: "zh_TW"))))
                                .font(.system(size: 9, weight: .light))
                                .foregroundColor(gold.opacity(0.3))
                                .kerning(2)
                            ornamentDiamond
                        }
                        .padding(.bottom, 60)
                    }
                    .padding(.horizontal, 28)
                }
            }
        }
    }

    // ── 內容渲染：自動辨識清單 vs 純文字 ──────────────────────
    @ViewBuilder
    private var contentBody: some View {
        let lines = (card.content ?? "").components(separatedBy: "\n")
        VStack(alignment: .leading, spacing: 0) {
            ForEach(Array(lines.enumerated()), id: \.offset) { idx, line in
                let trimmed = line.trimmingCharacters(in: .whitespaces)
                if trimmed.isEmpty {
                    Spacer().frame(height: 10)
                } else if trimmed.hasPrefix("# ") {
                    // 子標題
                    Text(trimmed.dropFirst(2))
                        .font(.system(size: 12, weight: .medium))
                        .foregroundColor(gold.opacity(0.8))
                        .kerning(2)
                        .padding(.top, 20)
                        .padding(.bottom, 8)
                        .frame(maxWidth: .infinity, alignment: .leading)
                } else if let entry = parseListEntry(trimmed) {
                    // 清單項目（邀請函條目樣式）
                    listEntryRow(index: entry.index, name: entry.name,
                                 detail: entry.detail, phone: entry.phone)
                        .padding(.bottom, 14)
                } else {
                    // 一般段落
                    Text(trimmed)
                        .font(.system(size: 14, weight: .light))
                        .foregroundColor(cream.opacity(0.85))
                        .lineSpacing(7)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .padding(.bottom, 6)
                }
            }
        }
    }

    // ── 清單條目 ─────────────────────────────────────────────
    private func listEntryRow(index: String, name: String,
                               detail: String?, phone: String?) -> some View {
        HStack(alignment: .top, spacing: 14) {
            // 序號章
            ZStack {
                Circle()
                    .stroke(gold.opacity(0.35), lineWidth: 0.5)
                    .frame(width: 24, height: 24)
                Text(index)
                    .font(.system(size: 9, weight: .medium))
                    .foregroundColor(gold.opacity(0.7))
                    .kerning(0.5)
            }
            .padding(.top, 2)

            VStack(alignment: .leading, spacing: 4) {
                Text(name)
                    .font(.system(size: 15, weight: .regular))
                    .foregroundColor(cream)
                if let detail = detail, !detail.isEmpty {
                    Text(detail)
                        .font(.system(size: 11, weight: .light))
                        .foregroundColor(gold.opacity(0.55))
                        .kerning(0.3)
                }
                if let phone = phone, !phone.isEmpty {
                    HStack(spacing: 5) {
                        Image(systemName: "phone")
                            .font(.system(size: 9))
                            .foregroundColor(gold.opacity(0.4))
                        Text(phone)
                            .font(.system(size: 11, weight: .light))
                            .foregroundColor(gold.opacity(0.55))
                    }
                }
            }
            Spacer()
        }
        .padding(.vertical, 10)
        .padding(.horizontal, 14)
        .background(
            RoundedRectangle(cornerRadius: 2)
                .fill(gold.opacity(0.04))
                .overlay(
                    RoundedRectangle(cornerRadius: 2)
                        .stroke(gold.opacity(0.1), lineWidth: 0.5)
                )
        )
    }

    // ── 清單行解析：「1. 店名（地址）☎ 電話」 ─────────────────
    private struct ListEntry {
        let index: String; let name: String
        let detail: String?; let phone: String?
    }
    private func parseListEntry(_ s: String) -> ListEntry? {
        guard let dotRange = s.range(of: ". "),
              let idx = Int(s[s.startIndex..<dotRange.lowerBound]),
              idx >= 1, idx <= 20 else { return nil }
        var rest = String(s[dotRange.upperBound...])
        var phone: String? = nil
        if let phoneMarker = rest.range(of: "☎ ") {
            phone = String(rest[phoneMarker.upperBound...]).trimmingCharacters(in: .whitespaces)
            rest = String(rest[..<phoneMarker.lowerBound]).trimmingCharacters(in: .whitespaces)
        }
        var name = rest; var detail: String? = nil
        if let ps = rest.range(of: "（"), let pe = rest.range(of: "）") {
            name   = String(rest[..<ps.lowerBound]).trimmingCharacters(in: .whitespaces)
            detail = String(rest[ps.upperBound..<pe.lowerBound])
        }
        return ListEntry(index: "\(idx)", name: name, detail: detail, phone: phone)
    }

    // ── 裝飾元件 ─────────────────────────────────────────────
    private var ornamentLine: some View {
        HStack(spacing: 6) {
            line; diamond; line
        }
    }
    private var line: some View {
        Rectangle()
            .fill(gold.opacity(0.25))
            .frame(height: 0.5)
    }
    private var diamond: some View {
        Text("◆")
            .font(.system(size: 5))
            .foregroundColor(gold.opacity(0.4))
    }
    private var goldDivider: some View {
        HStack(spacing: 8) {
            Rectangle().fill(gold.opacity(0.15)).frame(height: 0.5)
            Text("✦")
                .font(.system(size: 7))
                .foregroundColor(gold.opacity(0.35))
            Rectangle().fill(gold.opacity(0.15)).frame(height: 0.5)
        }
    }
    private var ornamentDiamond: some View {
        Text("◆  ◆  ◆")
            .font(.system(size: 5))
            .foregroundColor(gold.opacity(0.2))
            .kerning(4)
    }
}

// MARK: - 翻譯覆層（給對方看的大字）
struct TranslationOverlayView: View {
    let overlay: TranslationOverlay

    var body: some View {
        ZStack {
            Color.black.opacity(0.92).ignoresSafeArea()
            VStack(spacing: 24) {
                Text(langLabel)
                    .font(.system(size: 13, weight: .medium))
                    .foregroundColor(Color(hex: "#c9a84c80"))
                    .letterSpacing(2)
                Text(overlay.text)
                    .font(.system(size: 36, weight: .light))
                    .foregroundColor(Color(hex: "#e8d5b7"))
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, 32)
                    .lineSpacing(10)
            }
        }
    }

    var langLabel: String {
        switch overlay.lang {
        case "en": return "ENGLISH"
        case "ja": return "日本語"
        case "ko": return "한국어"
        case "fr": return "FRANÇAIS"
        case "es": return "ESPAÑOL"
        case "de": return "DEUTSCH"
        case "th": return "ภาษาไทย"
        default:   return overlay.lang.uppercased()
        }
    }
}

// MARK: - Helpers
extension Color {
    init(hex: String) {
        let h = hex.trimmingCharacters(in: CharacterSet.alphanumerics.inverted)
        var int: UInt64 = 0
        Scanner(string: h).scanHexInt64(&int)
        let a, r, g, b: UInt64
        switch h.count {
        case 6: (a, r, g, b) = (255, int >> 16, int >> 8 & 0xFF, int & 0xFF)
        case 8: (a, r, g, b) = (int >> 24, int >> 16 & 0xFF, int >> 8 & 0xFF, int & 0xFF)
        default: (a, r, g, b) = (255, 0, 0, 0)
        }
        self.init(.sRGB,
                  red: Double(r) / 255,
                  green: Double(g) / 255,
                  blue: Double(b) / 255,
                  opacity: Double(a) / 255)
    }
}

extension Text {
    func letterSpacing(_ spacing: CGFloat) -> some View {
        self.kerning(spacing)
    }
}
