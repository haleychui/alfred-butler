import SwiftUI
import MapKit

// MARK: - Maps Sub-App
// MKLocalSearch（Apple POI 資料庫）取代 Overpass，資料完整且含電話、開放時間

struct MapsSubAppView: View {
    let config   : SubAppConfig
    let onDismiss: () -> Void

    @State private var places: [MKMapItem] = []
    @State private var loading = true
    @State private var errorMsg = ""
    @State private var selectedPlace: MKMapItem? = nil
    @State private var showMap = false

    private let gold  = Color(hex: "#c9a84c")
    private let cream = Color(hex: "#e8d5b7")

    var body: some View {
        VStack(spacing: 0) {
            header
            if loading {
                Spacer(); ProgressView().tint(gold).scaleEffect(1.2); Spacer()
            } else if !errorMsg.isEmpty {
                Spacer()
                Text(errorMsg).foregroundColor(cream.opacity(0.6)).font(.system(size: 14, weight: .light)).padding(24)
                Spacer()
            } else {
                contentBody
            }
        }
        .background(Color(hex: "#0c0905").ignoresSafeArea())
        .task { await searchPlaces() }
        .sheet(isPresented: $showMap) {
            if let center = mapCenter {
                PlaceMapView(center: center, items: places)
                    .presentationDetents([.large])
            }
        }
    }

    private var header: some View {
        HStack {
            VStack(alignment: .leading, spacing: 2) {
                Text("L O C A T I O N S").font(.system(size: 9, weight: .medium)).foregroundColor(gold.opacity(0.5)).kerning(4)
                Text(config.query ?? "附近搜尋").font(.system(size: 18, weight: .thin)).foregroundColor(cream)
            }
            Spacer()
            if !places.isEmpty {
                Button(action: { showMap = true }) {
                    Image(systemName: "map").font(.system(size: 13, weight: .ultraLight))
                        .foregroundColor(gold.opacity(0.6))
                        .frame(width: 32, height: 32)
                        .background(gold.opacity(0.06)).clipShape(Circle())
                }.padding(.trailing, 8)
            }
            Button(action: onDismiss) {
                Image(systemName: "xmark").font(.system(size: 12, weight: .ultraLight))
                    .foregroundColor(gold.opacity(0.5)).frame(width: 32, height: 32)
                    .background(gold.opacity(0.06)).clipShape(Circle())
            }
        }
        .padding(.horizontal, 24).padding(.vertical, 20)
    }

    private var contentBody: some View {
        ScrollView(showsIndicators: false) {
            VStack(spacing: 12) {
                Text("\(places.count) 個結果")
                    .font(.system(size: 9, weight: .medium)).foregroundColor(gold.opacity(0.4)).kerning(3)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(.horizontal, 24)

                ForEach(Array(places.prefix(10).enumerated()), id: \.offset) { i, item in
                    placeRow(index: i + 1, item: item)
                }
                Spacer().frame(height: 40)
            }
            .padding(.top, 4)
        }
    }

