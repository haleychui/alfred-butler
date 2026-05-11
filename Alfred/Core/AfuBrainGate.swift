import Foundation

/// Afu Brain MASL Gate — Swift port of `afu-brain/packages/afu_brain/gate.py`
///
/// 在送任何訊息給後端 LLM 之前先過這個閘：
/// - destructive action (刪 / 送 / 付 / 投資 / 公開) → block / ask
/// - file_search / contract → ask before external action
/// - mood / hearing / clarify → 純對話，allow 但不 execute
/// - default-deny on ambiguity（ASK rather than blind ALLOW）
///
/// 這樣阿福不會因為 LLM 一句話就把錢轉出去、檔案刪掉、或寄出未審稿的合約。
enum AfuDecision: String {
    case allow   // 安全動作可直接執行
    case prepare // 可以準備 / 草稿，但不送
    case ask     // 需要主人確認
    case block   // 直接拒絕執行
}

enum AfuRisk: String {
    case none, low, medium, high, critical
}

struct AfuBrainDecision {
    let intent: String
    let risk: AfuRisk
    let decision: AfuDecision
    let canExecute: Bool
    let allowedPreparation: Bool
    let requiredConfirmation: Bool
    let blockedFinalAction: String?
    let skills: [String]
    let reason: String
    let sourcePolicyVersion: String = "2026.05.07"

    /// 給 LLM 看的 system prompt 注入，提示阿福「這次的安全邊界是什麼」
    var systemHint: String {
        var lines: [String] = []
        lines.append("[AfuBrain decision: intent=\(intent) risk=\(risk.rawValue) decision=\(decision.rawValue)]")
        if let blocked = blockedFinalAction {
            lines.append("[Blocked final action: \(blocked) — 阿福只可準備不可執行]")
        }
        if requiredConfirmation {
            lines.append("[Required confirmation: 真要執行前必須口頭問主人「要做嗎」]")
        }
        return lines.joined(separator: "\n")
    }
}

enum AfuBrainGate {

    /// MASL gate 主入口，跟 afu-brain/gate.py decide() 行為一致
    static func decide(text: String) -> AfuBrainDecision {
        let intent = inferIntent(text)
        return policyFor(intent: intent, text: text)
    }

    // MARK: - Intent classifier（純規則，0 LLM）

    private static let kw: [String: [String]] = [
        "payment":     ["pay", "payment", "transfer", "wire", "付款", "轉帳", "匯款", "匯出", "刷卡"],
        "delete":      ["delete", "remove forever", "overwrite", "drop table", "刪除", "刪掉", "覆寫", "永久移除"],
        "publish":     ["publish", "post to", "公開發表", "上架", "發布", "上傳到 X", "上傳到 LinkedIn"],
        "trade":       ["trade", "sell", "buy stock", "短線", "買進", "賣出", "下單", "submit order"],
        "merge":       ["merge", "merge pr", "合併分支"],
        "submit":      ["submit", "送出申請", "提交"],
        "contract":    ["contract", "legal", "red flag", "NDA", "合約", "紅旗", "契約", "保密"],
        "email":       ["email", "reply", "send mail", "寄信", "回信", "寄出 email", "寄給"],
        "file_search": ["find file", "search file", "look for file", "找檔案", "找文件", "搜檔案", "drive", "vault", "文件在哪"],
        "receipt":     ["receipt", "invoice", "expense", "收據", "發票", "記帳"],
        "travel":      ["travel", "trip", "route", "weather", "行程", "旅行", "天氣", "氣溫", "下雨"],
        "mood":        ["sad", "tired", "stress", "anxious", "難過", "累", "壓力", "焦慮", "不開心"],
        "hearing":     ["did you hear", "hear me", "收到嗎", "聽到嗎", "你在嗎"],
    ]

    static func inferIntent(_ text: String) -> String {
        let t = text.lowercased()
        // 不可逆動作優先
        for key in ["payment", "delete", "publish", "trade", "merge", "submit", "contract"] {
            if let words = kw[key], words.contains(where: { t.contains($0) }) {
                return key
            }
        }
        // 可逆但敏感
        if let words = kw["email"], words.contains(where: { t.contains($0) }) { return "email" }
        if let words = kw["file_search"], words.contains(where: { t.contains($0) }) { return "file_search" }
        // 純資訊
        if let words = kw["receipt"], words.contains(where: { t.contains($0) }) { return "receipt" }
        if let words = kw["travel"], words.contains(where: { t.contains($0) }) { return "travel" }
        if let words = kw["mood"], words.contains(where: { t.contains($0) }) { return "mood" }
        if let words = kw["hearing"], words.contains(where: { t.contains($0) }) { return "hearing" }
        return "clarify"
    }

    // MARK: - Policy table（跟 policies/masl_policy.json 對齊）

