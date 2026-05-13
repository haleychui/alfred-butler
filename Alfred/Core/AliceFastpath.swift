import Foundation

/// Alice 風格 fastpath — 能繞過 LLM 就繞過去，0 token 0 延遲
///
/// 核心哲學（Alice repo README）：完成任務 > LLM 表演。
/// 簡單問題（時間 / 日期 / 數學 / 換算 / 溫度單位）本地秒答，不打 VPS chat。
///
/// 這個模組回 nil 代表「沒抓到 fastpath，繼續走 LLM」。
/// 回非 nil 代表「我已經算出答案，直接給主人聽」。
enum AliceFastpath {

    /// 嘗試 fastpath。如果回 nil，呼叫端要繼續走 LLM。
    static func tryAnswer(_ message: String) -> String? {
        let t = message.trimmingCharacters(in: .whitespacesAndNewlines)
        if t.isEmpty { return nil }

        // 1. 時間查詢
        if let r = answerTime(t) { return r }
        // 2. 日期查詢
        if let r = answerDate(t) { return r }
        // 3. 純數學
        if let r = answerMath(t) { return r }
        // 4. 單位換算
        if let r = answerUnitConvert(t) { return r }
        // 5. 簡短禮貌語（晚安 / 早安 / 謝謝）
        if let r = answerGreeting(t) { return r }

        return nil
    }

    // MARK: - 1. Time

    private static func answerTime(_ t: String) -> String? {
        let lt = t.lowercased()
        let isTimeQ = lt.contains("現在幾點") || lt.contains("幾點了") ||
                      lt.contains("what time") || lt.contains("現在時間") ||
                      lt == "幾點" || lt == "時間"
        guard isTimeQ else { return nil }

        let f = DateFormatter()
        f.locale = Locale(identifier: "zh_TW")
        f.dateFormat = "a h 點 mm 分"
        let now = f.string(from: Date())
        return "主人，現在是\(now)。"
    }

    // MARK: - 2. Date / Day

    private static func answerDate(_ t: String) -> String? {
        let lt = t.lowercased()
        let cal = Calendar(identifier: .gregorian)
        let now = Date()

        if lt.contains("今天幾號") || lt.contains("今天日期") || lt.contains("今天是幾號") {
            let f = DateFormatter()
            f.locale = Locale(identifier: "zh_TW")
            f.dateFormat = "M 月 d 日"
            return "主人，今天是\(f.string(from: now))。"
        }
        if lt.contains("今天禮拜") || lt.contains("今天星期") || lt.contains("今天週") {
            let weekdays = ["", "禮拜日", "禮拜一", "禮拜二", "禮拜三", "禮拜四", "禮拜五", "禮拜六"]
            let w = cal.component(.weekday, from: now)
            return "主人，今天是\(weekdays[w])。"
        }
        if lt.contains("明天禮拜") || lt.contains("明天星期") {
            let weekdays = ["", "禮拜日", "禮拜一", "禮拜二", "禮拜三", "禮拜四", "禮拜五", "禮拜六"]
            let tomorrow = cal.date(byAdding: .day, value: 1, to: now)!
            let w = cal.component(.weekday, from: tomorrow)
            return "主人，明天是\(weekdays[w])。"
        }
        if lt.contains("今年") && (lt.contains("民國幾年") || lt.contains("民國")) {
            let y = cal.component(.year, from: now) - 1911
            return "主人，今年是民國 \(y) 年。"
        }
        if lt.contains("今年") && (lt.contains("西元") || lt.contains("公元") || lt.contains("年份")) {
            let y = cal.component(.year, from: now)
            return "主人，今年是西元 \(y) 年。"
        }

        return nil
    }

    // MARK: - 3. Math

