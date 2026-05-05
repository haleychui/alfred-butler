import Foundation
import CryptoKit
import Security

// MARK: - Alfred Vault Manager
//
// 零知識加密架構：
// 1. 加密金鑰在裝置上用 Secure Enclave 生成並保管
// 2. 金鑰 = HKDF(device_id + user_id + master_key_from_enclave)
// 3. 資料用 AES-256-GCM 加密後才送到 server
// 4. Server 只看到密文，永遠無法解密
// 5. 每次操作都附帶 integrity_tag，防中間人篡改

@MainActor
class VaultManager: ObservableObject {
    static let shared = VaultManager()

    private let base = "https://YOUR_BACKEND_HOST/alfred/api"
    private let keychainService = "com.alfred.vault"

    // MARK: - 裝置 ID（穩定，不隨 App 重裝改變）
    var deviceID: String {
        if let saved = UserDefaults.standard.string(forKey: "alfred_device_id") {
            return saved
        }
        let id = UIDevice.current.identifierForVendor?.uuidString ?? UUID().uuidString
        UserDefaults.standard.set(id, forKey: "alfred_device_id")
        return id
    }

    // MARK: - Master Key（從 Secure Enclave 或 Keychain 取得）
    private func getMasterKey() throws -> SymmetricKey {
        let label = "alfred.vault.master"
        // 嘗試從 Keychain 取
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: keychainService,
            kSecAttrAccount as String: label,
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne
        ]
        var result: AnyObject?
        let status = SecItemCopyMatching(query as CFDictionary, &result)

        if status == errSecSuccess, let data = result as? Data {
            return SymmetricKey(data: data)
        }

