import SwiftUI

struct ConsentView: View {
    var onAccept: () -> Void

    @State private var declined = false

    var body: some View {
        ZStack {
            Color(hex: "#090909").ignoresSafeArea()

            if declined {
                declinedBody
            } else {
                consentBody
            }
        }
    }

    private var consentBody: some View {
        ScrollView {
            VStack(spacing: 0) {
                Spacer().frame(height: 60)

                Text("🎩").font(.system(size: 52))
                    .padding(.bottom, 10)

                Text("A L F R E D")
                    .font(.system(size: 11, weight: .medium))
                    .foregroundColor(Color(hex: "#c9a84c80"))
                    .kerning(4)
                    .padding(.bottom, 32)

                Text("使用第三方 AI 服務聲明")
                    .font(.system(size: 18, weight: .semibold))
                    .foregroundColor(Color(hex: "#e8d5b7"))
                    .padding(.bottom, 8)

                Text("為提供智能助理功能，阿福會將您的語音、文字及上傳內容傳送至以下第三方 AI 服務進行處理：")
                    .font(.system(size: 14, weight: .light))
                    .foregroundColor(Color(hex: "#e8d5b7AA"))
                    .multilineTextAlignment(.center)
                    .lineSpacing(4)
                    .padding(.horizontal, 28)
                    .padding(.bottom, 28)

                // 單張綜合卡：列出所有第三方 AI 服務
                VStack(alignment: .leading, spacing: 14) {
                    HStack(spacing: 10) {
                        Text("🤖").font(.system(size: 22))
                        Text("阿福使用的 AI 服務")
                            .font(.system(size: 15, weight: .semibold))
                            .foregroundColor(Color(hex: "#c9a84c"))
                    }

                    VStack(alignment: .leading, spacing: 10) {
                        consentLine("OpenAI", "GPT-4o 對話 + Whisper 語音轉文字")
                        consentLine("Google Gemini", "輔助對話與圖像 / 照片分析")
                        consentLine("ElevenLabs", "語音合成（將阿福的回應轉為聲音）")
                    }

                    Text("您的資料僅用於產生回應，不會用於訓練模型。")
                        .font(.system(size: 12))
                        .foregroundColor(Color(hex: "#e8d5b780"))
                        .padding(.top, 4)
                }
                .padding(18)
                .background(Color(hex: "#ffffff07"))
                .overlay(
                    RoundedRectangle(cornerRadius: 12)
                        .stroke(Color(hex: "#c9a84c25"), lineWidth: 1)
                )
                .cornerRadius(12)
                .padding(.horizontal, 24)
                .padding(.bottom, 28)

                VStack(spacing: 6) {
                    Text("您的資料僅用於生成回應，不會用於訓練模型。")
                    Text("詳情請見隱私政策。")
                }
                .font(.system(size: 12))
                .foregroundColor(Color(hex: "#e8d5b750"))
                .multilineTextAlignment(.center)
                .padding(.horizontal, 32)
                .padding(.bottom, 36)

                Button(action: onAccept) {
                    ZStack {
                        RoundedRectangle(cornerRadius: 14)
                            .fill(Color(hex: "#c9a84c").opacity(0.85))
                        Text("同意並繼續使用阿福")
                            .font(.system(size: 16, weight: .semibold))
                            .foregroundColor(Color(hex: "#120e08"))
                    }
                    .frame(height: 52)
                }
                .padding(.horizontal, 32)

                Button(action: { declined = true }) {
                    Text("不同意")
                        .font(.system(size: 13))
                        .foregroundColor(Color(hex: "#c9a84c50"))
                }
                .padding(.top, 14)
                .padding(.bottom, 48)
            }
        }
    }

    private var declinedBody: some View {
        VStack(spacing: 20) {
            Spacer()
            Text("🎩").font(.system(size: 52))
            Text("阿福需要使用 AI 服務才能運作。\n如不同意，請解除安裝此 App。")
                .font(.system(size: 15, weight: .light))
                .foregroundColor(Color(hex: "#e8d5b7AA"))
                .multilineTextAlignment(.center)
                .lineSpacing(6)
                .padding(.horizontal, 32)
            Button(action: { declined = false }) {
                Text("返回")
                    .font(.system(size: 14))
                    .foregroundColor(Color(hex: "#c9a84c"))
            }
            Spacer()
        }
    }

    // 單卡內的單行：服務名 + 用途
    private func consentLine(_ name: String, _ purpose: String) -> some View {
        HStack(alignment: .top, spacing: 10) {
            Text("•")
                .foregroundColor(Color(hex: "#c9a84c"))
                .font(.system(size: 13, weight: .semibold))
            VStack(alignment: .leading, spacing: 2) {
                Text(name)
                    .font(.system(size: 13, weight: .semibold))
                    .foregroundColor(Color(hex: "#e8d5b7"))
                Text(purpose)
                    .font(.system(size: 12, weight: .light))
                    .foregroundColor(Color(hex: "#e8d5b7AA"))
            }
        }
    }

    private func serviceCard(icon: String, name: String, purpose: String) -> some View {
        HStack(alignment: .top, spacing: 14) {
            Text(icon)
                .font(.system(size: 26))
                .frame(width: 36)
                .padding(.top, 2)
            VStack(alignment: .leading, spacing: 4) {
                Text(name)
                    .font(.system(size: 15, weight: .semibold))
                    .foregroundColor(Color(hex: "#c9a84c"))
                Text(purpose)
                    .font(.system(size: 13, weight: .light))
                    .foregroundColor(Color(hex: "#e8d5b7AA"))
                    .lineSpacing(3)
            }
            Spacer()
        }
        .padding(16)
        .background(Color(hex: "#ffffff07"))
        .overlay(
            RoundedRectangle(cornerRadius: 12)
                .stroke(Color(hex: "#c9a84c25"), lineWidth: 1)
        )
        .cornerRadius(12)
    }
}