    /// 偵測純算式（含中英運算符 + 中文數字 + 折扣 + 平方）。能算就算。
    private static func answerMath(_ t: String) -> String? {
        // 先把中文數字 → 阿拉伯數字（一二三四五六七八九十百千萬）
        var s = chineseDigitsToArabic(t)
            .replacingOccurrences(of: "加上", with: "+")
            .replacingOccurrences(of: "加", with: "+")
            .replacingOccurrences(of: "減去", with: "-")
            .replacingOccurrences(of: "減", with: "-")
            .replacingOccurrences(of: "乘以", with: "*")
            .replacingOccurrences(of: "乘", with: "*")
            .replacingOccurrences(of: "除以", with: "/")
            .replacingOccurrences(of: "除", with: "/")
            .replacingOccurrences(of: "等於多少", with: "")
            .replacingOccurrences(of: "等於", with: "")
            .replacingOccurrences(of: "是多少", with: "")
            .replacingOccurrences(of: "多少", with: "")
            .replacingOccurrences(of: "?", with: "")
            .replacingOccurrences(of: "？", with: "")
            .replacingOccurrences(of: "。", with: "")
            .replacingOccurrences(of: " ", with: "")

        // === 1. 「3 的平方」 ===
        if let _ = s.range(of: #"^\d+的平方$"#, options: .regularExpression) {
            let n = Int(s.replacingOccurrences(of: "的平方", with: ""))!
            return "主人，\(n) 的平方是 \(n*n)。"
        }

        // === 2. 「打 N 折」/「N 折」/「N 元打 N 折」/「N 打 N 折」===
        // 不論有沒有「元」，不論順序，只要看到「打X折」就算
        if s.contains("打") && s.contains("折") {
            // 抓出所有數字
            let nums = s.split(whereSeparator: { !"0123456789.".contains($0) }).compactMap { Double($0) }
            if nums.count >= 2 {
                let price = nums[0]
                let discountRate = nums[1]
                // 一位數視為「X 折」(8 = 0.8)；兩位數視為已是 %（85 = 0.85）
                let ratio: Double = discountRate < 10 ? discountRate / 10.0 : discountRate / 100.0
                let result = price * ratio
                let resultStr = formatNumber(result)
                let priceStr = formatNumber(price)
                let discStr = formatNumber(discountRate)
                return "主人，\(priceStr) 打 \(discStr) 折是 \(resultStr) 元。"
            }
        }

        // === 3. 純算式 e.g. "1+1", "100*0.8" ===
        let mathRegex = try? NSRegularExpression(pattern: #"^[\d+\-*/().\s]+$"#)
        if let regex = mathRegex,
           regex.firstMatch(in: s, range: NSRange(s.startIndex..., in: s)) != nil,
           !s.isEmpty,
           s.contains(where: { "+-*/".contains($0) }) {
            let expr = NSExpression(format: s)
            if let r = expr.expressionValue(with: nil, context: nil) as? NSNumber {
                return "主人，\(s) = \(formatNumber(r.doubleValue))。"
            }
        }

        // === 4. 「N 分之 M」===
        if s.contains("分之") {
            let parts = s.components(separatedBy: "分之")
            if parts.count == 2,
               let denom = Double(parts[0].filter { "0123456789.".contains($0) }),
               let numer = Double(parts[1].filter { "0123456789.".contains($0) }),
               denom != 0 {
                return "主人，\(parts[1])/\(parts[0]) = \(formatNumber(numer/denom))。"
            }
        }

        return nil
    }

    /// 漂亮的數字輸出（整數不顯示 .0）
    private static func formatNumber(_ n: Double) -> String {
        if n.truncatingRemainder(dividingBy: 1) == 0 {
            return String(Int(n.rounded()))
        }
        return String(format: "%.2f", n)
    }

    /// 中文數字 → 阿拉伯數字（簡單實作，cover 「1299」「一千兩百九十九」這類）
    private static func chineseDigitsToArabic(_ s: String) -> String {
        // 簡單對應，STT 通常會出阿拉伯數字；這裡只做小數字 quick map
        // 跟「八折」「五折」這類常用單字數字
        let map: [String: String] = [
            "零": "0", "一": "1", "二": "2", "兩": "2", "三": "3", "四": "4",
            "五": "5", "六": "6", "七": "7", "八": "8", "九": "9", "十": "10"
        ]
        var out = s
        for (k, v) in map {
            out = out.replacingOccurrences(of: k, with: v)
        }
        return out
    }

    // MARK: - 4. Unit Convert

    private static func answerUnitConvert(_ t: String) -> String? {
        let lt = t.lowercased()
        if lt.contains("公斤") && lt.contains("磅") {
            return "主人，1 公斤大約等於 2.205 磅。"
        }
        if lt.contains("公里") && lt.contains("英里") {
            return "主人，1 公里大約等於 0.621 英里。"
        }
        if lt.contains("攝氏") && lt.contains("華氏") {
            return "主人，攝氏轉華氏的公式是 °F = °C × 9/5 + 32。"
        }
        return nil
    }

    // MARK: - 5. Greeting / Liveness

    /// 純社交查驗 / 簡單招呼 — 管家氣質的根本,應該秒答。
    /// 主人問「你還在嗎」應該 < 1s 從 voice_bank 預錄 mp3 播出來(Michael Caine 聲),
    /// 不該打 LLM,也不該打 ElevenLabs。
    /// 命中後 callsite 會問 voiceBankCategory(for:) 取對應預錄類別。
    private static let LIVENESS_PATTERNS: Set<String> = [
        "你還在嗎", "你還在", "你在嗎", "你在", "在不在", "還在嗎", "在嗎",
        "阿福你還在嗎", "阿福你在嗎", "阿福在嗎", "阿福你在", "阿福你還在",
        "阿福在不在", "你還活著嗎"
    ]
    private static let LIVENESS_REPLIES = [
        "主人，我在。請問有什麼需要我效勞的嗎?",
        "主人，我在，請吩咐。",
        "主人，在的。請說。",
        "主人，我一直都在。請問要做什麼?",
        "主人，我在，隨時為您效勞。"
    ]
    private static let GREETING_REPLIES = [
        "主人，您好。請問有什麼需要我效勞的嗎?",
        "主人好。請吩咐。",
        "主人您好。今天我能為您做什麼?"
    ]
    private static let MORNING_REPLIES = [
        "主人早安。今天有什麼需要我替您安排的嗎?",
        "主人早。請吩咐。"
    ]
    private static let NIGHT_REPLIES = [
        "主人晚安。今天辛苦了。",
        "主人，晚安。今天就先到這。"
    ]

    private static func answerGreeting(_ t: String) -> String? {
        let lt = t.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        let cal = Calendar.current
        let hour = cal.component(.hour, from: Date())

        // 移除標點
        var stripped = lt
        for p in ["。", ".", "?", "?", "!", "!", ",", ",", " "] {
            stripped = stripped.replacingOccurrences(of: p, with: "")
        }

        // 1. liveness 查驗(放寬到 20 字,因為「阿福你還在嗎」是 6 字)
        if stripped.count <= 20 && LIVENESS_PATTERNS.contains(stripped) {
            return LIVENESS_REPLIES.randomElement()!
        }

        // 2. 原有的「禮貌話 ≤ 4 字」邏輯,但用 voice_bank 風格的回應
        guard stripped.count <= 4 else { return nil }

        switch stripped {
        case "你好", "您好", "嗨", "嗨阿福", "阿福", "hi", "hello", "嘿", "hey":
            return GREETING_REPLIES.randomElement()!
        case "謝謝", "辛苦了":
            return "主人，能為您服務是阿福的本份。"
        case "晚安":
            return hour < 5 ? "主人，請早點休息。" : NIGHT_REPLIES.randomElement()!
        case "早安", "早", "早上好":
            return MORNING_REPLIES.randomElement()!
        case "午安", "中午好":
            return "主人，午安。請問需要我做什麼?"
        default:
            return nil
        }
    }

    /// 給 callsite 用 — 命中 fastpath 後問:這個 message 對應哪個 voice_bank category?
    /// 回 nil 表示「沒有對應預錄,請用 AVSpeechSynthesizer fallback」。
    /// 回 String 表示「請從 voice_bank/<category>_*.mp3 隨機抽一個播」。
    static func voiceBankCategory(for message: String) -> String? {
        let lt = message.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        var stripped = lt
        for p in ["。", ".", "?", "?", "!", "!", ",", ",", " "] {
            stripped = stripped.replacingOccurrences(of: p, with: "")
        }

        // liveness / 招呼 → ack_butler(101 個預錄「主人,我在」類)
        if LIVENESS_PATTERNS.contains(stripped) { return "ack_butler" }
        if stripped.count <= 4 {
            switch stripped {
            case "你好", "您好", "嗨", "嗨阿福", "阿福", "hi", "hello", "嘿", "hey":
                return "ack_butler"
            case "早安", "早", "早上好", "晚安", "午安", "中午好":
                return "greet_time"  // 50 個預錄問候類
            case "謝謝", "辛苦了":
                return "ack_butler"
            default:
                return nil
            }
        }
        return nil
    }
}
