import SwiftUI

// MARK: - 辦公室儀表板
struct OfficeDashboardView: View {
    @StateObject private var vm = OfficeViewModel.shared
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            ZStack {
                Color(hex: "#090909").ignoresSafeArea()

                if vm.isLoading && vm.eodWrap == nil {
                    loadingView
                } else {
                    ScrollView(showsIndicators: false) {
                        VStack(spacing: 16) {
                            eodCard
                            roomPulseCard
                            thanksCard
                            suppliesCard
                            teamCard
                            Spacer().frame(height: 24)
                        }
                        .padding(.horizontal, 16)
                        .padding(.top, 8)
                    }
                }
            }
            .navigationTitle("辦公室")
            .navigationBarTitleDisplayMode(.inline)
            .toolbarColorScheme(.dark, for: .navigationBar)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button(action: { dismiss() }) {
                        Image(systemName: "xmark")
                            .foregroundColor(Color(hex: "#c9a84c"))
                    }
                }
                ToolbarItem(placement: .topBarTrailing) {
                    HStack(spacing: 8) {
                        Text(vm.lastUpdatedText)
                            .font(.system(size: 11))
                            .foregroundColor(Color(hex: "#c9a84c60"))
                        if vm.isLoading {
                            ProgressView()
                                .tint(Color(hex: "#c9a84c"))
                                .scaleEffect(0.8)
                        } else {
                            Button(action: { Task { await vm.refresh() } }) {
                                Image(systemName: "arrow.clockwise")
                                    .foregroundColor(Color(hex: "#c9a84c"))
                                    .font(.system(size: 13))
                            }
                        }
                    }
                }
            }
        }
        .task { await vm.refresh() }
    }

    // MARK: - Loading
    var loadingView: some View {
        VStack(spacing: 16) {
            ProgressView()
                .tint(Color(hex: "#c9a84c"))
                .scaleEffect(1.2)
            Text("阿福正在整理辦公室狀況…")
                .font(.system(size: 14))
                .foregroundColor(Color(hex: "#c9a84c60"))
        }
    }

    // MARK: - EOD Wrap Card
    var eodCard: some View {
        OfficeCard(icon: "moon.stars", title: "下班收尾") {
            if let eod = vm.eodWrap {
                if eod.totalIssues == 0 {
                    statusRow(icon: "checkmark.circle", text: "今天乾淨收尾，沒有未了結的事", color: "#4CAF50")
                } else {
                    VStack(spacing: 8) {
                        if eod.openPromises > 0 {
                            statusRow(icon: "exclamationmark.circle",
                                      text: "承諾 \(eod.openPromises) 件未履行", color: "#FF6B6B")
                        }
                        if eod.pendingThanks > 0 {
                            statusRow(icon: "heart.circle",
                                      text: "\(eod.pendingThanks) 個人等你說謝謝", color: "#c9a84c")
                        }
                        if eod.pendingTodos > 0 {
                            statusRow(icon: "square.and.pencil",
                                      text: "待辦 \(eod.pendingTodos) 件還開著", color: "#e8d5b7")
                        }
                        if eod.lowSupplies > 0 {
                            statusRow(icon: "shippingbox",
                                      text: "\(eod.lowSupplies) 項耗材快沒了", color: "#FF9800")
                        }
                        if eod.openSubCommits > 0 {
                            statusRow(icon: "person.2",
                                      text: "對下屬 \(eod.openSubCommits) 個承諾未兌現", color: "#9C27B0")
                        }
                    }
                }
            } else {
                placeholderText("無資料")
            }
        }
    }

    // MARK: - Room Pulse Card
    var roomPulseCard: some View {
        OfficeCard(icon: "door.left.hand.open", title: "會議室感知") {
            if let pulse = vm.roomPulse {
                if pulse.count == 0 {
                    statusRow(icon: "checkmark.circle", text: "所有預約都有人進場", color: "#4CAF50")
                } else {
                    VStack(spacing: 8) {
                        ForEach(pulse.abandonedBookings.prefix(3)) { booking in
                            HStack {
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(booking.title)
                                        .font(.system(size: 14, weight: .medium))
                                        .foregroundColor(Color(hex: "#e8d5b7"))
                                    Text("\(booking.room ?? "未知會議室") · \(booking.startTime.prefix(16))")
                                        .font(.system(size: 11))
                                        .foregroundColor(Color(hex: "#c9a84c80"))
                                }
                                Spacer()
                                Button("釋出") {
                                    Task { await vm.releaseRoom(booking.bookingId) }
                                }
                                .font(.system(size: 12, weight: .medium))
                                .foregroundColor(Color(hex: "#090909"))
                                .padding(.horizontal, 12)
                                .padding(.vertical, 5)
                                .background(Color(hex: "#c9a84c"))
                                .cornerRadius(6)
                            }
                            .padding(.vertical, 4)
                        }
                    }
                }
            } else {
                placeholderText("無資料")
            }
        }
    }

    // MARK: - Thanks Card
    var thanksCard: some View {
        OfficeCard(icon: "heart", title: "感謝提醒") {
            if let thanks = vm.thanksNudge {
                if thanks.pending.isEmpty {
                    statusRow(icon: "checkmark.circle", text: "你都謝得很到位", color: "#4CAF50")
                } else {
                    VStack(spacing: 8) {
                        ForEach(thanks.pending.prefix(3)) { item in
                            HStack(alignment: .top) {
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(item.person)
                                        .font(.system(size: 14, weight: .medium))
                                        .foregroundColor(Color(hex: "#e8d5b7"))
                                    if !item.reason.isEmpty {
                                        Text(item.reason)
                                            .font(.system(size: 12))
                                            .foregroundColor(Color(hex: "#c9a84c80"))
                                    }
                                }
                                Spacer()
                                Text(item.date)
                                    .font(.system(size: 11))
                                    .foregroundColor(Color(hex: "#e8d5b740"))
                            }
                        }
                        if thanks.pending.count > 3 {
                            Text("還有 \(thanks.pending.count - 3) 位…")
                                .font(.system(size: 12))
                                .foregroundColor(Color(hex: "#c9a84c60"))
                        }
                    }
                }
            } else {
                placeholderText("無資料")
            }
        }
    }

    // MARK: - Supplies Card
    var suppliesCard: some View {
        OfficeCard(icon: "shippingbox", title: "耗材庫存") {
            if vm.supplies.isEmpty {
                placeholderText("尚未設定耗材，跟阿福說「新增耗材 XX 數量 Y」")
            } else if vm.lowSupplies.isEmpty {
                statusRow(icon: "checkmark.circle", text: "所有耗材庫存充足", color: "#4CAF50")
            } else {
                VStack(spacing: 8) {
                    ForEach(vm.lowSupplies.prefix(5)) { supply in
                        HStack {
                            Circle()
                                .fill(Color(hex: "#FF6B6B"))
                                .frame(width: 6, height: 6)
                            Text(supply.item)
                                .font(.system(size: 14))
                                .foregroundColor(Color(hex: "#e8d5b7"))
                            Spacer()
                            Text("剩 \(String(format: "%.0f", supply.quantity))\(supply.unit)")
                                .font(.system(size: 12))
                                .foregroundColor(Color(hex: "#FF6B6B"))
                        }
                    }
                    if vm.lowSupplies.count > 5 {
                        Text("還有 \(vm.lowSupplies.count - 5) 項…")
                            .font(.system(size: 12))
                            .foregroundColor(Color(hex: "#c9a84c60"))
                    }
                }
            }
        }
    }

    // MARK: - Team Card
    var teamCard: some View {
        OfficeCard(icon: "person.3", title: "團隊狀態") {
            VStack(spacing: 12) {
                // 沉默偵測
                if let radar = vm.silenceRadar {
                    if radar.silentColleagues.isEmpty {
                        statusRow(icon: "checkmark.circle",
                                  text: "所有人最近都有互動", color: "#4CAF50")
                    } else {
                        VStack(alignment: .leading, spacing: 6) {
                            HStack {
                                Image(systemName: "bell.slash")
                                    .foregroundColor(Color(hex: "#FF9800"))
                                    .font(.system(size: 13))
                                Text("沉默超過 \(radar.thresholdDays) 天")
                                    .font(.system(size: 13, weight: .medium))
                                    .foregroundColor(Color(hex: "#FF9800"))
                            }
                            ForEach(radar.silentColleagues.prefix(3)) { col in
                                HStack {
                                    Text("· \(col.name)")
                                        .font(.system(size: 13))
                                        .foregroundColor(Color(hex: "#e8d5b7"))
                                    if let role = col.role {
                                        Text("(\(role))")
                                            .font(.system(size: 11))
                                            .foregroundColor(Color(hex: "#c9a84c60"))
                                    }
                                    Spacer()
                                    if let days = col.daysSince {
                                        Text("\(days) 天前")
                                            .font(.system(size: 11))
                                            .foregroundColor(Color(hex: "#e8d5b740"))
                                    }
                                }
                            }
                        }
                        .frame(maxWidth: .infinity, alignment: .leading)
                    }
                }

                // 主管視角
                if let lens = vm.managerLens {
                    if !lens.openSubCommits.isEmpty || !lens.openPromises.isEmpty {
                        Divider()
                            .background(Color(hex: "#c9a84c20"))

                        VStack(alignment: .leading, spacing: 6) {
                            HStack {
                                Image(systemName: "exclamationmark.triangle")
                                    .foregroundColor(Color(hex: "#FF6B6B"))
                                    .font(.system(size: 13))
                                Text("未兌現承諾")
                                    .font(.system(size: 13, weight: .medium))
                                    .foregroundColor(Color(hex: "#FF6B6B"))
                            }
                            ForEach(lens.openSubCommits.prefix(2)) { c in
                                Text("· 對 \(c.sub)：\(c.content)")
                                    .font(.system(size: 12))
                                    .foregroundColor(Color(hex: "#e8d5b7"))
                                    .lineLimit(1)
                            }
                            ForEach(lens.openPromises.prefix(2)) { p in
                                Text("· 對 \(p.to)：\(p.content)")
                                    .font(.system(size: 12))
                                    .foregroundColor(Color(hex: "#e8d5b7"))
                                    .lineLimit(1)
                            }
                        }
                        .frame(maxWidth: .infinity, alignment: .leading)
                    }
                }
            }
        }
    }

    // MARK: - Helpers
    func statusRow(icon: String, text: String, color: String) -> some View {
        HStack(spacing: 8) {
            Image(systemName: icon)
                .foregroundColor(Color(hex: color))
                .font(.system(size: 14))
            Text(text)
                .font(.system(size: 14))
                .foregroundColor(Color(hex: "#e8d5b7"))
            Spacer()
        }
    }

    func placeholderText(_ text: String) -> some View {
        Text(text)
            .font(.system(size: 13))
            .foregroundColor(Color(hex: "#c9a84c40"))
            .italic()
            .frame(maxWidth: .infinity, alignment: .leading)
    }
}

// MARK: - 通用卡片容器
struct OfficeCard<Content: View>: View {
    let icon: String
    let title: String
    @ViewBuilder let content: () -> Content

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            // 標題列
            HStack(spacing: 8) {
                Image(systemName: icon)
                    .foregroundColor(Color(hex: "#c9a84c"))
                    .font(.system(size: 14, weight: .medium))
                Text(title)
                    .font(.system(size: 13, weight: .semibold))
                    .foregroundColor(Color(hex: "#c9a84c"))
                    .kerning(0.8)
            }

            // 內容
            content()
        }
        .padding(16)
        .background(Color(hex: "#13110e"))
        .overlay(
            RoundedRectangle(cornerRadius: 12)
                .stroke(Color(hex: "#c9a84c20"), lineWidth: 1)
        )
        .cornerRadius(12)
    }
}
