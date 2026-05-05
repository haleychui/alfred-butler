import SwiftUI
import JavaScriptCore

// MARK: - Engineering Calculator Sub-App
// 完全離線，JavaScriptCore 計算，不經 LLM

struct CalculatorSubAppView: View {
    let config   : SubAppConfig
    let onDismiss: () -> Void

    @StateObject private var calc = MathEngine()
    @State private var expression: String = ""
    @State private var showEngineeringPanel = false
    @FocusState private var inputFocused: Bool

    private let gold  = Color(hex: "#c9a84c")
    private let cream = Color(hex: "#e8d5b7")
    private let dim   = Color(hex: "#e8d5b7").opacity(0.45)

    var body: some View {
        VStack(spacing: 0) {
            header
            resultDisplay
            Divider().background(gold.opacity(0.15)).padding(.horizontal, 24)
            expressionInput
            if showEngineeringPanel { engineeringPanel }
            numpadSection
            Spacer().frame(height: 12)
        }
        .background(Color(hex: "#0c0905").ignoresSafeArea())
        .onAppear {
            expression = config.expression ?? ""
            if !expression.isEmpty { calc.evaluate(expression) }
        }
    }

    // MARK: Header
    private var header: some View {
        HStack {
            VStack(alignment: .leading, spacing: 2) {
                Text("C A L C U L A T O R").font(.system(size: 9, weight: .medium))
                    .foregroundColor(gold.opacity(0.5)).kerning(4)
                Text("工程計算機").font(.system(size: 16, weight: .thin)).foregroundColor(cream)
            }
            Spacer()
            // 工程面板切換
            Button(action: { showEngineeringPanel.toggle() }) {
                Text("f(x)").font(.system(size: 12, weight: .medium))
                    .foregroundColor(showEngineeringPanel ? gold : gold.opacity(0.4))
                    .frame(width: 36, height: 32)
                    .background(showEngineeringPanel ? gold.opacity(0.12) : gold.opacity(0.05))
                    .clipShape(RoundedRectangle(cornerRadius: 2))
            }.padding(.trailing, 8)
            Button(action: onDismiss) {
                Image(systemName: "xmark").font(.system(size: 12, weight: .ultraLight))
                    .foregroundColor(gold.opacity(0.5)).frame(width: 32, height: 32)
                    .background(gold.opacity(0.06)).clipShape(Circle())
            }
        }
        .padding(.horizontal, 24).padding(.vertical, 16)
    }

    // MARK: Result Display
    private var resultDisplay: some View {
        VStack(alignment: .trailing, spacing: 4) {
            // 歷史記錄（最後一筆）
            if let last = calc.history.last, last.expr != expression {
                Text(last.expr + " = " + last.result)
                    .font(.system(size: 11, weight: .ultraLight))
                    .foregroundColor(gold.opacity(0.3))
                    .lineLimit(1).truncationMode(.head)
                    .frame(maxWidth: .infinity, alignment: .trailing)
            }
            // 當前結果
            Text(calc.result.isEmpty ? "0" : calc.result)
                .font(.system(size: calc.result.count > 12 ? 28 : 44, weight: .thin))
                .foregroundColor(calc.isError ? Color(hex: "#d44") : cream)
                .minimumScaleFactor(0.5)
                .lineLimit(1)
                .frame(maxWidth: .infinity, alignment: .trailing)
                .contentTransition(.numericText())
                .animation(.spring(response: 0.25), value: calc.result)
        }
        .padding(.horizontal, 28).padding(.vertical, 12)
    }