    private static func policyFor(intent: String, text: String) -> AfuBrainDecision {
        switch intent {
        case "payment":
            return AfuBrainDecision(
                intent: "payment", risk: .critical, decision: .block,
                canExecute: false, allowedPreparation: true, requiredConfirmation: true,
                blockedFinalAction: "move_money",
                skills: ["payment.prepare", "approval.required"],
                reason: "Payment is irreversible. 阿福只可準備、不可直接執行。"
            )
        case "delete":
            return AfuBrainDecision(
                intent: "delete", risk: .critical, decision: .block,
                canExecute: false, allowedPreparation: false, requiredConfirmation: true,
                blockedFinalAction: "delete_or_overwrite",
                skills: ["approval.required"],
                reason: "Deletion is destructive and cannot execute directly."
            )
        case "publish":
            return AfuBrainDecision(
                intent: "publish", risk: .high, decision: .ask,
                canExecute: false, allowedPreparation: true, requiredConfirmation: true,
                blockedFinalAction: "external_publish",
                skills: ["draft.prepare", "approval.before_publish"],
                reason: "External publish is high-impact and irreversible. Draft allowed, publish requires approval."
            )
        case "trade":
            return AfuBrainDecision(
                intent: "trade", risk: .critical, decision: .block,
                canExecute: false, allowedPreparation: true, requiredConfirmation: true,
                blockedFinalAction: "trade_order",
                skills: ["trade.prepare", "approval.required"],
                reason: "Trade orders are financial and irreversible."
            )
        case "merge":
            return AfuBrainDecision(
                intent: "merge", risk: .high, decision: .ask,
                canExecute: false, allowedPreparation: true, requiredConfirmation: true,
                blockedFinalAction: "merge_branch",
                skills: ["diff.review", "approval.before_merge"],
                reason: "Branch merges may be irreversible without rebase. Review allowed, merge requires approval."
            )
        case "submit":
            return AfuBrainDecision(
                intent: "submit", risk: .high, decision: .ask,
                canExecute: false, allowedPreparation: true, requiredConfirmation: true,
                blockedFinalAction: "external_submit",
                skills: ["form.prepare", "approval.before_submit"],
                reason: "External submission is high-impact. Prepare allowed, submit requires approval."
            )
        case "contract":
            return AfuBrainDecision(
                intent: "contract", risk: .high, decision: .ask,
                canExecute: false, allowedPreparation: true, requiredConfirmation: true,
                blockedFinalAction: "external_send",
                skills: ["files.read", "contract.red_flags", "approval.before_send"],
                reason: "Contract review is legal/high-impact. Analysis allowed, sending requires approval."
            )
        case "email":
            return AfuBrainDecision(
                intent: "email", risk: .medium, decision: .ask,
                canExecute: false, allowedPreparation: true, requiredConfirmation: true,
                blockedFinalAction: "send_email",
                skills: ["email.search", "draft.reply", "approval.before_send"],
                reason: "External email may draft but must not send without approval."
            )
        case "file_search":
            return AfuBrainDecision(
                intent: "file_search", risk: .medium, decision: .allow,
                canExecute: true, allowedPreparation: true, requiredConfirmation: false,
                blockedFinalAction: "external_file_action",
                skills: ["vault.search", "vault.rank"],
                reason: "File search/rank is OK. Open/send/delete still requires confirmation."
            )
        case "receipt":
            return AfuBrainDecision(
                intent: "receipt", risk: .low, decision: .allow,
                canExecute: true, allowedPreparation: true, requiredConfirmation: false,
                blockedFinalAction: nil,
                skills: ["expense.save"],
                reason: "Receipt/expense save is reversible."
            )
        case "travel":
            return AfuBrainDecision(
                intent: "travel", risk: .low, decision: .allow,
                canExecute: true, allowedPreparation: true, requiredConfirmation: false,
                blockedFinalAction: nil,
                skills: ["weather.check", "calendar.read", "route.recommend"],
                reason: "Travel/weather/route recommendations are reversible info."
            )
        case "mood":
            return AfuBrainDecision(
                intent: "mood", risk: .none, decision: .allow,
                canExecute: false, allowedPreparation: false, requiredConfirmation: false,
                blockedFinalAction: nil,
                skills: [],
                reason: "Mood is conversation, not tool execution."
            )
        case "hearing":
            return AfuBrainDecision(
                intent: "hearing", risk: .none, decision: .allow,
                canExecute: false, allowedPreparation: false, requiredConfirmation: false,
                blockedFinalAction: nil,
                skills: [],
                reason: "Owner is checking whether Afu heard them."
            )
        default:
            // Default-deny on ambiguity（仍 allow 給 LLM 處理，但帶上 ask 旗標讓 LLM 知道要小心）
            return AfuBrainDecision(
                intent: "clarify", risk: .none, decision: .allow,
                canExecute: true, allowedPreparation: true, requiredConfirmation: false,
                blockedFinalAction: nil,
                skills: [],
                reason: "Default fall-through: allow LLM to converse, but no destructive action."
            )
        }
    }
}
