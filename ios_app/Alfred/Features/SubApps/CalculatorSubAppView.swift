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
        // 三角（角度版）
        case "sin°":  expression += "sin("
        case "cos°":  expression += "cos("
        case "tan°":  expression += "tan("
        case "asin°": expression += "asin("
        case "acos°": expression += "acos("
        case "atan°": expression += "atan("
        // 三角（弧度版）
        case "sinr":  expression += "sinr("
        case "cosr":  expression += "cosr("
        case "tanr":  expression += "tanr("
        // 對數/指數
        case "log₁₀": expression += "log("
        case "ln":    expression += "ln("
        case "log₂":  expression += "log2("
        case "√":     expression += "sqrt("
        case "∛":     expression += "cbrt("
        case "x²":    expression += "**2"
        case "x³":    expression += "**3"
        case "xⁿ":    expression += "**"
        case "|x|":   expression += "abs("
        case "π":     expression += "π"
        case "e":     expression += "e"
        case "!":     expression += "!"
        case "nPr":   expression += "perm("
        case "nCr":   expression += "comb("
        case "mod":   expression += "%"
        // 矩陣
        case "det2":   expression = "det2([[a,b],[c,d]])"
        case "det3":   expression = "det3([[a,b,c],[d,e,f],[g,h,i]])"
        case "inv2":   expression = "inv2([[a,b],[c,d]])"
        case "solve2": expression = "solve2([[a,b],[c,d]],[e,f])"
        case "matmul": expression = "matmul([[1,0],[0,1]],[[x,y],[z,w]])"
        // 複數
        case "ci":    expression += "ci("
        case "cabs":  expression += "cabs("
        case "carg":  expression += "carg("
        case "cconj": expression += "cconj("
        // 數值微積分
        case "nDiff": expression = "nDiff(\"sin(x)\",\"x\",π/4)"
        case "nInt":  expression = "nInt(\"sin(x)\",0,π)"
        // 統計
        case "mean":  expression = "mean([1,2,3,4,5])"
        case "std":   expression = "stddev([1,2,3,4,5])"
        case "var":   expression = "variance([1,2,3,4,5])"
        case "sum":   expression = "sum([1,2,3,4,5])"
        case "min":   expression = "arraymin([1,2,3,4,5])"
        case "max":   expression = "arraymax([1,2,3,4,5])"
        // 數論
        case "gcd":      expression += "gcd("
        case "lcm":      expression += "lcm("
        case "isprime":  expression += "isprime("
        case "bin":      expression = "toBase(255,2)"
        case "oct":      expression = "toBase(255,8)"
        case "hex":      expression = "toBase(255,16)"
        // 化學
        case "MW":    expression = "MW(\"H2O\")"
        case "pH":    expression = "pH(0.001)"
        case "pOH":   expression = "pOH(0.001)"
        case "PV_n":  expression = "PV_n(101325,0.0224,298)"
        case "molar": expression = "molar(2,18.015)"
        case "dilute":expression = "dilute(1,100,500)"
        // 物理
        case "Ek":   expression = "0.5*m*v**2"
        case "Ep":   expression = "m*9.8*h"
        case "F=ma": expression = "F_ma(10,2)"
        case "Q=mc": expression = "Q_mc(1,4186,10)"
        case "P=IV": expression = "12*2"
        case "Ohm":  expression = "V/R"
        // 元素符號（插入MW用）
        case let el where ["H","C","N","O","Na","Cl","Fe","Cu","Zn","Ca","Mg","Si"].contains(el):
            if expression.hasSuffix("\"") || expression.hasSuffix(")") {
                expression = "MW(\"\(el)\")"
            } else if expression.hasPrefix("MW(\"") {
                let inner = expression.dropFirst(4).dropLast(2)
                expression = "MW(\"\(inner)\(el)\")"
            } else {
                expression += el
            }
        case "":  break
        default:  expression += token
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
    var ans = 0; var pi = Math.PI; var e = Math.E;

    // ── 基礎數學 ────────────────────────────────────────────────────────
    function sin(x)  { return Math.sin(x*Math.PI/180); }
    function cos(x)  { return Math.cos(x*Math.PI/180); }
    function tan(x)  { return Math.tan(x*Math.PI/180); }
    function asin(x) { return Math.asin(x)*180/Math.PI; }
    function acos(x) { return Math.acos(x)*180/Math.PI; }
    function atan(x) { return Math.atan(x)*180/Math.PI; }
    function atan2d(y,x){ return Math.atan2(y,x)*180/Math.PI; }
    function sinr(x) { return Math.sin(x); }
    function cosr(x) { return Math.cos(x); }
    function tanr(x) { return Math.tan(x); }
    function sqrt(x) { return Math.sqrt(x); }
    function cbrt(x) { return Math.cbrt(x); }
    function nthrt(x,n){ return Math.pow(x,1/n); }
    function log(x)  { return Math.log10(x); }
    function log2(x) { return Math.log2(x); }
    function ln(x)   { return Math.log(x); }
    function exp(x)  { return Math.exp(x); }
    function abs(x)  { return Math.abs(x); }
    function sign(x) { return Math.sign(x); }
    function floor(x){ return Math.floor(x); }
    function ceil(x) { return Math.ceil(x); }
    function round(x){ return Math.round(x); }
    function pow(x,y){ return Math.pow(x,y); }
    function hypot(a,b){ return Math.hypot(a,b); }
    function sinh(x) { return Math.sinh(x); }
    function cosh(x) { return Math.cosh(x); }
    function tanh(x) { return Math.tanh(x); }
    function factorial(n){
        if(n<0)return NaN; if(n>170)return Infinity;
        var r=1; for(var i=2;i<=n;i++)r*=i; return r;
    }
    function perm(n,r){ return factorial(n)/factorial(n-r); }
    function comb(n,r){ return factorial(n)/(factorial(r)*factorial(n-r)); }

    // ── 矩陣（2×2 / 3×3 / N×N LU）──────────────────────────────────────
    function det2(m){ return m[0][0]*m[1][1]-m[0][1]*m[1][0]; }
    function det3(m){
        return m[0][0]*(m[1][1]*m[2][2]-m[1][2]*m[2][1])
              -m[0][1]*(m[1][0]*m[2][2]-m[1][2]*m[2][0])
              +m[0][2]*(m[1][0]*m[2][1]-m[1][1]*m[2][0]);
    }
    function detN(m){
        var n=m.length, a=m.map(function(r){return r.slice();}), sign=1, det=1;
        for(var i=0;i<n;i++){
            var pivot=i;
            for(var j=i+1;j<n;j++) if(Math.abs(a[j][i])>Math.abs(a[pivot][i]))pivot=j;
            if(pivot!==i){var tmp=a[i];a[i]=a[pivot];a[pivot]=tmp;sign*=-1;}
            if(Math.abs(a[i][i])<1e-12)return 0;
            det*=a[i][i];
            for(var j=i+1;j<n;j++){
                var f=a[j][i]/a[i][i];
                for(var k=i;k<n;k++) a[j][k]-=f*a[i][k];
            }
        }
        return sign*det;
    }
    function det(m){ if(m.length===2)return det2(m); if(m.length===3)return det3(m); return detN(m); }
    function inv2(m){
        var d=det2(m); if(Math.abs(d)<1e-12)return "奇異矩陣";
        return [[m[1][1]/d,-m[0][1]/d],[-m[1][0]/d,m[0][0]/d]];
    }
    function matmul(A,B){
        var n=A.length,p=B[0].length,q=B.length,C=[];
        for(var i=0;i<n;i++){C[i]=[];for(var j=0;j<p;j++){C[i][j]=0;for(var k=0;k<q;k++)C[i][j]+=A[i][k]*B[k][j];}}
        return C;
    }
    function mattrans(A){ return A[0].map(function(_,i){return A.map(function(r){return r[i];}); }); }
    // Gauss-Jordan solve Ax=b
    function solve2(A,b){
        var a00=A[0][0],a01=A[0][1],a10=A[1][0],a11=A[1][1];
        var d=a00*a11-a01*a10; if(Math.abs(d)<1e-12)return "無解或無窮多解";
        return [(b[0]*a11-b[1]*a01)/d,(a00*b[1]-a10*b[0])/d];
    }
    function solve3(A,b){
        var n=3, aug=A.map(function(r,i){return r.concat([b[i]]);});
        for(var i=0;i<n;i++){
            var mx=i;for(var j=i+1;j<n;j++)if(Math.abs(aug[j][i])>Math.abs(aug[mx][i]))mx=j;
            var tmp=aug[i];aug[i]=aug[mx];aug[mx]=tmp;
            if(Math.abs(aug[i][i])<1e-12)return "無解或無窮多解";
            for(var j=0;j<n;j++)if(j!==i){var f=aug[j][i]/aug[i][i];for(var k=i;k<=n;k++)aug[j][k]-=f*aug[i][k];}
        }
        return aug.map(function(r){return r[n]/r[n-1<0?0:n-1];}).map(function(v,i){return aug[i][n]/aug[i][i];});
    }
    function trace(A){ var t=0; for(var i=0;i<A.length;i++)t+=A[i][i]; return t; }

    // ── 複數（{r,i} 物件）────────────────────────────────────────────────
    function ci(r,i){ return {r:r,i:i,toString:function(){
        if(this.i===0)return ""+this.r;
        if(this.r===0)return this.i+"i";
        return this.r+(this.i>=0?"+":"")+this.i+"i";
    }}; }
    function cadd(a,b){ return ci(a.r+b.r,a.i+b.i); }
    function csub(a,b){ return ci(a.r-b.r,a.i-b.i); }
    function cmul(a,b){ return ci(a.r*b.r-a.i*b.i,a.r*b.i+a.i*b.r); }
    function cdiv(a,b){ var d=b.r*b.r+b.i*b.i; return ci((a.r*b.r+a.i*b.i)/d,(a.i*b.r-a.r*b.i)/d); }
    function cabs(a){ return Math.sqrt(a.r*a.r+a.i*a.i); }
    function carg(a){ return Math.atan2(a.i,a.r)*180/Math.PI; }
    function cconj(a){ return ci(a.r,-a.i); }
    function cpow(a,n){ var r=Math.pow(cabs(a),n),th=carg(a)*Math.PI/180*n; return ci(r*Math.cos(th),r*Math.sin(th)); }
    function cexp(a){ var er=Math.exp(a.r); return ci(er*Math.cos(a.i),er*Math.sin(a.i)); }

    // ── 數值微積分 ───────────────────────────────────────────────────────
    function nDiff(fStr,varStr,x){
        var h=1e-7;
        var f=new Function(varStr,"return "+fStr+";");
        return (f(x+h)-f(x-h))/(2*h);
    }
    function nInt(fStr,a,b){
        var n=1000, h=(b-a)/n, s=0;
        var f=new Function("x","return "+fStr+";");
        for(var i=0;i<=n;i++){
            var x=a+i*h, w=(i===0||i===n)?1:(i%2===0?2:4);
            s+=w*f(x);
        }
        return s*h/3;
    }
    function nDiff2(fStr,varStr,x){
        var h=1e-5;
        var f=new Function(varStr,"return "+fStr+";");
        return (f(x+h)-2*f(x)+f(x-h))/(h*h);
    }
    // 數列求和
    function sigma(fStr,n1,n2){
        var f=new Function("n","return "+fStr+";");
        var s=0; for(var n=n1;n<=n2;n++)s+=f(n); return s;
    }

    // ── 統計 ─────────────────────────────────────────────────────────────
    function mean(a){ return a.reduce(function(s,x){return s+x;},0)/a.length; }
    function sum(a) { return a.reduce(function(s,x){return s+x;},0); }
    function variance(a){ var m=mean(a); return mean(a.map(function(x){return (x-m)*(x-m);})); }
    function stddev(a)  { return Math.sqrt(variance(a)); }
    function arraymin(a){ return Math.min.apply(null,a); }
    function arraymax(a){ return Math.max.apply(null,a); }
    function median(a){
        var s=a.slice().sort(function(x,y){return x-y;});
        var m=Math.floor(s.length/2);
        return s.length%2===0?(s[m-1]+s[m])/2:s[m];
    }
    function linreg(xs,ys){
        var n=xs.length,sx=sum(xs),sy=sum(ys);
        var sxx=sum(xs.map(function(x){return x*x;}));
        var sxy=xs.map(function(x,i){return x*ys[i];}).reduce(function(a,b){return a+b;},0);
        var b=(n*sxy-sx*sy)/(n*sxx-sx*sx);
        var a=(sy-b*sx)/n;
        return {slope:b,intercept:a};
    }

    // ── 數論 ─────────────────────────────────────────────────────────────
    function gcd(a,b){ a=Math.abs(a);b=Math.abs(b); while(b){var t=b;b=a%b;a=t;} return a; }
    function lcm(a,b){ return Math.abs(a*b)/gcd(a,b); }
    function isprime(n){
        if(n<2)return false; if(n<4)return true;
        if(n%2===0||n%3===0)return false;
        for(var i=5;i*i<=n;i+=6) if(n%i===0||n%(i+2)===0)return false;
        return true;
    }
    function toBase(n,base){ return (n>>>0).toString(base).toUpperCase(); }
    function fromBase(s,base){ return parseInt(s,base); }

    // ── 化學 ─────────────────────────────────────────────────────────────
    var _AW = {H:1.008,He:4.003,Li:6.941,Be:9.012,B:10.81,C:12.011,N:14.007,O:15.999,
               F:19.00,Ne:20.18,Na:22.99,Mg:24.31,Al:26.98,Si:28.09,P:30.97,S:32.06,
               Cl:35.45,Ar:39.95,K:39.10,Ca:40.08,Sc:44.96,Ti:47.87,V:50.94,Cr:52.00,
               Mn:54.94,Fe:55.85,Co:58.93,Ni:58.69,Cu:63.55,Zn:65.38,Ga:69.72,Ge:72.63,
               As:74.92,Se:78.97,Br:79.90,Kr:83.80,Rb:85.47,Sr:87.62,Y:88.91,Zr:91.22,
               Ag:107.87,Sn:118.71,I:126.90,Cs:132.91,Ba:137.33,Au:196.97,Hg:200.59,
               Pb:207.2,U:238.03};
    function MW(formula){
        // 解析化學式，支援 H2O, Ca(OH)2, C6H12O6 等
        function parse(s,pos){
            var mw=0;
            while(pos<s.length){
                if(s[pos]==="("){
                    var end=pos+1,depth=1;
                    while(depth>0){end++;if(s[end]==="(")depth++;if(s[end]===")")depth--;}
                    var inner=parse(s.slice(pos+1,end),0);
                    pos=end+1;
                    var num="";while(pos<s.length&&s[pos]>="0"&&s[pos]<="9"){num+=s[pos];pos++;}
                    mw+=inner*(num?parseInt(num):1);
                } else if(s[pos]>="A"&&s[pos]<="Z"){
                    var el=s[pos];pos++;
                    while(pos<s.length&&s[pos]>="a"&&s[pos]<="z"){el+=s[pos];pos++;}
                    var num="";while(pos<s.length&&s[pos]>="0"&&s[pos]<="9"){num+=s[pos];pos++;}
                    var aw=_AW[el];
                    if(aw===undefined)return "未知元素:"+el;
                    mw+=aw*(num?parseInt(num):1);
                } else break;
            }
            return mw;
        }
        var result=parse(formula,0);
        return typeof result==="number"?Math.round(result*1000)/1000:result;
    }
    function pH(conc)   { return -Math.log10(conc); }
    function pOH(conc)  { return -Math.log10(conc); }
    function pHfromKa(Ka,c){ return 0.5*(Math.log10(Ka)-Math.log10(c))*(-1); }
    // 理想氣體 PV=nRT，求 n (mol)
    function PV_n(P,V,T){ return P*V/(8.314*T); }
    // mol/L (摩爾濃度) = 質量g / (MW * 體積L)
    function molar(g,mw_){ return g/mw_; }
    // 稀釋公式 C1V1 = C2V2，求 C2
    function dilute(C1,V1,V2){ return C1*V1/V2; }
    // 反應熱 q = mcΔT
    function Q_mc(m,c,dT){ return m*c*dT; }
    // 動能 Ek = ½mv²
    function Ek(m,v){ return 0.5*m*v*v; }
    // 位能 Ep = mgh
    function Ep(m,g,h){ return m*(g||9.8)*h; }
    // F = ma
    function F_ma(m,a){ return m*a; }
    // 電功率 P = IV
    function P_iv(I,V){ return I*V; }
    // 歐姆定律 I = V/R
    function Ohm_I(V,R){ return V/R; }
    // 波長 λ = c/f
    function wavelength(f){ return 3e8/f; }
    // RC 時間常數
    function RC(R,C){ return R*C; }

    // ── 工程換算 ─────────────────────────────────────────────────────────
    function dBm(mW_){ return 10*Math.log10(mW_); }
    function mWfromdBm(d){ return Math.pow(10,d/10); }
    function toRad(d){ return d*Math.PI/180; }
    function toDeg(r){ return r*180/Math.PI; }
    function ftoc(f){ return (f-32)*5/9; }
    function ctof(c){ return c*9/5+32; }
    function kmToMile(k){ return k*0.621371; }
    function mileToKm(m){ return m*1.60934; }
    function kgToLb(k){ return k*2.20462; }
    function lbToKg(l){ return l*0.453592; }
    function inToCm(i){ return i*2.54; }
    function cmToIn(c){ return c/2.54; }
    function barToPa(b){ return b*1e5; }
    function psiToPa(p){ return p*6894.76; }
    """
}