    private func placeRow(index: Int, item: MKMapItem) -> some View {
        HStack(alignment: .top, spacing: 14) {
            // 序號
            ZStack {
                Circle().stroke(gold.opacity(0.3), lineWidth: 0.5).frame(width: 24, height: 24)
                Text("\(index)").font(.system(size: 9, weight: .medium)).foregroundColor(gold.opacity(0.7))
            }.padding(.top, 2)

            VStack(alignment: .leading, spacing: 4) {
                Text(item.name ?? "未知").font(.system(size: 15, weight: .regular)).foregroundColor(cream)
                if let addr = item.placemark.thoroughfare {
                    Text(addr + (item.placemark.subThoroughfare.map { " " + $0 } ?? ""))
                        .font(.system(size: 11, weight: .light)).foregroundColor(gold.opacity(0.55))
                }
                if let phone = item.phoneNumber, !phone.isEmpty {
                    HStack(spacing: 5) {
                        Image(systemName: "phone").font(.system(size: 9)).foregroundColor(gold.opacity(0.4))
                        Text(phone).font(.system(size: 11, weight: .light)).foregroundColor(gold.opacity(0.55))
                    }
                }
                if let cat = item.pointOfInterestCategory?.rawValue.components(separatedBy: ".").last {
                    Text(poiLabel(cat)).font(.system(size: 9)).foregroundColor(gold.opacity(0.35)).kerning(1)
                }
            }
            Spacer()

            // 撥打電話按鈕
            if let phone = item.phoneNumber, !phone.isEmpty,
               let url = URL(string: "tel://\(phone.filter { $0.isNumber || $0 == "+" })") {
                Link(destination: url) {
                    Image(systemName: "phone.fill").font(.system(size: 11)).foregroundColor(gold.opacity(0.5))
                        .frame(width: 28, height: 28).background(gold.opacity(0.08)).clipShape(Circle())
                }
            }
        }
        .padding(.vertical, 12).padding(.horizontal, 14)
        .background(
            RoundedRectangle(cornerRadius: 2).fill(gold.opacity(0.04))
                .overlay(RoundedRectangle(cornerRadius: 2).stroke(gold.opacity(0.1), lineWidth: 0.5))
        )
        .padding(.horizontal, 24)
    }

    private var mapCenter: CLLocationCoordinate2D? {
        guard let lat = config.lat, let lng = config.lng else { return nil }
        return CLLocationCoordinate2D(latitude: lat, longitude: lng)
    }

    // MARK: - MKLocalSearch

    private func searchPlaces() async {
        guard let lat = config.lat, let lng = config.lng else {
            await MainActor.run { errorMsg = "無法取得位置資料"; loading = false }
            return
        }
        let request = MKLocalSearch.Request()
        request.naturalLanguageQuery = config.query ?? "餐廳"
        request.region = MKCoordinateRegion(
            center: CLLocationCoordinate2D(latitude: lat, longitude: lng),
            latitudinalMeters: 1200, longitudinalMeters: 1200
        )
        request.resultTypes = [.pointOfInterest]

        do {
            let response = try await MKLocalSearch(request: request).start()
            let items = response.mapItems
            await MainActor.run { places = items; loading = false }

            // 通知阿福說出結果
            if !items.isEmpty {
                let names = items.prefix(3).compactMap { $0.name }.joined(separator: "、")
                let summary = "找到\(items.count)個結果，前三名是：\(names)。需要訂位嗎？"
                await MainActor.run { AlfredViewModel.shared.speakPlacesResult(summary, items: items) }
            } else {
                await MainActor.run { errorMsg = "附近沒有找到相關地點"; loading = false }
            }
        } catch {
            await MainActor.run { errorMsg = "搜尋暫時無法使用"; loading = false }
        }
    }

    private func poiLabel(_ cat: String) -> String {
        let map: [String: String] = [
            "restaurant": "餐廳", "cafe": "咖啡廳", "bakery": "烘焙",
            "nightlife": "夜生活", "foodMarket": "食品市場", "brewery": "酒吧"
        ]
        return map[cat] ?? cat
    }
}

// MARK: - Embedded Map View

struct PlaceMapView: View {
    let center: CLLocationCoordinate2D
    let items : [MKMapItem]
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        Map(initialPosition: .region(MKCoordinateRegion(
            center: center,
            latitudinalMeters: 1200, longitudinalMeters: 1200
        ))) {
            ForEach(Array(items.prefix(10).enumerated()), id: \.offset) { _, item in
                Marker(item.name ?? "", coordinate: item.placemark.coordinate)
                    .tint(Color(hex: "#c9a84c"))
            }
        }
        .overlay(alignment: .topTrailing) {
            Button(action: { dismiss() }) {
                Image(systemName: "xmark").font(.system(size: 12, weight: .ultraLight))
                    .foregroundColor(Color(hex: "#c9a84c").opacity(0.8))
                    .frame(width: 32, height: 32)
                    .background(Color(hex: "#0c0905").opacity(0.85))
                    .clipShape(Circle())
            }.padding(16)
        }
    }
}
