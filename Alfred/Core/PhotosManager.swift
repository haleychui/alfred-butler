import Foundation
import Photos
import UIKit
import Combine

// MARK: - Photos Manager
// 阿福查 iPhone 相簿：先 request authorization、再用 PHAsset 依關鍵字 / 日期查照片。
// 取縮圖供 grid 顯示；若主人選某張要分析，再用原圖丟給 backend 的 /api/analyze-photo。
@MainActor
final class PhotosManager: ObservableObject {
    static let shared = PhotosManager()

    @Published private(set) var authStatus: PHAuthorizationStatus = .notDetermined

    init() {
        authStatus = PHPhotoLibrary.authorizationStatus(for: .readWrite)
    }

    /// 請求相簿讀取權限。回傳 .authorized 或 .limited 才能查詢。
    func requestAuthorization() async -> PHAuthorizationStatus {
        if authStatus == .authorized || authStatus == .limited { return authStatus }
        let s = await withCheckedContinuation { (cont: CheckedContinuation<PHAuthorizationStatus, Never>) in
            PHPhotoLibrary.requestAuthorization(for: .readWrite) { status in
                cont.resume(returning: status)
            }
        }
        self.authStatus = s
        return s
    }

    /// 撈最近 N 張照片（preview 用）。
    func fetchRecent(limit: Int = 24) async -> [PHAsset] {
        let s = await requestAuthorization()
        guard s == .authorized || s == .limited else { return [] }
        let opts = PHFetchOptions()
        opts.predicate = NSPredicate(format: "mediaType = %d", PHAssetMediaType.image.rawValue)
        opts.sortDescriptors = [NSSortDescriptor(key: "creationDate", ascending: false)]
        opts.fetchLimit = limit
        let result = PHAsset.fetchAssets(with: opts)
        var arr: [PHAsset] = []
        result.enumerateObjects { a, _, _ in arr.append(a) }
        return arr
    }

    /// 按日期區間查（例：上週 / 上個月旅行）。包含起訖日。
    func fetchInRange(from: Date, to: Date, limit: Int = 60) async -> [PHAsset] {
        let s = await requestAuthorization()
        guard s == .authorized || s == .limited else { return [] }
        let opts = PHFetchOptions()
        opts.predicate = NSPredicate(
            format: "mediaType = %d AND creationDate >= %@ AND creationDate <= %@",
            PHAssetMediaType.image.rawValue, from as NSDate, to as NSDate
        )
        opts.sortDescriptors = [NSSortDescriptor(key: "creationDate", ascending: false)]
        opts.fetchLimit = limit
        let result = PHAsset.fetchAssets(with: opts)
        var arr: [PHAsset] = []
        result.enumerateObjects { a, _, _ in arr.append(a) }
        return arr
    }

    /// 取縮圖（grid 顯示用）
    func thumbnail(for asset: PHAsset, size: CGSize = CGSize(width: 240, height: 240)) async -> UIImage? {
        await withCheckedContinuation { (cont: CheckedContinuation<UIImage?, Never>) in
            let opts = PHImageRequestOptions()
            opts.deliveryMode = .opportunistic
            opts.isSynchronous = false
            opts.isNetworkAccessAllowed = true
            PHImageManager.default().requestImage(
                for: asset, targetSize: size, contentMode: .aspectFill, options: opts
            ) { image, _ in
                cont.resume(returning: image)
            }
        }
    }

    /// 取原圖 Data（供 /api/analyze-photo 上傳）
    func originalData(for asset: PHAsset) async -> Data? {
        await withCheckedContinuation { (cont: CheckedContinuation<Data?, Never>) in
            let opts = PHImageRequestOptions()
            opts.deliveryMode = .highQualityFormat
            opts.isSynchronous = false
            opts.isNetworkAccessAllowed = true
            PHImageManager.default().requestImageDataAndOrientation(
                for: asset, options: opts
            ) { data, _, _, _ in
                cont.resume(returning: data)
            }
        }
    }
}