    // MARK: Expression Input
    private var expressionInput: some View {
        HStack(spacing: 8) {
            TextField("輸入算式", text: $expression)
                .font(.system(size: 16, weight: .light, design: .monospaced))
                .foregroundColor(cream)
                .tint(gold)
                .focused($inputFocused)
                .onChange(of: expression) { _, val in calc.evaluateLive(val) }
                .onSubmit { calc.evaluate(expression); calc.addToHistory(expression) }
            if !expression.isEmpty {
                Button(action: {
                    expression = String(expression.dropLast())
                    calc.evaluateLive(expression)
                }) {
                    Image(systemName: "delete.left").font(.system(size: 14, weight: .ultraLight))
                        .foregroundColor(gold.opacity(0.5))
                }
            }
        }
        .padding(.horizontal, 24).padding(.vertical, 12)
        .background(gold.opacity(0.04))
    }

    // MARK: Engineering Panel (三個分頁：三角/矩陣/化學)
    @State private var engTab = 0

    private var engineeringPanel: some View {
        VStack(spacing: 6) {
            // 分頁選擇
            HStack(spacing: 0) {
                ForEach(["三角/指數", "矩陣/複數", "化學/物理"], id: \.self) { tab in
                    let idx = ["三角/指數", "矩陣/複數", "化學/物理"].firstIndex(of: tab)!
                    Button(action: { engTab = idx }) {
                        Text(tab).font(.system(size: 9, weight: .medium))
                            .foregroundColor(engTab == idx ? gold : gold.opacity(0.35))
                            .kerning(1)
                            .frame(maxWidth: .infinity).padding(.vertical, 6)
                            .background(engTab == idx ? gold.opacity(0.1) : Color.clear)
                    }
                }
            }
            .background(gold.opacity(0.04))
            .overlay(Rectangle().fill(gold.opacity(0.12)).frame(height: 0.5), alignment: .bottom)

            switch engTab {
            case 0: // 三角/指數
                engRow(["sin°", "cos°", "tan°", "asin°", "acos°", "atan°"])
                engRow(["sinr", "cosr", "tanr", "log₁₀", "ln",    "log₂"])
                engRow(["√",    "∛",    "x²",   "x³",    "xⁿ",   "|x|"])
                engRow(["π",    "e",    "!",    "nPr",   "nCr",  "mod"])
            case 1: // 矩陣/複數
                engRow(["det2", "det3", "inv2", "solve2","matmul",""])
                engRow(["ci",   "cabs", "carg", "cconj", "nDiff", "nInt"])
                engRow(["mean", "std",  "var",  "sum",   "min",   "max"])
                engRow(["gcd",  "lcm",  "isprime","bin", "oct",   "hex"])
            default: // 化學/物理
                engRow(["MW",   "pH",   "pOH",  "PV_n", "molar", "dilute"])
                engRow(["Ek",   "Ep",   "F=ma", "Q=mc", "P=IV",  "Ohm"])
                engRow(["H",    "C",    "N",    "O",    "Na",    "Cl"])
                engRow(["Fe",   "Cu",   "Zn",   "Ca",   "Mg",    "Si"])
            }
        }
        .padding(.horizontal, 16).padding(.vertical, 8)
        .background(gold.opacity(0.03))
    }

    private func engRow(_ items: [String]) -> some View {
        HStack(spacing: 6) {
            ForEach(items, id: \.self) { label in
                engKey(label)
            }
        }
    }

    private func engKey(_ label: String) -> some View {
        Button(action: { insertEngToken(label) }) {
            Text(label)
                .font(.system(size: 11, weight: .medium, design: .monospaced))
                .foregroundColor(gold.opacity(0.75))
                .frame(maxWidth: .infinity)
                .frame(height: 32)
                .background(gold.opacity(0.06))
                .overlay(RoundedRectangle(cornerRadius: 2).stroke(gold.opacity(0.12), lineWidth: 0.5))
                .clipShape(RoundedRectangle(cornerRadius: 2))
        }
    }

    // MARK: Numpad
    private var numpadSection: some View {
        VStack(spacing: 6) {
            numRow(["C",  "(",  ")",  "÷"])
            numRow(["7",  "8",  "9",  "×"])
            numRow(["4",  "5",  "6",  "−"])
            numRow(["1",  "2",  "3",  "+"])
            numRow(["0",  ".",  "ANS", "="])
        }
        .padding(.horizontal, 16).padding(.vertical, 10)
    }