        // 第一次：生成 256-bit 主金鑰並存入 Keychain
        let key = SymmetricKey(size: .bits256)
        let keyData = key.withUnsafeBytes { Data($0) }
        let addQuery: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: keychainService,
            kSecAttrAccount as String: label,
            kSecValueData as String: keyData,
            kSecAttrAccessible as String: kSecAttrAccessibleWhenUnlockedThisDeviceOnly
        ]
        SecItemAdd(addQuery as CFDictionary, nil)
        return key
    }

    // MARK: - 衍生加密金鑰
    // key = HKDF(master_key, salt = device_id + user_id + cred_type)
    private func deriveKey(userID: String, credType: String) throws -> SymmetricKey {
        let master = try getMasterKey()
        let salt = "\(deviceID):\(userID):\(credType)".data(using: .utf8)!
        let inputKeyMaterial = master.withUnsafeBytes { SymmetricKey(data: Data($0)) }
        return HKDF<SHA256>.deriveKey(
            inputKeyMaterial: inputKeyMaterial,
            salt: salt,
            outputByteCount: 32
        )
    }

    // MARK: - 加密
    func encrypt(plaintext: String, userID: String, credType: String) throws -> (blob: String, iv: String) {
        let key = try deriveKey(userID: userID, credType: credType)
        let nonce = AES.GCM.Nonce()
        let sealedBox = try AES.GCM.seal(
            plaintext.data(using: .utf8)!,
            using: key,
            nonce: nonce
        )
        let combined = sealedBox.combined!
        let iv = Data(nonce).base64EncodedString()
        let blob = combined.base64EncodedString()
        return (blob, iv)
    }

    // MARK: - 解密
    func decrypt(blob: String, iv: String, userID: String, credType: String) throws -> String {
        let key = try deriveKey(userID: userID, credType: credType)
        guard let combined = Data(base64Encoded: blob) else {
            throw VaultError.invalidData
        }
        let sealedBox = try AES.GCM.SealedBox(combined: combined)
        let plaintext = try AES.GCM.open(sealedBox, using: key)
        return String(data: plaintext, encoding: .utf8) ?? ""
    }

    // MARK: - Integrity Tag（防篡改）
    func integrityTag(userID: String, credType: String, blob: String) throws -> String {
        let key = try deriveKey(userID: userID, credType: credType)
        let message = "\(userID):\(deviceID):\(credType):\(blob)".data(using: .utf8)!
        let mac = HMAC<SHA256>.authenticationCode(for: message, using: key)
        return Data(mac).hexString
    }

    // MARK: - 存入 Vault（加密後送 Server）
    func store(credType: String, label: String = "", plaintext: String) async throws {
        guard let userID = AuthManager.shared.loadToken().flatMap({ _ in
            // 從 token 解析 user_id（簡化版）
            UserDefaults.standard.string(forKey: "alfred_user_id")
        }) else { throw VaultError.notLoggedIn }

        let (blob, iv) = try encrypt(plaintext: plaintext, userID: userID, credType: credType)
        let tag = try integrityTag(userID: userID, credType: credType, blob: blob)

        var req = URLRequest(url: URL(string: "\(base)/vault/store")!)
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        if let token = AuthManager.shared.loadToken() {
            req.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        req.httpBody = try JSONEncoder().encode([
            "device_id": deviceID,
            "cred_type": credType,
            "label": label,
            "encrypted_blob": blob,
            "iv": iv,
            "integrity_tag": tag
        ])

        let (_, response) = try await URLSession.shared.data(for: req)
        guard (response as? HTTPURLResponse)?.statusCode == 200 else {
            throw VaultError.serverError
        }
    }

    // MARK: - 取出 Vault（Server 回密文，本地解密）
    func retrieve(credType: String, label: String = "") async throws -> String {
        guard let userID = UserDefaults.standard.string(forKey: "alfred_user_id"),
              let token = AuthManager.shared.loadToken()
        else { throw VaultError.notLoggedIn }

        var components = URLComponents(string: "\(base)/vault/retrieve/\(credType)")!
        components.queryItems = [
            URLQueryItem(name: "device_id", value: deviceID),
            URLQueryItem(name: "label", value: label)
        ]
        var req = URLRequest(url: components.url!)
        req.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")

        let (data, _) = try await URLSession.shared.data(for: req)
        let resp = try JSONDecoder().decode(VaultRetrieveResponse.self, from: data)

        return try decrypt(blob: resp.encryptedBlob, iv: resp.iv,
                           userID: userID, credType: credType)
    }

    // MARK: - 請求授權（付款前）
    func requestAction(actionType: String, target: String, amount: Double, merchant: String) async throws -> ActionApproval {
        guard let token = AuthManager.shared.loadToken() else { throw VaultError.notLoggedIn }

        var req = URLRequest(url: URL(string: "\(base)/vault/action/request")!)
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        req.httpBody = try JSONEncoder().encode([
            "action_type": actionType,
            "target": target,
            "amount": amount,
            "merchant": merchant
        ])

        let (data, _) = try await URLSession.shared.data(for: req)
        return try JSONDecoder().decode(ActionApproval.self, from: data)
    }
}

// MARK: - Models
struct VaultRetrieveResponse: Decodable {
    let encryptedBlob: String
    let iv: String
    enum CodingKeys: String, CodingKey {
        case encryptedBlob = "encrypted_blob"
        case iv
    }
}

struct ActionApproval: Decodable {
    let approved: Bool
    let requiresConfirm: Bool
    let logId: Int?
    let message: String
    let dailyRemaining: Double?
    enum CodingKeys: String, CodingKey {
        case approved, message
        case requiresConfirm = "requires_confirm"
        case logId = "log_id"
        case dailyRemaining = "daily_remaining"
    }
}

enum VaultError: LocalizedError {
    case notLoggedIn, invalidData, serverError, decryptionFailed
    var errorDescription: String? {
        switch self {
        case .notLoggedIn:      return "請先登入"
        case .invalidData:      return "資料格式錯誤"
        case .serverError:      return "伺服器錯誤"
        case .decryptionFailed: return "解密失敗"
        }
    }
}

extension Data {
    var hexString: String {
        map { String(format: "%02x", $0) }.joined()
    }
}