    private func numRow(_ items: [String]) -> some View {
        HStack(spacing: 6) {
            ForEach(items, id: \.self) { key in numKey(key) }
        }
    }

    private func numKey(_ key: String) -> some View {
        let isOp  = ["÷","×","−","+","=","C","ANS"].contains(key)
        let isEq  = key == "="
        return Button(action: { handleKey(key) }) {
            Text(key)
                .font(.system(size: isOp ? 18 : 20, weight: isEq ? .regular : .ultraLight))
                .foregroundColor(isEq ? Color(hex: "#0c0905") : (isOp ? gold : cream))
                .frame(maxWidth: .infinity)
                .frame(height: 58)
                .background(
                    isEq ? gold :
                    isOp ? gold.opacity(0.1) :
                    Color(hex: "#e8d5b7").opacity(0.05)
                )
                .overlay(RoundedRectangle(cornerRadius: 2).stroke(gold.opacity(0.1), lineWidth: 0.5))
                .clipShape(RoundedRectangle(cornerRadius: 2))
        }
    }

    // MARK: Key Handlers
    private func handleKey(_ key: String) {
        switch key {
        case "C":
            expression = ""; calc.result = ""; calc.isError = false
        case "=":
            calc.evaluate(expression)
            calc.addToHistory(expression)
        case "ANS":
            expression += calc.lastAnswer
        case "÷": expression += "÷"
        case "×": expression += "×"
        case "−": expression += "−"
        default:
            expression += key
        }
        if key != "=" && key != "C" { calc.evaluateLive(expression) }
    }

    private func insertEngToken(_ token: String) {
        switch token {
        case "sin°":  expression += "sin("
        case "cos°":  expression += "cos("
        case "tan°":  expression += "tan("
        case "asin°": expression += "asin("
        case "acos°": expression += "acos("
        case "atan°": expression += "atan("
        case "sin_r": expression += "sinr("
        case "cos_r": expression += "cosr("
        case "tan_r": expression += "tanr("
        case "log₁₀": expression += "log("
        case "ln":    expression += "ln("
        case "log₂":  expression += "log2("
        case "√":     expression += "sqrt("
        case "∛":     expression += "cbrt("
        case "x²":    expression += "^2"
        case "x³":    expression += "^3"
        case "xⁿ":    expression += "^"
        case "|x|":   expression += "abs("
        case "π":     expression += "π"
        case "e":     expression += "e"
        case "!":     expression += "!"
        case "mod":   expression += " mod "
        default:      expression += token
        }
        calc.evaluateLive(expression)
    }
}

// MARK: - Math Engine (JavaScriptCore)

@MainActor
class MathEngine: ObservableObject {
    @Published var result: String = ""
    @Published var isError: Bool = false
    @Published var history: [HistoryEntry] = []
    var lastAnswer: String = "0"

    private let ctx: JSContext = {
        let c = JSContext()!
        c.evaluateScript(MathEngine.prelude)
        return c
    }()

    struct HistoryEntry: Identifiable {
        let id = UUID()
        let expr: String
        let result: String
    }

    func evaluateLive(_ expr: String) {
        guard !expr.isEmpty else { result = ""; isError = false; return }
        let r = rawEval(expr)
        if r.starts(with: "ERR") { isError = false; result = "" }
        else { result = r; isError = false }
    }

    func evaluate(_ expr: String) {
        guard !expr.isEmpty else { return }
        let r = rawEval(expr)
        if r.starts(with: "ERR") { result = r.dropFirst(4).description; isError = true }
        else { result = r; isError = false; lastAnswer = r }
    }

    func addToHistory(_ expr: String) {
        guard !result.isEmpty, !isError else { return }
        history.append(HistoryEntry(expr: expr, result: result))
        if history.count > 50 { history.removeFirst() }
        ctx.evaluateScript("ans = \(result);")
    }

    private func rawEval(_ raw: String) -> String {
        var e = raw
            .replacingOccurrences(of: "÷", with: "/")
            .replacingOccurrences(of: "×", with: "*")
            .replacingOccurrences(of: "−", with: "-")
            .replacingOccurrences(of: "^", with: "**")
            .replacingOccurrences(of: "π", with: "Math.PI")
            .replacingOccurrences(of: "°", with: "")
            .replacingOccurrences(of: "√", with: "sqrt")
            .replacingOccurrences(of: " mod ", with: "%")

        // x! → factorial(x)
        if let m = e.range(of: #"(\d+)!"#, options: .regularExpression) {
            let n = e[m].dropLast()
            e = e.replacingCharacters(in: m, with: "factorial(\(n))")
        }

        guard let val = ctx.evaluateScript(e), !val.isUndefined, !val.isNull else {
            return "ERR: 無法解析"
        }
        let d = val.toDouble()
        if d.isNaN      { return "ERR: 無效運算" }
        if d.isInfinite { return d > 0 ? "∞" : "-∞" }
        if d == d.rounded() && abs(d) < 1e15 { return String(Int(d)) }
        // 最多 10 位有效數字
        let s = String(format: "%.10g", d)
        return s
    }

    private static let prelude = """
    var ans = 0;
    var pi  = Math.PI;
    var e   = Math.E;
    // 角度版（預設，最常用）
    function sin(x)  { return Math.sin(x * Math.PI / 180); }
    function cos(x)  { return Math.cos(x * Math.PI / 180); }
    function tan(x)  { return Math.tan(x * Math.PI / 180); }
    function asin(x) { return Math.asin(x) * 180 / Math.PI; }
    function acos(x) { return Math.acos(x) * 180 / Math.PI; }
    function atan(x) { return Math.atan(x) * 180 / Math.PI; }
    // 弧度版
    function sinr(x) { return Math.sin(x); }
    function cosr(x) { return Math.cos(x); }
    function tanr(x) { return Math.tan(x); }
    // 其他
    function sqrt(x)       { return Math.sqrt(x); }
    function cbrt(x)       { return Math.cbrt(x); }
    function log(x)        { return Math.log10(x); }
    function log2(x)       { return Math.log2(x); }
    function ln(x)         { return Math.log(x); }
    function exp(x)        { return Math.exp(x); }
    function abs(x)        { return Math.abs(x); }
    function floor(x)      { return Math.floor(x); }
    function ceil(x)       { return Math.ceil(x); }
    function round(x)      { return Math.round(x); }
    function pow(x, y)     { return Math.pow(x, y); }
    function hypot(a, b)   { return Math.hypot(a, b); }
    function factorial(n)  {
        if (n < 0)  return NaN;
        if (n > 20) return Infinity;
        var r = 1; for (var i = 2; i <= n; i++) r *= i; return r;
    }
    function perm(n, r)    { return factorial(n) / factorial(n - r); }
    function comb(n, r)    { return factorial(n) / (factorial(r) * factorial(n - r)); }
    // 工程常用
    function dBm(mW)       { return 10 * Math.log10(mW); }
    function mW(dBm)       { return Math.pow(10, dBm / 10); }
    function toRad(deg)    { return deg * Math.PI / 180; }
    function toDeg(rad)    { return rad * 180 / Math.PI; }
    function ftoc(f)       { return (f - 32) * 5 / 9; }
    function ctof(c)       { return c * 9 / 5 + 32; }
    function kmToMile(km)  { return km * 0.621371; }
    function mileToKm(mi)  { return mi * 1.60934; }
    function kgToLb(kg)    { return kg * 2.20462; }
    function lbToKg(lb)    { return lb * 0.453592; }
    """
}
